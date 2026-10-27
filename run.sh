#!/usr/bin/env bash
# Smart Hospital Network — SDN Simulation Launcher
# NGN 2025 | KFAU-KGTU
set -e
cd "$(dirname "$0")"

echo "=================================================="
echo "  SMART HOSPITAL NETWORK — SDN Network Slicing"
echo "  NGN 2025 | KFAU-KGTU"
echo "=================================================="
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt -q

echo ""
echo "Starting simulation..."
echo "  Press Ctrl+C to exit at any time."
echo ""
sleep 1

python main.py
