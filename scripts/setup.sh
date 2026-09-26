#!/usr/bin/env bash
# ============================================================
# 环境一键准备：在账套根目录执行 bash scripts/setup.sh
# 只负责“安装 Python 记账依赖 + 校验全部账本”，不碰账本数据，不改 Git 配置。
# 前提：本机已有 python3（>= 3.9）、pip、git。
# 云端运行环境（容器会被回收）可把本脚本填进环境的 setup script，每次开机自动准备好。
# ============================================================
set -euo pipefail
cd "$(dirname "$0")/.."

missing=()
for bin in python3 git; do
  command -v "$bin" >/dev/null 2>&1 || missing+=("$bin")
done
if [ ${#missing[@]} -gt 0 ]; then
  echo "[缺少基础工具] ${missing[*]}；本脚本只补 Python 依赖，请先安装上述工具。" >&2
  exit 1
fi
if ! python3 -m pip --version >/dev/null 2>&1; then
  echo "[缺少] python3 -m pip 不可用，请先安装 pip。" >&2
  exit 1
fi

echo "[1/2] 安装 Python 记账依赖（beancount）..."
python3 -m pip install -q -r requirements.txt

echo "[2/2] 校验账本 ..."
python3 scripts/ledger.py check

echo "环境就绪。"
