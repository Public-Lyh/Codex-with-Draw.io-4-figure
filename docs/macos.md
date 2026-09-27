# macOS：安装与分步配置

使用原生 macOS 程序，支持 Intel/Apple Silicon 的路径发现。当前 Homebrew drawio cask 的系统要求应以 [官方 cask 页面](https://formulae.brew.sh/cask/drawio) 为准；初版以 macOS 13+ 为目标。此版本尚未在真实 Mac 上完成端到端验证。

## 交互式入口

在仓库根目录执行：

```bash
bash install/macos.sh
```

脚本会检测 Python 和 Homebrew，缺失时询问安装；Homebrew 首次安装可能需要 Command Line Tools、密码和额外时间。之后安装 draw.io、Inkscape、所选 Agent skill，并执行导出测试。不需要 Xvfb。

## 手动步骤

1. 按 [Homebrew 官网](https://brew.sh/) 的说明安装 Homebrew。已安装则跳过。确保新终端可以运行 `brew`。

2. 安装依赖。

```bash
brew install python
brew install --cask drawio inkscape
```

也可从各自官网安装应用。默认检测 `/Applications/draw.io.app/Contents/MacOS/draw.io` 与 `/Applications/Inkscape.app/Contents/MacOS/inkscape`，以及用户 `~/Applications`。非标准路径可以通过 `--drawio`、`--inkscape` 指定。

3. 在仓库根目录配置工作流。

```bash
python3 scripts/setup_workflow.py --skip-software --agents codex
```

按提示选择 Agent 和 PATH。多选使用 `--agents codex,claude,opencode`。如需要项目级 skill，添加 `--scope project --project /absolute/project/path`。

4. 重新打开终端和 Agent，然后检查。

```bash
drawio-render doctor --pdf-engine inkscape
drawio-render self-test --output-dir diagrams/out
```

未配置 PATH 时，使用 `~/.local/share/codex-drawio/bin/drawio-render`。查看安装目录下 `prompts/START-HERE.md` 与 `test-output/`，检查图中字体、文字和箭头。

## 可选 CairoSVG

```bash
brew install cairo libffi pkg-config
python3 scripts/setup_workflow.py --skip-software --pdf-engine cairosvg
```

Python 转换包安装到工作流独立 venv。若 Cairo 动态库无法加载，先检查 Homebrew 与 Python 的 CPU 架构是否一致。默认 Inkscape 更便于避免 Python 原生库配置问题。

macOS 可能阻止首次运行下载的应用，请在系统设置中按应用官方说明允许运行；不要批量关闭 Gatekeeper。关闭已经打开的 draw.io 后重试 CLI，具体诊断见 [排障](troubleshooting.md)。
