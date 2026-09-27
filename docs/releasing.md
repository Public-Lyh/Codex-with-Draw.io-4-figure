# 发布到 GitHub

上传对象是本项目目录的公开源码与文档。原始 Word 对话、运行日志、用户路径配置和本机凭据不属于发布材料。

## 本地确认

1. 阅读 README 和三平台指南，核对项目名称、许可与维护者信息。当前使用 MIT License，版权归项目贡献者。
2. 运行 `python3 -m unittest discover -s tests -v`。在可用平台执行真实 `self-test` 并打开产物，将结果写入 `docs/validation.md`。
3. 检查待提交文件，确认没有 `config.json`、私人材料、缓存或安装环境。

## 创建仓库并推送

在 GitHub 创建名为 `Codex-with-Draw.io-4-figure` 的空仓库。以下操作由维护者在确认发布内容后执行；将远程地址换成自己创建的仓库地址。

```bash
git init -b main
git add README.md LICENSE THIRD_PARTY_NOTICES.md CONTRIBUTING.md .gitignore .gitattributes install scripts skills prompts examples docs tests .github
git diff --cached --stat
git diff --cached
git commit -m "Initial editable paper figure workflow"
# 将下面的占位地址替换为实际 GitHub 仓库地址
git remote add origin https://github.com/YOUR-ACCOUNT/Codex-with-Draw.io-4-figure.git
git push -u origin main
```

若已经初始化 Git，只需继续暂存、审查、提交。不要复制作者机器的账号或认证配置。发布后检查 Actions：单元测试自动运行；真实安装与渲染工作流通过 `workflow_dispatch` 手动触发。

## 首个版本的边界

在 Windows/macOS 原生验证完成前，保持 README 的“待验证”说明，不添加未经支持的全平台通过徽章。若发布早期版本，可标为预发布，并附上实测环境与已知限制。三平台真实成功后再更新验证矩阵。

建议在中文版内容确定后新增完整英文 README。英文 skill 已独立提供，无需等待 README 翻译才能安装使用。
