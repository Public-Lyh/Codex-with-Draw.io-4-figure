#!/usr/bin/env python3
"""Interactive user-local setup shared by the three platform entrypoints."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import venv

from drawio_render import RenderError, executable

REPO = Path(__file__).resolve().parent.parent
SKILL = "drawio-paper-figures"
AGENTS = ("codex", "claude", "opencode")
MARKER = ".codex-drawio-install.json"
PACKAGE_TIMEOUT = 1200


def ask(question: str, default: bool = True, yes: bool = False) -> bool:
    if yes:
        print(f"{question} -> yes (--yes)")
        return True
    if not sys.stdin.isatty():
        raise RenderError("交互安装需要终端。自动化运行请显式传 --yes 和所需选项。")
    while True:
        reply = input(question + (" [Y/n] " if default else " [y/N] ")).strip().lower()
        if not reply:
            return default
        if reply in ("y", "yes", "是"):
            return True
        if reply in ("n", "no", "否"):
            return False
        print("请输入 y 或 n。")


def choose(question: str, default: str, allowed: tuple[str, ...], yes: bool) -> str:
    if yes:
        return default
    if not sys.stdin.isatty():
        raise RenderError("交互安装需要终端；自动化请使用 --yes。")
    while True:
        answer = input(f"{question} ({'/'.join(allowed)}) [{default}]: ").strip().lower() or default
        if answer in allowed:
            return answer
        print("请选择列出的选项。")


def run(command: list[str], timeout: int = PACKAGE_TIMEOUT) -> None:
    print("+ " + subprocess.list2cmdline([str(x) for x in command]), flush=True)
    subprocess.run(command, check=True, timeout=timeout)


def fetch(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "Codex-with-Draw.io-4-figure/0.1"})
    with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as stream:
        shutil.copyfileobj(response, stream)


def privilege() -> list[str]:
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return []
    if not shutil.which("sudo"):
        raise RenderError("安装系统软件需要 sudo。请管理员按平台手动指南安装依赖后重新运行。")
    return ["sudo"]


def linux_packages(packages: list[str]) -> None:
    sudo = privilege()
    if shutil.which("apt-get"):
        run([*sudo, "apt-get", "update"])
        run([*sudo, "apt-get", "install", "-y", *packages])
    elif shutil.which("dnf"):
        translations = {"xvfb": "xorg-x11-server-Xvfb", "xauth": "xorg-x11-xauth",
                        "libcairo2": "cairo", "fonts-liberation": "liberation-fonts"}
        run([*sudo, "dnf", "install", "-y", *[translations.get(p, p) for p in packages]])
    else:
        raise RenderError("Linux 自动安装支持 apt/dnf；其他发行版请按 docs/linux.md 先安装依赖。")


def brew(yes: bool) -> str:
    candidate = shutil.which("brew")
    if candidate:
        return candidate
    for path in ("/opt/homebrew/bin/brew", "/usr/local/bin/brew"):
        if Path(path).is_file():
            return path
    if not ask("未找到 Homebrew，是否运行 Homebrew 官方安装程序？", yes=yes):
        raise RenderError("请手动安装 Draw.io/Inkscape 后重新运行；参见 docs/macos.md。")
    with tempfile.TemporaryDirectory(prefix="drawio-brew-") as temp:
        script = Path(temp) / "install.sh"
        fetch("https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh", script)
        run(["/bin/bash", str(script)])
    for path in ("/opt/homebrew/bin/brew", "/usr/local/bin/brew"):
        if Path(path).is_file():
            return path
    raise RenderError("Homebrew 安装未完成；请查看上方输出后重试。")


def winget(package: str) -> None:
    binary = shutil.which("winget")
    if not binary:
        raise RenderError("未找到 winget；请更新 Microsoft App Installer，或按 docs/windows.md 手动安装。")
    run([binary, "install", "--exact", "--id", package, "--source", "winget",
         "--accept-source-agreements", "--accept-package-agreements", "--disable-interactivity"])


def install_drawio_linux(version: str) -> None:
    machine = platform.machine().lower()
    architecture = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(machine)
    if not architecture:
        raise RenderError(f"尚未提供此 CPU 的自动安装：{machine}。请手动安装 Draw.io。")
    if version != "latest" and not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise RenderError("Draw.io 版本应为 latest 或数字版本，如 31.5.2。")
    extension = "deb" if shutil.which("apt-get") else "rpm" if shutil.which("dnf") else None
    if not extension:
        raise RenderError("自动安装支持 apt/dnf；其他发行版可自行安装官方 AppImage 后指定 --drawio。")
    endpoint = "https://api.github.com/repos/jgraph/drawio-desktop/releases/"
    endpoint += "latest" if version == "latest" else "tags/v" + version
    with tempfile.TemporaryDirectory(prefix="drawio-download-") as temp:
        directory = Path(temp)
        metadata_path = directory / "release.json"
        fetch(endpoint, metadata_path)
        release = json.loads(metadata_path.read_text(encoding="utf-8"))
        tag = release["tag_name"].removeprefix("v")
        if not re.fullmatch(r"\d+\.\d+\.\d+", tag):
            raise RenderError("上游 release 版本格式异常。")
        asset_arch = architecture if extension == "deb" else {"amd64": "x86_64", "arm64": "aarch64"}[architecture]
        expected = f"drawio-{asset_arch}-{tag}.{extension}"
        asset = next((a for a in release.get("assets", []) if a["name"] == expected), None)
        if not asset:
            raise RenderError(f"该 release 无 {expected}；请从官方 releases 选择本机安装包。")
        url = asset["browser_download_url"]
        if not url.startswith("https://github.com/jgraph/drawio-desktop/releases/download/"):
            raise RenderError("拒绝非官方 Draw.io release 下载地址。")
        package = directory / expected
        print(f"下载官方 Draw.io {tag} ({architecture})")
        fetch(url, package)
        digest = asset.get("digest") or ""
        if digest.startswith("sha256:"):
            actual = hashlib.sha256(package.read_bytes()).hexdigest()
            if actual != digest.split(":", 1)[1]:
                raise RenderError("Draw.io 安装包 SHA-256 校验失败。")
            print("上游 SHA-256 校验通过。")
        else:
            print("此 release 未公布 API SHA-256；下载来源为官方 HTTPS release。")
        # APT drops privileges to _apt when reading local packages.
        directory.chmod(0o755)
        package.chmod(0o644)
        manager = "apt-get" if extension == "deb" else "dnf"
        run([*privilege(), manager, "install", "-y", str(package)])


def ensure_software(args, pdf_engine: str) -> tuple[str, str | None]:
    binary = executable("drawio", args.drawio or os.environ.get("DRAWIO_BIN"))
    if binary:
        print(f"复用 Draw.io: {binary}")
    else:
        if not ask("未找到 Draw.io，是否从官方软件源安装？", yes=args.yes):
            raise RenderError("缺少 Draw.io；安装中止。可使用 --drawio 指定已有程序。")
        if sys.platform.startswith("linux"):
            install_drawio_linux(args.drawio_version)
        elif sys.platform == "darwin":
            run([brew(args.yes), "install", "--cask", "drawio"])
        else:
            winget("JGraph.Draw")
        binary = executable("drawio", args.drawio or os.environ.get("DRAWIO_BIN"))
        if not binary:
            raise RenderError("安装后仍找不到 Draw.io；请重新打开终端或用 --drawio 指定程序绝对路径。")
    if sys.platform.startswith("linux"):
        missing = [pkg for cmd, pkg in (("xvfb-run", "xvfb"), ("xauth", "xauth")) if not shutil.which(cmd)]
        if missing:
            if not ask("安装无桌面导出依赖 " + ", ".join(missing) + "？", yes=args.yes):
                raise RenderError("缺少 Xvfb/xauth，安装中止。")
            linux_packages(missing + ["fonts-liberation"])
    converter = executable("inkscape", args.inkscape or os.environ.get("INKSCAPE_BIN")) if pdf_engine == "inkscape" else None
    if pdf_engine == "inkscape" and not converter:
        if not ask("安装 Inkscape，用于 SVG → PDF 转换？", yes=args.yes):
            raise RenderError("未安装所选 PDF 后端；可用 --pdf-engine none 仅安装 PNG/SVG 流程。")
        if sys.platform.startswith("linux"):
            linux_packages(["inkscape"])
        elif sys.platform == "darwin":
            run([brew(args.yes), "install", "--cask", "inkscape"])
        else:
            winget("Inkscape.Inkscape")
        converter = executable("inkscape", args.inkscape or os.environ.get("INKSCAPE_BIN"))
        if not converter:
            raise RenderError("安装后未找到 Inkscape；用 --inkscape 指定可执行文件。")
    if pdf_engine == "cairosvg":
        if sys.platform.startswith("linux"):
            import ctypes.util
            if not ctypes.util.find_library("cairo"):
                if not ask("安装 CairoSVG 所需的系统 Cairo 库？", yes=args.yes):
                    raise RenderError("缺少 Cairo 系统库。")
                linux_packages(["libcairo2"])
        elif sys.platform == "darwin":
            run([brew(args.yes), "install", "cairo", "pkg-config"])
        else:
            print("Windows CairoSVG 需要已安装并可加载的 Cairo DLL；推荐 Inkscape。")
            if not ask("继续使用已经配置好的 Windows Cairo 环境？", default=False, yes=args.yes):
                raise RenderError("请用 --pdf-engine inkscape 重新运行。")
    return binary, converter


def skill_locations(agents: list[str], scope: str, project: Path | None) -> list[Path]:
    if scope == "project":
        if project is None:
            raise RenderError("项目级安装必须提供 --project /absolute/path。")
        roots = {"codex": project / ".agents/skills", "claude": project / ".claude/skills",
                 "opencode": project / ".opencode/skills"}
    else:
        config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        roots = {"codex": Path.home() / ".agents/skills", "claude": Path.home() / ".claude/skills",
                 "opencode": config_home / "opencode/skills"}
    return [roots[agent] / SKILL for agent in agents]


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'" if os.name == "nt" else shlex.quote(value)


def make_launcher(prefix: Path, python: Path) -> Path:
    directory = prefix / "bin"
    directory.mkdir(exist_ok=True)
    script = prefix / "scripts/drawio_render.py"
    if os.name == "nt":
        command = directory / "drawio-render.cmd"
        # Relative ASCII paths work even when the user profile contains Unicode.
        command.write_bytes(b'@echo off\r\nsetlocal DisableDelayedExpansion\r\n"%~dp0..\\venv\\Scripts\\python.exe" "%~dp0..\\scripts\\drawio_render.py" %*\r\nexit /b %errorlevel%\r\n')
    else:
        command = directory / "drawio-render"
        command.write_text("#!/bin/sh\nexec " + shlex.quote(str(python)) + " " + shlex.quote(str(script)) + ' "$@"\n', encoding="utf-8")
        command.chmod(0o755)
    return command


def add_path(directory: Path) -> list[str]:
    if os.name == "nt":
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            try:
                old, kind = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                old, kind = "", winreg.REG_EXPAND_SZ
            if str(directory).casefold() not in [p.rstrip("\\").casefold() for p in old.split(";")]:
                winreg.SetValueEx(key, "Path", 0, kind, str(directory) + (";" + old if old else ""))
        # Notify Explorer so terminals launched afterwards inherit the new PATH.
        import ctypes
        result = ctypes.c_size_t()
        ctypes.windll.user32.SendMessageTimeoutW(
            0xFFFF, 0x001A, 0, ctypes.c_wchar_p("Environment"), 2, 2000, ctypes.byref(result)
        )
        return ["HKCU/Environment/Path"]
    shell = Path(os.environ.get("SHELL", "/bin/bash")).name
    files = [Path.home() / ".zshrc", Path.home() / ".zprofile"] if shell == "zsh" else [Path.home() / ".bashrc", Path.home() / ".profile"]
    marker = "# >>> Codex-with-Draw.io-4-figure >>>"
    block = marker + "\nexport PATH=" + shlex.quote(str(directory)) + ':"$PATH"\n# <<< Codex-with-Draw.io-4-figure <<<\n'
    changed = []
    for path in files:
        old = path.read_text(encoding="utf-8") if path.exists() else ""
        pattern = r"# >>> Codex-with-Draw.io-4-figure >>>\n.*?# <<< Codex-with-Draw.io-4-figure <<<\n?"
        new = re.sub(pattern, lambda _: block, old, flags=re.S) if marker in old else old + "\n" + block
        if new != old:
            path.write_text(new, encoding="utf-8")
            changed.append(str(path))
    return changed


def backup_and_copy(source: Path, destination: Path) -> None:
    if destination.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        destination.rename(destination.with_name(destination.name + ".backup-" + stamp))
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="Accept installation prompts for the selected components")
    parser.add_argument("--prefix", type=Path)
    parser.add_argument("--agents", help="Comma-separated codex,claude,opencode; or none")
    parser.add_argument("--scope", choices=("user", "project"), default="user")
    parser.add_argument("--project", type=Path)
    parser.add_argument("--pdf-engine", choices=("inkscape", "cairosvg", "none"))
    parser.add_argument("--drawio")
    parser.add_argument("--inkscape")
    parser.add_argument("--drawio-version", default="latest", help="Linux download version; existing installations are reused")
    parser.add_argument("--no-sandbox", action="store_true", help="Use draw.io --no-sandbox for this workflow only")
    parser.add_argument("--add-to-path", action="store_true")
    parser.add_argument("--skip-path", action="store_true")
    parser.add_argument("--skip-test", action="store_true")
    parser.add_argument("--skip-software", action="store_true", help="Only configure workflow files; do not install system applications")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 10):
        parser.error("Python 3.10+ is required.")
    if sys.platform not in ("linux", "darwin", "win32"):
        parser.error("Supported operating systems: Linux, macOS, Windows.")
    try:
        default_prefix = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "CodexDrawio" if os.name == "nt" else Path.home() / ".local/share/codex-drawio"
        prefix = (args.prefix or default_prefix).expanduser().resolve()
        if prefix == REPO or REPO in prefix.parents or prefix in REPO.parents or prefix == Path.home().resolve():
            raise RenderError("请使用仓库外的专用安装目录，例如 ~/.local/share/codex-drawio；不能直接使用家目录。")
        if prefix.exists() and any(prefix.iterdir()) and not (prefix / MARKER).is_file():
            raise RenderError(f"目标目录非空且不是本项目的安装目录：{prefix}")
        engine = args.pdf_engine or choose("PDF 转换方式", "inkscape", ("inkscape", "cairosvg", "none"), args.yes)
        selected = args.agents
        if selected is None:
            if not args.yes and not sys.stdin.isatty():
                raise RenderError("交互安装需要终端；自动化请使用 --yes。")
            selected = "codex" if args.yes else input("安装到哪些 Agent？逗号分隔 codex,claude,opencode，或 none [codex]: ").strip() or "codex"
        agents = [] if selected == "none" else list(dict.fromkeys(x.strip() for x in selected.split(",")))
        if any(agent not in AGENTS for agent in agents):
            raise RenderError("Agent 仅支持 codex,claude,opencode 或 none。")
        project = args.project.expanduser().resolve() if args.project else None
        destinations = skill_locations(agents, args.scope, project)
        print(f"\n工作流目录: {prefix}\nPDF: {engine}\nAgent: {', '.join(agents) or 'none'}")
        print("只安装绘图依赖与本项目 skill/提示词；Agent 登录仍由用户完成。")
        for destination in destinations:
            print(f"Skill: {destination}")
        if not ask("按以上设置安装？已有同名 skill 会先备份。", yes=args.yes):
            return 0
        if args.skip_software:
            binary = executable("drawio", args.drawio or os.environ.get("DRAWIO_BIN"))
            converter = executable("inkscape", args.inkscape or os.environ.get("INKSCAPE_BIN")) if engine == "inkscape" else None
        else:
            binary, converter = ensure_software(args, engine)
        prefix.mkdir(parents=True, exist_ok=True)
        marker = prefix / MARKER
        marker.write_text(json.dumps({"project": "Codex-with-Draw.io-4-figure", "status": "installing"}) + "\n", encoding="utf-8")
        for name in ("scripts", "examples", "prompts", "skills"):
            backup_and_copy(REPO / name, prefix / name)
        environment = prefix / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if engine == "cairosvg":
            run([str(python), "-m", "pip", "install", "cairosvg>=2.7,<3"])
            # Import verifies the native Cairo library too, unlike find_spec().
            run([str(python), "-c", "import cairosvg; print('CairoSVG', cairosvg.__version__)"])
        config = {"drawio": binary, "inkscape": converter,
                  "pdf_engine": "auto" if engine == "none" else engine,
                  "no_sandbox": args.no_sandbox}
        (prefix / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        launcher = make_launcher(prefix, python)
        direct = ("& " if os.name == "nt" else "") + shell_quote(str(python)) + " " + shell_quote(str(prefix / "scripts/drawio_render.py"))
        installation = ("# Local installation\n\nUse this exact command in the local shell:\n\n```" +
                        ("powershell" if os.name == "nt" else "bash") + "\n" + direct + " doctor\n" + direct +
                        " input.drawio output.svg svg 1\n```\n\nPDF backend: " + engine +
                        ".\nThe runtime and examples are copied to this installation; the original checkout may be moved.\n")
        for destination in destinations:
            if destination.resolve() in (REPO / "skills" / SKILL, prefix / "skills" / SKILL):
                raise RenderError("Skill 安装路径与源目录相同。")
            backup_and_copy(prefix / "skills" / SKILL, destination)
            (destination / "references/local-installation.md").write_text(installation, encoding="utf-8")
        template = (prefix / "prompts/paper-figure.zh.md").read_text(encoding="utf-8")
        generated = template.replace("{{RENDER_COMMAND}}", direct).replace("{{SKILL_PATH}}", str(destinations[0] / "SKILL.md") if destinations else str(prefix / "skills" / SKILL / "SKILL.md"))
        prompt_path = prefix / "prompts/START-HERE.md"
        prompt_path.write_text(generated, encoding="utf-8")
        change_path = not args.skip_path and (args.add_to_path or (not args.yes and ask("把绘图命令加入当前用户 PATH？", default=True)))
        path_changes = add_path(launcher.parent) if change_path else []
        report = {"project": "Codex-with-Draw.io-4-figure", "version": "0.1.0", "prefix": str(prefix),
                  "launcher": str(launcher), "skill_paths": [str(p) for p in destinations],
                  "path_changes": path_changes, "prompt": str(prompt_path), "status": "configured-not-tested"}
        marker.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if not args.skip_test:
            command = [str(python), str(prefix / "scripts/drawio_render.py"), "self-test", "--output-dir", str(prefix / "test-output")]
            if engine == "none":
                command.append("--skip-pdf")
            run(command, timeout=600)
            report["status"] = "render-tests-passed"
            marker.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("\n" + ("安装与渲染测试完成。" if not args.skip_test else "配置完成；你选择跳过测试，尚未验证绘图。"))
        print(f"命令: {launcher}\n提示词: {prompt_path}\n安装记录: {marker}")
        print("重新打开终端和 Agent，使 PATH/skill 被加载。请打开测试图检查文字、箭头和字体。")
        return 0
    except (RenderError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"\n安装未完成: {exc}\n保留了已安装组件；修复上述问题后可重新运行。参见对应平台指南与 docs/troubleshooting.md。", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
