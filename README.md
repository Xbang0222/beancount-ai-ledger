# beancount-ai-ledger

简体中文 | [English](README.en.md)

[![CI](https://github.com/Xbang0222/beancount-ai-ledger/actions/workflows/ci.yml/badge.svg)](https://github.com/Xbang0222/beancount-ai-ledger/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Xbang0222/beancount-ai-ledger)](https://github.com/Xbang0222/beancount-ai-ledger/releases)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](requirements.txt)
[![License](https://img.shields.io/github/license/Xbang0222/beancount-ai-ledger)](LICENSE)

基于 [Beancount](https://github.com/beancount/beancount) 的纯文本复式账套模板，专为 AI 记账设计。日常用口语对 Claude Code、Codex、豆包等 AI 描述收支，AI 按仓库里的规则转成规范分录，经脚本平衡校验后写入账本，再用 Git（或云盘备份）保存。默认一本个人账，可按需增加店铺、工作室、家庭共同账等独立账本。

## 文档约定

- `CATEGORIES.md`：记账规则，涵盖付款渠道对应账户、科目归类、摘要写法、往来、信贷与投资，是记账口径的唯一依据。**建账后按你的习惯改**，AI 的记法跟着变。
- `CLASSIFY.md`：分类速查词典（常见东西、商家平台直接对到科目）、分类的参考依据与「用户原话 → 怎么记」对照示例。
- `STATE.md`：进行中的行程、临时默认付款账户等会过期的临时上下文，事项结束即删除。
- `AGENTS.md`（`CLAUDE.md`、`GEMINI.md` 引用它）：给 AI 的操作规范，主流 AI 编程助手打开仓库就会读到。
- 稳定规则只写进 CATEGORIES，易变情况只写进 STATE，两者不混放；冲突时以 CATEGORIES 为准。

## 记账示例

> 你：中午在楼下吃了碗面 18，微信付的；晚上打车回家 32，花呗
>
> AI：已记 2 笔：餐饮 18.00 元（微信零钱）；交通 32.00 元（花呗）。无标签。

写入账本的分录（`time` 由脚本注入录入时刻，不靠 AI 估）：

```beancount
2026-09-26 * "面馆" "餐饮-牛肉面"
  time: "12:10"
  Expenses:Food:Dining  18.00 CNY
  Assets:Wechat

2026-09-26 * "网约车" "交通-打车"
  time: "21:47"
  Expenses:Transport:Local  32.00 CNY
  Liabilities:Huabei
```

月底问"这个月存下多少钱"，AI 运行月报（示例账本的输出）：

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

| 你的情况 | 看这篇 |
|---|---|
| 在自己电脑上用 Claude Code、Codex 等 AI 编程助手，会用 Git | [快速开始：用 Git 保存账本](docs/QUICKSTART.md) |
| 只用豆包这类 AI，不会用 Git | [不用 Git：只用豆包记账](docs/NO-GIT.md) |

任何能读文件、跑命令的 AI 都能用。账本存哪按你手里有什么来：**私有 Git 仓库**（GitHub、Gitee 等）最好，没有就备份到云盘，AI 按 `AGENTS.md`「账本存哪」自己判断。下面的命令也由 AI 来跑；自己动手的，前提是本机已有 Python 3.9+ 和 git，依赖装在仓库自己的 `.venv` 里，不动系统 Python：

```bash
python3 scripts/bootstrap.py                 # 建 .venv、装依赖、校验账本
git config core.hooksPath scripts/hooks      # 启用提交前自动检查（每个克隆做一次）
python3 scripts/ledger.py doctor             # 环境、账本、Git 远程仓库是否就绪
```

> 账本是你的真实财务数据：请用 **Use this template** 建一个**私有**仓库再记账，不要 Fork（公开仓库的 Fork 也是公开的）。`doctor` 发现远程仓库是公开的会提醒。

## 目录结构

```
beancount-ai-ledger/
├── personal.beancount          # 个人账入口
├── ledger.toml                 # 账套配置：账本清单、往来镜像、时区、本位币、利润分配
├── CATEGORIES.md               # 记账规则（记账口径依据）
├── CLASSIFY.md                 # 分类速查词典、参考依据与对照示例
├── STATE.md                    # 当前临时状态（失效即删）
├── AGENTS.md                   # AI 操作规范（CLAUDE.md / GEMINI.md 引用它）
├── common/
│   ├── commodities.beancount   # 币种声明
│   └── prices.beancount        # 外币、基金等价格
├── personal/
│   ├── accounts.beancount      # 个人会计科目表
│   ├── opening.beancount       # 期初余额
│   └── journal/YYYY-MM.beancount  # 按月序时簿（由脚本自动追加）
├── scripts/
│   ├── ledger.py               # 统一入口（入账/更正/作废/校验/查询/对账/格式化）
│   ├── bootstrap.py            # 环境准备：建 .venv、装依赖、校验账本
│   ├── hooks/pre-commit        # 提交前自动检查
│   └── ledgerlib/              # 实现与科目表模板
├── examples/
│   ├── cookbook.beancount      # AA、代垫、信用卡、退款、押金、贷款、基金、外币等写法
│   └── demo/                   # 个人账 + 店铺账的完整示例账套
├── docs/                       # 快速开始、使用指南、命令参考、常见问题
└── tests/                      # pytest 用例（在临时账套上跑，不碰真实账本）
```

用 `new-book` 新增的账本（如 `shop`）会多出一组同样结构的 `shop.beancount` 与 `shop/` 目录。

## 记账流程

1. 用口语描述收支：金额、事由、付款方式，没说的按 `CATEGORIES.md` 的默认规则补全；
2. AI 查看 `CATEGORIES.md` 与 `STATE.md`，把口语转成规范分录：必填日期、金额、科目、付款账户，标签按需；归类由 AI 自己定，**不反复问你"记在哪"**，只有金额、日期、是不是借出/代垫这类事实缺失才问；
3. 经 `ledger.py add` 入账，一次一笔：借贷不平衡、科目未开立、未来日期、疑似重复时整笔回滚；
4. AI 回报大类、金额、付款账户与标签，记错了一句话就能改（`amend` / `void`，不手改账本文件）；
5. 每次改动立即提交并推送到你的私有仓库（没有远程仓库的按 [NO-GIT](docs/NO-GIT.md) 备份到云盘）。

## 常用命令

完整清单与参数以 `python3 scripts/ledger.py --help` 为准，详细说明见 [命令与配置](docs/REFERENCE.md)：

```bash
python3 scripts/ledger.py check                        # 校验全部账本 + 跨账本往来对账
python3 scripts/ledger.py recent personal              # 最近 10 笔（行首 [编号]）
python3 scripts/ledger.py find personal 午餐 18        # 按关键词找分录
python3 scripts/ledger.py amend personal <编号>        # 更正：stdin 传入新分录替换这一笔
python3 scripts/ledger.py void personal <编号>         # 作废这一笔
python3 scripts/ledger.py summary personal 2026-09     # 按一级大类汇总
python3 scripts/ledger.py report personal 2026-09      # 月度收支 / 储蓄率分析
python3 scripts/ledger.py tag personal trip 2026-09    # 按标签查明细（如一趟旅行的总花费）
python3 scripts/ledger.py networth                     # 合并资产负债，外币金银基金股票按现价折算
python3 scripts/ledger.py quote USD AU F161226         # 现拉汇率、金价（每克）、基金净值
python3 scripts/ledger.py dividend 2026-09             # 合伙店铺按月利润分配
python3 scripts/ledger.py new-book shop --template business --link personal   # 新增店铺账
python3 scripts/ledger.py backup --daily               # 打包整个账套（含 Git 历史），存云盘用
```

## 核算要点

- **会计主体分离**：个人与店铺、家庭共同账各设一本账，账本之间的资金往来双边镜像登记，不确认收支；`reconcile` 核对两边相加为 0，`networth` 合并时自动抵销。
- **两级分类**：支出只分大类 + 小类（如 `Expenses:Food:Dining`），跟谁花的、哪趟行程交给标签（`#trip`、`#family`），摘要写清具体买了什么。
- **消费信贷**：花呗、白条、信用卡消费确认负债，还款冲减负债，不重复记支出。
- **退款与代垫**：退款冲减原支出，不算收入；借出、代垫挂往来，不算消费。
- **折现**：默认本位币 CNY，外币、加密币、黄金白银、基金、股票算总资产时自动现拉当天价格折算（拉不到用账内 `price`）；只记了金额的积存金按每笔当天金价估算克数和现值；养老金、医保个人账户取不出来，不计入净资产。
- **利润分配**：合伙店铺在 `ledger.toml` 配 `[dividend]` 比例，每月初跑 `dividend`，算出各方应得、已分配与本次实付。
- **店铺账只作内部管理**：店铺是注册主体的，对外纳税申报仍按税法与会计准则设账（可委托代理记账），这里的流水可以交给会计作依据。只记个人账的不用管这条。
- 完整分录范例见 [`examples/cookbook.beancount`](examples/cookbook.beancount)。

## 数据可靠性

三道把关，越往后越兜底：

1. **命令内**：`add` / `amend` / `void` / `fmt` 写盘后整本校验，不通过原样还原；
2. **提交前**：`scripts/hooks/pre-commit` 跑账本校验、往来对账与排版检查，改了脚本再跑 ruff 与 pytest；
3. **推送后**：GitHub Actions 把上面全部再跑一遍。

此外，入账守卫拒绝未来日期、估出来的时间、缺对方或摘要、内容相同的重复分录；Git 管理全部变更，可追溯、可 diff、可回滚。

## 更多文档

| 文档 | 内容 |
|---|---|
| [使用指南](docs/GUIDE.md) | 记账、改错、查账、对账时怎么跟 AI 说 |
| [命令与配置](docs/REFERENCE.md) | 全部命令、多本账、利润分配、`ledger.toml`、目录结构 |
| [常见问题](docs/FAQ.md) | 支持的 AI 工具、Windows、云环境、升级模板 |
| [更新日志](CHANGELOG.md) | 每个版本改了什么 |

## 致谢

记账引擎是 Martin Blais 开发的 [Beancount](https://github.com/beancount/beancount)（GPL-2.0），通过 pip 单独安装，不随本仓库分发。
