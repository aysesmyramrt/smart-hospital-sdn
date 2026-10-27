from __future__ import annotations
import time
from typing import TYPE_CHECKING

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from .models import SliceType, SLICE_CFG

if TYPE_CHECKING:
    from .simulator import NetworkSimulator


# ─────────────────────────────────────────────────────────────────────────────
# Layout builders
# ─────────────────────────────────────────────────────────────────────────────

def _header(sim: "NetworkSimulator") -> Panel:
    cong = sim.congestion_level
    cong_color = "bright_green" if cong < 0.3 else "yellow" if cong < 0.7 else "bright_red"

    t = Text(justify="center")
    t.append("  SMART HOSPITAL NETWORK  ", style="bold white on blue")
    t.append("  SDN-Based Network Slicing  ", style="bold cyan")
    t.append("  NGN 2025 · KFAU-KGTU  ", style="dim white")
    t.append("\n")
    t.append(f"  Phase: {sim.phase_label}  ", style="bold yellow")
    t.append(f"  Congestion: ", style="white")
    t.append(f"{cong:.0%}  ", style=f"bold {cong_color}")
    t.append(f"  Controller: RYU (Active, OpenFlow 1.3)  ", style="bright_green")
    t.append(f"  Uptime: {sim.uptime_str}  ", style="dim")
    return Panel(t, border_style="blue", padding=(0, 1))


def _kpi_table(sim: "NetworkSimulator") -> Panel:
    tbl = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold white",
        expand=True,
    )
    tbl.add_column("Slice",        width=18, no_wrap=True)
    tbl.add_column("Priority",     justify="center", width=10)
    tbl.add_column("Avg Latency",  justify="right",  width=13)
    tbl.add_column("Target",       justify="center", width=9)
    tbl.add_column("P95 Latency",  justify="right",  width=12)
    tbl.add_column("Jitter",       justify="right",  width=9)
    tbl.add_column("Reliability",  justify="right",  width=13)
    tbl.add_column("Pkt Loss",     justify="right",  width=10)
    tbl.add_column("Throughput",   justify="right",  width=12)
    tbl.add_column("Status",       justify="center", width=8)

    for stype in SliceType:
        cfg = SLICE_CFG[stype]
        kpi = sim.kpi[stype]
        color = cfg["color"]
        letter = cfg["slice_letter"]

        avg  = kpi.avg_latency_ms
        p95  = kpi.p95_latency_ms
        jit  = kpi.jitter_ms
        rel  = kpi.reliability_pct
        loss = kpi.loss_pct
        tput = kpi.throughput_kbps

        lat_ok = 0 < avg <= cfg["latency_target"]
        rel_ok = rel >= cfg["reliability_target"]
        ok_all = lat_ok and rel_ok

        lat_col  = "bright_green" if lat_ok else "bright_red"
        rel_col  = "bright_green" if rel_ok else "bright_red"
        status   = "[bright_green]  ✓ OK  [/bright_green]" if ok_all else "[bright_red]  ✗ FAIL[/bright_red]"

        tput_str = f"{tput/1000:.2f} Mbps" if tput >= 1000 else f"{tput:.1f} Kbps"

        tbl.add_row(
            Text(f"[{letter}] {stype.value} — {cfg['badge']}", style=f"bold {color}"),
            f"P{cfg['priority']}",
            Text(f"{avg:.2f} ms" if avg else "—", style=lat_col),
            f"<{cfg['latency_target']:.0f} ms",
            f"{p95:.2f} ms" if p95 else "—",
            f"{jit:.2f} ms" if jit else "—",
            Text(f"{rel:.3f}%", style=rel_col),
            f"{loss:.4f}%",
            tput_str,
            Text.from_markup(status),
        )

    return Panel(tbl, title="[bold]Network Slice KPIs[/bold]", border_style="cyan")


def _device_table(sim: "NetworkSimulator") -> Panel:
    tbl = Table(box=box.SIMPLE, show_header=True, header_style="bold", expand=True)
    tbl.add_column("Device",      width=22)
    tbl.add_column("Dept",        width=14)
    tbl.add_column("Slice",       width=8,  justify="center")
    tbl.add_column("IP",          width=12)
    tbl.add_column("Traffic Type",width=18)
    tbl.add_column("Rate",        width=8,  justify="right")

    for dev in sim.devices:
        cfg = SLICE_CFG[dev.slice_type]
        tbl.add_row(
            dev.name,
            dev.department,
            Text(dev.slice_type.value, style=cfg["color"]),
            dev.ip,
            dev.traffic_type,
            f"{dev.send_rate_pps} pps",
        )
    return Panel(tbl, title="[bold]Hospital Devices[/bold]", border_style="dim")


def _flow_table(sim: "NetworkSimulator") -> Panel:
    tbl = Table(box=box.SIMPLE, show_header=True, header_style="bold", expand=True)
    tbl.add_column("Rule ID",     width=14)
    tbl.add_column("Match Src",   width=11)
    tbl.add_column("Priority",    width=9,  justify="right")
    tbl.add_column("Slice",       width=7,  justify="center")
    tbl.add_column("Queue",       width=7,  justify="center")
    tbl.add_column("Action",      width=16)

    for rule in sim.controller.flow_table:
        cfg = SLICE_CFG[rule.slice_type]
        tbl.add_row(
            rule.rule_id,
            rule.match_prefix + "*",
            str(rule.priority),
            Text(rule.slice_type.value, style=cfg["color"]),
            f"Q{rule.queue_id}",
            rule.action,
        )
    return Panel(tbl, title="[bold blue]SDN Flow Table — OpenFlow 1.3[/bold blue]", border_style="blue")


def _events_panel(sim: "NetworkSimulator") -> Panel:
    t = Text()
    for line in list(sim.recent_events):
        if "BREACH" in line:
            t.append(line + "\n", style="bold red")
        elif "URLLC" in line:
            t.append(line + "\n", style="bright_red")
        elif "mIoT" in line:
            t.append(line + "\n", style="bright_green")
        else:
            t.append(line + "\n", style="bright_blue")
    for ev in list(sim.controller.events)[-4:]:
        t.append(ev + "\n", style="dim yellow")
    return Panel(t, title="[bold yellow]Network Events[/bold yellow]", border_style="yellow")


# ─────────────────────────────────────────────────────────────────────────────
# Layout assembly
# ─────────────────────────────────────────────────────────────────────────────

def _make_layout() -> Layout:
    layout = Layout(name="root")
    layout.split_column(
        Layout(name="header",  size=4),
        Layout(name="kpi",     size=12),
        Layout(name="middle",  size=18),
        Layout(name="bottom"),
    )
    layout["middle"].split_row(
        Layout(name="devices"),
        Layout(name="flows"),
    )
    return layout


def _refresh(layout: Layout, sim: "NetworkSimulator") -> None:
    layout["header"].update(_header(sim))
    layout["kpi"].update(_kpi_table(sim))
    layout["devices"].update(_device_table(sim))
    layout["flows"].update(_flow_table(sim))
    layout["bottom"].update(_events_panel(sim))


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def run_dashboard(sim: "NetworkSimulator") -> None:
    """Block the calling thread, rendering the live dashboard until sim stops."""
    layout = _make_layout()
    console = Console()

    with Live(layout, console=console, refresh_per_second=2, screen=True):
        while sim.running:
            _refresh(layout, sim)
            time.sleep(0.5)
