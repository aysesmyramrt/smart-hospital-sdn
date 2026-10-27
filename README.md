# Smart Hospital Network: SDN Network Slicing

A Next Generation Networks (NGN 2025) course project that models a smart hospital network split into three SDN slices with different QoS priorities. The repository has two parts:

1. **A Python simulation** of the SDN controller and the hospital traffic, with a terminal dashboard (Rich) and a web dashboard (Flask).
2. **A Mininet emulation** (Open vSwitch + Ryu, run in Docker) of the same topology, with QoS queues and automated latency and throughput tests.

The project proposal and the network design are in `docs/`.

## Network slices

| Slice | Type | Hosts / IP range | Priority / queue | Latency target |
| --- | --- | --- | --- | --- |
| A | URLLC (critical care) | ICU monitors, surgical robot, emergency alerts (10.0.x.x) | 300 / queue 0 | 5 ms |
| B | mIoT (sensor network) | wearables, environment and bed sensors, infusion pump (10.1.x.x) | 200 / queue 1 | 50 ms |
| C | eMBB (general network) | staff tablet, admin PC, guest Wi-Fi, MRI upload (10.2.x.x) | 100 / queue 2 | 100 ms |

## Part 1: Python simulation (`hospital_sdn/`)

- `controller.py`: a simulated OpenFlow 1.3 controller that installs prefix-based flow rules and classifies traffic into slices.
- `topology.py`: 13 hospital devices, each with its slice, IP, traffic type, send rate and packet size.
- `simulator.py`: one traffic generator thread per device and a delivery thread. Congestion adds queuing delay and packet loss to mIoT and eMBB, while URLLC keeps its base latency. The simulator tracks average and p95 latency, jitter, reliability, loss and throughput per slice.
- `dashboard.py`: a live terminal dashboard built with Rich.

Both entry points run the same four phases: normal operation (0-30 s), moderate congestion of 60% (30-55 s), heavy congestion of 88% (55-75 s), and recovery (75 s onward).

- `main.py` runs the terminal dashboard and exits after 95 s.
- `web_main.py` serves a web dashboard at `http://localhost:5050`. `GET /api/status` returns per-slice KPIs, the flow table, recent events and the latency history behind the live chart (`web/templates/index.html`).

## Part 2: Mininet emulation (`mininet/`)

- `hospital_topology.py` builds a core switch `s0` and three slice switches `s1`, `s2` and `s3` (OVS, OpenFlow 1.3, standalone fail mode). It adds 10 hosts with per-slice link bandwidth, delay and jitter. Each slice switch port gets three Linux HTB queues, and `ovs-ofctl` installs `set_queue` flow rules by source and destination subnet. The script then runs `pingall`, ping-based latency, jitter and loss tests, and `iperf3` throughput tests per slice, and finally opens the Mininet CLI.
- `hospital_controller.py` is a Ryu application that installs the same prefix → queue rules, with a learning-switch fallback. `run.sh` starts it on port 6633 before the topology. The topology itself creates its switches in standalone mode with `controller=None`.
- `Dockerfile` builds an image with Ubuntu 20.04, Open vSwitch, Mininet 2.3.1b4, Ryu and iperf3.

## Tech stack

Python 3, Flask, Rich, Mininet, Open vSwitch, Ryu (OpenFlow 1.3), iperf3, Docker / Docker Compose

## Project structure

```
smart-hospital-sdn/
├── hospital_sdn/          # simulation package (controller, models, topology, simulator, dashboard)
├── main.py                # terminal simulation entry point
├── web_main.py            # web dashboard entry point (port 5050)
├── web/templates/         # dashboard HTML
├── mininet/               # Mininet topology, Ryu controller, Dockerfile, run.sh
├── docker-compose.yml     # runs the Mininet container (privileged, host network)
├── requirements.txt       # rich, flask
├── run.sh / run_web.sh    # install requirements and start the simulation
└── docs/                  # project proposal and network design (PDF)
```

## Running

**Simulation** (any OS with Python 3.9+):

```bash
pip install -r requirements.txt
python main.py        # terminal dashboard
python web_main.py    # web dashboard at http://localhost:5050
```

You can also use `bash run.sh` or `bash run_web.sh`.

**Mininet emulation** (Linux host with Docker; the container runs privileged on the host network):

```bash
docker compose up --build
# or attach interactively for the Mininet CLI:
docker compose run --rm smart-hospital-mininet
```

## Team

- Ayşe Sümeyra Mert
- Fatma Zehra Bestil
- Betül Korkmaz
