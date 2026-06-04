#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export CLANG_MODULE_CACHE_PATH="${CLANG_MODULE_CACHE_PATH:-/private/tmp/bookmaker-clang-cache}"

swift build
BIN_DIR="$(swift build --show-bin-path)"
APP_DIR="$ROOT/dist/BookMaker.app"
EXECUTABLE="$APP_DIR/Contents/MacOS/BookMaker"

if [[ -e "$APP_DIR" ]]; then
  DEPRECATED_DIR="$ROOT/dist/.deprecated_BookMaker.app_$(date -u +%Y%m%dT%H%M%SZ)"
  mv "$APP_DIR" "$DEPRECATED_DIR"
fi

mkdir -p "$APP_DIR/Contents/MacOS" "$APP_DIR/Contents/Resources"
cp "$BIN_DIR/BookMaker" "$EXECUTABLE"
chmod +x "$EXECUTABLE"

RESOURCE_BUNDLE="$BIN_DIR/BookMaker_BookMaker.bundle"
if [[ -e "$RESOURCE_BUNDLE" ]]; then
  cp -R "$RESOURCE_BUNDLE" "$APP_DIR/Contents/Resources/BookMaker_BookMaker.bundle"
fi

cat > "$APP_DIR/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleDisplayName</key>
  <string>BookMaker</string>
  <key>CFBundleExecutable</key>
  <string>BookMaker</string>
  <key>CFBundleIdentifier</key>
  <string>local.bookmaker.BookMaker</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>BookMaker</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>0.1.0</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>LSMinimumSystemVersion</key>
  <string>15.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>NSPrincipalClass</key>
  <string>NSApplication</string>
</dict>
</plist>
PLIST

if command -v codesign >/dev/null 2>&1; then
  codesign --force --sign - "$APP_DIR" >/dev/null
fi

echo "$APP_DIR"
