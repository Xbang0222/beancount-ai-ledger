"""入账：追加一笔分录到序时簿，校验失败自动回滚。

写盘、整本校验、失败还原由 store 负责；这里只管分录从哪读、写到哪个月、算不算重复。
"""
import os
import sys

from . import config, journal
from .books import transactions
from .entry import (
    count_transactions,
    first_date,
    future_error,
    has_active_include,
    inject_time,
    touched_accounts,
    validate,
)
from .query import print_summary
from .store import book_lock, commit


def _decode(raw):
    """按 UTF-8 解码（兼容带 BOM 或走本地编码的 Windows 管道与文件）。"""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        import locale

        return raw.decode(locale.getpreferredencoding(False))


def read_block(stream=None, path=None):
    """从文件或 stdin 读入一笔分录的文本；读不到时打印原因并返回 None。"""
    if path is not None:
        try:
            with open(path, "rb") as f:
                block = _decode(f.read())
        except OSError as ex:
            print(f"[FAIL] 读不了分录文件 {path}：{ex.strerror or ex}（本次未写入）。")
            return None
    else:
        block = stream.read() if stream is not None else _decode(sys.stdin.buffer.read())
    block = block.replace("\r\n", "\n").strip("\n")
    if not block.strip():
        print("[FAIL] 没有读到分录：请从 stdin 或 --file 传入一笔分录（本次未写入）。")
        return None
    return block


def precheck(block):
    """写盘前的文本级检查；有问题打印原因并返回 None，否则返回 (年, 月)。"""
    err = future_error(block) or validate(block)
    if err:
        print(f"[FAIL] {err}")
        return None
    ymd = first_date(block)
    if not ymd:
        print("[FAIL] 分录首行必须是 YYYY-MM-DD 日期")
        return None
    if count_transactions(block) > 1:
        print("[FAIL] 检测到多笔交易：一次只录一笔，请分多次提交（本次未写入）。")
        return None
    return ymd


def cmd_add(book, stream=None, path=None, allow_duplicate=False):
    block = read_block(stream, path)
    if block is None:
        return 1
    ymd = precheck(block)
    if ymd is None:
        return 1
    block = inject_time(block)
    ym = f"{ymd[0]}-{ymd[1]}"

    with book_lock():
        rc = _write(book, ym, block, allow_duplicate)
    if rc == 0:
        mirror_hint(book, block)
    return rc


def append_plan(book, ym, block, changes=None):
    """算出把 block 写进 ym 月序时簿要写的文件内容，并入 changes。

    序时簿本来就按日期时间排好时，block 插到它该在的位置（补记较早的账也不打乱顺序）；
    否则追加到末尾，不替用户重排已有分录——那是 fmt 的事。
    返回 (changes, 序时簿绝对路径, 序时簿相对路径, block 首行落在文件的第几行)。
    changes 里已有同一文件的待写内容时在它的基础上写（更正时先删后加）。
    """
    changes = {} if changes is None else changes
    main_path, jdir, jdir_rel = config.book_paths(book)
    title = config.get_book(book).title
    os.makedirs(jdir, exist_ok=True)
    jpath = os.path.join(jdir, f"{ym}.beancount")
    jrel = f"{jdir_rel}/{ym}.beancount"
    # include 路径相对入口文件所在目录（beancount 的解析规则），入口不在根目录时也能找到
    inc_rel = os.path.relpath(jpath, os.path.dirname(main_path)).replace(os.sep, "/")

    with open(main_path, encoding="utf-8") as f:
        main_text = f.read()
    if not has_active_include(main_text, inc_rel):
        if not main_text.endswith("\n"):
            main_text += "\n"
        changes[main_path] = main_text + f'include "{inc_rel}"\n'

    if jpath in changes:
        j_text = changes[jpath]
    elif os.path.exists(jpath):
        with open(jpath, encoding="utf-8") as f:
            j_text = f.read()
    else:
        j_text = f"; {title} · {ym} 流水\n\n"
    placed = journal.insert_sorted(j_text, block)
    if placed is not None:
        changes[jpath], lineno = placed
        return changes, jpath, jrel, lineno
    # 分录之间空一行，序时簿才翻得动、diff 才看得清
    if j_text and not j_text.endswith("\n\n"):
        j_text += "\n" if j_text.endswith("\n") else "\n\n"
    lineno = j_text.count("\n") + 1
    changes[jpath] = j_text + block + "\n"
    return changes, jpath, jrel, lineno


def _signature(txn):
    """判重口径：日期、对方、摘要、各科目金额都相同（time、标签、排版不算）。"""
    # 金额按数值比：18、18.0、18.00 是同一个数（Decimal 相等且哈希相同）
    legs = sorted((p.account, p.units.number, p.units.currency)
                  for p in txn.postings if p.units is not None)
    return (txn.date, txn.payee, txn.narration, tuple(legs))


def find_duplicate(entries, path, first_line, last_line):
    """刚写入的那笔（位于 path 的 first_line..last_line 行）若与账上另一笔内容相同，返回那一笔。"""
    real = os.path.realpath(path)
    txns = transactions(entries)

    def _mine(t):
        meta = t.meta or {}
        return (os.path.realpath(meta.get("filename") or "") == real
                and first_line <= (meta.get("lineno") or 0) <= last_line)

    new = next((t for t in txns if _mine(t)), None)
    if new is None:
        return None
    sig = _signature(new)
    return next((t for t in txns if t is not new and _signature(t) == sig), None)


def reject_duplicate(dup, rollback):
    rollback()
    time_str = (dup.meta or {}).get("time", "")
    print("[FAIL] 账上已有一笔内容相同的分录，疑似重复入账，已回滚：")
    print(f"   - {dup.date} {time_str} {dup.payee or ''} {dup.narration or ''}".rstrip())
    print("   确实是两笔（比如同一天同一家店买了两次同样的东西）就加 --allow-duplicate 重录。")
    return 1


def _write(book, ym, block, allow_duplicate=False):
    changes, jpath, jrel, lineno = append_plan(book, ym, block)
    entries, rollback = commit(book, changes)
    if entries is None:
        return 1
    if not allow_duplicate:
        dup = find_duplicate(entries, jpath, lineno, lineno + block.count("\n"))
        if dup is not None:
            return reject_duplicate(dup, rollback)

    if count_transactions(block) == 0:
        # 余额断言、价格等非交易指令：能走到这里说明校验通过（断言不符会在上面回滚并报出差额）
        print(f"[OK] 已写入并通过校验：{book} -> {jrel}")
        return 0
    print(f"[OK] 已入账：{book} -> {jrel}")
    # 复用校验时已加载的 entries，不再为出汇总重新解析一遍账本
    print_summary(book, ym, entries=entries)
    return 0


def mirror_hint(book, block, action="登记"):
    """本笔触及跨账本往来科目时，提醒去另一本账处理镜像分录——只动单边 check 是发现不了的。"""
    mine = {}
    for m in config.load().mirrors:
        (lb, la), (rb, ra) = m.sides()
        if lb == book:
            mine.setdefault(la, []).append((rb, ra, m.currency))
        if rb == book:
            mine.setdefault(ra, []).append((lb, la, m.currency))
    for acc in touched_accounts(block, mine):
        for ob, oacc, cur in mine[acc]:
            print(f"\n[提示] 本笔触及往来科目 {acc}（{cur}），其镜像是 {ob} 账的 {oacc}："
                  f"请在 {ob} 账{action}对应分录，然后运行 reconcile 确认两侧相加为 0。")
