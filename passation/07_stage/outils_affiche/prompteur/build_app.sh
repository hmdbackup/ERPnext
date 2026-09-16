#!/bin/zsh
# Compile Prompteur.swift en une app double-cliquable : outils_affiche/prompteur/Prompteur.app
set -e
cd "$(dirname "$0")"
APP=Prompteur.app
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
swiftc -O -swift-version 5 -o "$APP/Contents/MacOS/Prompteur" Prompteur.swift
cp prompteur.json "$APP/Contents/Resources/prompteur.json"
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Prompteur</string>
  <key>CFBundleDisplayName</key><string>Prompteur</string>
  <key>CFBundleIdentifier</key><string>ma.mohamedslim.prompteur</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundleExecutable</key><string>Prompteur</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST
codesign --force --sign - "$APP" 2>/dev/null || true
echo "→ $PWD/$APP"
