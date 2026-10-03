# beancount-ai-ledger

简体中文 | [English](README.en.md)

[![CI](https://github.com/Xbang0222/beancount-ai-ledger/actions/workflows/ci.yml/badge.svg)](https://github.com/Xbang0222/beancount-ai-ledger/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Xbang0222/beancount-ai-ledger)](https://github.com/Xbang0222/beancount-ai-ledger/releases)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](requirements.txt)
[![License](https://img.shields.io/github/license/Xbang0222/beancount-ai-ledger)](LICENSE)

用 AI 编程助手记账的 [Beancount](https://github.com/beancount/beancount) 账本模板。

你对 Claude Code、Codex 等 AI 助手说"午饭 18，微信付的"，它按仓库里的规则写成复式分录，脚本校验通过后写入账本并提交到 Git。账本是纯文本文件，保存在你自己的私有仓库里。不会用 Git、只用豆包的，账本可以存在自己的云盘里。

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

## 开始使用

| 你的情况 | 看这篇 |
|---|---|
| 在自己电脑上用 Claude Code、Codex 等 AI 编程助手，会用 Git | [快速开始：用 Git 保存账本](docs/QUICKSTART.md) |
| 只用豆包这类 AI，不会用 Git | [不用 Git：只用豆包记账](docs/NO-GIT.md) |

## 文档

| 文档 | 内容 |
|---|---|
| [使用指南](docs/GUIDE.md) | 记账、改错、查账、对账时怎么跟 AI 说 |
| [命令与配置](docs/REFERENCE.md) | `ledger.py` 的全部命令、多本账、`ledger.toml`、目录结构 |
| [常见问题](docs/FAQ.md) | 支持的 AI 工具、Windows、云环境、升级模板 |
| [更新日志](CHANGELOG.md) | 每个版本改了什么 |
| [`AGENTS.md`](AGENTS.md)、[`CATEGORIES.md`](CATEGORIES.md) | 给 AI 的操作规范和记账规则，建账后按你的习惯改 |

## 致谢

记账引擎是 Martin Blais 开发的 [Beancount](https://github.com/beancount/beancount)（GPL-2.0），通过 pip 单独安装，不随本仓库分发。
