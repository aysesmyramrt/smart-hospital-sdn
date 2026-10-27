#!/usr/bin/env python3
"""
Smart Hospital Network — Web Dashboard
NGN 2025 | KFAU-KGTU

Run: python web_main.py
Then open: http://localhost:5050
"""
import threading
import time
import webbrowser
from collections import deque

from flask import Flask, jsonify, render_template

from hospital_sdn.controller import SDNController
from hospital_sdn.models import SLICE_CFG, SliceType
from hospital_sdn.simulator import NetworkSimulator
from hospital_sdn.topology import build_devices

# ─────────────────────────────────────────────────────────────────────────────
# Flask app setup
# ─────────────────────────────────────────────────────────────────────────────

app = Flask(__name__, template_folder="web/templates", static_folder="web/static")
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

# ─────────────────────────────────────────────────────────────────────────────
# Global simulation state
# ─────────────────────────────────────────────────────────────────────────────

ctrl = SDNController()
devices = build_devices()
sim = NetworkSimulator(ctrl, devices)

# Rolling history for chart (120 points = 60 seconds at 500ms sampling)
HISTORY_LEN = 120
history: dict[SliceType, deque[float]] = {s: deque([0.0] * HISTORY_LEN, maxlen=HISTORY_LEN) for s in SliceType}
history_lock = threading.Lock()

# Simulation phases
PHASES = [
    (0,  0.00, "NORMAL OPERATION"),
    (30, 0.60, "MODERATE CONGESTION (60%)"),
    (55, 0.88, "HEAVY CONGESTION (88%)"),
    (75, 0.00, "RECOVERY — Congestion Released"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Background threads
# ─────────────────────────────────────────────────────────────────────────────

def _sampler() -> None:
    """Record latency samples for the live chart every 500 ms."""
    while sim.running:
        with history_lock:
            for stype in SliceType:
                val = sim.kpi[stype].avg_latency_ms
                history[stype].append(round(val, 2) if val > 0 else 0.0)
        time.sleep(0.5)


def _phase_scheduler() -> None:
    """Drive the four simulation phases automatically."""
    start = time.perf_counter()
    for delay, level, label in PHASES:
        wait = (start + delay) - time.perf_counter()
        if wait > 0:
            time.sleep(wait)
        if not sim.running:
            return
        sim.set_congestion(level, label)


# ─────────────────────────────────────────────────────────────────────────────
# API routes
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    slices = {}
    for stype in SliceType:
        kpi = sim.kpi[stype]
        cfg = SLICE_CFG[stype]
        avg = kpi.avg_latency_ms
        rel = kpi.reliability_pct
        tput = kpi.throughput_kbps
        slices[stype.value] = {
            "label":             cfg["label"],
            "badge":             cfg["badge"],
            "slice_letter":      cfg["slice_letter"],
            "avg_latency":       round(avg, 2),
            "p95_latency":       round(kpi.p95_latency_ms, 2),
            "jitter":            round(kpi.jitter_ms, 2),
            "reliability":       round(rel, 3),
            "loss":              round(kpi.loss_pct, 4),
            "throughput":        f"{tput/1000:.2f} Mbps" if tput >= 1000 else f"{tput:.1f} Kbps",
            "sent":              kpi.sent,
            "delivered":         kpi.delivered,
            "dropped":           kpi.dropped,
            "latency_target":    cfg["latency_target"],
            "reliability_target": cfg["reliability_target"],
            "lat_ok":            0 < avg <= cfg["latency_target"],
            "rel_ok":            rel >= cfg["reliability_target"],
        }

    flow_table = [
        {
            "rule_id":  r.rule_id,
            "match":    r.match_prefix + "*",
            "priority": r.priority,
            "slice":    r.slice_type.value,
            "queue":    r.queue_id,
            "action":   r.action,
        }
        for r in ctrl.flow_table
    ]

    with history_lock:
        hist = {s.value: list(history[s]) for s in SliceType}

    return jsonify(
        phase=sim.phase_label,
        congestion=round(sim.congestion_level * 100),
        uptime=sim.uptime_str,
        slices=slices,
        flow_table=flow_table,
        events=list(sim.recent_events)[-18:],
        ctrl_events=list(ctrl.events)[-5:],
        history=hist,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def _start() -> None:
    sim.start()
    threading.Thread(target=_sampler, daemon=True).start()
    threading.Thread(target=_phase_scheduler, daemon=True).start()
    time.sleep(1.2)
    webbrowser.open("http://localhost:5050")


if __name__ == "__main__":
    print("\n" + "=" * 56)
    print("  SMART HOSPITAL NETWORK — Web Dashboard")
    print("  NGN 2025 | KFAU-KGTU")
    print("=" * 56)
    print("  Starting simulation...")
    print("  Dashboard: http://localhost:5050")
    print("  Press Ctrl+C to stop.")
    print("=" * 56 + "\n")

    _start()
    app.run(host="0.0.0.0", port=5050, debug=False, threaded=True, use_reloader=False)
