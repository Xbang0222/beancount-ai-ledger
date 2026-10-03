"""backup：把整个账套打成一个压缩包。

给不用 Git 的环境用：豆包这类云电脑每次会话都会重置，账本得存到用户的云盘或网盘里。
一个压缩包就是一份完整的账套（账本、规则、脚本），解压后装好依赖就能接着记。

先校验再打包：有错误的账本不生成压缩包，免得拿坏的那份盖掉云盘里好的那份。
"""
import os
import zipfile

from . import config
from .books import load_book, print_errors, transactions

# 压缩包里的顶层目录名：解压出来就是一个叫 ledger 的账套目录
ARCHIVE_ROOT = "ledger"
DEFAULT_DIR = "backups"

# 环境与缓存可以重建，原始账单含敏感信息，旧备份不必套娃
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".fava",
             ".idea", ".vscode", "exports", "账单导出", DEFAULT_DIR}
SKIP_NAMES = {".ledger.lock", ".DS_Store", "Thumbs.db"}
SKIP_SUFFIXES = (".zip", ".csv", ".xlsx", ".pyc", ".tmp", ".backup", ".swp", "~")


def _files(root, out_dir):
    """账套里要打包的文件，返回排好序的 [(绝对路径, 相对路径)]。"""
    out_real = os.path.realpath(out_dir)
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS
                             and os.path.realpath(os.path.join(dirpath, d)) != out_real)
        for name in sorted(filenames):
            if name in SKIP_NAMES or name.endswith(SKIP_SUFFIXES):
                continue
            path = os.path.join(dirpath, name)
            found.append((path, os.path.relpath(path, root).replace(os.sep, "/")))
    return found


def _last_line(entries):
    """一本账的交易笔数与最后一笔的说明；pad 生成的补差交易（标志 P）不算用户记的账。"""
    from .query import _time_key

    txns = [t for t in transactions(entries) if t.flag != "P"]
    if not txns:
        return "还没有交易"
    _, last = max(enumerate(txns), key=lambda it: (it[1].date, _time_key(it[1]), it[0]))
    parts = [str(last.date), _time_key(last), last.payee or "", last.narration or ""]
    return f"交易 {len(txns)} 笔，最后一笔 " + " ".join(p for p in parts if p)


def cmd_backup(out_dir=None, now=None):
    cfg = config.load()
    ok, lines = True, []
    for book in cfg.books:
        entries, errors, _ = load_book(book)
        if errors:
            ok = False
            print_errors(book, errors)
        else:
            lines.append(f"  {book}：{_last_line(entries)}")
    if not ok:
        print("[FAIL] 账本有错误，没有生成压缩包。先运行 check 修好再备份。")
        return 1

    if now is None:
        from .entry import now_local

        now = now_local()
    out_dir = os.path.abspath(out_dir or os.path.join(config.ROOT, DEFAULT_DIR))
    files = _files(config.ROOT, out_dir)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"ledger-backup-{now:%Y%m%d-%H%M%S}.zip")
    tmp = path + ".part"
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            for src, rel in files:
                z.write(src, f"{ARCHIVE_ROOT}/{rel}")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    try:
        shown = os.path.relpath(path, config.ROOT).replace(os.sep, "/")
    except ValueError:  # Windows 上跨盘符无法取相对路径
        shown = path
    if shown.startswith(".."):
        shown = path
    print(f"[OK] 已备份：{shown}（{len(files)} 个文件，{os.path.getsize(path) / 1024:.1f} KB）")
    for line in lines:
        print(line)
    print(f"把这个压缩包存到账本所有者的云盘或网盘。下次开始时取最新的一份解压，得到 {ARCHIVE_ROOT}/ 目录，"
          "先核对上面的最后一笔，再接着记。")
    return 0
