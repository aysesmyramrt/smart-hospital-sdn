#!/usr/bin/env python3
"""
Smart Hospital Network — Mininet Topology
NGN 2025 | KFAU-KGTU

Topoloji (Proposal Section 5 & Diagram):
  Controller (RYU, OpenFlow 1.3)
        |
    s0  (Core Switch)
   / \  \
  s1  s2  s3
  |    |    |
 URLLC mIoT eMBB
 hosts hosts hosts
"""
import time
import sys

from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info, error
from mininet.link import TCLink


# ─────────────────────────────────────────────────────────────────
# QoS — OVS kuyruk konfigürasyonu
# ─────────────────────────────────────────────────────────────────

def setup_qos(net):
    """Her switch'e 3 HTB kuyruğu ekle (URLLC > mIoT > eMBB)."""
    info('\n*** QoS kuyrukları yapılandırılıyor...\n')
    for sw_name in ['s1', 's2', 's3']:
        sw = net.get(sw_name)
        for intf in sw.intfList():
            if intf.name == 'lo':
                continue
            sw.cmd(
                f'ovs-vsctl set port {intf.name} qos=@qos '
                f'-- --id=@qos  create qos  type=linux-htb '
                f'queues=0=@q0,1=@q1,2=@q2 '
                f'-- --id=@q0 create queue '
                f'   other-config:min-rate=50000000 '   # 50 Mbps garantili URLLC
                f'   other-config:max-rate=100000000 '
                f'-- --id=@q1 create queue '
                f'   other-config:min-rate=5000000  '   # 5 Mbps garantili mIoT
                f'   other-config:max-rate=20000000  '
                f'-- --id=@q2 create queue '
                f'   other-config:min-rate=1000000  '   # 1 Mbps min eMBB
                f'   other-config:max-rate=100000000'
            )
    info('    QoS kuyrukları hazır.\n')


# ─────────────────────────────────────────────────────────────────
# SDN Flow Kuralları — Slice sınıflandırması (Controller mantığı)
# ─────────────────────────────────────────────────────────────────

def install_slice_flows(net):
    """Her switch'e slice'a göre OpenFlow kuyruk atama kuralları yükle.
    URLLC (10.0.x.x) -> queue 0 (en yüksek öncelik)
    mIoT  (10.1.x.x) -> queue 1
    eMBB  (10.2.x.x) -> queue 2 (best-effort)
    """
    info('\n*** SDN flow kuralları yükleniyor (slice -> queue eşlemesi)...\n')
    SLICES = [
        ('10.0.0.0/8',  0, 'URLLC'),
        ('10.1.0.0/16', 1, 'mIoT'),
        ('10.2.0.0/16', 2, 'eMBB'),
    ]
    for sw_name in ['s0', 's1', 's2', 's3']:
        sw = net.get(sw_name)
        for cidr, queue, name in SLICES:
            sw.cmd(
                f'ovs-ofctl -O OpenFlow13 add-flow {sw_name} '
                f'"priority=100,ip,nw_src={cidr},actions=set_queue:{queue},normal"'
            )
            sw.cmd(
                f'ovs-ofctl -O OpenFlow13 add-flow {sw_name} '
                f'"priority=100,ip,nw_dst={cidr},actions=set_queue:{queue},normal"'
            )
    info('    Flow kuralları yüklendi (URLLC>mIoT>eMBB önceliklendirmesi aktif).\n')


# ─────────────────────────────────────────────────────────────────
# KPI Testleri
# ─────────────────────────────────────────────────────────────────

