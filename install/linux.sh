#!/usr/bin/env bash
set -euo pipefail
[[ "$(uname -s)" == Linux ]] || { echo '请在 Linux 运行本入口。' >&2; exit 1; }
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
workflow_python="${DRAWIO_PYTHON:-python3}"
if ! "$workflow_python" -c 'import sys, venv, ensurepip; assert sys.version_info >= (3,10)' 2>/dev/null; then
  echo '需要 Python 3.10+ 和 venv。将使用本机 apt/dnf 安装 Python。'
  auto_yes=false
  for arg in "$@"; do [[ "$arg" != --yes ]] || auto_yes=true; done
  if ! $auto_yes; then
    read -r -p '是否安装？[Y/n] ' reply
    case "$reply" in n|N|no|NO) exit 1;; esac
  fi
  sudo_cmd=()
  if (( EUID != 0 )); then sudo_cmd=(sudo); fi
  if command -v apt-get >/dev/null; then
    "${sudo_cmd[@]}" apt-get update
    "${sudo_cmd[@]}" apt-get install -y python3 python3-venv
  elif command -v dnf >/dev/null; then
    "${sudo_cmd[@]}" dnf install -y python3 python3-pip
  else
    echo '请先安装 Python 3.10+ 和 venv，再运行本脚本。' >&2; exit 1
  fi
  workflow_python=python3
fi
"$workflow_python" -c 'import sys; assert sys.version_info >= (3,10), "Python 3.10+ required (Ubuntu 22.04+ recommended)"'
# Debian may provide venv without ensurepip until python3-venv is installed.
if ! "$workflow_python" -c 'import ensurepip' 2>/dev/null; then
  echo '当前 Python 缺少 ensurepip；请安装匹配版本的 python3-venv，或通过 DRAWIO_PYTHON 指定完整 Python。' >&2
  exit 1
fi
exec "$workflow_python" "$repo_dir/scripts/setup_workflow.py" "$@"
