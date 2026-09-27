# 参与开发

请围绕“研究内容 → 可编辑图稿 → 可检查的导出”提交改进。与安装平台相关的变更请同时更新对应指南，并说明实际测试的系统、CPU 架构、Python、draw.io 与 PDF 后端版本。

```bash
python3 -m unittest discover -s tests -v
python3 scripts/drawio_render.py doctor --pdf-engine inkscape
python3 scripts/drawio_render.py self-test --output-dir diagrams/out
```

Windows 用 `python`。核心测试只需标准库；真实导出需本机 draw.io 和 Inkscape，Linux 还需 Xvfb/xauth。不要把 mock 测试通过写成真实平台导出通过。

修复安装问题时保留已存在的用户文件、备份语义、失败退出码和未测试状态。修改渲染器时验证 SVG 文本、PDF 外部转换路线和失败后不覆盖旧成品。新增格式或复杂标签支持时提供真实图稿与视觉检查结果。

不要提交本机 `config.json`、绝对用户路径、私人论文、账号信息或运行日志。通用示例应由贡献者自行创作，并具有明确的使用权。
