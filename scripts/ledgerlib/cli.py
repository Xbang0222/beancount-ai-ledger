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
  python3 scripts/ledger.py doctor                       检查环境与账套状态，首次使用时先执行
  python3 scripts/ledger.py brief                        入账所需的现场信息：日期、临时状态、可用科目、写法、范例
  python3 scripts/ledger.py lookup 猫粮 拼多多            按关键词检索应记的科目与规则所在章节
  python3 scripts/ledger.py check                        校验全部账本；配置了往来镜像时同时对账
  python3 scripts/ledger.py add personal <<'EOF'         从标准输入入账一笔，分录写在 heredoc 中，以 EOF 结束
  python3 scripts/ledger.py add personal --file entry.tmp   从 UTF-8 文件入账一笔，用于不支持 heredoc 的终端
  python3 scripts/ledger.py pair <<'EOF'                 往来在两本账同时登记：每段首行为 [账本名]，共两段
  python3 scripts/ledger.py recent personal              最近 10 笔，行首 [编号] 用于更正与作废
  python3 scripts/ledger.py find personal 午餐 39.02     按关键词查找分录并显示编号
  python3 scripts/ledger.py amend personal <编号> <<'EOF'   更正：以新分录整笔替换，校验失败时还原
  python3 scripts/ledger.py void personal <编号>         作废：删除该笔
  python3 scripts/ledger.py summary personal 2026-09     按一级大类汇总
  python3 scripts/ledger.py balances personal            科目余额表
  python3 scripts/ledger.py tag personal trip 2026-09    按标签汇总明细，一次一个标签
  python3 scripts/ledger.py report personal 2026-09      月度报告：收支与储蓄率
  python3 scripts/ledger.py networth                     合并资产负债，抵销账本之间的往来
  python3 scripts/ledger.py networth --rate USD=7.1      指定汇率试算
  python3 scripts/ledger.py quote AU USD F161226         联网查询每克金价、汇率、基金净值
  python3 scripts/ledger.py dividend 2026-10             按月利润分配，按 ledger.toml 的 [dividend] 比例拆分
  python3 scripts/ledger.py new-book shop --template business --link personal
  python3 scripts/ledger.py backup                       将整个账套连同 Git 历史打包，供没有远程仓库时存入云盘
  python3 scripts/ledger.py backup --daily               同上，当日已备份时跳过
  python3 scripts/ledger.py --root examples/demo check   操作其他目录中的账套

约定：
  - 一次 add 只入账一笔交易，多笔分多次入账；
  - 账本之间的往来使用 pair 在两本账同时登记，add 遇到往来科目会拒绝；
  - 更正与作废一律使用 amend / void，不得手工编辑序时簿；
  - 账本存在加载错误时，查询类命令直接报错、不输出报告，须先执行 check 并修复。
