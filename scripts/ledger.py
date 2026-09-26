#!/usr/bin/env python3
"""统一记账入口（由 AI 调用，也可手动运行）。

用法：
  python3 scripts/ledger.py check                               校验全部账本（有往来镜像时含跨账本对账）
  printf '%s' '<分录>' | python3 scripts/ledger.py add <账本>     追加【一笔】（自动校验，失败自动回滚）
  python3 scripts/ledger.py recent <账本> [-n N]                 最近 N 笔交易
  python3 scripts/ledger.py summary <账本> [YYYY-MM]             按大类汇总支出/收入
  python3 scripts/ledger.py balances <账本>                      各账户余额
  python3 scripts/ledger.py tag <账本> <单个标签> [YYYY-MM]      按标签查账（一次只支持一个标签）
  python3 scripts/ledger.py report <账本> [YYYY-MM]              月度财务分析报告
  python3 scripts/ledger.py reconcile                            跨账本往来对账
  python3 scripts/ledger.py networth [--rate 币种=汇率]          资产负债汇总
  python3 scripts/ledger.py fmt [--check] [账本]                 序时簿排版规范化
  python3 scripts/ledger.py books                                列出账本与往来镜像
  python3 scripts/ledger.py new-book <名称> [--template ...] [--link ...]   新建账本

账本名来自账套根目录的 ledger.toml。实现拆分在 scripts/ledgerlib/ 下，本文件只做入口转发。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ledgerlib.cli import main  # noqa: E402


def _utf8_output():
    """输出编码表示不了中文时（如英文版 Windows 把输出重定向到管道）改用 UTF-8，避免打印报错。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            "账".encode(stream.encoding or "ascii")
        except (UnicodeEncodeError, LookupError):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, ValueError):
                pass


def _run():
    _utf8_output()
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
