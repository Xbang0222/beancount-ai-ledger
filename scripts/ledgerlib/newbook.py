"""新建账本：生成入口文件、科目表、期初余额模板，并登记到 ledger.toml。

  python3 scripts/ledger.py new-book personal                                  # 个人账
  python3 scripts/ledger.py new-book shop --template business --link personal   # 店铺账，与个人账建立往来
  python3 scripts/ledger.py new-book family --template minimal --title "家庭共同账" --no-consolidate

--link 会在两本账各开一对往来科目，并在 ledger.toml 里登记两对 [[mirrors]]；此后两本账之间的
垫付/代收按双边镜像登记，reconcile 自动核对两侧是否相加为 0。

整个过程是事务性的：任何一步校验失败，都会删除新建的文件、还原被修改的文件。
已存在的文件一律不覆盖。
"""
import json
import os
import re
from datetime import date

from . import config
from .books import load_book, print_errors

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
TEMPLATES = ("personal", "business", "minimal")
DEFAULT_OPEN_DATE = "1970-01-01"
DEFAULT_TITLES = {"personal": "个人账本", "business": "经营账本", "minimal": "账本"}
DEFAULT_TIMEZONE = "Asia/Shanghai"
DEFAULT_CURRENCY = "CNY"
CURRENCY_NAMES = {"CNY": "人民币", "USD": "美元", "HKD": "港币", "EUR": "欧元", "JPY": "日元"}

CONFIG_HEADER = f"""\
# ============================================================
# 账套配置：有哪些账本、账本之间的往来怎么对账
# 说明见 README「配置 ledger.toml」。新增账本请用：
#   python3 scripts/ledger.py new-book <名称> [--template personal|business|minimal] [--link <已有账本>]
# ============================================================

[ledger]
{'timezone = "' + DEFAULT_TIMEZONE + '"':<32}# 记账时区：自动注入的 time、未来日期/时间校验都按它
{{base_line}}# 本位币：networth 折算合计的目标币种
"""


