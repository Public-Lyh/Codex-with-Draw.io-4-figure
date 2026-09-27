# Linux：安装与分步配置

自动安装面向带 apt 的 Debian/Ubuntu、带 dnf 的 Fedora；Python 需 3.10+，建议从 Ubuntu 22.04+ 开始。其他发行版可手动安装依赖后使用共用配置器。无桌面服务器通过 Xvfb 导出，不需要浏览器或真实 X11 会话。

## 交互式入口

在仓库根目录执行：

```bash
bash install/linux.sh
```

系统应用使用 sudo 安装；工作流默认放当前用户目录。不要用 `sudo bash install/linux.sh`，否则 skill 会装到 root 用户。

## 手动步骤

1. 安装 Python、虚拟显示、字体与 PDF 转换器。

```bash
# Debian / Ubuntu
sudo apt-get update
sudo apt-get install -y python3 python3-venv xvfb xauth inkscape fonts-liberation fonts-noto-cjk
# Fedora：改用以下命令
# sudo dnf install -y python3 python3-pip xorg-x11-server-Xvfb xorg-x11-xauth inkscape liberation-fonts google-noto-sans-cjk-fonts
```

2. 从 [draw.io Desktop 官方 releases](https://github.com/jgraph/drawio-desktop/releases) 下载匹配 CPU 的 `.deb` 或 `.rpm`。示例中的本地文件路径需替换为实际下载路径。

```bash
sudo apt-get install /absolute/path/to/drawio-package.deb
# Fedora：sudo dnf install /absolute/path/to/drawio-package.rpm
```

无管理员权限时可让管理员安装 Xvfb/xauth，自己使用官方 AppImage，并通过 `--drawio /absolute/path/to/AppImage` 指定。AppImage 需要执行权限及相应 FUSE 运行条件；也可按其说明解包后指向内部可执行文件。

3. 在仓库根目录配置 skill、提示词与命令。可选择多个 Agent。

```bash
python3 scripts/setup_workflow.py --skip-software --agents codex,claude,opencode
```

不想安装任何 Agent skill 时选 `--agents none`。仅在一个项目启用时添加 `--scope project --project /absolute/project/path`。Codex 使用 `.agents/skills`，Claude Code 使用 `.claude/skills`，OpenCode 使用 `.opencode/skills`。

4. 重新打开终端和 Agent，验证安装。

```bash
drawio-render doctor --pdf-engine inkscape
drawio-render self-test --output-dir diagrams/out
```

如果 PATH 尚未配置，使用 `~/.local/share/codex-drawio/bin/drawio-render`。安装时已经运行相同的真实导出测试，手动再测用于排障或环境变更后复核。

5. 打开打印出的 `prompts/START-HERE.md`，填入论文材料，交给 Agent。测试图位于安装目录 `test-output/render-test-*`；请检查导出图片和 PDF。

## 可选 CairoSVG

```bash
sudo apt-get install -y libcairo2
python3 scripts/setup_workflow.py --skip-software --pdf-engine cairosvg
```

Python 包安装到工作流自己的 venv。若系统没有兼容的二进制 wheel，按 CairoSVG 官方说明安装编译器、Python/FFI 开发头文件。默认 Inkscape 路线无需这些 Python 转换依赖。

出现 Electron sandbox 错误时，先检查日志。确需兼容服务器环境时可显式添加 `--no-sandbox`，该选项仅配置本工作流的导出进程。不要将历史排障中的系统级 AppArmor 或资源限制改动直接复制到所有机器。
