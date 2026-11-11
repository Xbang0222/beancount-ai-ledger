#!/usr/bin/env python3
"""统一记账入口（由 AI 调用，也可手动运行）。

命令清单与参数以 `python3 scripts/ledger.py --help` 为准（定义在 ledgerlib/cli.py），这里不另抄一份。
账本名来自账套根目录的 ledger.toml。实现拆分在 scripts/ledgerlib/ 下，本文件只做入口转发。
缺依赖时，如果仓库里有 .venv（scripts/bootstrap.py 建的），会自动改用 .venv 的解释器运行。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ledgerlib import env  # noqa: E402  只用标准库，依赖没装时也能导入


def _run():
    env.utf8_output()
    rc = env.ensure(__file__, sys.argv[1:])
    if rc is not None:
        return rc
    from ledgerlib.cli import main

    try:
        return main()
    except BrokenPipeError:
        # 输出被 head / less 提前关闭时安静退出，不抛 traceback
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 0
    except KeyboardInterrupt:
        print("\n已中断。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(_run())
