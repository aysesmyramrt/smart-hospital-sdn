#!/usr/bin/env bash
# Smart Hospital Network — Web Dashboard Launcher
# NGN 2025 | KFAU-KGTU
set -e
cd "$(dirname "$0")"

echo ""
echo "  ======================================================"
echo "    SMART HOSPITAL NETWORK — Web Dashboard"
echo "    NGN 2025 | KFAU-KGTU"
echo "  ======================================================"
echo ""
echo "  Bağımlılıklar yükleniyor..."
pip install -r requirements.txt -q

echo ""
echo "  Simülasyon başlatılıyor..."
echo "  Tarayıcı otomatik açılacak: http://localhost:5050"
echo ""
echo "  Durdurmak için: Ctrl+C"
echo "  ======================================================"
echo ""

python web_main.py