def run_kpi_tests(net):
    """Her slice için ping (latency/jitter) ve iperf (throughput) testi."""
    SEPARATOR = '=' * 60

    tests = [
        ('URLLC', 'icu1',  'icu2',   '< 5 ms'),
        ('mIoT',  'wear1', 'wear2',  '< 50 ms'),
        ('eMBB',  'staff', 'admin',  '< 150 ms'),
    ]

    info(f'\n{SEPARATOR}\n')
    info('  KPI TEST SONUÇLARI\n')
    info(f'{SEPARATOR}\n')

    results = {}
    for slice_name, src_name, dst_name, target in tests:
        src = net.get(src_name)
        dst = net.get(dst_name)
        dst_ip = dst.IP()

        info(f'\n[{slice_name}] {src_name} ({src.IP()}) → {dst_name} ({dst_ip})\n')
        info(f'  Hedef gecikme: {target}\n')

        # 20 ping — latency + jitter
        raw = src.cmd(f'ping -c 20 -i 0.1 -q {dst_ip}')
        avg_ms = '?'
        mdev_ms = '?'
        loss_pct = '?'
        for line in raw.splitlines():
            if 'rtt' in line and 'avg' in line:
                # rtt min/avg/max/mdev = 0.x/1.x/2.x/0.x ms
                parts = line.split('=')[1].strip().split('/')
                avg_ms   = parts[1].strip()
                mdev_ms  = parts[3].replace(' ms', '').strip()
            if 'packet loss' in line:
                loss_pct = line.split('%')[0].split()[-1]

        ok = ''
        try:
            target_val = float(target.replace('<','').replace('ms','').strip())
            ok = '✓ HEDEF KARSILANDI' if float(avg_ms) < target_val else '✗ HEDEF ASILDI'
        except Exception:
            ok = '?'

        info(f'  Ortalama Gecikme : {avg_ms} ms\n')
        info(f'  Jitter (mdev)    : {mdev_ms} ms\n')
        info(f'  Paket Kaybi      : %{loss_pct}\n')
        info(f'  Durum            : {ok}\n')

        results[slice_name] = {
            'avg_ms': avg_ms, 'jitter': mdev_ms,
            'loss': loss_pct, 'status': ok
        }

    # iperf throughput
    info(f'\n{SEPARATOR}\n')
    info('  THROUGHPUT TESTLERİ (iperf3)\n')
    info(f'{SEPARATOR}\n')
    throughput_tests = [
        ('URLLC', 'icu1',  'icu2'),
        ('mIoT',  'wear1', 'wear2'),
        ('eMBB',  'staff', 'admin'),
    ]
    for slice_name, src_name, dst_name in throughput_tests:
        src = net.get(src_name)
        dst = net.get(dst_name)
        dst.cmd('iperf3 -s -D')
        time.sleep(0.3)
        out = src.cmd(f'iperf3 -c {dst.IP()} -t 3 --json 2>/dev/null || iperf3 -c {dst.IP()} -t 3')
        for line in out.splitlines():
            if 'sender' in line or 'receiver' in line:
                info(f'  [{slice_name}] {line.strip()}\n')
        dst.cmd('pkill iperf3')

    info(f'\n{SEPARATOR}\n')
    return results


# ─────────────────────────────────────────────────────────────────
# Ana topoloji
# ─────────────────────────────────────────────────────────────────

