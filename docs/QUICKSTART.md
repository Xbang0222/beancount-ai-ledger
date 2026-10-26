# 快速开始：用 Git 保存账本

适合在自己电脑上用 Claude Code、Codex 这类 AI 编程助手的人。账本放在你自己的私有 Git 仓库里。
不会用 Git、只用豆包的，看[不用 Git：只用豆包记账](NO-GIT.md)。

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

AI 会先运行 `doctor` 检查环境，再按你的账户改科目表、登记期初余额，校验通过后提交。日常记账、改错、查账、对账怎么说，见 [使用指南](GUIDE.md)。

> [!TIP]
> 想先看效果，可以在示例账本上试命令，不用改任何文件：
>
> ```bash
> python3 scripts/ledger.py --root examples/demo report personal 2026-09
> python3 scripts/ledger.py --root examples/demo networth
> ```
