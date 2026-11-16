"""入账前的一页现场信息：今天几号、当前临时状态、该补的周期分录、能用哪些科目、怎么写、最近几笔长什么样。

把“读 STATE.md、查 rules、翻科目表、看最近几笔”合成一条命令，记账的人（多半是 AI）照着输出写分录，
不用靠记性去拼这些信息。只读不写。
"""
import os
import re

from . import config, entry, journal, naming, recurring
from .books import Chart, load_book
from .display import pad

STATE_NAME = "STATE.md"
RECENT_SHOWN = 3
WEEKDAY_CN = "一二三四五六日"
GROUPS = (("Assets", "资产（钱在哪、别人欠的）"), ("Liabilities", "负债（花呗、信用卡、欠别人的）"),
          ("Expenses", "支出"), ("Income", "收入"), ("Equity", "权益（期初、利润分配）"))


def state_lines():
    """STATE.md 里当前生效的内容（去掉 HTML 注释和开头的说明段）；没有文件或没有内容返回空列表。"""
    try:
        with open(os.path.join(config.ROOT, STATE_NAME), encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return []
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    lines = text.split("\n")
    start = next((i for i, line in enumerate(lines) if line.startswith("## ")), None)
    body = [line.rstrip() for line in (lines[start + 1:] if start is not None else lines[1:])]
    body = [line for line in body if line.strip()]
    return body if any(not line.startswith("#") for line in body) else []


def _mirrored(cfg, book):
    """这本账的往来科目 -> 对侧 "账本 科目"。"""
    out = {}
    for m in cfg.mirrors:
        (lb, la), (rb, ra) = m.sides()
        if lb == book:
            out[la] = f"{rb} {ra}"
        if rb == book:
            out[ra] = f"{lb} {la}"
    return out


def _print_accounts(cfg, book, entries):
    chart = Chart(entries)
    mirrored = _mirrored(cfg, book)
    print(f"\n===== {book}（{cfg.books[book].title}）可用科目 =====")
    print("  科目 · 币种 · 摘要开头 · 说明（只能用这里列出的；要新科目先在科目表 open）")
    for root, title in GROUPS:
        accounts = [a for a in chart.active if a == root or a.startswith(root + ":")]
        if not accounts:
            continue
        print(f"\n----- {title} -----")
        for acc in accounts:
            currencies = "/".join(chart.opens[acc].currencies or []) or "不限"
            head = " / ".join(naming.heads_of(book, acc))
            note = chart.note(acc)
            if acc in mirrored:
                note = f"【往来，对应 {mirrored[acc]}，用 pair 两本账一起录】{note}"
            print(f"  {pad(acc, 38)}{pad(currencies, 10)}{pad(head, 16)}{note}".rstrip())


def _print_recent(book):
    blocks = sorted(journal.book_blocks(book), key=lambda b: b.sort_key)
    txns = [b for b in blocks if entry.TXN_RE.search(b.text)][-RECENT_SHOWN:]
    if not txns:
        return
    print(f"\n----- {book}：最近 {len(txns)} 笔（写法照这个来）-----")
    for b in txns:
        print()
        for line in b.lines:
            print(f"  {line}")


def cmd_brief(book=None):
    cfg = config.load()
    books = [book] if book else list(cfg.books)
    now = entry.now_local()
    loaded = {}
    for b in books:
        entries, errors, _ = load_book(b)
        if errors:
            print(f"[FAIL] {b} 账本存在 {len(errors)} 个错误，请先运行 check 修复后再入账。")
            return 1
        loaded[b] = entries

    print("===== 现在 =====")
    print(f"  {now:%Y-%m-%d} 周{WEEKDAY_CN[now.weekday()]} {now:%H:%M}（{cfg.timezone}）")
    print("  用户没说日期就记今天；没报具体时间就不写 time 行。日期晚于今天、当天 time 晚于此刻会被拒绝。")

    print(f"\n===== 当前临时状态（{STATE_NAME}）=====")
    lines = state_lines()
    for line in lines:
        print(f"  {line}")
    if not lines:
        print("  （无进行中事项）")

    if cfg.recurring:
        print("\n===== 该补的周期分录 =====")
        todo = recurring.pending(cfg, loaded, now.date())
        if not todo:
            print("  （都记了）")
        for rule, days in todo:
            print(f"  {rule.book} · {rule.name}：{len(days)} 天没记（{'、'.join(d.isoformat() for d in days)}）")
            how = "先跟用户确认这几天确实发生了，再逐笔入账" if rule.confirm else "按约定直接逐笔补记，不用问用户"
            print(f"    {how}" + ("，分录如下：" if rule.entry else "。"))
            for d in days if rule.entry else []:
                print()
                for line in recurring.render(rule, d).split("\n"):
                    print(f"    {line}")

    for b in books:
        _print_accounts(cfg, b, loaded[b])

    if cfg.naming is not None:
        print("\n===== 对方与摘要怎么写 =====")
        for b in books:
            naming.print_patterns(cfg.naming, b)
        naming.print_general(cfg.naming)

    print("\n===== 写法范例 =====")
    for b in books:
        _print_recent(b)

    print("\n===== 怎么录 =====")
    print("  普通一笔：python3 scripts/ledger.py add <账本> <<'EOF' …分录… EOF（一次一笔）")
    if cfg.mirrors:
        print("  账本之间的往来：python3 scripts/ledger.py pair <<'EOF'，[账本名] 一段一笔、共两段，两本账一起录")
    print("  记错了：ledger.py find <账本> <关键词> 查编号，再 amend / void；不要手改序时簿")
    print("  录完：python3 scripts/ledger.py check 通过后提交")
    return 0
