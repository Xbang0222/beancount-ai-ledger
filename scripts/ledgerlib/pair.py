"""往来两边一起录：同一笔业务在两本账各记一笔，要么都记上，要么都不动。

beancount 只校验单本账内部平衡，账本之间的往来只记了一边它发现不了。pair 一次读入两笔分录，
各自过入账前检查，一起写盘、逐本校验，再核对每对镜像科目的差额没有被这次录入改变。

输入写法（一段一个账本，方括号里是 ledger.toml 的账本名）：

    [personal]
    2026-09-23 * "商店" "代垫商店采购款-某供应商（股东往来）"
      Assets:Receivable:Shop  50.00 CNY
      Assets:Wechat
    [shop]
    2026-09-23 * "某供应商" "主营业务成本-采购"
      Expenses:COGS  50.00 CNY
      Liabilities:OwnerLoan
"""
import re
import textwrap
from decimal import Decimal

from . import config, entry
from .add import append_plan, find_duplicate, precheck, read_block, reject_duplicate
from .books import balances, load_book
from .config import EPSILON
from .entry import count_transactions, inject_time, touched_accounts
from .reconcile import mirror_diffs
from .store import book_lock, commit_many

SECTION_RE = re.compile(r"^\[([A-Za-z][A-Za-z0-9_-]*)\]\s*$")

USAGE = """\
pair 的输入是两段，每段第一行是方括号里的账本名，下面是这本账的一笔分录：

python3 scripts/ledger.py pair <<'EOF'
[{a}]
<{a} 账的分录>
[{b}]
<{b} 账的分录>
EOF"""


def _sections(text):
    """拆成 [(账本名, 分录文本)]；第一段之前有内容、或没有任何段落标记时返回 None。"""
    out = []
    for line in text.split("\n"):
        m = SECTION_RE.match(line.strip())
        if m:
            out.append([m.group(1), []])
        elif out:
            out[-1][1].append(line)
        elif line.strip():
            return None
    # 整段带着缩进贴进来的（照着示例抄时常见）先去掉公共缩进，日期才在行首
    return [(book, textwrap.dedent("\n".join(lines)).strip("\n")) for book, lines in out]


def _usage(books):
    a, b = (list(books) + ["账本甲", "账本乙"])[:2]
    return USAGE.format(a=a, b=b)


def _mirror_accounts(cfg, book, other):
    """book 这一侧、与 other 账本成对的镜像科目：{科目: (对侧科目, 币种)}。"""
    out = {}
    for m in cfg.mirrors:
        (lb, la), (rb, ra) = m.sides()
        if (lb, rb) == (book, other):
            out[la] = (ra, m.currency)
        if (rb, lb) == (book, other):
            out[ra] = (la, m.currency)
    return out


def cmd_pair(stream=None, path=None, allow_duplicate=False):
    text = read_block(stream, path)
    if text is None:
        return 1
    cfg = config.load()
    sections = _sections(text)
    if not sections or len(sections) != 2 or sections[0][0] == sections[1][0]:
        print("[FAIL] pair 要恰好两段、分属两本不同的账（本次未写入）。\n" + _usage(cfg.books))
        return 1
    for book, _ in sections:
        config.get_book(book)  # 未声明的账本名在这里报错并列出可选项

    now = entry.now_local()  # 两笔注入同一个录入时刻
    plans = []
    for (book, block), (other, _) in zip(sections, reversed(sections)):
        if not block.strip() or count_transactions(block) != 1:
            print(f"[FAIL] [{book}] 这一段要恰好一笔交易（本次未写入）。\n" + _usage(cfg.books))
            return 1
        ymd = precheck(block, book)
        if ymd is None:
            print(f"   （出错的是 [{book}] 这一段；两本账都未写入）")
            return 1
        mine = _mirror_accounts(cfg, book, other)
        if not touched_accounts(block, mine):
            want = "、".join(mine) or "（ledger.toml 没有给这两本账配 [[mirrors]]）"
            print(f"[FAIL] [{book}] 这一段没有用到与 {other} 账成对的往来科目（{want}），不是往来分录（本次未写入）。"
                  "不涉及往来的账用 add 各记各的。")
            return 1
        plans.append((book, f"{ymd[0]}-{ymd[1]}", inject_time(block, now)))

    eps = Decimal(EPSILON)
    with book_lock():
        before = {}
        for book, _, _ in plans:
            entries, errors, _ = load_book(book)
            before[book] = balances(entries)  # 账本本身有错时，下面的整本校验会报出来并回滚
        placed, changes_by_book = {}, {}
        for book, ym, block in plans:
            changes, jpath, jrel, lineno = append_plan(book, ym, block)
            changes_by_book[book] = changes
            placed[book] = (jpath, jrel, lineno, block)
        loaded, rollback = commit_many(changes_by_book)
        if loaded is None:
            return 1
        if not allow_duplicate:
            for book, (jpath, _, lineno, block) in placed.items():
                dup = find_duplicate(loaded[book], jpath, lineno, lineno + block.count("\n"))
                if dup is not None:
                    return reject_duplicate(dup, rollback)
        after = {book: balances(entries) for book, entries in loaded.items()}
        was = dict(mirror_diffs(cfg, before))
        moved = [(m, d - was[m]) for m, d in mirror_diffs(cfg, after) if abs(d - was[m]) >= eps]
        if moved:
            rollback()
            print("[FAIL] 两边的往来金额对不上，已回滚，两本账都未改动：")
            for m, delta in moved:
                (lb, la), (rb, ra) = m.sides()
                print(f"   - {m.name}（{m.currency}）：{lb} 账 {la} 与 {rb} 账 {ra} 这次记的金额应当大小相同、"
                      f"方向相反（一边借、一边贷），现在相差 {delta:.2f}")
            return 1

    print("[OK] 两本账已一起入账，往来镜像前后一致：")
    for book, (_, jrel, _, _) in placed.items():
        print(f"   - {book} -> {jrel}")
    return 0
