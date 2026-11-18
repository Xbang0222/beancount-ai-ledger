# beancount-ai-ledger

简体中文 | [English](README.en.md)

[![Release](https://img.shields.io/github/v/release/Xbang0222/beancount-ai-ledger)](https://github.com/Xbang0222/beancount-ai-ledger/releases)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](requirements.txt)
[![License](https://img.shields.io/github/license/Xbang0222/beancount-ai-ledger)](LICENSE)

基于 [Beancount](https://github.com/beancount/beancount) 的纯文本复式账套模板，专为 AI 记账设计。日常用口语对 Claude Code、Codex、豆包等 AI 描述收支，AI 按仓库里的规则转成规范分录，经脚本平衡校验后写入账本，再用 Git（或云盘备份）保存。默认一本个人账，可按需增加店铺、工作室、家庭共同账等独立账本。

## 文档约定

| 文档 | 内容 | 读取时机 |
|---|---|---|
| `AGENTS.md` | AI 作业规程：作业流程、强制约束、回报要求、文档索引。`CLAUDE.md`、`GEMINI.md` 引用它，主流 AI 编程助手打开仓库即会读取 | 会话开始时 |
| `rules/daily.md` | 日常入账规则：分录要素、账本判定、结算账户对照表、往来、退款、时间、标签。**建账后按你的习惯修改**，AI 的记法随之改变 | 每次入账前 |
| `rules/` 其余文件 | 按主题划分的规则：对方与摘要、标签、分类表、速查词典、判例，以及信贷、投资、估值、共有账本等专题；自定的少见口径也写在这里 | 按 `AGENTS.md` 的索引按需读取，或用 `ledger.py lookup <关键词>` 检索 |
| `STATE.md` | 会失效的临时上下文：进行中的行程、临时默认结算账户 | 由 `ledger.py brief` 输出 |
| `docs/AI-SETUP.md`、`docs/AI-TASKS.md` | 建账与账本存放；更正、余额核对、导入账单、升级等常见请求的处理 | 按 `AGENTS.md` 的索引按需读取 |
| `docs/COMMITS.md`、`docs/DEVELOPMENT.md` | 提交信息规范、开发规范 | 提交前、修改脚本时 |

长期规则只写入 `rules/`，一个主题一个文件；临时上下文只写入 `STATE.md`；规则冲突时以 `rules/daily.md` 为准。

## 记账示例

> 你：中午在楼下吃了碗面 18，微信付的；晚上打车回家 32，花呗
>
> AI：已记 2 笔：餐饮 18.00 元（微信零钱）；交通 32.00 元（花呗）。无标签。

写入账本的分录如下，`time` 由脚本注入录入时刻，不由 AI 估算：

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

月末询问「这个月存下多少钱」时，AI 执行月度报告。以下为示例账本的输出：

```text
$ python3 scripts/ledger.py report personal 2026-09

【支出】
  Expenses:Food                       280.50 CNY  (5.7%)
  Expenses:Housing                   2650.00 CNY  (53.7%)
  Expenses:Travel                    1358.00 CNY  (27.5%)
  ...
  支出合计                           4932.50 CNY

【结余与储蓄率】
  收入 12000.00 − 支出 4932.50 = 结余 7067.50 CNY
  储蓄率: 58.9%
```

## 开始使用

| 使用场景 | 文档 |
|---|---|
| 在本机使用 Claude Code、Codex 等 AI 编程助手，使用 Git | [快速开始：以 Git 保存账本](docs/QUICKSTART.md) |
| 只使用豆包这类 AI，不使用 Git | [不使用 Git：通过豆包记账](docs/NO-GIT.md) |

能读取文件、执行命令的 AI 均可使用。账本的存放方式取决于现有条件：首选**私有 Git 仓库**（GitHub、Gitee 等），没有时备份到云盘，由 AI 按 `docs/AI-SETUP.md`「账本存放」判断。下列命令通常由 AI 执行；手动执行须本机已安装 Python 3.9+ 与 git，依赖安装在仓库自带的 `.venv` 中，不影响系统 Python：

```bash
python3 scripts/bootstrap.py                 # 创建 .venv、安装依赖、校验账本
git config core.hooksPath scripts/hooks      # 启用提交前自动检查，每个克隆执行一次
python3 scripts/ledger.py doctor             # 检查环境、账本与 Git 远程仓库
```

> 账本是真实的财务数据：请通过 **Use this template** 建立**私有**仓库后再记账，不要 Fork，公开仓库的 Fork 同样公开。`doctor` 发现远程仓库为公开时会给出提醒。

## 目录结构

```
beancount-ai-ledger/
├── personal.beancount          # 个人账入口
├── ledger.toml                 # 账套配置：账本清单、往来镜像、时区、本位币、利润分配
├── rules/                      # 记账规则，按主题分文件；daily.md 为每次入账必读
├── STATE.md                    # 当前临时状态，失效即删
├── AGENTS.md                   # AI 作业规程，CLAUDE.md、GEMINI.md 引用它
├── common/
│   ├── commodities.beancount   # 币种声明
│   └── prices.beancount        # 外币、基金等价格
├── personal/
│   ├── accounts.beancount      # 个人会计科目表
│   ├── opening.beancount       # 期初余额
│   └── journal/YYYY-MM.beancount  # 按月序时簿，由脚本追加
├── scripts/
│   ├── ledger.py               # 统一入口：入账、更正、作废、校验、查询、对账、排版
│   ├── bootstrap.py            # 环境准备：创建 .venv、安装依赖、校验账本
│   ├── hooks/pre-commit        # 提交前自动检查
│   ├── hooks/commit-msg        # 提交信息写法检查
│   └── ledgerlib/              # 实现与科目表模板
├── examples/
│   ├── cookbook.beancount      # AA、代垫、信用卡、退款、押金、贷款、基金、外币等写法
│   └── demo/                   # 个人账与店铺账的完整示例账套
├── docs/                       # 快速开始、使用指南、命令参考、常见问题；供 AI 读取的建账、常见请求、提交与开发规范
└── tests/                      # pytest 用例，在临时账套上运行，不接触真实账本
```

通过 `new-book` 新增的账本（例如 `shop`）另有一组结构相同的 `shop.beancount` 与 `shop/` 目录。

## 记账流程

1. 用户以口语描述收支：金额、事由、付款方式；未说明的部分按 `rules/daily.md` 的默认规则补全。
2. AI 执行 `ledger.py brief` 取得现场信息：当前日期、`STATE.md` 中生效的临时状态、待补记的周期分录、可用科目；再按 `rules/daily.md` 将口语转为规范分录，日期、金额、科目、付款账户必填，标签按需。归类由 AI 决定，**不向用户询问记入哪一类**；仅当金额、日期、是否属于借出或代垫等事实缺失时才确认。
3. 通过 `ledger.py add` 入账，一次一笔：借贷不平、科目未开立、日期晚于当日、疑似重复时整笔回滚，并以中文说明修改方法；两本账之间的往来通过 `ledger.py pair` 同时登记。
4. AI 回报大类、金额、付款账户与标签。记错时用一句话说明即可更正，由 `amend` / `void` 处理，不手工编辑账本文件。
5. 每次改动后立即提交并推送到私有仓库；没有远程仓库时按 [NO-GIT](docs/NO-GIT.md) 备份到云盘。

## 常用命令

完整清单与参数以 `python3 scripts/ledger.py --help` 为准，详细说明见 [命令与配置](docs/REFERENCE.md)：

```bash
python3 scripts/ledger.py brief                        # 入账所需的现场信息：日期、临时状态、待补记的周期分录、可用科目
python3 scripts/ledger.py lookup 猫粮 拼多多            # 按关键词检索科目与规则所在章节
python3 scripts/ledger.py check                        # 校验全部账本并核对账本之间的往来
python3 scripts/ledger.py recent personal              # 最近 10 笔，行首为 [编号]
python3 scripts/ledger.py find personal 午餐 18        # 按关键词查找分录
python3 scripts/ledger.py amend personal <编号>        # 更正：从标准输入读取新分录，整笔替换
python3 scripts/ledger.py void personal <编号>         # 作废该笔
python3 scripts/ledger.py summary personal 2026-09     # 按一级大类汇总
python3 scripts/ledger.py report personal 2026-09      # 月度报告：收支与储蓄率
python3 scripts/ledger.py tag personal trip 2026-09    # 按标签汇总明细，例如一次旅行的总花费
python3 scripts/ledger.py networth                     # 合并资产负债，外币、金银、基金、股票按现价折算
python3 scripts/ledger.py quote USD AU F161226         # 联网查询汇率、每克金价、基金净值
python3 scripts/ledger.py dividend 2026-09             # 合伙店铺按月利润分配
python3 scripts/ledger.py new-book shop --template business --link personal   # 新增店铺账
python3 scripts/ledger.py backup --daily               # 将整个账套连同 Git 历史打包，供存入云盘
```

## 核算要点

- **会计主体分离**：个人与店铺、家庭共同账各设一本账，账本之间的资金往来双边镜像登记，不确认收支；`reconcile` 核对两边相加为 0，`networth` 合并时自动抵销。
- **两级分类**：支出只分大类与小类，例如 `Expenses:Food:Dining`；交易对象与行程由标签表示（`#trip`、`#family`），摘要写明具体事项。
- **消费信贷**：花呗、白条、信用卡消费确认负债，还款冲减负债，不重复记支出。
- **退款与代垫**：退款冲减原支出，不确认收入；借出、代垫挂往来科目，不确认支出。
- **估值**：默认本位币为 CNY。计算总资产时，外币、加密货币、黄金白银、基金、股票按联网取得的当日价格折算，无法取得时改用账内 `price`；只登记了金额的积存金按每笔发生当日的金价估算克数与现值；养老保险、医保个人账户无法支取，不计入净资产。
- **利润分配**：合伙店铺在 `ledger.toml` 的 `[dividend]` 中配置比例，每月初执行 `dividend`，得出各方应得、已分配与本次实付。
- **店铺账仅用于内部管理**：店铺为注册主体的，对外纳税申报仍须按税法与会计准则设账，可委托代理记账；本账套的流水可作为会计的记账依据。只记个人账的不涉及本条。
- 完整分录范例见 [`examples/cookbook.beancount`](examples/cookbook.beancount)。

## 数据可靠性

校验分两级：

1. **命令内**：`add`、`pair`、`amend`、`void`、`fmt` 写盘后校验整本账，未通过即还原。
2. **提交前**：`scripts/hooks/pre-commit` 执行账本校验、往来对账与排版检查，修改脚本时另执行 ruff 与 pytest；`scripts/hooks/commit-msg` 检查提交信息。

推送后没有云端检查：每台设备、每个克隆均须先启用钩子（`git config core.hooksPath scripts/hooks`）。`brief`、`doctor` 与 `add`、`pair`、`amend`、`void` 发现本仓库未启用时自动启用。

此外，入账命令拒绝晚于当日的日期、估算的时间、缺少对方或摘要的分录，以及内容相同的重复分录；全部变更由 Git 管理，可追溯、可比较、可回滚。

## 更多文档

| 文档 | 内容 |
|---|---|
| [使用指南](docs/GUIDE.md) | 记账、更正、查询、对账时对 AI 的说法 |
| [命令与配置](docs/REFERENCE.md) | 全部命令、多本账、利润分配、`ledger.toml`、目录结构 |
| [常见问题](docs/FAQ.md) | 支持的 AI 工具、Windows、云环境、升级模板 |
| [更新日志](CHANGELOG.md) | 各版本的改动 |

## 致谢

记账引擎是 Martin Blais 开发的 [Beancount](https://github.com/beancount/beancount)（GPL-2.0），通过 pip 单独安装，不随本仓库分发。