class _Changes:
    """记录本次新建/修改过的文件，失败时整体还原。"""

    def __init__(self):
        self.created = []
        self.created_dirs = []
        self.modified = {}

    def mkdirs(self, path):
        missing = []
        while path and not os.path.exists(path):
            missing.append(path)
            path = os.path.dirname(path)
        for d in reversed(missing):
            os.mkdir(d)
            self.created_dirs.append(d)

    def create(self, path, text):
        if os.path.exists(path):
            raise FileExistsError(path)
        self.mkdirs(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        self.created.append(path)

    def append(self, path, text):
        if path not in self.modified and path not in self.created:
            with open(path, encoding="utf-8") as f:
                self.modified[path] = f.read()
        with open(path, encoding="utf-8") as f:
            current = f.read()
        with open(path, "a", encoding="utf-8") as f:
            if current and not current.endswith("\n"):
                f.write("\n")
            f.write(text)

    def rollback(self):
        for p in reversed(self.created):
            if os.path.exists(p):
                os.remove(p)
        for d in reversed(self.created_dirs):
            try:
                os.rmdir(d)
            except OSError:
                pass
        for p, text in self.modified.items():
            with open(p, "w", encoding="utf-8") as f:
                f.write(text)


def camel(name):
    """账本名转科目名片段：shop → Shop，my-shop → MyShop。"""
    return "".join(part[:1].upper() + part[1:] for part in re.split(r"[-_]", name) if part)


def _toml_str(s):
    return json.dumps(s, ensure_ascii=False)


_OPEN_LINE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} open \S+(?: [A-Z][\w',.-]*)?) *; ?(.*)$")
COMMENT_COLUMN = 50


def _render(template_name, **values):
    with open(os.path.join(TEMPLATES_DIR, template_name), encoding="utf-8") as f:
        text = f.read()
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return _align_comments(text)


def _align_comments(text):
    """占位符替换后长度变了，把 open 行的行尾注释重新对齐到同一列。"""
    out = []
    for line in text.split("\n"):
        m = _OPEN_LINE_RE.match(line)
        out.append(f"{m.group(1).ljust(COMMENT_COLUMN - 1)} ; {m.group(2)}" if m else line)
    return "\n".join(out)


def _opened_accounts(book):
    from beancount.core.data import Open

    entries, _, _ = load_book(book)
    return {e.account for e in entries if isinstance(e, Open)}


def _fail(msg):
    print(f"[FAIL] {msg}")
    return 1


def cmd_new_book(name, template="personal", title=None, kind=None, link=None, open_date=None,
                 consolidate=True):
    root = config.ROOT
    if not config.BOOK_NAME_RE.match(name):
        return _fail(f"账本名 {name!r} 不合法：只能用小写字母开头的小写字母、数字、- 和 _（如 personal、shop、family）")
    if template not in TEMPLATES:
        return _fail(f"模板只能是 {' / '.join(TEMPLATES)}")
    kind = kind or ("business" if template == "business" else "personal")
    title = title or DEFAULT_TITLES[template]
    if any(c in title for c in '"\\\n'):
        return _fail("标题里不能有双引号、反斜杠或换行")
    open_date = open_date or DEFAULT_OPEN_DATE
    try:
        date.fromisoformat(open_date)
    except ValueError:
        return _fail(f"--open-date 应为 YYYY-MM-DD，收到：{open_date!r}")

    cfg_path = config.config_path()
    cfg = config.load() if os.path.exists(cfg_path) else None
    if cfg and name in cfg.books:
        return _fail(f"ledger.toml 里已经有账本 {name}")
    if link:
        if cfg is None or link not in cfg.books:
            declared = " / ".join(cfg.books) if cfg else "（还没有任何账本）"
            return _fail(f"--link 的账本 {link!r} 不存在；已声明：{declared}")
        if link == name:
            return _fail("--link 不能指向自己")
    base = cfg.base_currency if cfg else DEFAULT_CURRENCY

    main_rel = f"{name}.beancount"
    for rel in (main_rel, name):
        if os.path.exists(os.path.join(root, rel)):
            return _fail(f"{rel} 已存在，不会覆盖；换个账本名，或先手动处理这个文件/目录")

    owner_accounts = set()
    if link:
        owner_entries, owner_errors, _ = load_book(link)
        if owner_errors:
            print_errors(link, owner_errors)
            return _fail(f"{link} 账本本身有错误，先 check 修复再新建关联账本")
        owner_accounts = _opened_accounts(link)

    ch = _Changes()
    notes = []
    try:
        _ensure_common(ch, base, notes)
        ch.create(os.path.join(root, main_rel), _render(
            "main.beancount", TITLE=title, NAME=name, MAIN=main_rel, CURRENCY=base))
        accounts_text = _render(f"{template}.beancount", TITLE=title, OPEN_DATE=open_date, CURRENCY=base)
        ch.create(os.path.join(root, name, "accounts.beancount"), accounts_text)
        ch.create(os.path.join(root, name, "opening.beancount"), _render(
            "opening.beancount", TITLE=title, CURRENCY=base))
        ch.mkdirs(os.path.join(root, name, "journal"))
        notes += [f"新建  {main_rel}", f"新建  {name}/accounts.beancount", f"新建  {name}/opening.beancount"]

        toml_text = f"\n[books.{name}]\ntitle = {_toml_str(title)}\nkind = \"{kind}\"\n"
        if not consolidate:
            toml_text += "consolidate = false            # 与他人共有：不并入 networth 合并资产负债\n"
        if link:
            toml_text += _link(ch, cfg, name, title, link, base, open_date, owner_accounts, notes)
        if cfg is None:
            ch.create(cfg_path, CONFIG_HEADER.replace("{base_line}", f'base_currency = "{base}"'.ljust(32)) + toml_text)
            notes.append(f"新建  {config.CONFIG_NAME}")
        else:
            ch.append(cfg_path, toml_text)
            notes.append(f"修改  {config.CONFIG_NAME}（登记 [books.{name}]" + (" 与 2 对 [[mirrors]]）" if link else "）"))

        config.load()
        for book in (name, link) if link else (name,):
            entries, errors, _ = load_book(book)
            if errors:
                print_errors(book, errors)
                raise RuntimeError(f"{book} 账本校验未通过")
    except (Exception, KeyboardInterrupt) as ex:
        ch.rollback()
        return _fail(f"新建账本失败，已还原全部改动：{ex}")

    merged = "" if consolidate else "，不并入 networth"
    print(f"[OK] 已新建账本 {name}（{title}，kind = {kind}，模板 {template}{merged}）")
    for n in notes:
        print(f"  {n}")
    print("\n下一步：")
    print(f"  1. 按实际情况增删 {name}/accounts.beancount 里的科目（用不到的删掉，缺的照格式补上）")
    print(f"  2. 在 {name}/opening.beancount 登记期初余额")
    print("  3. 运行 python3 scripts/ledger.py check")
    step = 4
    if cfg is not None:  # 已有别的账本：要告诉 AI 这本账记什么
        print(f"  {step}. 在 CATEGORIES.md 第 3 节写清哪些业务记进 {name}，AI 记账时才分得清账本")
        step += 1
    if link:
        print(f"  {step}. {link} 与 {name} 之间的垫付/代收按双边镜像登记（CATEGORIES.md 第 4 节），记完跑 reconcile")
    return 0


def _ensure_common(ch, base, notes):
    """各账本共用的币种与价格文件；全新账套里还没有就生成一份。"""
    root = config.ROOT
    commodities = os.path.join(root, "common", "commodities.beancount")
    if not os.path.exists(commodities):
        name = CURRENCY_NAMES.get(base)
        meta = f'\n  name: "{name}"' if name else ""
        ch.create(commodities, "; 币种声明（各账本共用）；用到其他币种、基金代码时照格式追加\n\n"
                               f"1970-01-01 commodity {base}{meta}\n")
        notes.append("新建  common/commodities.beancount")
    prices = os.path.join(root, "common", "prices.beancount")
    if not os.path.exists(prices):
        ch.create(prices, _render("prices.beancount", CURRENCY=base))
        notes.append("新建  common/prices.beancount")


def _link(ch, cfg, name, title, link, base, open_date, owner_accounts, notes):
    """在两本账各开一对往来科目，返回要追加到 ledger.toml 的 [[mirrors]] 文本。"""
    root = config.ROOT
    owner = cfg.books[link]
    cap = camel(name)
    recv, pay = f"Assets:Receivable:{cap}", f"Liabilities:{cap}"

    # 所有者一侧：优先写进它的 accounts.beancount，找不到就写进入口文件
    owner_accounts_file = os.path.join(root, os.path.dirname(owner.journal), "accounts.beancount")
    if not os.path.exists(owner_accounts_file):
        owner_accounts_file = os.path.join(root, owner.main)
    def open_line(account, comment):
        return f"{open_date} open {account} {base}".ljust(COMMENT_COLUMN - 1) + f" ; {comment}"

    lines = []
    if recv not in owner_accounts:
        lines.append(open_line(recv, f"其他应收款－{title}（本人垫付/借给该账本、尚未收回的款项）"))
    if pay not in owner_accounts:
        lines.append(open_line(pay, f"其他应付款－{title}（本人代收/占用该账本的资金）"))
    if lines:
        ch.append(owner_accounts_file,
                  f"\n; —— 与{title}（{name} 账本）的往来：双边镜像登记，见 ledger.toml [[mirrors]] ——\n"
                  + "\n".join(lines) + "\n")
        notes.append(f"修改  {os.path.relpath(owner_accounts_file, root)}（开立 {recv}、{pay}）")

    # 新账本一侧
    ch.append(os.path.join(root, name, "accounts.beancount"),
              f"\n; —— 与{owner.title}（{link} 账本）的往来：双边镜像登记，见 ledger.toml [[mirrors]] ——\n"
              + open_line("Liabilities:OwnerLoan", f"其他应付款－{owner.title}（其垫付/投入、本账本尚未归还的款项）") + "\n"
              + open_line("Assets:Receivable:Owner", f"其他应收款－{owner.title}（本账本资金由其代收/占用）") + "\n")

    return (
        f"\n# {link} ⇄ {name} 往来（new-book --link 生成）：每对两侧余额相加必须为 0，reconcile 自动核对\n"
        f"[[mirrors]]\nname = {_toml_str(f'{link} 垫付 {name}')}\ncurrency = \"{base}\"\n"
        f"accounts = {{ {link} = \"{recv}\", {name} = \"Liabilities:OwnerLoan\" }}\n"
        f"\n[[mirrors]]\nname = {_toml_str(f'{link} 代收/占用 {name} 资金')}\ncurrency = \"{base}\"\n"
        f"accounts = {{ {link} = \"{pay}\", {name} = \"Assets:Receivable:Owner\" }}\n"
    )
