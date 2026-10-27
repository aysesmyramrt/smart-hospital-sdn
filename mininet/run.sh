#!/bin/bash
# Smart Hospital Network — Container başlatma scripti
set -e

echo ""
echo "======================================================"
echo "  SMART HOSPITAL NETWORK — Mininet + RYU"
echo "  NGN 2025 | KFAU-KGTU"
echo "======================================================"
echo ""

# Open vSwitch başlat
echo "[1/4] Open vSwitch başlatılıyor..."
service openvswitch-switch start > /dev/null 2>&1
sleep 2
echo "      OVS hazır."

# RYU controller arka planda başlat
echo "[2/4] RYU SDN Controller başlatılıyor (port 6633)..."
ryu-manager --ofp-tcp-listen-port 6633 hospital_controller.py \
    > /tmp/ryu.log 2>&1 &
RYU_PID=$!
sleep 4

# RYU çalışıyor mu kontrol et
if ! kill -0 $RYU_PID 2>/dev/null; then
    echo "HATA: RYU başlatılamadı. Log:"
    cat /tmp/ryu.log
    exit 1
fi
echo "      RYU Controller hazır (PID: $RYU_PID)"

# Mininet topolojisini başlat
echo "[3/4] Mininet topolojisi başlatılıyor..."
echo "[4/4] KPI testleri otomatik çalışacak..."
echo ""
echo "======================================================"

python3 hospital_topology.py

# Temizlik
echo ""
echo "Temizleniyor..."
kill $RYU_PID 2>/dev/null || true
mn -c > /dev/null 2>&1 || true
echo "Tamamlandı."
