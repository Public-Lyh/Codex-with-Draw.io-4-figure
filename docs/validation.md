# 验证记录

日期：2026-09-26。版本：0.1.0 开发初版。

## 已完成的检查

| 检查 | 环境与结果 |
| --- | --- |
| Python 行为测试 | Python 3.11.14，15 项通过 |
| Bash 语法 | Linux/macOS 安装入口及 Bash 渲染入口通过 `bash -n` |
| 英文 skill 结构 | skill-creator 的 `quick_validate.py` 通过 |
| Linux 真实渲染 | Ubuntu 22.04.5 x86_64、Draw.io 24.7.17、Xvfb；PNG/SVG/PDF 通过 |
| 默认 PDF 路线 | Inkscape 1.1.2，`.drawio → SVG → PDF` 成功 |
| 可选 PDF 路线 | CairoSVG 2.9.1，`.drawio → SVG → PDF` 成功 |
| 隔离安装 | 在含空格的独立安装目录、含中文与空格的项目路径中通过 |
| 多 Agent 配置 | Codex / Claude Code / OpenCode 三份项目级 skill 成功生成；未更改真实账号配置 |
| 重复安装 | 从首次渲染失败恢复后重跑，成功备份既有资源、重新配置并通过真实导出 |
| 跳过测试 | `--skip-test --agents none --skip-path` 保持 `configured-not-tested`，未误标为测试通过 |
| 公开文件审查 | 未包含作者机器的用户路径或私人 DOCX；原始材料保留在仓库外 |

Linux 测试复用了现有 Draw.io；Inkscape 从发行版安装包解压到隔离临时目录，CairoSVG 装在独立 venv。没有修改已有服务器渲染器、系统软件或真实 Agent 配置。测试使用环境所需的显式 `--no-sandbox`。

最终自检产物：PNG 为 1786 × 472、44,325 bytes，并经 Pillow 完整解码；SVG 为 7,888 bytes；Inkscape PDF 为 16,306 bytes；CairoSVG PDF 为 16,312 bytes。字节数仅记录本次环境，不作为其他机器上的通过条件。

两种 PDF 均由 pypdf 读取为单页（669.75 × 177 pt），四个模块标签完整；经 Poppler 栅格化后与最终 PNG 一起目视检查，文字、三条箭头与边框可见，未发现明显重叠或裁字。该结论仅覆盖自带通用示例。

## 本轮修正的真实问题

- Draw.io 导出的 SVG 带标准外部 DOCTYPE；初版校验器误拒绝，现已允许标准声明并拒绝内部实体声明。
- `html=0` 配合 `whiteSpace=wrap` 在实测版本中仍会产生 SVG `foreignObject`。已将示例、skill 与提示词改为原生文本、显式换行；PDF 路线继续拦截含 HTML 的 SVG。
- 安装目录含空格、项目路径含中文，以及安装时通过环境变量指定转换器的场景已处理。失败导出不会覆盖已有成品。
- Draw.io 24.7.17 的 PNG 嵌入源图导出在本次测试中产生损坏的 zTXt CRC 和不完整尾部。已取消 PNG 的嵌入选项，保留独立 `.drawio`，并新增数据块 CRC 与结束标记检查；修正后完整解码通过。早期仅检查签名和尺寸的成功记录不足以验证 PNG，已由最终重跑结果替代。

## 尚未验证的边界

- 原生 Windows 和 macOS：安装脚本与手动方法已编写，尚未在对应系统完成软件安装、Agent 加载及真实导出。
- PowerShell 语法解析：本机无 PowerShell；尝试下载官方便携版遇到 TLS/超时，未完成 AST 解析。仓库的 Windows CI 配置了该检查，但尚未运行。
- Linux 全新系统上的 apt/dnf 自动安装路径未在此共享服务器执行；本轮实际安装使用 `--skip-software` 复用/指定依赖。
- 真实 Agent 的自动 skill 发现、复杂论文图、CJK/特殊字体和复杂公式，需要在具体使用环境继续验证。
- GitHub Actions 文件已经提供，但配置文件存在不等于 CI 已经通过。实际软件安装与渲染 CI 面向 Linux/macOS，Windows 原机安装仍需单独验证。

## 复核方法

```bash
python3 -m unittest discover -s tests -v
python3 scripts/drawio_render.py doctor --pdf-engine inkscape
python3 scripts/drawio_render.py self-test --output-dir diagrams/out
```

配置器安装后也会运行真实自检；成功报告位于新建的 `render-test-*` 目录。逐项检查 PNG/SVG/PDF 的实际内容；结构检查和文字抽取不能替代视觉检查。

要在隔离环境复核安装，可指定仓库外的临时 `--prefix` 和项目目录，选 `--scope project`、`--skip-path`，并按需要传入 `--drawio` / `--inkscape`。不要使用本记录中的产物大小作为跨平台断言。
