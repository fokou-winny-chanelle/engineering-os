#!/usr/bin/env sh
# engineering-os bootstrap for macOS / Linux (and WSL).
#   git clone <your-fork>/engineering-os ~/engineering-os && ~/engineering-os/bootstrap.sh [eos bootstrap options]
# Examples:
#   ./bootstrap.sh                         # Cursor + Cline (default)
#   ./bootstrap.sh --tools all --global-hooks
#   ./bootstrap.sh --dry-run               # show what would change
# It is idempotent: re-run it after editing personal/PROFILE.user.md (your git-ignored profile), mcp/servers.json or secrets.env.
set -eu
here=$(cd "$(dirname "$0")" && pwd)

need() { command -v "$1" >/dev/null 2>&1; }

if ! need git; then
  echo "git is required. macOS: xcode-select --install | Debian/Ubuntu: sudo apt-get install -y git" >&2
  exit 1
fi

if ! need python3; then
  echo "python3 (>= 3.10) is required. macOS: brew install python | Debian/Ubuntu: sudo apt-get install -y python3" >&2
  exit 1
fi
python3 - <<'PY' || { echo "python3 >= 3.10 is required" >&2; exit 1; }
import sys
sys.exit(0 if sys.version_info >= (3, 10) else 1)
PY

if ! need uv; then
  echo "uv not found. Installing it with the official installer (https://docs.astral.sh/uv/)."
  echo "Read the script first if you prefer: https://astral.sh/uv/install.sh"
  if need curl; then curl -LsSf https://astral.sh/uv/install.sh | sh
  elif need wget; then wget -qO- https://astral.sh/uv/install.sh | sh
  else echo "need curl or wget to install uv" >&2; exit 1; fi
  PATH="$HOME/.local/bin:$PATH"; export PATH
fi

if ! need pre-commit; then
  uv tool install "pre-commit==$(sed -n 's/^"pre-commit" = "\(.*\)".*/\1/p' "$here/versions.toml")" || true
fi

exec python3 "$here/bin/eos.py" bootstrap "$@"
