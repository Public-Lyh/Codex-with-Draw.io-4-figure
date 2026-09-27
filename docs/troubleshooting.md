# 故障排查与维护

先看报错中指出的 `<输出文件名>.log`，再运行 `drawio-render doctor --pdf-engine inkscape`。导出失败不会用已有旧文件冒充成功，也不会覆盖旧成品。成功退出表示通过结构检查，仍需目视检查复杂图片。

| 现象 | 处理 |
| --- | --- |
| 找不到 drawio-render | 重新打开终端，或使用安装器打印的完整路径；检查是否选择加入 PATH |
| 找不到 Draw.io / Inkscape | 安装应用后重开终端，或重跑安装器并传 `--drawio` / `--inkscape` 绝对路径 |
| 安装时要求终端 | 交互模式需要真实终端；自动化使用明确的 `--yes` 与选项 |
| Linux xvfb-run/xauth 缺失 | 安装 Xvfb 和 xauth；WSL 同样需要 Linux 依赖 |
| Electron sandbox 报错 | 先确认安装及权限；确需兼容时显式添加 `--no-sandbox`，不全局关闭系统防护 |
| mmap / V8 地址空间预留失败 | 查看 doctor 的 address_space_limits_bytes；虚拟地址空间限制不同于实际内存占用。包装器仅在硬限制允许时提高子进程软限制，不修改整机配置 |
| 超时、无文件 | 关闭已有 draw.io 窗口后重试，检查日志；复杂图可用 `--timeout 180`；不要无限重复同一命令 |
| PDF 提示 foreignObject | 源图使用了 HTML 标签；将文字改为 `html=0` 原生文本并禁用 `whiteSpace=wrap` 自动换行后重新导出。不要忽略错误继续转 PDF |
| 中文方框、字体变化 | 安装所用字体，例如 Linux 的 Noto CJK；重导出并同时检查 PNG 和 PDF |
| CairoSVG 无法导入 | 它同时依赖 Python 包和原生 Cairo；优先切回 Inkscape，或按官方文档配置原生库 |
| 多页输入被拒绝 | 本工作流每文件一图；在 draw.io 中把目标页另存为单页源文件 |
| PNG 校验失败或看图软件打不开 | 查看日志并升级/更换 draw.io 版本。包装器默认不在 PNG 中嵌入 XML，以避开实测旧版的损坏元数据问题；源文件另外保留 |

## 命令与路径

路径中存在空格时加引号。PowerShell 调用引号中的可执行路径要加 `&`。中文用户目录遇到 CMD 编码问题时，使用 `START-HERE.md` 给出的 Python 绝对路径命令。

环境变量 `DRAWIO_BIN`、`INKSCAPE_BIN` 可覆盖应用位置；`DRAWIO_FIGURE_CONFIG` 指向 JSON 配置文件。安装目录的 `config.json` 保存 `drawio`、`inkscape`、`pdf_engine`、`no_sandbox`。不需要编辑 Agent 的认证或模型配置。

Linux 渲染进程会隔离 XDG 缓存目录，清理可能由 Conda/编辑器注入的动态库变量。原有 shell 环境保持不变。若你的自定义 AppImage/转换器确实依赖动态库搜索路径，请使用一个显式设置自身依赖的包装脚本，再通过 `--drawio` 或 `--inkscape` 指向它。

## 重新安装、备份与移除

用相同入口和 `--prefix` 重跑即可重新配置。已有 skill 与工作流资源目录会改名为 `.backup-时间戳` 后再复制新版；备份可自行审查、恢复或删除。修改过的提示词应另存至项目目录，以免更新后继续使用旧路径。

卸载本项目工作流时，先阅读安装目录内 `.codex-drawio-install.json`，确认记录的安装目录、skill 路径和 PATH 文件。删除本项目专用目录与对应 skill；若需要恢复旧 skill，将相应备份目录改回原名。Linux/macOS 从 shell 配置中移除 `codex-drawio` 标记块；Windows 在用户环境变量 PATH 中移除该安装目录的 `bin`。

Draw.io、Inkscape、Python 等可能还被其他项目使用，按需通过原软件管理器单独卸载。请勿删除整个 `.agents`、`.claude` 或 `.config` 目录。

## 历史部署与通用安装的区别

早期服务器调试可能涉及特定版本、系统资源限制或权限设置；它们不是所有电脑的安装前提。此仓库不创建专用 Linux 账号、不配置 SSH 或多人共享 Agent、不假设 Mermaid 转换工具已安装，也不把未经当前版本验证的自动布局参数写入默认流程。
