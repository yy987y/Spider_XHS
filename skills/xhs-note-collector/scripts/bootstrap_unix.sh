#!/usr/bin/env bash
set -euo pipefail

SEARCH_QUERY=""
KEYWORDS=""
DATE_RANGE="recent_7_days"
MAX_SEARCH_CANDIDATES="50"
NO_OPEN="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --search-query)
      SEARCH_QUERY="${2:-}"
      shift 2
      ;;
    --keywords)
      KEYWORDS="${2:-}"
      shift 2
      ;;
    --date-range)
      DATE_RANGE="${2:-recent_7_days}"
      shift 2
      ;;
    --max-search-candidates)
      MAX_SEARCH_CANDIDATES="${2:-50}"
      shift 2
      ;;
    --no-open)
      NO_OPEN="1"
      shift
      ;;
    *)
      echo "未知参数：$1" >&2
      exit 2
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

refresh_path() {
  export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

run_sudo() {
  if [[ "$(id -u)" == "0" ]]; then
    "$@"
  else
    sudo -n "$@"
  fi
}

ensure_homebrew() {
  refresh_path
  if have_cmd brew; then
    return
  fi
  NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  refresh_path
  have_cmd brew || {
    echo "Homebrew 自动安装后仍不可用。" >&2
    exit 1
  }
}

ensure_python() {
  refresh_path
  if have_cmd python3; then
    return
  fi
  if [[ "$(uname -s)" == "Darwin" ]]; then
    ensure_homebrew
    brew install python@3.12
    refresh_path
    return
  fi
  if have_cmd apt-get; then
    run_sudo apt-get update
    if [[ "$(id -u)" == "0" ]]; then
      DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-pip
    else
      sudo -n env DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-pip
    fi
  elif have_cmd dnf; then
    run_sudo dnf install -y python3 python3-pip
  elif have_cmd yum; then
    run_sudo yum install -y python3 python3-pip
  elif have_cmd pacman; then
    run_sudo pacman -Sy --noconfirm python python-pip
  else
    echo "未找到可用包管理器，无法自动安装 Python。" >&2
    exit 1
  fi
}

ensure_python

ARGS=("$SCRIPT_DIR/launch_wizard.py" "--date-range" "$DATE_RANGE" "--max-search-candidates" "$MAX_SEARCH_CANDIDATES")
if [[ -n "$SEARCH_QUERY" ]]; then
  ARGS+=("--search-query" "$SEARCH_QUERY" "--auto-start")
fi
if [[ -n "$KEYWORDS" ]]; then
  ARGS+=("--keywords" "$KEYWORDS")
fi
if [[ "$NO_OPEN" == "1" ]]; then
  ARGS+=("--no-open")
fi

python3 "${ARGS[@]}"
