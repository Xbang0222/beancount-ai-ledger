"""运行环境：依赖检查，以及自动改用仓库里的 .venv。

只用标准库：scripts/ledger.py 在导入其余模块之前就要调用这里，此时依赖可能还没装。
"""
import os
import re
import subprocess
import sys
from importlib.util import find_spec

MIN_PYTHON = (3, 9)
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VENV_DIR = os.path.join(REPO_ROOT, ".venv")
REQUIREMENTS = os.path.join(REPO_ROOT, "requirements.txt")
# 已经切换过一次解释器的标记，防止 .venv 损坏时来回重启
REEXEC_FLAG = "LEDGER_VENV_REEXEC"


def utf8_output():
    """输出编码表示不了中文时（如英文版 Windows 把输出重定向到管道）改用 UTF-8，避免打印报错。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            "账".encode(stream.encoding or "ascii")
        except (UnicodeEncodeError, LookupError):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, ValueError):
                pass


def required_modules():
    mods = ["beancount"]
    if sys.version_info < (3, 11):
        mods.append("tomli")    # 3.11 起标准库自带 tomllib
    if sys.platform == "win32":
        mods.append("tzdata")   # Windows 没有系统时区库
    return mods


def beancount_version():
    try:
        from importlib.metadata import version

        return version("beancount")
    except Exception:
        return None


def missing_modules():
    """当前解释器缺少的依赖；装的是 beancount 2.x 也算缺（脚本需要 3.x）。"""
    missing = [m for m in required_modules() if find_spec(m) is None]
    if "beancount" not in missing:
        v = beancount_version()
        m = re.match(r"\d+", v or "")
        if m and int(m.group()) < 3:
            missing.insert(0, f"beancount>=3（当前 {v}）")
    return missing


def venv_python():
    """仓库 .venv 里的解释器路径；没有 .venv 时返回 None。"""
    for parts in (("bin", "python"), ("Scripts", "python.exe")):
        path = os.path.join(VENV_DIR, *parts)
        if os.path.isfile(path):
            return path
    return None


def in_venv():
    return os.path.normcase(os.path.realpath(sys.prefix)) == os.path.normcase(os.path.realpath(VENV_DIR))


def python_label():
    return f"{sys.executable}，Python {sys.version.split()[0]}"


def ensure(script, argv):
    """依赖齐全返回 None，调用方照常运行。

    缺依赖但仓库里有 .venv 时，用 .venv 的解释器重跑同一条命令并返回它的退出码；
    都不行时打印安装办法并返回 3。
    """
    if sys.version_info < MIN_PYTHON:
        print(f"[FAIL] 需要 Python {'.'.join(map(str, MIN_PYTHON))} 或更高版本（当前：{python_label()}）。")
        return 3
    missing = missing_modules()
    if not missing:
        return None
    py = venv_python()
    if py and not in_venv() and not os.environ.get(REEXEC_FLAG):
        env = dict(os.environ, **{REEXEC_FLAG: "1"})
        try:
            return subprocess.call([py, os.path.abspath(script)] + list(argv), env=env)
        except KeyboardInterrupt:
            return 130
        except OSError:
            pass  # .venv 损坏（比如解释器被删），按缺依赖处理
    where = "仓库的 .venv 里也缺依赖" if py else "缺少依赖"
    print(f"[FAIL] {where}：{', '.join(missing)}（当前解释器：{python_label()}）")
    print("       运行 python3 scripts/bootstrap.py 安装（Windows 用 python 或 py 代替 python3）。")
    print("       依赖会装进仓库的 .venv，之后照常运行 python3 scripts/ledger.py，入口会自动改用 .venv。")
    return 3
