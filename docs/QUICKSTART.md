# 快速开始：以 Git 保存账本

- 适用对象：在本机使用 Claude Code、Codex 等 AI 编程助手的用户；账本存放在用户自己的私有 Git 仓库。
- 环境要求：Python 3.9 或更高版本、Git。
- 不使用 Git、只使用豆包的用户见[不使用 Git：通过豆包记账](NO-GIT.md)。

## 1 创建私有仓库

在本仓库页面点击 **Use this template** → **Create a new repository**，可见性选择 **Private**，然后克隆到本地。已安装 [GitHub CLI](https://cli.github.com/) 时可用一条命令完成：

```bash
gh repo create my-ledger --private --template Xbang0222/beancount-ai-ledger --clone
```

> [!WARNING]
> 账本包含收支与余额，须存放在私有仓库。不要 Fork：公开仓库的 Fork 同样公开。从银行、支付宝导出的原始账单不得提交，`.gitignore` 已忽略 `*.csv` 与 `*.xlsx`。

## 2 安装依赖

```bash
cd my-ledger
python3 scripts/bootstrap.py
```

脚本将 Beancount 安装到仓库的 `.venv`，并校验账本。此后直接执行 `python3 scripts/ledger.py`，入口自动使用 `.venv`。Windows 上将 `python3` 换为 `python` 或 `py`。

## 3 交由 AI 建账

在仓库目录打开 Claude Code、Codex 等工具，第一条消息说明账户与余额：

> 帮我初始化账本，从今天开始记。我有招商银行卡 5000、支付宝 1200、微信 800，信用卡欠 1500。平时没说怎么付的就算微信。

AI 先执行 `doctor` 检查环境，再按所述账户修改科目表、登记期初余额，校验通过后提交。日常记账、更正、查询、对账的表述方式见[使用指南](GUIDE.md)。

> [!TIP]
> 需要先了解效果时，可在示例账本上试用命令，不改动任何文件：
>
> ```bash
> python3 scripts/ledger.py --root examples/demo report personal 2026-09
> python3 scripts/ledger.py --root examples/demo networth
> ```
