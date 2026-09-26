"""命令行入口：参数校验与分发。"""
import argparse
import os
import re
import sys
from decimal import Decimal, InvalidOperation

from . import __version__, config
from .books import load_book, print_errors
from .display import pad
from .entry import parse_ym

EPILOG = """\
示例：
  python3 scripts/ledger.py doctor                       检查环境与账套状态（第一次用先跑它）
  python3 scripts/ledger.py check                        校验全部账本（有往来镜像时连带对账）
  python3 scripts/ledger.py add personal <<'EOF'         从 stdin 录一笔，分录写在 heredoc 里，以 EOF 结束
  python3 scripts/ledger.py add personal --file entry.tmp   从 UTF-8 文件录一笔（PowerShell 等没有 heredoc 时用）
  python3 scripts/ledger.py recent personal              最近 10 笔（核对刚才记上没有）
  python3 scripts/ledger.py summary personal 2026-09     按一级大类汇总
  python3 scripts/ledger.py balances personal            科目余额表
  python3 scripts/ledger.py tag personal trip 2026-09    按标签查明细（一次一个标签）
  python3 scripts/ledger.py report personal 2026-09      月度收支 / 储蓄率分析
  python3 scripts/ledger.py networth                     资产负债汇总（多本账时抵销账本间往来）
  python3 scripts/ledger.py networth --rate USD=7.1      临时指定汇率试算
  python3 scripts/ledger.py new-book shop --template business --link personal
  python3 scripts/ledger.py --root examples/demo check   对另一个目录里的账套操作

约定：
  - 一次 add 只录一笔交易，多笔请分多次；
  - 查询类命令在账本存在加载错误时直接报错、不出报告，请先 check 修复。
"""


def _ym(value):
    try:
        return parse_ym(value)
    except ValueError as ex:
        raise argparse.ArgumentTypeError(str(ex))


def _rate(value):
    m = re.match(r"^([A-Z][A-Z0-9'._-]*[A-Z0-9])=(.+)$", value or "")
    try:
        rate = Decimal(m.group(2)) if m else None
    except InvalidOperation:
        rate = None
    if rate is None or not rate.is_finite() or rate <= 0:
        raise argparse.ArgumentTypeError(f"汇率写成 币种=数值，如 USD=7.1，收到：{value!r}")
    return m.group(1), rate


def _positive_int(value):
    try:
        n = int(value)
    except ValueError:
        n = 0
    if n <= 0:
        raise argparse.ArgumentTypeError(f"应为正整数，收到：{value!r}")
    return n


def build_parser():
    p = argparse.ArgumentParser(
        prog="ledger.py",
        description="Beancount 复式记账账套的统一入口：入账、校验、查询、对账",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--root", metavar="DIR", help="账套根目录（ledger.toml 所在目录），默认为本仓库根目录")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", metavar="命令")

    sub.add_parser("doctor", help="检查运行环境、各账本状态和 Git 远程仓库是否安全")

    c = sub.add_parser("check", help="校验全部账本（有往来镜像时默认连带对账）")
    c.add_argument("--no-reconcile", action="store_true", help="跳过跨账本往来对账")

    a = sub.add_parser("add", help="追加一笔分录（从 stdin 或 --file 读取；自动校验，失败自动回滚）")
    a.add_argument("book")
    a.add_argument("-f", "--file", metavar="PATH",
                   help="从 UTF-8 文本文件读取分录，不读 stdin（Windows PowerShell 管道会弄坏中文时用）")

    rc = sub.add_parser("recent", help="按发生时间列出最近几笔交易")
    rc.add_argument("book")
    rc.add_argument("-n", type=_positive_int, default=10, metavar="N", help="显示笔数，默认 10")

    s = sub.add_parser("summary", help="按一级大类汇总支出/收入")
    s.add_argument("book")
    s.add_argument("ym", nargs="?", type=_ym, metavar="YYYY-MM")

    b = sub.add_parser("balances", help="各账户余额")
    b.add_argument("book")

    t = sub.add_parser("tag", help="按标签查账（一次只支持一个标签）")
    t.add_argument("book")
    t.add_argument("tag")
    t.add_argument("ym", nargs="?", type=_ym, metavar="YYYY-MM")

    r = sub.add_parser("report", help="月度财务分析报告")
    r.add_argument("book")
    r.add_argument("ym", nargs="?", type=_ym, metavar="YYYY-MM")

    sub.add_parser("reconcile", help="跨账本往来对账（每对镜像科目两侧余额必须相加为 0）")

    n = sub.add_parser("networth", help="资产负债汇总：合并各账本、抵销账本间往来，外币折合本位币")
    n.add_argument("--rate", type=_rate, action="append", metavar="币种=汇率",
                   help="临时指定汇率（如 USD=7.1，可重复），只用于本次试算、不写入账本")

    f = sub.add_parser("fmt", help="序时簿排版规范化（分录间空行、按日期时间重排）")
    f.add_argument("--check", action="store_true", help="只检测不写入，未格式化则退出码 1")
    f.add_argument("book", nargs="?")

    sub.add_parser("books", help="列出 ledger.toml 中的账本与往来镜像")

    nb = sub.add_parser("new-book", help="新建账本（生成科目表模板并登记到 ledger.toml）")
    nb.add_argument("name", help="账本名：小写字母开头，可含数字、- 和 _（如 personal、shop、family）")
    nb.add_argument("--template", choices=("personal", "business", "minimal"), default="personal",
                    help="科目表模板：personal 个人（默认）/ business 经营 / minimal 最小")
    nb.add_argument("--title", help="账本标题，如 \"家庭共同账\"")
    nb.add_argument("--kind", choices=config.KINDS,
                    help="账本性质：personal 算储蓄率 / business 看经营结余；默认随模板")
    nb.add_argument("--link", metavar="BOOK", help="与已有账本建立往来（生成双边往来科目与 [[mirrors]]）")
    nb.add_argument("--open-date", metavar="YYYY-MM-DD", help="科目开户日期，默认 1970-01-01")
    nb.add_argument("--no-consolidate", action="store_true",
                    help="不并入 networth 合并资产负债（与他人共有的账本，如家庭共同账）")

    return p