"""


def _date(value):
    from datetime import date

    try:
        return date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"日期写成 YYYY-MM-DD，收到：{value}") from None


def _ym(value):
    try:
        return parse_ym(value)
    except ValueError as ex:
        raise argparse.ArgumentTypeError(str(ex)) from None


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
        description="Beancount 复式账套的统一入口：入账、更正、校验、查询、对账",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--root", metavar="DIR", help="账套根目录，即 ledger.toml 所在目录；默认为本仓库根目录")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", metavar="命令")

    sub.add_parser("doctor", help="检查运行环境、各账本状态、Git 远程仓库是否私有")

    c = sub.add_parser("check", help="校验全部账本；配置了往来镜像时同时对账")
    c.add_argument("--no-reconcile", action="store_true", help="跳过账本之间的往来对账")

    a = sub.add_parser("add", help="入账一笔分录：从标准输入或 --file 读取，校验失败时回滚")
    a.add_argument("book")
    a.add_argument("-f", "--file", metavar="PATH",
                   help="从 UTF-8 文本文件读取分录，不读标准输入；用于 Windows PowerShell 管道损坏中文的情形")
    a.add_argument("--allow-duplicate", action="store_true",
                   help="账上已有内容相同的分录时仍然入账，仅用于确属两笔独立交易的情形")
    a.add_argument("--one-sided", action="store_true",
                   help="分录用到往来科目时仍只登记本账本，仅用于补平既有的往来差额；其余情形使用 pair")

    pr = sub.add_parser("pair", help="往来在两本账同时登记：两本账各一笔，一并校验，任一边未通过则均不写入")
    pr.add_argument("-f", "--file", metavar="PATH", help="从 UTF-8 文本文件读取，不读标准输入")
    pr.add_argument("--allow-duplicate", action="store_true",
                    help="账上已有内容相同的分录时仍然入账，仅用于确属两笔独立交易的情形")

    fd = sub.add_parser("find", help="按关键词查找分录并显示编号；对方、摘要、科目、金额、标签均可检索")
    fd.add_argument("book")
    fd.add_argument("keyword", nargs="+", help="关键词；给出多个时须同时出现")
    fd.add_argument("--month", type=_ym, metavar="YYYY-MM", help="只在该月份内查找")
    fd.add_argument("-n", type=_positive_int, default=20, metavar="N", help="最多显示最近 N 笔，默认 20")

    vd = sub.add_parser("void", help="作废一笔分录：从序时簿删除，校验失败时回滚")
    vd.add_argument("book")
    vd.add_argument("id", help="分录编号，见 find / recent 输出行首的 [编号]")

    am = sub.add_parser("amend", help="更正一笔分录：以标准输入或 --file 传入的新分录整笔替换")
    am.add_argument("book")
    am.add_argument("id", help="分录编号，见 find / recent 输出行首的 [编号]")
    am.add_argument("-f", "--file", metavar="PATH", help="从 UTF-8 文本文件读取新分录，不读标准输入")
    am.add_argument("--allow-duplicate", action="store_true",
                    help="更正后与账上另一笔分录内容相同时仍然写入")

    rc = sub.add_parser("recent", help="按发生时间列出最近的交易")
    rc.add_argument("book")
    rc.add_argument("-n", type=_positive_int, default=10, metavar="N", help="显示笔数，默认 10")

    s = sub.add_parser("summary", help="按一级大类汇总支出与收入")
    s.add_argument("book")
    s.add_argument("ym", nargs="?", type=_ym, metavar="YYYY-MM")

    b = sub.add_parser("balances", help="科目余额表")
    b.add_argument("book")

    t = sub.add_parser("tag", help="按标签汇总明细，一次一个标签")
    t.add_argument("book")
    t.add_argument("tag")
    t.add_argument("ym", nargs="?", type=_ym, metavar="YYYY-MM")

    r = sub.add_parser("report", help="月度报告：收入、支出占比、结余与储蓄率")
    r.add_argument("book")
    r.add_argument("ym", nargs="?", type=_ym, metavar="YYYY-MM")

    sub.add_parser("reconcile", help="核对账本之间的往来：每对镜像科目两侧余额合计须为 0")

    n = sub.add_parser("networth", help="合并资产负债：合并各账本、抵销账本之间的往来，按当日价格折合本位币")
    n.add_argument("--rate", type=_rate, action="append", metavar="币种=汇率",
                   help="指定汇率，如 USD=7.1，可重复；只用于本次试算，不写入账本")
    n.add_argument("--offline", action="store_true", help="不联网取价，只使用账内 price")

    qt = sub.add_parser("quote", help="联网查询价格：外币、加密货币、金银（每克）、基金、股票，折合本位币")
    qt.add_argument("code", nargs="+", metavar="代码", help="USD、USDT、AU、AG、F161226、SH600519、HK00700、US.AAPL")
    qt.add_argument("--date", type=_date, metavar="YYYY-MM-DD", help="查询该日的历史价格；股票只有最新价")

    dv = sub.add_parser("dividend", help="按月利润分配：计算当月净利润，外币联网取汇率折算，按 [dividend] 比例拆分")
    dv.add_argument("ym", type=_ym, metavar="YYYY-MM")
    dv.add_argument("--rate", type=_rate, action="append", metavar="币种=汇率",
                    help="指定汇率，如 USDT=6.69；未指定时联网取得当日汇率")
    dv.add_argument("--recalc", action="store_true",
                    help="已发放分红的月份也重新计算应得与差额；默认视为已结清，只列实发金额")

    f = sub.add_parser("fmt", help="整理序时簿排版：分录间空行、按日期与时间排序")
    f.add_argument("--check", action="store_true", help="只检查不写入；排版不合规时退出码为 1")
    f.add_argument("book", nargs="?")

    sub.add_parser("books", help="列出 ledger.toml 中的账本与往来镜像")

    br = sub.add_parser("brief", help="入账所需的现场信息：日期、临时状态、待补记的周期分录、可用科目、写法、范例")
    br.add_argument("book", nargs="?", help="只输出该账本，默认全部")

    lk = sub.add_parser("lookup", help="按关键词检索分类表、速查词典、规则文档和科目说明")
    lk.add_argument("words", nargs="+", metavar="关键词", help="物品、商家或平台、业务名称；可给出多个，逐个检索")

    ru = sub.add_parser("rules", help="对方、摘要与 note 的写法对照表，取自 ledger.toml 的 [naming]")
    ru.add_argument("book", nargs="?", help="只输出该账本，默认全部")

    cm = sub.add_parser("commit-msg", help="检查提交信息：由 commit-msg 钩子调用；--range 检查已有的提交")
    cm.add_argument("file", nargs="?", help="git 传入的提交信息文件")
    cm.add_argument("--range", dest="rev_range", metavar="A..B",
                    help="改为检查该范围内已有的提交，如 origin/main..HEAD")

    nb = sub.add_parser("new-book", help="新建账本：生成科目表并登记到 ledger.toml")
    nb.add_argument("name", help="账本名：小写字母开头，可含数字、- 和 _，如 personal、shop、family")
    nb.add_argument("--template", choices=("personal", "business", "minimal"), default="personal",
                    help="科目表模板：personal 个人（默认）、business 经营、minimal 最小")
    nb.add_argument("--title", help="账本标题，如 \"家庭共同账\"")
    nb.add_argument("--kind", choices=config.KINDS,
                    help="账本性质：personal 的月度报告计算储蓄率，business 计算经营结余；默认随模板")
    nb.add_argument("--link", metavar="BOOK", help="与已有账本建立往来：生成双边往来科目与 [[mirrors]]")
    nb.add_argument("--open-date", metavar="YYYY-MM-DD", help="科目开户日期，默认 1970-01-01")
    nb.add_argument("--no-consolidate", action="store_true",
                    help="不并入 networth 的合并资产负债，用于与他人共有的账本，如家庭共同账")

    bk = sub.add_parser("backup", help="将整个账套连同 Git 历史打包为一个压缩包，供没有远程仓库时存入云盘")
    bk.add_argument("-o", "--out", metavar="DIR",
                    help="压缩包的存放目录；默认为账套根目录下的 backups/，只保留最新一份")
    bk.add_argument("--daily", action="store_true", help="当日已备份时跳过，用于每日备份一次")

    return p


def cmd_check(no_reconcile=False):
    cfg = config.load()
    ok = True
    for book in cfg.books:
        entries, errors, _ = load_book(book)
        if errors:
            ok = False
            print_errors(book, errors, entries)
        else:
            print(f"[OK] {book}: 校验通过，共 {len(entries)} 条指令")
            ok = _check_naming(book, entries) and ok
    if no_reconcile or not cfg.mirrors:
        return 0 if ok else 1
    if not ok:
        print("\n[skip] 账本有错误，跳过跨账套对账。")
        return 1
    from .reconcile import cmd_reconcile

    return cmd_reconcile()


def _check_naming(book, entries):
    """对方、摘要与 note 的写法（ledger.toml 的 [naming]）；不合规的逐笔列出文件与行号。"""
    from .naming import scan, unmapped

    ok = True
    missing = unmapped(book, entries)
    if missing:
        ok = False
        print(f"[FAIL] {book}: {len(missing)} 个收支科目没配摘要开头，这些科目的账不会被检查；"
              f"请在 {config.CONFIG_NAME} 的 [naming.prefix.{book}] 补上：")
        for acc in missing:
            print(f"   - {acc}")
    found = scan(book, entries)
    if not found:
        return ok
    print(f"[FAIL] {book}: {len(found)} 笔对方、摘要或 note 的写法不合规"
          f"（对照表见 ledger.py rules {book}，用 amend 更正）：")
    for t, msgs in found:
        meta = t.meta or {}
        where = os.path.relpath(meta.get("filename", ""), config.ROOT).replace(os.sep, "/")
        print(f"   - {where}:{meta.get('lineno')}  {t.date} \"{t.payee or ''}\" \"{t.narration or ''}\"")
        for m in msgs:
            print(f"       {m}")
    return False


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


def _remind_hooks(rc):
    """改完账顺带检查：这台设备没启用提交检查的话直接启用，否则排版和提交信息不合规也能提交上去。"""
    if rc == 0:
        from .doctor import ENABLED_NOTE, HOOKS_DIR, enable_hooks, hooks_missing

        if enable_hooks():
            print(f"\n[OK] {ENABLED_NOTE}")
        elif hooks_missing():
            print(f"\n[WARN] 这台设备没有启用提交前自动检查，提交前先运行一次：git config core.hooksPath {HOOKS_DIR}")
    return rc


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
    if args.cmd == "commit-msg":
        from . import commitmsg

        if args.rev_range:
            return commitmsg.cmd_commit_range(args.rev_range)
        if not args.file:
            print("[FAIL] commit-msg 要给提交信息文件，或用 --range A..B 检查已有的提交。")
            return 1
        return commitmsg.cmd_commit_msg(args.file)
    if args.cmd == "brief":
        from .brief import cmd_brief

        return cmd_brief(args.book)
    if args.cmd == "lookup":
        from .lookup import cmd_lookup

        return cmd_lookup(args.words)
    if args.cmd == "rules":
        from .naming import cmd_rules

        return cmd_rules(args.book)
    if args.cmd == "backup":
        from .backup import cmd_backup

        return cmd_backup(args.out, daily=args.daily)
    if args.cmd == "add":
        from .add import cmd_add

        return _remind_hooks(cmd_add(args.book, path=args.file, allow_duplicate=args.allow_duplicate,
                                     one_sided=args.one_sided))
    if args.cmd == "pair":
        from .pair import cmd_pair

        return _remind_hooks(cmd_pair(path=args.file, allow_duplicate=args.allow_duplicate))
    if args.cmd in ("find", "void", "amend"):
        from . import edit

        if args.cmd == "find":
            return edit.cmd_find(args.book, args.keyword, args.month, args.n)
        if args.cmd == "void":
            return _remind_hooks(edit.cmd_void(args.book, args.id))
        return _remind_hooks(
            edit.cmd_amend(args.book, args.id, path=args.file, allow_duplicate=args.allow_duplicate))
    if args.cmd == "reconcile":
        from .reconcile import cmd_reconcile

        return cmd_reconcile()
    if args.cmd == "networth":
        from .networth import cmd_networth

        return cmd_networth(dict(args.rate or []), offline=args.offline)
    if args.cmd == "quote":
        from .quote import cmd_quote

        return cmd_quote(args.code, args.date)
    if args.cmd == "dividend":
        from .dividend import cmd_dividend

        return cmd_dividend(args.ym, dict(args.rate or []), args.recalc)
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
