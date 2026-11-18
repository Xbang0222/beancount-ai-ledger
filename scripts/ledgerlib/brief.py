"""入账前的一页现场信息：今天几号、当前临时状态、该补的周期分录、能用哪些科目、怎么写、标准范例。

把“读 STATE.md、查 rules、翻科目表、看范例”合成一条命令，记账的人（多半是 AI）照着输出写分录，
不用靠记性去拼这些信息。不改账本；本仓库未启用提交检查时顺带启用。

范例取自 rules/daily.md 的「分录范例」一节，不取最近入账的分录：最近的分录一旦写错，
记账的人会照着继续写错，错误随范例一路传下去。范例由账套所有者维护，文档测试保证其符合写法规则。
"""
import os
import re

from . import config, entry, naming, recurring, rulebook
from .books import Chart, load_book
from .display import pad

STATE_NAME = "STATE.md"
EXAMPLES_TITLE = "分录范例"
WEEKDAY_CN = "一二三四五六日"
GROUPS = (("Assets", "资产（资金账户、应收款）"), ("Liabilities", "负债（消费信贷、应付款）"),
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
            head = pad(head, 16)
            if not head.endswith(" "):          # 摘要开头超出栏宽时，与说明之间仍留出间隔
                head += "  "
            print(f"  {pad(acc, 38)}{pad(currencies, 10)}{head}{note}".rstrip())


def example_lines():
    """规则文档中「分录范例」一节的正文（去掉代码块围栏与末尾空行）；没有这一节返回 (路径, [])。"""
    rel = rulebook.ref("daily")
    try:
        with open(os.path.join(config.ROOT, *rel.split("/")), encoding="utf-8") as f:
            lines = f.read().split("\n")
    except OSError:
        return rel, []
    start = next((i for i, ln in enumerate(lines) if ln.startswith("## ") and EXAMPLES_TITLE in ln), None)
    if start is None:
        return rel, []
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    body = [ln.rstrip() for ln in lines[start + 1:end] if not ln.startswith("```")]
    while body and not body[0]:
        body.pop(0)
    while body and not body[-1]:
        body.pop()
    return rel, body


def _print_examples():
    rel, body = example_lines()
    print(f"\n===== 写法范例（{rel}「{EXAMPLES_TITLE}」，写法以此为准）=====")
    if not body:
        print(f"  （{rel} 中没有「{EXAMPLES_TITLE}」一节；写法以上方规则为准）")
    for line in body:
        print(f"  {line}".rstrip())
    print("\n  最近入账的分录不作写法参照，其中可能有未被校验拦下的错误写法；"
          "核对是否重复入账用 ledger.py recent <账本>")


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

    from .doctor import ENABLED_NOTE, enable_hooks

    if enable_hooks():
        print(f"[OK] {ENABLED_NOTE}\n")
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
            print("  （无待补记）")
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
        print("\n===== 对方、摘要与 note 的写法 =====")
        for b in books:
            naming.print_patterns(cfg.naming, b)
        naming.print_general(cfg.naming)

    _print_examples()

    print("\n===== 操作命令 =====")
    print("  单本账入账：python3 scripts/ledger.py add <账本> <<'EOF' …分录… EOF（一次一笔）")
    if cfg.mirrors:
        print("  账本之间的往来：python3 scripts/ledger.py pair <<'EOF'，[账本名] 一段一笔、共两段，两本账同时入账")
    print("  归类或业务处理不确定：python3 scripts/ledger.py lookup <物品、商家或业务名>，按输出的科目和章节处理")
    print("  更正与作废：ledger.py find <账本> <关键词> 查编号，再 amend / void；不得手工编辑序时簿")
    print("  入账后：python3 scripts/ledger.py check 通过后提交")
    return 0
