"""查询类命令：summary / balances / tag / report / recent。"""
import re
from collections import defaultdict
from decimal import Decimal

from . import config
from .books import balances, load_entries, transactions
from .config import EPSILON, MOVE_PREFIX
from .display import pad, print_txn
from .entry import entry_ym


def _top_category(account):
    """一级大类 : 二级明细 → 取前两级作为汇总口径。"""
    return ":".join(account.split(":")[:2])


def _in_period(txn, ym):
    return ym is None or entry_ym(txn.date) == ym


def _collect(entries, ym=None):
    exp = defaultdict(lambda: defaultdict(Decimal))
    inc = defaultdict(lambda: defaultdict(Decimal))
    for txn in transactions(entries):
        if not _in_period(txn, ym):
            continue
        for p in txn.postings:
            if p.units is None:
                continue
            cur = p.units.currency
            num = Decimal(p.units.number)
            if p.account.startswith("Expenses:"):
                exp[_top_category(p.account)][cur] += num
            elif p.account.startswith("Income:"):
                inc[_top_category(p.account)][cur] += -num
    return exp, inc


def print_summary(book, ym=None, entries=None):
    if entries is None:
        entries = load_entries(book)
    if entries is None:
        return 1
    exp, inc = _collect(entries, ym)
    label = ym or "累计"
    print(f"\n===== {book} · {label} · 支出大类 =====")
    total = defaultdict(Decimal)
    for cat in sorted(exp):
        for cur, v in exp[cat].items():
            print(f"  {cat:<36}{v:>10.2f} {cur}")
            total[cur] += v
    for cur, v in total.items():
        print(f"  {pad('— 支出合计 —', 36)}{v:>10.2f} {cur}")
    if inc:
        print("----- 收入 -----")
        for cat in sorted(inc):
            for cur, v in inc[cat].items():
                print(f"  {cat:<36}{v:>10.2f} {cur}")
    if not exp and not inc:
        print(f"  （{label} 无收支记录）")
    return 0


def cmd_summary(book, ym=None):
    return print_summary(book, ym)


def cmd_balances(book):
    entries = load_entries(book)
    if entries is None:
        return 1
    bals = balances(entries)
    print(f"\n===== {book} · 科目余额表 =====")
    for acc in sorted(bals):
        for cur, v in bals[acc].items():
            if abs(v) >= Decimal(EPSILON):
                print(f"  {acc:<38}{v:>12.2f} {cur}")
    return 0


def cmd_tag(book, tag, ym=None):
    entries = load_entries(book)
    if entries is None:
        return 1
    tag = tag.lstrip("#")
    matched = []
    # 支出、收入、往来/资金移动三桶分开，不把收入支出绝对值加成一个“合计”
    exp_cat = defaultdict(lambda: defaultdict(Decimal))
    inc_cat = defaultdict(lambda: defaultdict(Decimal))
    move_cat = defaultdict(lambda: defaultdict(Decimal))
    exp_sum = defaultdict(Decimal)
    inc_sum = defaultdict(Decimal)
    for txn in transactions(entries):
        if tag not in (txn.tags or set()):
            continue
        if not _in_period(txn, ym):
            continue
        matched.append(txn)
        for p in txn.postings:
            if p.units is None:
                continue
            cur = p.units.currency
            num = Decimal(p.units.number)
            acct = p.account
            if acct.startswith("Expenses:"):
                exp_cat[_top_category(acct)][cur] += num
                exp_sum[cur] += num
            elif acct.startswith("Income:"):
                inc_cat[_top_category(acct)][cur] += -num
                inc_sum[cur] += -num
            elif acct.startswith(MOVE_PREFIX):
                move_cat[acct][cur] += num
    label = ym or "累计"
    print(f"\n===== {book} · 标签 #{tag} · {label} · 共 {len(matched)} 笔 =====")
    for txn in matched:
        print_txn(txn)

    def _block(title, cats, sums, empty="（无）"):
        print(f"\n----- {title} -----")
        if not cats:
            print(f"  {empty}")
            return
        for cat in sorted(cats):
            for cur, v in cats[cat].items():
                print(f"  {cat:<36}{v:>10.2f} {cur}")
        for cur, v in sums.items():
            print(f"  {pad('— 小计 —', 36)}{v:>10.2f} {cur}")

    _block("支出", exp_cat, exp_sum)
    _block("收入", inc_cat, inc_sum)
    print("\n----- 往来 / 资金移动（非收支，带方向，不计入上面合计） -----")
    if move_cat:
        for acc in sorted(move_cat):
            for cur, v in move_cat[acc].items():
                print(f"  {acc:<36}{v:>10.2f} {cur}")
    else:
        print("  （无）")
    return 0


