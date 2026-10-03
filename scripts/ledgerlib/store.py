"""序时簿写盘：进程间互斥、写入后整本校验、不通过就原样还原。

入账（add）、更正与作废（edit）都经这里落盘，保证“坏账绝不留在磁盘上”只有一处实现。
本模块不关心分录内容，只管把一组文件改动作为一个整体提交或撤销。
"""
import contextlib
import os

from . import config
from .books import _print_error_lines, load_book

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
    import msvcrt

LOCK_NAME = ".ledger.lock"


@contextlib.contextmanager
def book_lock():
    """进程间互斥：避免两个会话并发写入时，一方的回滚覆写吃掉另一方的分录。"""
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


def _read_bytes(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None


def _put(path, data):
    if data is None:
        if os.path.exists(path):
            os.remove(path)
        return
    with open(path, "wb") as f:
        f.write(data)


def _encode(text, original):
    """文本转成要写盘的字节，换行符沿用文件原有的（新文件用系统默认）。

    读文件时 CRLF 已统一成 LF 处理；不换回去的话，Windows 上录一笔账整份文件的换行符都会变。
    """
    if original is None:
        newline = os.linesep
    else:
        newline = "\r\n" if b"\r\n" in original else "\n"
    if newline != "\n":
        text = text.replace("\n", newline)
    return text.encode("utf-8")


def commit(book, changes):
    """把 {绝对路径: 新文本 | None（删除文件）} 写盘，再整本校验。

    返回 (entries, rollback)。校验不过、或校验过程崩溃（如依赖未安装）时已经原样还原并打印
    原因，entries 为 None；通过时调用方若还有别的检查不满意，可以再调 rollback() 撤销。
    还原按字节进行：原来不存在的文件会被删掉，不留空壳。
    """
    originals = {p: _read_bytes(p) for p in changes}

    def rollback():
        for p, data in originals.items():
            _put(p, data)

    try:
        for p, text in changes.items():
            _put(p, None if text is None else _encode(text, originals[p]))
        entries, errors, _ = load_book(book)
    except Exception as ex:
        rollback()
        print(f"[FAIL] 校验过程异常，已回滚：{ex}")
        return None, rollback
    if errors:
        rollback()
        print("[FAIL] 未通过校验，已回滚，账本未被改动：")
        _print_error_lines(errors)
        return None, rollback
    return entries, rollback
