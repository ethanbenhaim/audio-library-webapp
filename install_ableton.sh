#!/usr/bin/env bash
# Install Ableton Live Remote Scripts for Audio Web App
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
REMOTE_SCRIPTS_DIR="$HOME/Music/Ableton/User Library/Remote Scripts"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${CYAN}[install]${NC} $*"; }
ok()   { echo -e "${GREEN}[install]${NC} $*"; }
warn() { echo -e "${YELLOW}[install]${NC} $*"; }

# ── Create Remote Scripts directory if needed ────────────────────────────────
mkdir -p "$REMOTE_SCRIPTS_DIR"

# ── Install AbletonOSC ───────────────────────────────────────────────────────
ABLETONOSC_DEST="$REMOTE_SCRIPTS_DIR/AbletonOSC"

if [[ -d "$ABLETONOSC_DEST" ]]; then
  warn "AbletonOSC already installed at $ABLETONOSC_DEST"
else
  log "Downloading AbletonOSC…"
  TMP=$(mktemp -d)
  curl -fsSL "https://github.com/ideoforms/AbletonOSC/archive/refs/heads/master.zip" -o "$TMP/abletonosc.zip"
  unzip -q "$TMP/abletonosc.zip" -d "$TMP"

  # The zip contains AbletonOSC-master/AbletonOSC/ — copy the inner folder
  if [[ -d "$TMP/AbletonOSC-master/AbletonOSC" ]]; then
    cp -r "$TMP/AbletonOSC-master/AbletonOSC" "$ABLETONOSC_DEST"
  else
    # Fallback: copy the whole extracted folder
    cp -r "$TMP/AbletonOSC-master" "$ABLETONOSC_DEST"
  fi

  rm -rf "$TMP"
  ok "AbletonOSC installed → $ABLETONOSC_DEST"
fi

# ── Install AudioWebApp ───────────────────────────────────────────────────────
AUDIOWEBAPP_SRC="$ROOT/ableton_scripts/AudioWebApp"
AUDIOWEBAPP_DEST="$REMOTE_SCRIPTS_DIR/AudioWebApp"

log "Installing AudioWebApp Remote Script…"
rm -rf "$AUDIOWEBAPP_DEST"
cp -r "$AUDIOWEBAPP_SRC" "$AUDIOWEBAPP_DEST"
ok "AudioWebApp installed → $AUDIOWEBAPP_DEST"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
ok "Remote Scripts installed. Next steps:"
echo ""
echo "  1. Open (or restart) Ableton Live"
echo "  2. Go to Preferences → Link/Tempo/MIDI"
echo "  3. In the Control Surface list, add TWO entries:"
echo "       Slot 1: AbletonOSC"
echo "       Slot 2: AudioWebApp"
echo "  4. No MIDI input/output needed for either — leave them as 'None'"
echo ""
echo "  Both scripts communicate over localhost UDP — no extra configuration needed."
echo ""
