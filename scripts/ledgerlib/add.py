"""入账：追加一笔分录到序时簿，校验失败自动回滚。"""
import contextlib
import os
import sys

from . import config
from .books import MAX_SHOWN_ERRORS, _describe, load_book
from .entry import count_transactions, first_date, future_error, has_active_include, inject_time, touched_accounts
from .query import print_summary

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
    import msvcrt

LOCK_NAME = ".ledger.lock"


@contextlib.contextmanager
def _book_lock():
    """进程间互斥：避免两个会话并发追加时，一方的回滚覆写吃掉另一方的分录。"""
    path = os.path.join(config.ROOT, LOCK_NAME)
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        if fcntl:
            fcntl.flock(fd, fcntl.LOCK_EX)
        else:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
        yield
    finally:
        if fcntl:
            fcntl.flock(fd, fcntl.LOCK_UN)
        else:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        os.close(fd)


def _read_stdin():
    """按 UTF-8 读 stdin（兼容 Windows 管道带 BOM 或走本地编码的情况）。"""
    raw = sys.stdin.buffer.read()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        import locale

        return raw.decode(locale.getpreferredencoding(False))


def cmd_add(book, stream=None):
    block = (stream.read() if stream is not None else _read_stdin())
    block = block.replace("\r\n", "\n").strip("\n")
    if not block.strip():
        print("[FAIL] 没有读到分录：请通过 stdin 传入一笔分录（本次未写入）。")
        return 1
    err = future_error(block)
    if err:
        print(f"[FAIL] {err}")
        return 1
    block = inject_time(block)
    ymd = first_date(block)
    if not ymd:
        print("[FAIL] 分录首行必须是 YYYY-MM-DD 日期")
        return 1
    if count_transactions(block) > 1:
        print("[FAIL] 检测到多笔交易：一次 add 只录一笔，请分多次提交（本次未写入）。")
        return 1
    ym = f"{ymd[0]}-{ymd[1]}"

    with _book_lock():
        rc = _write(book, ym, block)
    if rc == 0:
        _mirror_hint(book, block)
    return rc


def _write(book, ym, block):
    main_path, jdir, jdir_rel = config.book_paths(book)
    title = config.get_book(book).title
    os.makedirs(jdir, exist_ok=True)
    jpath = os.path.join(jdir, f"{ym}.beancount")
    jrel = f"{jdir_rel}/{ym}.beancount"
    # include 路径相对入口文件所在目录（beancount 的解析规则），入口不在根目录时也能找到
    inc_rel = os.path.relpath(jpath, os.path.dirname(main_path)).replace(os.sep, "/")
    include_line = f'include "{inc_rel}"'

    with open(main_path, encoding="utf-8") as f:
        main_orig = f.read()

    # 记下是否由本次调用新建月份文件：回滚时要连文件一起删掉，不留空壳
    created_journal = not os.path.exists(jpath)
    if created_journal:
        with open(jpath, "w", encoding="utf-8") as f:
            f.write(f"; {title} · {ym} 流水\n\n")

    added_include = not has_active_include(main_orig, inc_rel)
    if added_include:
        main_new = main_orig if main_orig.endswith("\n") else main_orig + "\n"
        main_new += include_line + "\n"
        with open(main_path, "w", encoding="utf-8") as f:
            f.write(main_new)

    with open(jpath, encoding="utf-8") as f:
        j_orig = f.read()
    with open(jpath, "a", encoding="utf-8") as f:
        # 分录之间空一行，序时簿才翻得动、diff 才看得清
        if j_orig and not j_orig.endswith("\n\n"):
            f.write("\n" if j_orig.endswith("\n") else "\n\n")
        f.write(block + "\n")

    def rollback():
        if created_journal:
            os.remove(jpath)
        else:
            with open(jpath, "w", encoding="utf-8") as fh:
                fh.write(j_orig)
        if added_include:
            with open(main_path, "w", encoding="utf-8") as fh:
                fh.write(main_orig)

    try:
        entries, errors, _ = load_book(book)
    except Exception as ex:
        # 校验过程崩溃（如依赖未安装）：同样回滚，避免留坏账
        rollback()
        print(f"[FAIL] 校验过程异常，已回滚：{ex}")
        return 1
    if errors:
        # 校验失败：回滚月份文件与 include，保证账本永远处于可用状态
        rollback()
        print("[FAIL] 未通过校验，已回滚，账本未被改动：")
        for e in errors[:MAX_SHOWN_ERRORS]:
            print("   -", _describe(e))
        if len(errors) > MAX_SHOWN_ERRORS:
            print(f"   ...另有 {len(errors) - MAX_SHOWN_ERRORS} 个错误未显示")
        return 1

    print(f"[OK] 已入账：{book} -> {jrel}")
    # 复用校验时已加载的 entries，不再为出汇总重新解析一遍账本
    print_summary(book, ym, entries=entries)
    return 0


def _mirror_hint(book, block):
    """本笔触及跨账本往来科目时，提醒去另一本账登记镜像分录——只记单边 check 是发现不了的。"""
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
                  f"请在 {ob} 账登记对应分录，然后运行 reconcile 确认两侧相加为 0。")
