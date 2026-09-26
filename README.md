# Beancount AI Ledger · 对 AI 说句话就能记账

[![CI](https://github.com/Xbang0222/beancount-ai-ledger/actions/workflows/ci.yml/badge.svg)](https://github.com/Xbang0222/beancount-ai-ledger/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

一套开箱即用的**纯文本复式记账模板**，记账引擎用 [Beancount](https://github.com/beancount/beancount)，记账员是你的 AI 编程助手（[Claude Code](https://claude.com/claude-code)、Codex 等）。

你用大白话说「中午吃面 18，微信付的」，AI 按你定的规则写成规范的会计分录，脚本校验通过才落账，每一笔都是一次 Git 提交。账本是你自己的文本文件，不依赖任何记账 App，也不怕平台关停。

这套账套最初是作者自己每天用 AI 记账、一条条踩坑打磨出来的，现在把代码和规则整理成通用模板开源出来。

📖 **不知道该怎么跟 AI 说？看 [使用指南](docs/GUIDE.md)**：建账、日常记账、AA、借钱、退款、旅行、改错、查账、对账，每种情况都有可以照着说的例句。

## 能做什么

- **口语记账**：说人话就行，AI 按 [`CATEGORIES.md`](CATEGORIES.md) 里的规则选科目、写摘要、打标签，然后一句话回报「大类、金额、付款账户、标签」，错了你一句话纠正。
- **入账有护栏**：一次只录一笔；自动注入时间，不许 AI 估时间；拒绝未来日期；不平衡或科目不存在就整笔回滚。账本永远处在可用状态。
- **一本账起步，多本账随加**：默认只有一本个人账。有店铺、工作室、家庭共同账的，一条命令加一本；账本之间的往来两边登记，自动对账。
- **查询报表**：最近几笔、月度汇总、月报（储蓄率）、余额表、按标签查（一趟旅行花了多少）、合并净资产（多币种折算）。
- **纯文本 + Git**：每笔账可追溯、可 diff、可回滚；需要图表时装 [Fava](https://github.com/beancount/fava) 就有网页报表。

## 看看效果

> **你**：中午在楼下吃了碗面 18，微信付的；晚上打车回家 32，花呗
>
> **AI**：已记 2 笔：餐饮 18.00 元（微信零钱）；交通 32.00 元（花呗）。无标签。

AI 实际写进账本的分录（`time` 由脚本自动注入）：

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

月底问一句「这个月花在哪了」：

```text
$ python3 scripts/ledger.py summary personal 2026-09

===== personal · 2026-09 · 支出大类 =====
  Expenses:Entertainment                   25.00 CNY
  Expenses:Food                           280.50 CNY
  Expenses:Housing                       2650.00 CNY
  Expenses:Shopping                       399.00 CNY
  Expenses:Social                         120.00 CNY
  Expenses:Transport                      100.00 CNY
  Expenses:Travel                        1358.00 CNY
  — 支出合计 —                           4932.50 CNY
----- 收入 -----
  Income:Salary                         12000.00 CNY
```

## ⚠️ 先说隐私

账本是你的隐私数据，请务必：

- 用本模板建自己的仓库时**选 Private（私有）**；
- **不要 Fork**：公开仓库的 Fork 也是公开的；
- 银行、支付宝导出的原始账单不要提交，`.gitignore` 已经忽略了 `*.csv`、`*.xlsx`。

## 快速开始

### 1. 建一个自己的私有仓库

- 在 GitHub 页面点 **Use this template → Create a new repository**，可见性选 **Private**；
- 或者克隆下来，推到你自己新建的私有仓库：

  ```bash
  git clone https://github.com/Xbang0222/beancount-ai-ledger.git my-ledger
  cd my-ledger
  git remote rename origin upstream                 # 留着以后升级脚本用
  git remote add origin <你的私有仓库地址>
  git push -u origin main
  ```

### 2. 安装依赖

需要 Python 3.9 或更高版本：

```bash
pip install -r requirements.txt     # 或 bash scripts/setup.sh（装依赖并校验账本）
```

### 3. 改成你自己的账户

1. `personal/accounts.beancount`：会计科目表。用不到的删掉，缺的补上，银行卡建议按银行细分（如 `Assets:Bank:CMB`）。
2. `personal/opening.beancount`：登记开始记账那天各账户的余额，写法见文件里的例子。
3. `CATEGORIES.md` 第 0 节：「付款渠道 → 账户」对照表改成你的账户名，默认付款账户改成你最常用的。
4. 校验一下：

   ```bash
   python3 scripts/ledger.py check
   ```

### 4. 开始记账

**用 AI 记**（推荐）：在仓库目录打开 Claude Code 或 Codex，直接说「昨晚和朋友吃烧烤 AA，我先付了 240，微信」。
AI 会先读 [`AGENTS.md`](AGENTS.md)（硬规矩）、[`CATEGORIES.md`](CATEGORIES.md)（分类规则）、[`STATE.md`](STATE.md)（临时状态），再通过脚本入账、校验、提交。

第 3 步也可以直接交给 AI：「帮我初始化账本，从今天开始记。我有招商银行卡 5000、支付宝 1200、微信 800，信用卡欠 1500。」更多说法见 [使用指南](docs/GUIDE.md)。

**手动记**：分录从 stdin 传给 `add`，一次一笔：

```bash
printf '%s' '2026-09-26 * "面馆" "餐饮-午餐"
  Expenses:Food:Dining  18.00 CNY
  Assets:Wechat' | python3 scripts/ledger.py add personal
```

更多分录写法（AA 代垫、花呗还款、退款、押金、贷款、基金定投、境外消费……）见 [`examples/cookbook.beancount`](examples/cookbook.beancount)。

### 5. 在云端或手机上记（可选）

用 Claude Code 网页版或手机 App 时，每次会话都在新容器里运行。在环境设置的 setup script 里填上 `pip install -r requirements.txt`，就不用每次手动装依赖。

## 先看看示例账本

`examples/demo/` 里是一套虚构的账：一个上班族的个人账，加一家小网店，数据都是编的。不用改任何东西就能把命令都试一遍：

```bash
python3 scripts/ledger.py --root examples/demo check                 # 校验两本账并对账
python3 scripts/ledger.py --root examples/demo report personal 2026-09
python3 scripts/ledger.py --root examples/demo tag personal chengdu   # 一趟成都旅行花了多少
python3 scripts/ledger.py --root examples/demo networth               # 合并净资产（含美元、基金折算）
```

## 目录结构

```text
.
├── ledger.toml                 # 账套配置：有哪些账本、往来怎么对账、时区与本位币
├── personal.beancount          # 个人账入口（Fava 也打开它）
├── personal/
│   ├── accounts.beancount      # 会计科目表
│   ├── opening.beancount       # 期初余额
│   └── journal/YYYY-MM.beancount  # 按月序时簿（第一次 add 时自动创建，别手改）
├── common/
│   ├── commodities.beancount   # 币种、基金代码声明
│   └── prices.beancount        # 汇率与净值（networth 折算用）
├── AGENTS.md                   # AI 记账硬规矩（Codex 读它；CLAUDE.md 引用它）
├── CLAUDE.md                   # Claude Code 入口
├── CATEGORIES.md               # 分类与核算规则（改成你自己的）
├── STATE.md                    # 临时状态：进行中的行程、临时默认账户等
├── docs/GUIDE.md               # 使用指南：各种情况怎么跟 AI 说
├── examples/
│   ├── cookbook.beancount      # 各类分录写法范例
│   └── demo/                   # 虚构的两本账示例
├── scripts/
│   ├── ledger.py               # 统一入口
│   ├── ledgerlib/              # 实现与科目表模板
│   └── setup.sh                # 一键装依赖并校验
└── tests/                      # pytest 用例（在临时目录跑，不碰真实账本）
```

## 多本账：店铺、家庭账……

**先判断需不需要新账本。** 一本账等于一个会计主体：需要单独算盈亏、或者钱不完全属于你的，才新建账本，比如店铺或工作室、家庭共同账、多人 AA 的活动经费、替父母代管的钱。
只是想看「某件事花了多少」，比如一次旅行、装修、婚礼，**不用新建账本，打标签就行**：旅行支出打 `#trip #chengdu`，用 `ledger.py tag personal chengdu` 一查就是整趟的花费。

新建账本用 `new-book`，它会生成入口文件、科目表模板、期初余额模板，并登记到 `ledger.toml`：

```bash
# 店铺账（经营科目模板），并和个人账建立往来
python3 scripts/ledger.py new-book shop --template business --title "我的小店" --link personal

# 家庭共同账（最小模板），与他人共有、不并入你个人的净资产
python3 scripts/ledger.py new-book family --template minimal --title "家庭共同账" --no-consolidate
```

`--link personal` 会在两本账各开一对往来科目，并登记两对「镜像」：

| 情形 | 个人账记 | 店铺账记 |
|---|---|---|
| 你用个人账户替店里付了钱 | 应收商店 `Assets:Receivable:Shop` | 欠股东 `Liabilities:OwnerLoan` |
| 店里的钱进了你的个人账户 | 欠商店 `Liabilities:Shop` | 应收股东 `Assets:Receivable:Owner` |

同一笔钱两本账各记一边，每对镜像科目的余额相加永远是 0。beancount 只能校验单本账内部平衡，**只记了一边它发现不了**，所以：

- `add` 碰到往来科目时会提醒你另一边该记在哪；
- `reconcile`（`check` 会连带执行）核对每一对镜像，对不上就列出最近相关的分录帮你定位；
- `networth` 合并各账本时自动抵销这些"左手欠右手"的往来，不会让资产和负债同时虚增。

完整规则见 [`CATEGORIES.md`](CATEGORIES.md) 第 3、4 节。

## 配置 ledger.toml

```toml
[ledger]
timezone = "Asia/Shanghai"      # 记账时区：自动注入的 time、未来日期/时间校验都按它
base_currency = "CNY"           # 本位币：networth 折算合计的目标币种

[books.personal]                # 账本名：小写字母开头，命令里用它，如 add personal
title = "个人账本"
kind = "personal"               # personal：月报算储蓄率；business：月报看经营结余

[books.shop]
title = "我的小店"
kind = "business"
consolidate = true              # 是否并入 networth 合并资产负债，默认 true
# main = "shop.beancount"       # 入口文件，默认 <账本名>.beancount
# journal = "shop/journal"      # 序时簿目录，默认 <账本名>/journal

[[mirrors]]                     # 一对往来镜像科目：两侧余额相加必须为 0
name = "personal 垫付 shop"
currency = "CNY"
accounts = { personal = "Assets:Receivable:Shop", shop = "Liabilities:OwnerLoan" }
```

配置写错（拼错键名、引用不存在的账本、同一科目重复出现在多对镜像里等）会直接报错，而不是悄悄关掉对账。

## 命令一览

所有命令都是 `python3 scripts/ledger.py <命令>`；加 `--root <目录>` 可以操作别的账套目录。

| 命令 | 作用 |
|---|---|
| `check [--no-reconcile]` | 校验全部账本；有往来镜像时连带对账 |
| `add <账本>` | 从 stdin 追加一笔分录：注入时间、校验，失败整笔回滚 |
| `recent <账本> [-n N]` | 按发生时间列出最近 N 笔（默认 10） |
| `summary <账本> [YYYY-MM]` | 按一级大类汇总支出和收入 |
| `report <账本> [YYYY-MM]` | 月报：收入、支出占比、结余与储蓄率（经营账看利润率） |
| `balances <账本>` | 科目余额表 |
| `tag <账本> <标签> [YYYY-MM]` | 按标签查明细，支出、收入、往来分开汇总 |
| `networth [--rate 币种=汇率]` | 资产负债汇总：合并账本、抵销往来、外币折合本位币 |
| `reconcile` | 跨账本往来对账 |
| `fmt [--check] [账本]` | 序时簿排版：按日期时间重排、分录间空一行；前后比对余额，不动账 |
| `books` | 列出账本与往来镜像 |
| `new-book <名称> [--template personal\|business\|minimal] [--title T] [--link 账本] [--no-consolidate]` | 新建账本 |

## 为什么这样设计

- **AI 只能通过 `add` 入账，不能直接改账本文件。** `add` 会注入时间、校验平衡、失败回滚；让 AI 直接改文件，这些保护就全没了。
- **一次只录一笔。** 一次写入多笔，出错时很难定位；跨月的多笔还会被塞进同一个月份文件。
- **不许估时间。** AI 很容易把「晚上」编成 `20:00`，或者把上午当成晚上。没报时间就记录入时刻；手写的时间晚于此刻、日期晚于今天，都会直接拒绝。
- **规则与临时状态分开。** 长期规则放 `CATEGORIES.md`，「这周在外地旅行」这种会过期的情况放 `STATE.md`，过期即删，规则文件不会越写越乱。
- **往来两边登记、自动对账。** 多本账最常见的错误就是只记了一边，靠人盯是盯不住的。

## 常见问题

**Windows 能用吗？** 能。建议在 Git Bash 或 WSL 里用（Claude Code 在 Windows 上本来就通过 Git Bash 执行命令）；命令里的 `python3` 换成 `python` 或 `py`。

**多台设备、多个 AI 会话同时记账会冲突吗？** 每次动手前先 `git pull --ff-only`；同一台机器上 `add` 自带文件锁，并发写入不会互相覆盖。

**能看图表吗？** `pip install fava && fava personal.beancount`，浏览器打开 http://localhost:5000 。

**不用 AI 行不行？** 行。所有功能都是命令行脚本，手写分录通过 `add` 入账即可。

**模板更新了，怎么升级我自己的账套？** 只更新脚本和测试，不碰你的账本数据：

```bash
git remote add upstream https://github.com/Xbang0222/beancount-ai-ledger.git   # 只需一次
git fetch upstream
git checkout upstream/main -- scripts tests requirements.txt requirements-dev.txt
python3 -m pytest tests/ -q && python3 scripts/ledger.py check
git commit -m "chore(script): 同步上游脚本"
```

`AGENTS.md`、`CATEGORIES.md` 的更新可以对照上游自行合并，里面可能有你自己改过的规则。

## 开发与测试

```bash
pip install -r requirements-dev.txt
python3 -m pytest tests/ -q
```

实现在 `scripts/ledgerlib/`：`config` 读取 ledger.toml，`add` 负责入账与回滚，`query` 管查询，`reconcile` 管对账，`networth` 管合并资产负债，`newbook` 管新建账本，`fmt` 管排版。
代码里不写死任何账本名。测试通过 `tests/conftest.py` 的 fixture 在临时目录搭账套，不会碰真实账本。欢迎提 Issue 和 PR。

## 许可证

[MIT](LICENSE)。记账引擎 [Beancount](https://github.com/beancount/beancount) 由 Martin Blais 开发，以 GPL-2.0 发布，通过 `pip` 单独安装，不随本仓库分发。

---

## English

**Beancount AI Ledger** is a plain-text, double-entry bookkeeping template built on [Beancount](https://github.com/beancount/beancount) and designed to be operated by an AI coding agent such as Claude Code or Codex. You describe a transaction in everyday language; the agent turns it into a proper entry following the rules in `CATEGORIES.md`, and `scripts/ledger.py add` validates it before anything is written. A bad entry is rolled back, and every change is a Git commit.

- Guardrails: one transaction per `add`; timestamps are injected rather than guessed; future dates and times are rejected; unbalanced entries and unknown accounts are rolled back.
- Starts with a single personal book. Add more (a shop, a studio, a family pool) with `new-book`. Transfers between books are recorded on both sides as declared mirror accounts in `ledger.toml`, and `reconcile` checks that each pair nets to zero.
- Reports: recent entries, monthly summary and report (savings rate), balances, tag drill-down (for example, the cost of a whole trip), and a consolidated net worth with FX conversion.
- Try it without setup: `python3 scripts/ledger.py --root examples/demo networth`.

The documentation and the default categories target users in mainland China (Alipay, WeChat Pay, Huabei and so on). The code itself is locale-agnostic: timezone and base currency are configurable. Keep your own ledger in a **private** repository and don't fork it publicly. MIT licensed.
