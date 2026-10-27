from __future__ import annotations
import threading
import time
import random
from collections import deque
from typing import Callable

from .models import SliceType, Packet, SLICE_CFG, HospitalDevice
from .controller import SDNController


# ─────────────────────────────────────────────────────────────────────────────
# KPI Statistics (rolling window per slice)
# ─────────────────────────────────────────────────────────────────────────────

class KPIStats:
    WINDOW = 300  # rolling packet window

    def __init__(self, slice_type: SliceType):
        self.slice_type = slice_type
        self._lock = threading.Lock()
        self.latencies: deque[float] = deque(maxlen=self.WINDOW)
        self.sent = 0
        self.delivered = 0
        self.dropped = 0
        # sliding window for throughput
        self._recent_bytes: deque[tuple[float, int]] = deque()

    def record_delivered(self, pkt: Packet) -> None:
        with self._lock:
            self.sent += 1
            self.delivered += 1
            self.latencies.append(pkt.latency_ms)
            self._recent_bytes.append((pkt.delivered_at, pkt.size_bytes))
            # trim entries older than 5 seconds
            cutoff = pkt.delivered_at - 5.0
            while self._recent_bytes and self._recent_bytes[0][0] < cutoff:
                self._recent_bytes.popleft()

    def record_dropped(self) -> None:
        with self._lock:
            self.sent += 1
            self.dropped += 1

    # ── Computed properties ───────────────────────────────────────────────────

    @property
    def avg_latency_ms(self) -> float:
        with self._lock:
            return sum(self.latencies) / len(self.latencies) if self.latencies else 0.0

    @property
    def p95_latency_ms(self) -> float:
        with self._lock:
            if not self.latencies:
                return 0.0
            s = sorted(self.latencies)
            return s[int(len(s) * 0.95)]

    @property
    def jitter_ms(self) -> float:
        with self._lock:
            lats = list(self.latencies)
            if len(lats) < 2:
                return 0.0
            diffs = [abs(lats[i] - lats[i - 1]) for i in range(1, len(lats))]
            return sum(diffs) / len(diffs)

    @property
    def reliability_pct(self) -> float:
        with self._lock:
            return (self.delivered / self.sent * 100.0) if self.sent else 100.0

    @property
    def loss_pct(self) -> float:
        return 100.0 - self.reliability_pct

    @property
    def throughput_kbps(self) -> float:
        with self._lock:
            if len(self._recent_bytes) < 2:
                return 0.0
            now = time.perf_counter()
            recent = [(t, b) for t, b in self._recent_bytes if t >= now - 5.0]
            if not recent:
                return 0.0
            total_bytes = sum(b for _, b in recent)
            elapsed = now - recent[0][0]
            return (total_bytes * 8 / elapsed / 1000.0) if elapsed > 0 else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Network Simulator
# ─────────────────────────────────────────────────────────────────────────────

class NetworkSimulator:
    """
    Core SDN simulation engine.

    Architecture:
    • One traffic-generator thread per hospital device
    • In-flight list: packets with a scheduled delivery timestamp
    • Delivery thread: polls at 1 ms resolution, fires callbacks
    • Congestion model: lower-priority slices get extra queuing delay + loss
    """

    def __init__(self, controller: SDNController, devices: list[HospitalDevice]):
        self.controller = controller
        self.devices = devices
        self.running = False
        self.congestion_level: float = 0.0
        self.phase_label: str = "NORMAL OPERATION"
        self.start_time: float = 0.0

        self.kpi: dict[SliceType, KPIStats] = {s: KPIStats(s) for s in SliceType}
        self.recent_events: deque[str] = deque(maxlen=22)

        self._inflight: list[tuple[float, Packet]] = []
        self._inflight_lock = threading.Lock()
        self._threads: list[threading.Thread] = []

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        self.running = True
        self.start_time = time.perf_counter()

        for dev in self.devices:
            t = threading.Thread(target=self._traffic_loop, args=(dev,), daemon=True)
            t.start()
            self._threads.append(t)

        delivery = threading.Thread(target=self._delivery_loop, daemon=True)
        delivery.start()
        self._threads.append(delivery)

    def stop(self) -> None:
        self.running = False

    def set_congestion(self, level: float, label: str = "") -> None:
        self.congestion_level = max(0.0, min(1.0, level))
        if label:
            self.phase_label = label
        self.controller.log(
            f"[CTRL] Congestion set to {self.congestion_level:.0%} — Phase: {self.phase_label}"
        )

    @property
    def uptime_str(self) -> str:
        elapsed = int(time.perf_counter() - self.start_time)
        return f"{elapsed // 60:02d}:{elapsed % 60:02d}"

    # ── Traffic generation ────────────────────────────────────────────────────

    def _traffic_loop(self, dev: HospitalDevice) -> None:
        interval = 1.0 / dev.send_rate_pps
        while self.running:
            self._send_packet(dev)
            jitter = random.uniform(-interval * 0.08, interval * 0.08)
            time.sleep(max(0.001, interval + jitter))

    def _send_packet(self, dev: HospitalDevice) -> None:
        cfg = SLICE_CFG[dev.slice_type]
        cong = self.congestion_level

        # ── Drop decision (SDN ingress policy) ─────────────────────────────
        loss = cfg["base_loss"]
        if cong > 0:
            if dev.slice_type == SliceType.eMBB:
                loss += cong * 0.045
            elif dev.slice_type == SliceType.mIoT:
                loss += cong * 0.009
            # URLLC: hardware-guaranteed — zero extra loss

        if random.random() < loss:
            self.kpi[dev.slice_type].record_dropped()
            return

        # ── Latency calculation (queuing model) ────────────────────────────
        base = cfg["base_latency"]
        sigma = cfg["jitter_sigma"]
        extra = 0.0
        if cong > 0:
            if dev.slice_type == SliceType.eMBB:
                extra = cong * 90.0 * (0.8 + random.random() * 0.6)
            elif dev.slice_type == SliceType.mIoT:
                extra = cong * 22.0 * (0.5 + random.random() * 0.5)
            # URLLC: dedicated bandwidth, no queuing delay added

        latency_ms = abs(random.gauss(base, sigma)) + extra
        latency_ms = max(0.3, latency_ms)

        pkt = Packet(
            slice_type=dev.slice_type,
            source=dev.ip,
            traffic_type=dev.traffic_type,
            size_bytes=dev.packet_size,
        )
        deliver_at = pkt.created_at + latency_ms / 1000.0

        with self._inflight_lock:
            self._inflight.append((deliver_at, pkt))

    # ── Packet delivery ───────────────────────────────────────────────────────

    def _delivery_loop(self) -> None:
        while self.running:
            now = time.perf_counter()
            delivered: list[Packet] = []
            remaining: list[tuple[float, Packet]] = []

            with self._inflight_lock:
                for deliver_at, pkt in self._inflight:
                    if now >= deliver_at:
                        delivered.append(pkt)
                    else:
                        remaining.append((deliver_at, pkt))
                self._inflight = remaining

            for pkt in delivered:
                pkt.delivered_at = now
                self.kpi[pkt.slice_type].record_delivered(pkt)
                self._append_event(pkt)

            time.sleep(0.001)

    def _append_event(self, pkt: Packet) -> None:
        cfg = SLICE_CFG[pkt.slice_type]
        ok = pkt.latency_ms <= cfg["latency_target"]
        mark = "✓" if ok else "✗ BREACH"
        self.recent_events.append(
            f"[{pkt.slice_type.value:5s}] {pkt.traffic_type:<18s} "
            f"{pkt.source}  →  {pkt.latency_ms:6.1f} ms  {mark}"
        )
