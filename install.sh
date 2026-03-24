#!/usr/bin/env bash
# =============================================================================
# creds — Personal Credential Manager for macOS
# Installer & Setup Wizard
# =============================================================================
set -e

# ── Colors ────────────────────────────────────────────────────────────────────
BOLD='\033[1m'
DIM='\033[2m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
RESET='\033[0m'

CREDS_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_BIN="$HOME/.local/bin/creds"

# ── Helpers ───────────────────────────────────────────────────────────────────
header() { echo -e "\n${BOLD}${CYAN}$1${RESET}"; }
ok()     { echo -e "  ${GREEN}✓${RESET}  $1"; }
warn()   { echo -e "  ${YELLOW}⚠${RESET}  $1"; }
err()    { echo -e "  ${RED}✗${RESET}  $1"; }
dim()    { echo -e "  ${DIM}$1${RESET}"; }

confirm() {
    local prompt="$1"
    local default="${2:-y}"
    local hint="[Y/n]"
    [ "$default" = "n" ] && hint="[y/N]"
    echo -en "\n  ${BOLD}$prompt${RESET} ${DIM}$hint${RESET} "
    read -r answer
    answer="${answer:-$default}"
    [[ "$answer" =~ ^[Yy] ]]
}

# ── Welcome ───────────────────────────────────────────────────────────────────
echo -e "${BOLD}"
cat << 'BANNER'
  ╔═══════════════════════════════════════════════════════╗
  ║           creds — Personal Credential Manager         ║
  ║                    macOS Installer                    ║
  ╚═══════════════════════════════════════════════════════╝
BANNER
echo -e "${RESET}"

echo -e "  ${BOLD}What is creds?${RESET}"
echo ""
echo "  A personal API key manager for macOS that stores every credential"
echo "  in the macOS Keychain — the same encrypted store used by Safari,"
echo "  iCloud, and system apps — and gives you a unified dashboard to"
echo "  view, add, rotate, and audit all of them."
echo ""
echo -e "  ${BOLD}How it's secure:${RESET}"
echo ""
echo "  • Keys live in the macOS Keychain under 'io.creds.store'"
echo "    AES-256-GCM encrypted, hardware-backed on Apple Silicon"
echo "  • Locked when your screen is locked — no plaintext on disk"
echo "  • creds never writes keys to files (except an ephemeral .env"
echo "    at startup, permissions 600, regenerated each run)"
echo "  • 'creds env' prints 'export KEY=value' to stdout only —"
echo "    values go straight into shell memory, not disk"
echo "  • Rotation reminders via ntfy push — you'll know when a key"
echo "    is overdue to rotate"
echo ""
echo -e "  ${BOLD}What it replaces:${RESET}"
echo ""
echo "  • Scattered 'security find-generic-password' calls in scripts"
echo "  • API keys buried in .env files that get accidentally committed"
echo "  • Mental overhead of tracking which keys are set, where, and how old"
echo ""
echo -en "  Press ${BOLD}Enter${RESET} to begin installation... "
read -r

# ── System checks ─────────────────────────────────────────────────────────────
header "1 / 6  — Checking prerequisites"

# macOS only
if [[ "$(uname)" != "Darwin" ]]; then
    err "creds requires macOS (uses Keychain Services)"
    exit 1
fi
ok "macOS $(sw_vers -productVersion)"