def cmd_report(book, ym=None):
    entries = load_entries(book)
    if entries is None:
        return 1
    is_business = config.get_book(book).kind == "business"
    label = ym or "累计"
    inc_total = defaultdict(Decimal)
    exp_total = defaultdict(Decimal)
    inc_cat = defaultdict(lambda: defaultdict(Decimal))
    exp_cat = defaultdict(lambda: defaultdict(Decimal))
    bals = defaultdict(lambda: defaultdict(Decimal))
    for txn in transactions(entries):
        in_period = _in_period(txn, ym)
        for p in txn.postings:
            if p.units is None:
                continue
            cur = p.units.currency
            num = Decimal(p.units.number)
            bals[p.account][cur] += num
            if not in_period:
                continue
            if p.account.startswith("Income:"):
                inc_cat[_top_category(p.account)][cur] += -num
                inc_total[cur] += -num
            elif p.account.startswith("Expenses:"):
                exp_cat[_top_category(p.account)][cur] += num
                exp_total[cur] += num
    print(f"\n{'='*50}")
    print(f"  {book} · {label} · 财务分析报告")
    print(f"{'='*50}")
    if not inc_cat and not exp_cat:
        print(f"\n  （{label} 无收支记录）")
    print("\n【收入】")
    for cat in sorted(inc_cat):
        for cur, v in inc_cat[cat].items():
            print(f"  {cat:<32}{v:>10.2f} {cur}")
    for cur, v in inc_total.items():
        print(f"  {pad('收入合计', 32)}{v:>10.2f} {cur}")
    print("\n【支出】")
    for cat in sorted(exp_cat):
        for cur, v in exp_cat[cat].items():
            pct = (v / exp_total[cur] * 100) if exp_total[cur] else 0
            print(f"  {cat:<32}{v:>10.2f} {cur}  ({pct:.1f}%)")
    for cur, v in exp_total.items():
        print(f"  {pad('支出合计', 32)}{v:>10.2f} {cur}")
    print("\n【结余与储蓄率】" if not is_business else "\n【经营结余】")
    for cur in sorted(set(list(inc_total) + list(exp_total))):
        inc = inc_total.get(cur, Decimal(0))
        exp = exp_total.get(cur, Decimal(0))
        net = inc - exp
        print(f"  收入 {inc:.2f} − 支出 {exp:.2f} = 结余 {net:.2f} {cur}")
        if is_business:
            if inc > 0:
                print(f"  经营利润率: {net / inc * 100:.1f}%")
        elif inc > 0:
            print(f"  储蓄率: {net / inc * 100:.1f}%")
        else:
            print("  储蓄率: 不适用（本期无收入，比率无意义）")
    bal_title = "【主要账户余额（累计到最新时点，非查询当月末）】" if ym else "【账户余额（累计全期）】"
    print(f"\n{bal_title}")
    for acc in sorted(bals):
        if acc.startswith(("Equity:", "Income:", "Expenses:")):
            continue
        for cur, v in bals[acc].items():
            if abs(v) >= Decimal(EPSILON):
                print(f"  {acc:<34}{v:>12.2f} {cur}")
    return 0


_HM_RE = re.compile(r"^(\d{1,2}):(\d{2})")


def _time_key(txn):
    """time 元数据规范成 HH:MM 便于排序；没有 time 的排在同日最前。"""
    m = _HM_RE.match(str((txn.meta or {}).get("time", "")))
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else ""


def cmd_recent(book, n=10):
    """按发生日期与时间列出最近 n 笔交易（核对刚才是否记上、有没有重复时用）。"""
    entries = load_entries(book)
    if entries is None:
        return 1
    txns = transactions(entries)
    ordered = sorted(
        enumerate(txns),
        key=lambda it: (it[1].date, _time_key(it[1]), it[0]),
    )
    shown = [t for _, t in ordered[-n:]] if n > 0 else []
    print(f"\n===== {book} · 最近 {len(shown)} 笔（按发生日期与时间，共 {len(txns)} 笔） =====")
    if not shown:
        print("  （暂无交易）")
    for txn in shown:
        print_txn(txn)
    return 0
