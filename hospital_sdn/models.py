from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import time
import uuid


class SliceType(Enum):
    URLLC = "URLLC"
    mIoT  = "mIoT"
    eMBB  = "eMBB"


SLICE_CFG: dict[SliceType, dict] = {
    SliceType.URLLC: dict(
        priority=3,
        label="Ultra-Reliable Low-Latency",
        latency_target=5.0,
        reliability_target=99.999,
        base_latency=1.8,
        jitter_sigma=0.40,
        base_loss=0.00001,
        color="bright_red",
        badge="CRITICAL",
        slice_letter="A",
    ),
    SliceType.mIoT: dict(
        priority=2,
        label="Massive IoT",
        latency_target=50.0,
        reliability_target=99.9,
        base_latency=18.0,
        jitter_sigma=4.0,
        base_loss=0.001,
        color="bright_green",
        badge="MEDIUM",
        slice_letter="B",
    ),
    SliceType.eMBB: dict(
        priority=1,
        label="Enhanced Mobile Broadband",
        latency_target=100.0,
        reliability_target=99.0,
        base_latency=42.0,
        jitter_sigma=12.0,
        base_loss=0.005,
        color="bright_blue",
        badge="STANDARD",
        slice_letter="C",
    ),
}


@dataclass
class Packet:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    slice_type: SliceType = SliceType.URLLC
    source: str = ""
    traffic_type: str = ""
    size_bytes: int = 64
    created_at: float = field(default_factory=time.perf_counter)
    delivered_at: float = 0.0
    dropped: bool = False

    @property
    def latency_ms(self) -> float:
        if self.delivered_at > 0:
            return (self.delivered_at - self.created_at) * 1000
        return 0.0


@dataclass
class HospitalDevice:
    device_id: str
    name: str
    department: str
    slice_type: SliceType
    ip: str
    traffic_type: str
    send_rate_pps: float   # packets per second
    packet_size: int = 64


@dataclass
class FlowRule:
    rule_id: str
    slice_type: SliceType
    match_prefix: str
    priority: int
    queue_id: int
    action: str = "forward→queue"
