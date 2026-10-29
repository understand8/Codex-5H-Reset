# Contributing to Codex-5H-Reset

首先非常欢迎并感谢你为 **Codex-5H-Reset** 做出贡献！

本项目致力于打造一个高品质、零遥测隐私泄露、轻量现代的 **AI CLI 额度管家**。无论你是修复一个拼写错误、改进一个系统托盘交互、还是为新的 AI CLI（例如 Claude Code、Copilot CLI）编写 Provider 适配器，我们都热忱欢迎你的参与。

---

## 🛠 开发环境搭建

本项目采用纯标准库为主，辅助极少数轻量跨平台依赖（`pystray`, `Pillow`, `psutil`）：

```bash
# 1. 克隆仓库
git clone https://github.com/understand8/Codex-5H-Reset.git
cd Codex-5H-Reset

# 2. 安装开发与运行依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 3. 运行测试套件
python -m unittest discover -s tests -p "test_*.py"

# 4. 启动 GUI 进行本地调试
python main.py

# 5. 或启动无头守护进程模式
python main.py daemon
```

---

## 📐 架构设计与代码组织

```
Codex-5H-Reset/
├── codex_timer/
│   ├── core.py             # 纯无头调度引擎（无 GUI 依赖，支持 Linux/VPS/NAS）
│   ├── config.py           # 配置与多账号 Profile 管理
│   ├── webhooks.py         # 多渠道 Webhook 报警（钉钉、飞书、企微、Telegram、Server酱）
│   ├── cli.py              # 终端子命令 (daemon / status / check / send / profile)
│   ├── providers/          # 开放式 Provider 抽象架构
│   │   ├── base.py         # BaseRateLimitProvider 抽象接口
│   │   ├── codex.py        # Codex CLI 适配器（原生 JSON-RPC + 进程隔离沙箱）
│   │   └── claude.py       # Claude Code 适配器拓展骨架
│   └── gui/                # 跨平台现代化 Tkinter GUI
│       ├── app.py          # 主仪表盘（固定尺寸 800x635 Slate 现代主题）
│       ├── overlay.py      # 单行极简悬浮条（380x36 胶囊条，右键菜单，滚轮透明度，防出界）
│       └── tray.py         # 系统托盘与后台常驻管理
├── tests/                  # 自动化测试用例
├── scripts/                # 打包与自动化脚本 (build_exe.py)
└── main.py                 # 统一启动入口
```

---

## 🤝 贡献流程 (Pull Request Workflow)

1. **Fork 本仓库** 到你的 GitHub 个人账号。
2. 从 `main` 分支切出一条功能分支，分支命名遵循语义化规范：
   - 功能开发：`feat/your-feature-name`
   - 缺陷修复：`fix/issue-description`
   - 文档完善：`docs/improve-readme`
3. 提交代码时遵守简洁明了的 Commit 信息格式（Conventional Commits）：
   ```text
   feat: add webhook support for Discord
   fix: handle null reset timestamp in weekly window
   test: add test cases for multi-account profile switching
   ```
4. 确保所有单元测试 100% 通过：
   ```bash
   python -m unittest discover -s tests -p "test_*.py"
   ```
5. 提交 PR 并关联相关的 Issue。

---

## 🛡️ 零外网隐私遥测承诺（Zero-Telemetry Audit）

所有贡献的代码必须严格遵守 **零遥测与隐私保护原则**：
1. **绝不向任何作者个人服务器或非官方第三方云端发送请求**。
2. 所有额度探测必须直接在本地与目标 CLI 官方进程（或官方端点）进行隔离通信。
3. Webhook 通知必须完全由用户显式配置目标 URL，且仅在发生指定调度事件时由本地直接发往对应 Webhook 服务端。
