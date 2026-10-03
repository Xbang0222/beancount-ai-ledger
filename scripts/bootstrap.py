#!/usr/bin/env python3
"""准备运行环境：装好记账依赖，再校验一遍账本。

用法（Windows 用 python 或 py 代替 python3）：
  python3 scripts/bootstrap.py                    装依赖并校验账本
  python3 scripts/bootstrap.py --no-check         只装依赖
  python3 scripts/bootstrap.py -i <镜像地址>       指定 PyPI 镜像，如 https://pypi.tuna.tsinghua.edu.cn/simple

没指定镜像而官方源装不上时，会自动换清华镜像再试一次。

当前 Python 已经装好依赖就不再安装；否则在仓库根目录建 .venv（已有就复用），把
requirements.txt 装进去。之后照常运行 python3 scripts/ledger.py，入口会自动改用 .venv。
不往系统 Python 里装包，不碰账本数据，不改 Git 配置。只用标准库，Windows / macOS / Linux 通用。
"""
import argparse
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ledgerlib import env  # noqa: E402

LEDGER = os.path.join(env.REPO_ROOT, "scripts", "ledger.py")
# 官方源装不上时自动换它重试一次：国内网络、云电脑里很常见，省得再让人（或 AI）手动加 -i
FALLBACK_INDEX = "https://pypi.tuna.tsinghua.edu.cn/simple"


def _has_pip(python):
    return subprocess.call([python, "-m", "pip", "--version"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def _venv_hint():
    if sys.platform.startswith("linux"):
        print("       Debian / Ubuntu 需要先装 venv 模块：sudo apt install python3-venv")
    if shutil.which("uv"):
        print("       也可以用 uv：uv venv .venv && uv pip install --python .venv -r requirements.txt")
    print("       处理好后删掉 .venv 目录，再运行一次本脚本。")


def _target_python():
    """返回要安装依赖的解释器：正在 .venv 里运行就装进当前解释器，否则用（必要时新建）.venv。"""
    if env.in_venv():
        return sys.executable
    python = env.venv_python()
    if python:
        print(f"[..] 复用已有的虚拟环境 {env.VENV_DIR}")
        return python
    print(f"[..] 创建虚拟环境 {env.VENV_DIR}")
    rc = subprocess.call([sys.executable, "-m", "venv", env.VENV_DIR])
    python = env.venv_python()
    if rc != 0 or not python:
        print("[FAIL] 创建虚拟环境失败。")
        _venv_hint()
        return None
    return python


def main(argv=None):
    env.utf8_output()
    ap = argparse.ArgumentParser(prog="bootstrap.py", description="装好记账依赖并校验账本")
    ap.add_argument("--no-check", action="store_true", help="只装依赖，不校验账本")
    ap.add_argument("-i", "--index-url", metavar="URL", help="PyPI 镜像地址（官方源太慢时用）")
    args = ap.parse_args(argv)

    if sys.version_info < env.MIN_PYTHON:
        print(f"[FAIL] 需要 Python {'.'.join(map(str, env.MIN_PYTHON))} 或更高版本（当前：{env.python_label()}）。")
        return 3

    missing = env.missing_modules()
    if not missing:
        print(f"[OK] 当前 Python 已装好依赖（{env.python_label()}），不需要安装。")
        python = sys.executable
    else:
        print(f"[..] 缺少依赖：{', '.join(missing)}")
        python = _target_python()
        if not python:
            return 3
        if not _has_pip(python):
            print(f"[FAIL] {python} 没有可用的 pip。")
            _venv_hint()
            return 3
        print("[..] 安装 requirements.txt")
        cmd = [python, "-m", "pip", "install", "--disable-pip-version-check", "-r", env.REQUIREMENTS]
        rc = subprocess.call(cmd + (["--index-url", args.index_url] if args.index_url else []))
        if rc != 0 and not args.index_url:
            print(f"[..] 官方源安装失败，换镜像 {FALLBACK_INDEX} 再试一次")
            rc = subprocess.call(cmd + ["--index-url", FALLBACK_INDEX])
        if rc != 0:
            print("[FAIL] 安装失败，原因见上面 pip 的输出。可以换别的镜像重试：")
            print("       python3 scripts/bootstrap.py -i <镜像地址>")
            return 3

    if args.no_check:
        print("[OK] 依赖已就绪。")
        return 0
    print("[..] 校验账本")
    rc = subprocess.call([python, LEDGER, "check"])
    if rc == 0:
        print("\n环境就绪。之后直接运行 python3 scripts/ledger.py <命令>（会自动使用 .venv）。")
    return rc


if __name__ == "__main__":
    sys.exit(main())