def cmd_check(no_reconcile=False):
    cfg = config.load()
    ok = True
    for book in cfg.books:
        entries, errors, _ = load_book(book)
        if errors:
            ok = False
            print_errors(book, errors)
        else:
            print(f"[OK] {book}: 校验通过，共 {len(entries)} 条指令")
    if no_reconcile or not cfg.mirrors:
        return 0 if ok else 1
    if not ok:
        print("\n[skip] 账本有错误，跳过跨账套对账。")
        return 1
    from .reconcile import cmd_reconcile

    return cmd_reconcile()


def cmd_books():
    cfg = config.load()
    print(f"\n===== 账本清单（{config.CONFIG_NAME}，时区 {cfg.timezone}，本位币 {cfg.base_currency}） =====")
    for b in cfg.books.values():
        merged = "并入 networth" if b.consolidate else "不并入 networth"
        print(f"  {pad(b.name, 12)}{pad(b.title, 16)}{pad(b.kind, 10)}{pad(b.main, 24)}{merged}")
    print(f"\n----- 往来镜像 {len(cfg.mirrors)} 对 -----")
    if not cfg.mirrors:
        print("  （无）")
    for m in cfg.mirrors:
        (lb, la), (rb, ra) = m.sides()
        print(f"  {m.name}（{m.currency}）：{lb} {la}  ⇄  {rb} {ra}")
    return 0


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    if not args.cmd:
        parser.print_help()
        return 1
    if args.root:
        config.ROOT = os.path.abspath(args.root)
    try:
        return _dispatch(args)
    except config.ConfigError as ex:
        print(f"[FAIL] {ex}")
        return 2


def _dispatch(args):
    if args.cmd == "doctor":
        from .doctor import cmd_doctor

        return cmd_doctor()
    if args.cmd == "new-book":
        from .newbook import cmd_new_book

        return cmd_new_book(args.name, template=args.template, title=args.title, kind=args.kind,
                            link=args.link, open_date=args.open_date,
                            consolidate=not args.no_consolidate)
    if getattr(args, "book", None) is not None:
        config.get_book(args.book)  # 未声明的账本名在这里统一报错并列出可选项

    if args.cmd == "check":
        return cmd_check(args.no_reconcile)
    if args.cmd == "books":
        return cmd_books()
    if args.cmd == "add":
        from .add import cmd_add

        return cmd_add(args.book, path=args.file)
    if args.cmd == "reconcile":
        from .reconcile import cmd_reconcile

        return cmd_reconcile()
    if args.cmd == "networth":
        from .networth import cmd_networth

        return cmd_networth(dict(args.rate or []))
    if args.cmd == "fmt":
        from .fmt import cmd_fmt

        return cmd_fmt((args.book,) if args.book else None, check_only=args.check)

    from . import query

    if args.cmd == "recent":
        return query.cmd_recent(args.book, args.n)
    if args.cmd == "summary":
        return query.cmd_summary(args.book, args.ym)
    if args.cmd == "balances":
        return query.cmd_balances(args.book)
    if args.cmd == "tag":
        return query.cmd_tag(args.book, args.tag, args.ym)
    if args.cmd == "report":
        return query.cmd_report(args.book, args.ym)
    return 1