# Python 3.11+
PYTHON=""
for py in python3.13 python3.12 python3.11 python3; do
    if command -v "$py" &>/dev/null; then
        version=$("$py" --version 2>&1 | awk '{print $2}')
        major=$(echo "$version" | cut -d. -f1)
        minor=$(echo "$version" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
            PYTHON="$py"
            ok "Python $version ($py)"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    err "Python 3.11+ required. Install via: brew install python@3.12"
    exit 1
fi

# uv (preferred) or pip
if command -v uv &>/dev/null; then
    ok "uv package manager found"
    USE_UV=true
else
    warn "uv not found — will use pip (slower)"
    USE_UV=false
fi

# ── Install ───────────────────────────────────────────────────────────────────
header "2 / 6  — Installing creds"

VENV_DIR="$CREDS_DIR/.venv"

echo ""
echo "  Installing to: $VENV_DIR"
echo "  Symlink at:    $INSTALL_BIN"
echo ""

if [ -d "$VENV_DIR" ]; then
    warn "Virtual environment already exists — upgrading"
    if [ "$USE_UV" = true ]; then
        uv pip install -e "$CREDS_DIR[dev]" --quiet 2>&1 | sed 's/^/    /'
    else
        "$VENV_DIR/bin/pip" install -e "$CREDS_DIR[dev]" --quiet 2>&1 | sed 's/^/    /'
    fi
else
    if [ "$USE_UV" = true ]; then
        uv venv "$VENV_DIR" --python "$PYTHON" --quiet
        uv pip install -e "$CREDS_DIR[dev]" --quiet --python "$VENV_DIR/bin/python" 2>&1 | sed 's/^/    /'
    else
        "$PYTHON" -m venv "$VENV_DIR"
        "$VENV_DIR/bin/pip" install -e "$CREDS_DIR[dev]" --quiet 2>&1 | sed 's/^/    /'
    fi
fi

ok "Package installed"

# Symlink
mkdir -p "$HOME/.local/bin"
ln -sf "$VENV_DIR/bin/creds" "$INSTALL_BIN"
ok "Symlink: $INSTALL_BIN"

# PATH check
if ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
    echo ""
    warn "~/.local/bin is not in your PATH"
    echo ""
    echo "  Add one of these to your shell profile:"
    echo -e "  ${DIM}# ~/.zshrc or ~/.bashrc${RESET}"
    echo -e "  ${CYAN}export PATH=\"\$HOME/.local/bin:\$PATH\"${RESET}"
    echo ""
    read -rp "  Press Enter to continue..."
else
    ok "~/.local/bin is in PATH"
fi

# ── Migration scan ────────────────────────────────────────────────────────────
header "3 / 6  — Scanning for existing credentials"

echo ""
echo "  creds will look for API keys in common legacy Keychain locations:"
dim "  Common Keychain service names, environment variables,"
dim "  org.n8n.*, and environment variables"
echo ""

MIGRATE_OUTPUT=$("$INSTALL_BIN" migrate --dry-run 2>&1)
FOUND_COUNT=$(echo "$MIGRATE_OUTPUT" | grep -c "^  +" || true)

if [ "$FOUND_COUNT" -eq 0 ]; then
    ok "No legacy credentials found — starting fresh"
    SKIP_MIGRATE=true
else
    echo "  Found ${BOLD}$FOUND_COUNT${RESET} credential(s) in legacy locations:"
    echo ""
    echo "$MIGRATE_OUTPUT" | grep "^  +" | sed 's/^/  /'
    echo ""
    echo "  Migration will:"
    echo "  • Copy each key into the canonical 'io.creds.store' Keychain store"
    echo "  • Leave the original entries untouched (safe to delete later)"
    echo "  • Record when each credential was added (for rotation tracking)"
    SKIP_MIGRATE=false
fi

# ── Migration choice ──────────────────────────────────────────────────────────
if [ "$SKIP_MIGRATE" = false ]; then
    header "4 / 6  — Migration"

    echo ""
    echo "  How would you like to handle your existing credentials?"
    echo ""
    echo "  1) Migrate all now   — copy everything found into creds  ${DIM}(recommended)${RESET}"
    echo "  2) Review one-by-one — confirm each key individually"
    echo "  3) Skip migration    — I'll add credentials manually via 'creds add'"
    echo ""
    echo -en "  ${BOLD}Choice [1/2/3]:${RESET} "
    read -r migrate_choice
    migrate_choice="${migrate_choice:-1}"

    echo ""
    case "$migrate_choice" in
        1)
            echo "  Migrating all credentials..."
            "$INSTALL_BIN" migrate --yes 2>&1 | sed 's/^/  /'
            ok "Migration complete"
            ;;
        2)
            echo "  Starting interactive migration..."
            echo ""
            "$INSTALL_BIN" migrate 2>&1
            ;;
        3)
            warn "Skipping migration — run 'creds migrate' any time to do it later"
            ;;
        *)
            warn "Unrecognized choice — skipping migration"
            ;;
    esac
else
    header "4 / 6  — Migration"
    ok "Nothing to migrate"
