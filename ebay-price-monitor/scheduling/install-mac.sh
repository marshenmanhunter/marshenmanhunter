#!/bin/bash
# Schedules pricewatch on macOS with launchd, the Mac's built-in job scheduler.
# Unlike cron, launchd runs a scan you missed while the Mac slept as soon as it wakes.
#
#   ./scheduling/install-mac.sh             scan every 60 minutes
#   ./scheduling/install-mac.sh 15          scan every 15 minutes (5, 10, 15, 20, 30 or 60)
#   ./scheduling/install-mac.sh --dry-run   print the job file, change nothing
#   ./scheduling/install-mac.sh --uninstall stop and remove the job
set -euo pipefail

LABEL="com.pricewatch.scan"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
DIR="$(cd "$(dirname "$0")/.." && pwd)"
PY="$DIR/.venv/bin/python"
EVERY=60
DRY=0

for arg in "$@"; do
  case "$arg" in
    --uninstall)
      launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
      rm -f "$PLIST"
      echo "removed $LABEL"
      exit 0 ;;
    --dry-run) DRY=1 ;;
    5|10|15|20|30|60) EVERY="$arg" ;;
    *) echo "unknown option: $arg (use 5, 10, 15, 20, 30, 60, --dry-run or --uninstall)"; exit 1 ;;
  esac
done

if [ "$DRY" -eq 0 ]; then
  [ -x "$PY" ] || { echo "no virtualenv at $DIR/.venv. Run first:"; echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"; exit 1; }
  [ -f "$DIR/config.yaml" ] || { echo "no config.yaml in $DIR. Run: cp config.example.yaml config.yaml"; exit 1; }
  if ! grep -Eq '^[[:space:]]*client_id:[[:space:]]*[^[:space:]#]' "$DIR/config.yaml"; then
    echo "warning: launchd jobs do not see 'export' lines from your shell."
    echo "         Put client_id and client_secret under ebay: in config.yaml or every scan will fail."
  fi
fi

case "$DIR" in
  "$HOME/Desktop"*|"$HOME/Documents"*|"$HOME/Downloads"*)
    echo "warning: macOS blocks background jobs from Desktop, Documents and Downloads."
    echo "         Move this folder, e.g. to ~/code/ebay-price-monitor, then rerun this script." ;;
esac

MINUTES=""
for ((m = 0; m < 60; m += EVERY)); do
  MINUTES+="    <dict><key>Minute</key><integer>$m</integer></dict>"$'\n'
done

CONTENT="<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">
<plist version=\"1.0\">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PY</string>
    <string>-m</string>
    <string>pricewatch</string>
    <string>run</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$DIR</string>
  <key>StartCalendarInterval</key>
  <array>
${MINUTES}  </array>
  <key>StandardOutPath</key>
  <string>$DIR/pricewatch.log</string>
  <key>StandardErrorPath</key>
  <string>$DIR/pricewatch.log</string>
</dict>
</plist>"

if [ "$DRY" -eq 1 ]; then
  echo "$CONTENT"
  exit 0
fi

mkdir -p "$HOME/Library/LaunchAgents"
echo "$CONTENT" > "$PLIST"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "installed: pricewatch scans every $EVERY minutes"
echo "log:       $DIR/pricewatch.log"
echo "run now:   launchctl kickstart gui/$(id -u)/$LABEL"
echo "remove:    ./scheduling/install-mac.sh --uninstall"
