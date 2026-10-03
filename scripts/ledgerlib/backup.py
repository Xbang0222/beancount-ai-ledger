"""backup：把整个账套打成一个压缩包。

给没有远程仓库的环境用：豆包这类云电脑每次会话都会重置，账本得存到用户的云盘或网盘里。
一个压缩包就是一份完整的账套（账本、规则、脚本）；账套目录是 Git 仓库时连提交历史一起带上，
解压出来仍然是一个能接着提交的仓库，用户不需要 GitHub 账号。

先校验再打包：有错误的账本不生成压缩包，免得拿坏的那份盖掉云盘里好的那份。
"""
import os
import shutil
import subprocess
import zipfile

from . import config
from .books import load_book, print_errors
from .query import last_summary

# 压缩包里的顶层目录名：解压出来就是一个叫 ledger 的账套目录
ARCHIVE_ROOT = "ledger"
DEFAULT_DIR = "backups"

# 环境与缓存可以重建，原始账单含敏感信息，旧备份不必套娃
SKIP_DIRS = {".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache", ".fava",
             ".idea", ".vscode", "exports", "账单导出", DEFAULT_DIR}
SKIP_NAMES = {".ledger.lock", ".DS_Store", "Thumbs.db"}
SKIP_SUFFIXES = (".zip", ".csv", ".xlsx", ".pyc", ".tmp", ".backup", ".swp", "~")


def _files(root, out_dir):
    """账套里要打包的文件（和 .git 里的空目录），返回排好序的 [(绝对路径, 相对路径)]。"""
    out_real = os.path.realpath(out_dir)
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        in_git = ".git" in os.path.relpath(dirpath, root).split(os.sep)
        dirnames[:] = sorted(d for d in dirnames if (in_git or d not in SKIP_DIRS)
                             and os.path.realpath(os.path.join(dirpath, d)) != out_real)
        if in_git and not dirnames and not filenames:
            # .git 里的空目录（refs/tags、整理后的 refs/heads）也得在，缺了 Git 不认这个仓库
            found.append((dirpath, os.path.relpath(dirpath, root).replace(os.sep, "/")))
        for name in sorted(filenames):
            # .git 里的文件原样全收：对象、引用的文件名不受上面的排除规则约束
            if not in_git and (name in SKIP_NAMES or name.endswith(SKIP_SUFFIXES)):
                continue
            path = os.path.join(dirpath, name)
            found.append((path, os.path.relpath(path, root).replace(os.sep, "/")))
    return found


def _git(root, *args):
    """在账套目录跑 git，返回 (退出码, 标准输出)；没装 git 返回 (None, "")。"""
    if not shutil.which("git"):
        return None, ""
    try:
        p = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None, ""
    return p.returncode, p.stdout.strip()


def _history(root):
    """账套目录自己就是 Git 仓库时返回 (提交次数, 未提交的文件数)，否则返回 None。

    只认 .git 就在账套根目录的情况：账套只是别的仓库里的一个子目录时，历史不归它管。
    """
    if not os.path.exists(os.path.join(root, ".git")):
        return None
    rc, count = _git(root, "rev-list", "--count", "HEAD")
    commits = int(count) if rc == 0 and count.isdigit() else 0
    rc, status = _git(root, "status", "--porcelain")
    if rc != 0:
        return None
    # 松散对象攒多了会让压缩包变大；达到 Git 自己的阈值才真的整理，平时几乎不花时间
    _git(root, "gc", "--auto", "--quiet")
    return commits, len([line for line in status.splitlines() if line.strip()])


def cmd_backup(out_dir=None, now=None):
    cfg = config.load()
    ok, lines = True, []
    for book in cfg.books:
        entries, errors, _ = load_book(book)
        if errors:
            ok = False
            print_errors(book, errors)
        else:
            lines.append(f"  {book}：{last_summary(entries)}")
    if not ok:
        print("[FAIL] 账本有错误，没有生成压缩包。先运行 check 修好再备份。")
        return 1

    if now is None:
        from .entry import now_local

        now = now_local()
    out_dir = os.path.abspath(out_dir or os.path.join(config.ROOT, DEFAULT_DIR))
    history = _history(config.ROOT)
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
    if history:
        commits, dirty = history
        print(f"  含 Git 历史：{commits} 次提交")
        if dirty:
            print(f"[WARN] 有 {dirty} 个文件的改动还没提交：压缩包里有这些改动，但提交历史里没有。"
                  "先 git add -A && git commit 再备份更稳妥。")
    print(f"把这个压缩包存到账本所有者的云盘或网盘。下次开始时取最新的一份解压，得到 {ARCHIVE_ROOT}/ 目录，"
          "先核对上面的最后一笔，再接着记。")
    return 0
