# Windows：安装与分步配置

面向 Windows 10/11 的原生 PowerShell，默认 Inkscape。需要可用的 winget（Microsoft App Installer）；缺失时可以手动安装软件后运行 Python 配置器。此版本尚未在真实 Windows 上完成端到端验证。

## 交互式入口

用 PowerShell 进入仓库根目录，执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install\windows.ps1
```

此选项只影响本次 PowerShell 进程。脚本检查 Python 3.10+，必要时安装 Python 3.12，然后检测/安装 draw.io 和 Inkscape，配置 skill、提示词并测试。软件安装可能触发 UAC；不要默认以另一位管理员身份运行整个工作流配置。

## 手动步骤

1. 安装依赖。已有软件可跳过对应命令。

```powershell
winget install --exact --id Python.Python.3.12 --source winget
winget install --exact --id JGraph.Draw --source winget
winget install --exact --id Inkscape.Inkscape --source winget
```

没有 winget 时，从 [Python](https://www.python.org/downloads/windows/)、[draw.io Desktop](https://github.com/jgraph/drawio-desktop/releases)、[Inkscape](https://inkscape.org/release/) 官方下载页安装。Python 安装时启用 launcher 或 PATH。安装后重新打开 PowerShell。

2. 在仓库根目录配置工作流。

```powershell
py -3 scripts/setup_workflow.py --skip-software --agents codex
```

如果 `py` 不可用，可用 `python` 或明确的 `python.exe` 路径。多个 Agent 用 `--agents 'codex,claude,opencode'`。项目级安装使用 `--scope project --project 'D:\Research\My Paper'`。

标准程序路径会自动检测；自定义安装位置可以显式传入：

```powershell
py -3 scripts/setup_workflow.py --skip-software --drawio 'D:\Apps\draw.io\draw.io.exe' --inkscape 'D:\Apps\Inkscape\bin\inkscape.exe'
```

3. 重新打开 PowerShell 和 Agent，运行验证。

```powershell
drawio-render doctor --pdf-engine inkscape
drawio-render self-test --output-dir diagrams/out
```

PATH 尚未生效时可直接运行：

```powershell
& "$env:LOCALAPPDATA\CodexDrawio\bin\drawio-render.cmd" doctor --pdf-engine inkscape
```

4. 打开 `%LOCALAPPDATA%\CodexDrawio\prompts\START-HERE.md`，填入论文材料交给 Agent，并检查 `test-output` 中的 PNG、SVG、PDF。安装后的提示词使用 Python 绝对路径，方便绕过 PATH 或 CMD 字符编码问题。

## CairoSVG 与 WSL

可选 `--pdf-engine cairosvg`，但 Windows 必须先配置 Python 能加载的原生 Cairo DLL；仅 `pip install cairosvg` 不一定足够。优先使用默认 Inkscape。详见 [CairoSVG 官方依赖说明](https://cairosvg.org/documentation/)。

WSL 是另一套 Linux 环境：在其中运行 `bash install/linux.sh`，使用 Linux 版 draw.io、Inkscape 与 Xvfb。不要把原生 Windows 的配置路径直接搬进 WSL。