def hospital_topology():
    setLogLevel('info')

    # OVSSwitch standalone mod: gerçek OVS kernel switch, harici controller gerektirmez
    net = Mininet(
        controller=None,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
    )

    info('\n*** Smart Hospital Network — Mininet Topolojisi kuruluyor\n')
    info('*** NGN 2025 | KFAU-KGTU\n\n')

    # ── Switches ──────────────────────────────────────────────────────
    info('*** OpenFlow 1.3 switch\'ler ekleniyor (OVS, standalone mod)\n')
    s0 = net.addSwitch('s0', failMode='standalone', protocols='OpenFlow13')
    s1 = net.addSwitch('s1', failMode='standalone', protocols='OpenFlow13')
    s2 = net.addSwitch('s2', failMode='standalone', protocols='OpenFlow13')
    s3 = net.addSwitch('s3', failMode='standalone', protocols='OpenFlow13')

    # ── URLLC Hosts — Slice A ─────────────────────────────────────
    info('*** Slice A (URLLC) cihazları ekleniyor\n')
    icu1  = net.addHost('icu1',  ip='10.0.1.1/8')
    icu2  = net.addHost('icu2',  ip='10.0.1.2/8')
    robot = net.addHost('robot', ip='10.0.2.1/8')
    emerg = net.addHost('emerg', ip='10.0.3.1/8')

    # ── mIoT Hosts — Slice B ──────────────────────────────────────
    info('*** Slice B (mIoT) cihazları ekleniyor\n')
    wear1  = net.addHost('wear1',  ip='10.1.1.1/8')
    wear2  = net.addHost('wear2',  ip='10.1.1.2/8')
    sensor = net.addHost('sensor', ip='10.1.2.1/8')

    # ── eMBB Hosts — Slice C ──────────────────────────────────────
    info('*** Slice C (eMBB) cihazları ekleniyor\n')
    staff = net.addHost('staff', ip='10.2.1.1/8')
    admin = net.addHost('admin', ip='10.2.2.1/8')
    guest = net.addHost('guest', ip='10.2.2.2/8')

    # ── Backbone links ────────────────────────────────────────────
    info('*** Backbone bağlantılar ekleniyor\n')
    net.addLink(s0, s1, bw=1000)
    net.addLink(s0, s2, bw=1000)
    net.addLink(s0, s3, bw=1000)

    # ── URLLC links — ultra-low latency ──────────────────────────
    info('*** URLLC bağlantıları (0.5ms, 100Mbps)\n')
    net.addLink(s1, icu1,  bw=100, delay='0.5ms', jitter='0.1ms')
    net.addLink(s1, icu2,  bw=100, delay='0.5ms', jitter='0.1ms')
    net.addLink(s1, robot, bw=100, delay='0.5ms', jitter='0.1ms')
    net.addLink(s1, emerg, bw=100, delay='0.5ms', jitter='0.1ms')

    # ── mIoT links — moderate latency ────────────────────────────
    info('*** mIoT bağlantıları (5ms, 10Mbps)\n')
    net.addLink(s2, wear1,  bw=10, delay='5ms', jitter='1ms')
    net.addLink(s2, wear2,  bw=10, delay='5ms', jitter='1ms')
    net.addLink(s2, sensor, bw=5,  delay='10ms', jitter='2ms')

    # ── eMBB links — best-effort ──────────────────────────────────
    info('*** eMBB bağlantıları (20ms, 100Mbps)\n')
    net.addLink(s3, staff, bw=100, delay='20ms', jitter='5ms')
    net.addLink(s3, admin, bw=100, delay='20ms', jitter='5ms')
    net.addLink(s3, guest, bw=100, delay='40ms', jitter='10ms', loss=1)

    # ── Start ─────────────────────────────────────────────────────
    info('\n*** Ağ başlatılıyor...\n')
    net.start()
    time.sleep(1)

    # QoS kuyrukları ve SDN flow kuralları
    setup_qos(net)
    install_slice_flows(net)

    # Ağ bağlantı testi
    info('\n*** Temel bağlantı testi (pingall):\n')
    net.pingAll()

    # KPI testleri
    run_kpi_tests(net)

    # Interaktif CLI
    info('\n*** Mininet CLI hazır. Komutlar:\n')
    info('    pingall                     → tüm hostlar arası ping\n')
    info('    icu1 ping -c5 icu2          → URLLC latency testi\n')
    info('    wear1 ping -c5 wear2        → mIoT latency testi\n')
    info('    staff ping -c5 admin        → eMBB latency testi\n')
    info('    icu1 iperf3 -s &            → iperf server başlat\n')
    info('    icu2 iperf3 -c 10.0.1.1    → iperf client çalıştır\n')
    info('    exit                        → çıkış\n\n')

    CLI(net)
    net.stop()
    info('*** Ağ durduruldu.\n')


if __name__ == '__main__':
    hospital_topology()