fi

# ── Rotation reminders ────────────────────────────────────────────────────────
header "5 / 6  — Rotation reminders (optional)"

echo ""
echo "  creds can send you a push notification on the 1st of each month"
echo "  if any API key is overdue for rotation (default: 180 days)."
echo ""
echo "  This uses ntfy.sh — a free, open-source push notification service."
echo "  You receive notifications via the ntfy app (iOS/Android/desktop)."
echo ""

if confirm "Set up monthly rotation reminders?"; then
    # Check if ntfy topic is already set
    NTFY_TOPIC=$("$INSTALL_BIN" get ntfy 2>/dev/null || true)
    if [ -z "$NTFY_TOPIC" ]; then
        echo ""
        echo "  You need an ntfy topic. Options:"
        echo "  a) Generate a random one now"
        echo "  b) Enter an existing topic"
        echo ""
        echo -en "  ${BOLD}Choice [a/b]:${RESET} "
        read -r ntfy_choice
        ntfy_choice="${ntfy_choice:-a}"

        if [[ "$ntfy_choice" =~ ^[Bb] ]]; then
            echo -en "  ${BOLD}ntfy topic:${RESET} "
            read -r NTFY_TOPIC
        else
            NTFY_TOPIC="creds-$(openssl rand -hex 4)"
            echo ""
            ok "Generated topic: ${BOLD}$NTFY_TOPIC${RESET}"
        fi

        "$INSTALL_BIN" set ntfy "$NTFY_TOPIC" --context personal
        ok "ntfy topic saved to creds"
    else
        ok "ntfy topic already set: $NTFY_TOPIC"
    fi

    # Install cron
    CRON_CMD="0 9 1 * * $HOME/.local/bin/creds-rotation-check"
    CRON_SCRIPT="$CREDS_DIR/bin/creds-rotation-check"

    if [ -f "$CRON_SCRIPT" ]; then
        ln -sf "$CRON_SCRIPT" "$HOME/.local/bin/creds-rotation-check"
        # Add cron if not already present
        if ! crontab -l 2>/dev/null | grep -q "creds-rotation-check"; then
            (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
            ok "Cron job installed (runs 9am on 1st of each month)"
        else
            ok "Cron job already installed"
        fi
        echo ""
        echo -e "  ${DIM}Subscribe in the ntfy app: ntfy.sh/$NTFY_TOPIC${RESET}"
    else
        warn "creds-rotation-check script not found — skipping cron"
    fi
else
    warn "Skipping rotation reminders — run 'creds' and add your ntfy topic later"
fi

# ── Final audit ───────────────────────────────────────────────────────────────
header "6 / 6  — Credential status"

echo ""
"$INSTALL_BIN" audit 2>&1 | sed 's/^/  /'

echo ""
echo -e "  ${DIM}Legend: ${GREEN}+${RESET}${DIM} = set, - = missing, WARN = rotation due, OVERDUE = rotate now${RESET}"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}  ══════════════════════════════════════════════${RESET}"
echo -e "${BOLD}${GREEN}  Installation complete!${RESET}"
echo -e "${BOLD}${GREEN}  ══════════════════════════════════════════════${RESET}"
echo ""
echo "  Quick reference:"
echo ""
echo -e "  ${CYAN}creds${RESET}                    Open the TUI dashboard"
echo -e "  ${CYAN}creds add anthropic${RESET}      Add or update a credential"
echo -e "  ${CYAN}creds get anthropic${RESET}      Print a key to stdout"
echo -e "  ${CYAN}creds audit${RESET}              Show all credential status"
echo -e "  ${CYAN}creds audit --missing${RESET}    Show only unset credentials"
echo -e "  ${CYAN}creds migrate${RESET}            Scan + import legacy keys"
echo -e "  ${CYAN}eval \$(creds env)${RESET}       Load all keys into shell"
echo ""
echo "  Available services (run 'creds audit' for full list):"
dim "  anthropic, openai, deepseek, openrouter, cerebras, mistral,"
dim "  litellm, google-api, google-oauth, coda, slack, notion, github, ntfy"
echo ""
echo -e "  ${DIM}Credentials stored at: Keychain > io.creds.store${RESET}"
echo ""
