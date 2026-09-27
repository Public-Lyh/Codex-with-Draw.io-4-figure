#!/usr/bin/env bash
set -euo pipefail
[[ "$(uname -s)" == Darwin ]] || { echo '请在 macOS 运行本入口。' >&2; exit 1; }
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
workflow_python="${DRAWIO_PYTHON:-python3}"
if ! "$workflow_python" -c 'import sys, venv; assert sys.version_info >= (3,10)' 2>/dev/null; then
  echo '需要 Python 3.10+。将通过 Homebrew 安装。'
  auto_yes=false
  for arg in "$@"; do [[ "$arg" != --yes ]] || auto_yes=true; done
  if ! $auto_yes; then
    read -r -p '是否继续安装 Python / 必要时安装 Homebrew？[Y/n] ' reply
    case "$reply" in n|N|no|NO) exit 1;; esac
  fi
  brew_bin="$(command -v brew || true)"
  for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    if [[ -z "$brew_bin" && -x "$candidate" ]]; then brew_bin="$candidate"; fi
  done
  if [[ -z "$brew_bin" ]]; then
    brew_script="$(mktemp -t codex-drawio-brew)"
    trap 'rm -f "$brew_script"' EXIT
    curl --fail --location --proto '=https' --tlsv1.2 https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh -o "$brew_script"
    /bin/bash "$brew_script"
    rm -f "$brew_script"
    trap - EXIT
    for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew; do
      if [[ -x "$candidate" ]]; then brew_bin="$candidate"; break; fi
    done
  fi
  [[ -n "$brew_bin" ]] || { echo 'Homebrew 未安装完成。' >&2; exit 1; }
  "$brew_bin" install python
  workflow_python="$("$brew_bin" --prefix)/bin/python3"
fi
exec "$workflow_python" "$repo_dir/scripts/setup_workflow.py" "$@"
