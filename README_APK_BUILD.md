# Luxor 3 Mobile Track Creator — Android APK Build Package

This repository contains the complete native Android codebase for Luxor 3 Mobile Track Creator.

## Option 1: Automated 1-Click Cloud APK Build (Recommended - Zero Installation)
1. Push or upload this extracted folder to a new repository on **GitHub** (public or private).
2. Go to the **Actions** tab in your repository.
3. The "Build Luxor 3 Android APK" workflow runs automatically.
4. When finished (usually ~5-8 minutes), click the completed run and download **Luxor3-TrackCreator-Debug-APK**.
5. Transfer the APK to your Android phone or tablet and tap to install!

## Option 2: Local Build on Ubuntu / WSL2
If you have a Linux machine or Windows with WSL2:
```bash
chmod +x build_apk_local.sh
./build_apk_local.sh
```
The generated APK will be output in the `bin/` directory:
`bin/luxor3trackcreator-15.0.0-arm64-v8a_armeabi-v7a-debug.apk`
