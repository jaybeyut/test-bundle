#!/usr/bin/env bash
# ==============================================================================
# Luxor 3 Mobile Track Creator — Local Android APK Build Script
# Run this script on Ubuntu (20.04/22.04 LTS) or WSL2 (Windows Subsystem for Linux)
# ==============================================================================

set -e

echo "=== [1/4] Checking and Installing System Dependencies ==="
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
    git zip unzip openjdk-17-jdk python3-pip autoconf libtool pkg-config \
    zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev \
    libssl-dev build-essential ccache

echo "=== [2/4] Setting Up Buildozer and Cython ==="
python3 -m pip install --upgrade pip
python3 -m pip install --upgrade --user buildozer cython virtualenv

export PATH=$PATH:~/.local/bin

echo "=== [3/4] Ensuring buildozer.spec and main.py are linked ==="
if [ ! -f main.py ]; then
    if [ -f kivy_main.py ]; then
        cp kivy_main.py main.py
        echo "Linked kivy_main.py -> main.py"
    fi
fi

echo "=== [4/4] Starting Buildozer Android Debug Build ==="
echo "Building APK for arm64-v8a & armeabi-v7a (API 34)..."
buildozer android debug

echo ""
echo "=============================================================================="
echo "🎉 BUILD COMPLETE!"
echo "Your test APK is located in the bin/ directory:"
ls -lh bin/*.apk
echo "To install directly to a connected phone with USB debugging enabled, run:"
echo "    adb install -r bin/*.apk"
echo "=============================================================================="
