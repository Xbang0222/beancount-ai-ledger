# beancount-ai-ledger

简体中文 | [English](README.en.md)

[![CI](https://github.com/Xbang0222/beancount-ai-ledger/actions/workflows/ci.yml/badge.svg)](https://github.com/Xbang0222/beancount-ai-ledger/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Xbang0222/beancount-ai-ledger)](https://github.com/Xbang0222/beancount-ai-ledger/releases)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](requirements.txt)
[![License](https://img.shields.io/github/license/Xbang0222/beancount-ai-ledger)](LICENSE)

用 AI 编程助手记账的 [Beancount](https://github.com/beancount/beancount) 账本模板。

你对 Claude Code、Codex 等 AI 助手说"午饭 18，微信付的"，它按仓库里的规则写成复式分录，脚本校验通过后写入账本并提交到 Git。账本是纯文本文件，保存在你自己的私有仓库里。

[快速开始](#快速开始) · [不会用 Git](#不会用-git只用豆包也可以) · [使用指南](docs/GUIDE.md) · [命令](#命令) · [多本账](#多本账) · [常见问题](#常见问题)

## 示例

> 你：中午在楼下吃了碗面 18，微信付的；晚上打车回家 32，花呗
>
> AI：已记 2 笔：餐饮 18.00 元（微信零钱）；交通 32.00 元（花呗）。无标签。

写入账本的分录，`time` 是脚本注入的录入时间：

```beancount
2026-09-26 * "面馆" "餐饮-午餐"
  time: "12:10"
  Expenses:Food:Dining  18.00 CNY
  Assets:Wechat

2026-09-26 * "网约车" "交通-打车"
  time: "21:47"
  Expenses:Transport:Local  32.00 CNY
  Liabilities:Huabei
```

月底问"这个月存下多少钱"，AI 会运行月报（以下为示例账本的输出）：

```text
$ python3 scripts/ledger.py report personal 2026-09

【支出】
  Expenses:Entertainment               25.00 CNY  (0.5%)
  Expenses:Food                       280.50 CNY  (5.7%)
  Expenses:Housing                   2650.00 CNY  (53.7%)
  Expenses:Shopping                   399.00 CNY  (8.1%)
  Expenses:Social                     120.00 CNY  (2.4%)
  Expenses:Transport                  100.00 CNY  (2.0%)
  Expenses:Travel                    1358.00 CNY  (27.5%)
  支出合计                           4932.50 CNY

【结余与储蓄率】
  收入 12000.00 − 支出 4932.50 = 结余 7067.50 CNY
  储蓄率: 58.9%
```

## 功能

- 记账口径写在 [`CATEGORIES.md`](CATEGORIES.md)：付款方式对应哪个账户、支出归哪个科目、摘要和标签怎么写。改这个文件，AI 的记法就跟着变。
- AI 记新账不直接写账本文件，而是经 `ledger.py add` 写入：一次一笔，自动注入录入时间，拒绝未来的日期和时间，借贷不平衡或科目未开立时整笔回滚。
- 默认只有一本个人账。店铺、工作室、家庭共同账用 `new-book` 新增，账本之间的往来两边登记，由 `reconcile` 核对。
- 查询：最近记录、月度汇总、月报（储蓄率）、余额表、按标签汇总（比如一次旅行的总花费）、多账本合并净资产（含外币和基金折算）。
- 自带 `AGENTS.md`、`CLAUDE.md`、`GEMINI.md`，主流 AI 编程助手打开仓库就能读到规则；`doctor` 命令帮 AI 检查依赖、账本状态和仓库是否私有。

## 快速开始

需要 Python 3.9 或更高版本，以及 Git。

### 1. 创建私有仓库

在本仓库页面点击 **Use this template** → **Create a new repository**，可见性选 **Private**，然后克隆到本地。装了 [GitHub CLI](https://cli.github.com/) 的话，一条命令即可：

```bash
gh repo create my-ledger --private --template Xbang0222/beancount-ai-ledger --clone
```

> [!WARNING]
> 账本里是你的收支和余额，请放在私有仓库。不要 Fork，公开仓库的 Fork 也是公开的。从银行、支付宝导出的原始账单不要提交，`.gitignore` 已忽略 `*.csv` 和 `*.xlsx`。

### 2. 安装依赖

```bash
cd my-ledger
python3 scripts/bootstrap.py
```

脚本把 Beancount 装进仓库的 `.venv`，再校验一遍账本。之后直接运行 `python3 scripts/ledger.py`，入口会自动使用 `.venv`。Windows 上把 `python3` 换成 `python` 或 `py`。

### 3. 交给 AI

在仓库目录打开 Claude Code、Codex 等工具，第一句说：

> 帮我初始化账本，从今天开始记。我有招商银行卡 5000、支付宝 1200、微信 800，信用卡欠 1500。平时没说怎么付的就算微信。

AI 会先运行 `doctor` 检查环境，再按你的账户改科目表、登记期初余额，校验通过后提交。日常记账、改错、查账、对账怎么说，见 [使用指南](docs/GUIDE.md)。

> [!TIP]
> 想先看效果，可以在示例账本上试命令，不用改任何文件：
>
> ```bash
> python3 scripts/ledger.py --root examples/demo report personal 2026-09
> python3 scripts/ledger.py --root examples/demo networth
> ```

## 不会用 Git？只用豆包也可以

不想碰 GitHub、Git 和命令行，只用豆包这类自带云电脑和云盘的 AI，也能用。账本不放仓库，改成一个压缩包存在你自己的云盘里。

1. 下载[模板压缩包](https://github.com/Xbang0222/beancount-ai-ledger/archive/refs/heads/main.zip)。打不开 GitHub 的话，让已经在用的朋友把压缩包转给你。
2. 把压缩包发给豆包，第一句说：

   > 这是一个 AI 记账模板。请解压它，先读里面的 AGENTS.md（重点看「不用 Git 时」一节）和 CATEGORIES.md，然后帮我建账，从今天开始记。我不会用 Git，账本请存到我云盘的「AI记账」文件夹，每次记完都存一次。
   > 我有招商银行卡 5000、支付宝 1200、微信 800，花呗欠 420。平时没说怎么付的就算微信。

3. 以后每次记账，开头说一句账本在哪：

   > 帮我记账。账本在我云盘的「AI记账」文件夹，取最新的 ledger-backup 压缩包，按里面的 AGENTS.md 来。今天午饭 18 微信，打车 32 花呗。

AI 每次会先告诉你账本里最后一笔是什么，你看一眼对不对；记完会把最新的账本存回云盘。云电脑被重置也不影响，账本一直在你的云盘里。详见[使用指南第九节](docs/GUIDE.md#九在其他-ai-工具里用)。

## 命令

格式为 `python3 scripts/ledger.py <命令>`，加 `--root <目录>` 可以操作其他目录里的账套。

| 命令 | 说明 |
|---|---|
| `doctor` | 检查依赖、各账本状态，以及 Git 远程仓库是否私有 |
| `check [--no-reconcile]` | 校验全部账本，有往来镜像时连带对账 |
| `add <账本> [--file 文件]` | 从标准输入或文件写入一笔分录，校验失败整笔回滚 |
| `recent <账本> [-n N]` | 按发生时间列出最近 N 笔，默认 10 笔 |
| `summary <账本> [YYYY-MM]` | 按一级科目汇总支出和收入 |
| `report <账本> [YYYY-MM]` | 月报：收入、支出占比、结余与储蓄率（经营账为利润率） |
| `balances <账本>` | 科目余额表 |
| `tag <账本> <标签> [YYYY-MM]` | 按标签汇总明细 |
| `networth [--rate 币种=汇率]` | 合并资产负债：抵销账本之间的往来，外币折合本位币 |
| `reconcile` | 核对账本之间的往来 |
| `fmt [--check] [账本]` | 整理序时簿格式、按日期时间排序，不改金额 |
| `books` | 列出账本与往来镜像 |
| `new-book <名称> [选项]` | 新建账本，见[多本账](#多本账) |
| `backup [-o 目录]` | 把整个账套打成一个压缩包，不用 Git 时存到云盘、网盘 |

不经过 AI、手动入账时这样写：

```bash
python3 scripts/ledger.py add personal <<'EOF'
2026-09-26 * "面馆" "餐饮-午餐"
  Expenses:Food:Dining  18.00 CNY
  Assets:Wechat
EOF
```

AA、代垫、信用卡还款、退款、押金、贷款、基金、外币等写法见 [`examples/cookbook.beancount`](examples/cookbook.beancount)。

## 多本账

一本账对应一个会计主体。需要单独核算盈亏，或者钱不全归你（店铺、工作室、家庭共同账、活动经费）时，才需要新建账本。只想统计一件事花了多少，比如一次旅行，打标签就够了：`ledger.py tag personal chengdu`。

```bash
# 店铺账：经营科目模板，并与个人账建立往来
python3 scripts/ledger.py new-book shop --template business --title "我的小店" --link personal

# 家庭共同账：不并入个人净资产
python3 scripts/ledger.py new-book family --template minimal --title "家庭共同账" --no-consolidate
```

`--link personal` 会在两本账各开一对往来科目，并在 `ledger.toml` 里登记为镜像：

| 情形 | 个人账 | 店铺账 |
|---|---|---|
| 用个人账户替店里付款 | `Assets:Receivable:Shop` | `Liabilities:OwnerLoan` |
| 店里的钱进了个人账户 | `Liabilities:Shop` | `Assets:Receivable:Owner` |

每对镜像科目的余额相加应当为 0。Beancount 只校验单本账内部平衡，只记了一边它发现不了，所以 `add` 碰到往来科目会提示另一边该记在哪，`reconcile` 逐对核对，`networth` 合并时自动抵销。

`ledger.toml` 的完整写法：

```toml
[ledger]
timezone = "Asia/Shanghai"      # 注入 time、判断未来日期都按这个时区
base_currency = "CNY"           # networth 折算的目标币种

[books.personal]                # 账本名：小写字母开头
title = "个人账本"
kind = "personal"               # personal 月报算储蓄率；business 月报看经营结余

[books.shop]
title = "我的小店"
kind = "business"
consolidate = true              # 是否并入 networth，默认 true
# main = "shop.beancount"       # 入口文件，默认 <账本名>.beancount
# journal = "shop/journal"      # 序时簿目录，默认 <账本名>/journal

[[mirrors]]                     # 一对往来镜像科目，两侧余额相加必须为 0
name = "personal 垫付 shop"
currency = "CNY"
accounts = { personal = "Assets:Receivable:Shop", shop = "Liabilities:OwnerLoan" }
```

键名拼错、引用了不存在的账本、同一个科目出现在多对镜像里，都会直接报错。

## 目录结构

```text
.
├── ledger.toml              账套配置：账本、往来镜像、时区、本位币
├── personal.beancount       个人账入口（Fava 也打开这个文件）
├── personal/
│   ├── accounts.beancount   科目表
│   ├── opening.beancount    期初余额
│   └── journal/             按月的序时簿，由 add 自动创建
├── common/                  币种声明、汇率与净值
├── AGENTS.md                给 AI 的操作规范
├── CLAUDE.md, GEMINI.md     让 Claude Code、Gemini CLI 载入 AGENTS.md
├── CATEGORIES.md            分类与核算规则
├── STATE.md                 临时状态，如进行中的行程
├── docs/GUIDE.md            使用指南
├── examples/                分录范例与示例账本
├── scripts/                 ledger.py、bootstrap.py 及实现
└── tests/                   pytest 用例
```

## 常见问题

**支持哪些 AI 工具？**
能读取仓库文件、能执行命令的 AI 编程助手都可以。Claude Code 和 Gemini CLI 通过 `CLAUDE.md`、`GEMINI.md` 载入规则，Codex、Cursor、GitHub Copilot 等直接读取 `AGENTS.md`。其他工具的用法见[使用指南第九节](docs/GUIDE.md#九在其他-ai-工具里用)。

**Windows 能用吗？**
能，CI 在 Windows 上跑全部测试。命令里的 `python3` 换成 `python` 或 `py`。PowerShell 没有 heredoc，手动入账时先把分录存成 UTF-8 文件，再用 `add <账本> --file <文件>`。

**在 Claude Code 网页版、Codex 云端这类云环境里呢？**
每次会话都是新环境，AI 会按 `AGENTS.md` 先运行 `bootstrap.py` 安装依赖，然后照常记账。

**不用 Git，账本存在哪？会不会丢？**
存在你自己的云盘或网盘里。AI 每次改动后运行 `backup`，把整个账套打成 `ledger-backup-日期-时间.zip` 存进去，下次取最新的一份解压接着记。账本有错误时 `backup` 不会生成压缩包，不会拿坏的盖掉好的。云盘里留最近几份，等于有了历史版本。

**多台设备同时记账会冲突吗？**
AI 每次开始前会先 `git pull --ff-only`。同一台机器上 `add` 带文件锁，并发写入不会互相覆盖。

**能看图表吗？**
可以用 [Fava](https://github.com/beancount/fava)：`pip install fava && fava personal.beancount`，然后打开 http://localhost:5000 。

**不用 AI 可以吗？**
可以，所有功能都是命令行脚本。

**推送后 GitHub Actions 在跑什么？**
用模板建的仓库每次推送只跑一遍 `check` 校验账本，约一分钟。不需要的话，删掉 `.github/workflows/` 目录即可。

**模板更新后怎么升级？**
只同步脚本和测试，账本数据不动：

```bash
git remote add upstream https://github.com/Xbang0222/beancount-ai-ledger.git   # 只需一次
git fetch upstream
git checkout upstream/main -- scripts tests requirements.txt requirements-dev.txt
python3 -m pytest tests/ -q && python3 scripts/ledger.py check
git commit -m "chore(script): 同步上游脚本"
```

`AGENTS.md`、`CATEGORIES.md` 里可能有你自己改过的规则，请对照[更新日志](CHANGELOG.md)手动合并。

## 致谢

记账引擎是 Martin Blais 开发的 [Beancount](https://github.com/beancount/beancount)（GPL-2.0），通过 pip 单独安装，不随本仓库分发。
