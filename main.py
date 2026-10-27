#!/usr/bin/env python3
"""
Smart Hospital Network — SDN Network Slicing Simulation
NGN 2025 | KFAU-KGTU
Members:
    212010020004 — Ayse Sumeyra Mert
    212010020058 — Fatma Zehra Bestil
    212010020113 — Betul Korkmaz

Run:
    python main.py

The simulation runs four phases automatically:
    Phase 1 (0–30s)  : Normal operation  — all slices within KPI targets
    Phase 2 (30–55s) : Moderate congestion (60%) — eMBB starts degrading
    Phase 3 (55–75s) : Heavy congestion (88%) — eMBB breaches target, URLLC holds
    Phase 4 (75–90s) : Recovery — congestion cleared, all slices recover
Press Ctrl+C at any time to exit.
"""

import signal
import sys
import threading
import time

from hospital_sdn.controller import SDNController
from hospital_sdn.topology import build_devices
from hospital_sdn.simulator import NetworkSimulator
from hospital_sdn.dashboard import run_dashboard


# ─────────────────────────────────────────────────────────────────────────────
# Simulation phase schedule
# ─────────────────────────────────────────────────────────────────────────────

PHASES = [
    # (delay_s, congestion_level, label)
    (0,  0.00, "NORMAL OPERATION"),
    (30, 0.60, "MODERATE CONGESTION (60%)"),
    (55, 0.88, "HEAVY CONGESTION (88%)"),
    (75, 0.00, "RECOVERY — Congestion Released"),
]

TOTAL_DURATION = 95  # seconds before auto-exit (set to 0 to run indefinitely)


def _phase_scheduler(sim: NetworkSimulator) -> None:
    """Background thread that drives congestion phases."""
    start = time.perf_counter()
    for delay, level, label in PHASES:
        target_time = start + delay
        now = time.perf_counter()
        if target_time > now:
            time.sleep(target_time - now)
        if not sim.running:
            return
        sim.set_congestion(level, label)

    if TOTAL_DURATION > 0:
        time.sleep(max(0, TOTAL_DURATION - (time.perf_counter() - start)))
        sim.stop()


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    controller = SDNController()
    devices = build_devices()
    sim = NetworkSimulator(controller, devices)

    def _exit(sig, frame):  # noqa: ARG001
        sim.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _exit)
    signal.signal(signal.SIGTERM, _exit)

    sim.start()

    scheduler = threading.Thread(target=_phase_scheduler, args=(sim,), daemon=True)
    scheduler.start()

    # Dashboard blocks until sim.running is False
    run_dashboard(sim)
    print("\nSimulation complete. Thank you!")


if __name__ == "__main__":
    main()
