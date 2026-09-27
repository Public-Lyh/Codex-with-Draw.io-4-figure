#!/usr/bin/env python3
"""Cross-platform draw.io export; PDF always passes through SVG.

The core uses only Python's standard library. CairoSVG is an optional backend.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
import zlib

VERSION = "0.1.0"
ROOT = Path(__file__).resolve().parent.parent
FORMATS = {"png", "svg", "pdf", "jpg"}


class RenderError(RuntimeError):
    pass


def read_config(path: str | None = None) -> dict:
    location = Path(path or os.environ.get("DRAWIO_FIGURE_CONFIG", ROOT / "config.json"))
    if not location.exists():
        return {}
    try:
        result = json.loads(location.read_text(encoding="utf-8"))
        if not isinstance(result, dict):
            raise ValueError("expected a JSON object")
        return result
    except (OSError, ValueError) as exc:
        raise RenderError(f"Invalid config {location}: {exc}") from exc


def executable(name: str, explicit: str | None = None) -> str | None:
    """Resolve actual executables, including installations outside PATH."""
    if explicit:
        found = shutil.which(explicit)
        if found:
            return str(Path(found).absolute())
        candidate = Path(explicit).expanduser()
        if candidate.is_file() and (os.name == "nt" or os.access(candidate, os.X_OK)):
            return str(candidate.absolute())
        raise RenderError(f"Executable not found: {explicit}")
    names = ("drawio", "draw.io", "draw.io.exe") if name == "drawio" else ("inkscape", "inkscape.exe")
    for entry in names:
        found = shutil.which(entry)
        if found:
            return str(Path(found).absolute())
    candidates: list[Path] = []
    if sys.platform == "darwin":
        app = "draw.io.app/Contents/MacOS/draw.io" if name == "drawio" else "Inkscape.app/Contents/MacOS/inkscape"
        candidates = [Path("/Applications") / app, Path.home() / "Applications" / app]
    elif os.name == "nt":
        relative = ("draw.io/draw.io.exe", "Programs/draw.io/draw.io.exe") if name == "drawio" else ("Inkscape/bin/inkscape.exe", "Programs/Inkscape/bin/inkscape.exe")
        for variable in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
            base = os.environ.get(variable)
            if base:
                candidates.extend(Path(base) / item for item in relative)
    else:
        candidates = [Path("/opt/drawio/drawio")] if name == "drawio" else []
    return next((str(p) for p in candidates if p.is_file()), None)


def clean_environment(work: Path) -> dict[str, str]:
    env = os.environ.copy()
    for key in ("LD_LIBRARY_PATH", "LD_PRELOAD", "GTK_MODULES", "ELECTRON_RUN_AS_NODE"):
        env.pop(key, None)
    env["DRAWIO_DISABLE_UPDATE"] = "true"
    if sys.platform.startswith("linux"):
        runtime = work / "runtime"
        runtime.mkdir(mode=0o700)
        env["XDG_RUNTIME_DIR"] = str(runtime)
        env["XDG_CONFIG_HOME"] = str(work / "config")
        env["XDG_CACHE_HOME"] = str(work / "cache")
        env["LIBGL_ALWAYS_SOFTWARE"] = "1"
        env.pop("DBUS_SESSION_BUS_ADDRESS", None)
        env.pop("DISPLAY", None)
    return env


def run_command(command: list[str], env: dict[str, str], timeout: float, log) -> None:
    log.write("COMMAND " + json.dumps(command, ensure_ascii=False) + "\n")
    log.flush()
    kwargs = {"start_new_session": True} if os.name != "nt" else {}
    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env, **kwargs)
    try:
        code = process.wait(timeout=timeout)
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            process.kill()
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait()
        raise RenderError(f"Export stopped (timeout {timeout:g}s or interruption). See the log.") from exc
    if code != 0:
        raise RenderError(f"Export command exited with status {code}. See the log.")


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def load_xml(path: Path) -> ET.Element:
    try:
        data = path.read_bytes()
        # draw.io exports a standard external SVG DTD. ElementTree does not
        # fetch external DTDs; internal subsets/entities are unnecessary here.
        if b"<!ENTITY" in data.upper() or re.search(br"<!DOCTYPE[^>]*\[", data, re.I):
            raise RenderError("DTD/entity declarations are not supported in diagram input.")
        return ET.fromstring(data)
    except (OSError, ET.ParseError) as exc:
        raise RenderError(f"Cannot read XML {path}: {exc}") from exc


def validate_artifact(path: Path, fmt: str) -> dict:
    if not path.is_file() or path.stat().st_size == 0:
        raise RenderError(f"No non-empty {fmt.upper()} was produced: {path}")
    with path.open("rb") as stream:
        header = stream.read(32)
    info = {"bytes": path.stat().st_size}
    if fmt == "png":
        if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
            raise RenderError("Output is not a PNG.")
        width, height = struct.unpack(">II", header[16:24])
        if not width or not height:
            raise RenderError("PNG has invalid dimensions.")
        info.update(width=width, height=height)
        # Some draw.io versions emit broken embedded-XML PNG chunks. A valid
        # signature/dimension pair must not turn those files into a success.
        saw_data = False
        saw_end = False
        with path.open("rb") as stream:
            stream.seek(8)
            while stream.tell() < info["bytes"]:
                chunk_header = stream.read(8)
                if len(chunk_header) != 8:
                    raise RenderError("PNG has a truncated chunk header.")
                length, kind = struct.unpack(">I4s", chunk_header)
                if length > info["bytes"] - stream.tell() - 4:
                    raise RenderError("PNG has a truncated chunk.")
                payload = stream.read(length)
                checksum = struct.unpack(">I", stream.read(4))[0]
                if zlib.crc32(kind + payload) & 0xFFFFFFFF != checksum:
                    raise RenderError("PNG chunk checksum failed; try a draw.io version without broken metadata export.")
                saw_data = saw_data or kind == b"IDAT"
                if kind == b"IEND":
                    saw_end = length == 0
                    break
        if not saw_data or not saw_end:
            raise RenderError("PNG is incomplete (missing image data or end marker).")
    elif fmt == "jpg" and header[:3] != b"\xff\xd8\xff":
        raise RenderError("Output is not a JPEG.")
    elif fmt == "pdf":
        if not header.startswith(b"%PDF-"):
            raise RenderError("Output is not a PDF.")
        with path.open("rb") as stream:
            stream.seek(max(0, path.stat().st_size - 2048))
            if b"%%EOF" not in stream.read():
                raise RenderError("PDF is incomplete (missing EOF marker).")
    elif fmt == "svg":
        if local_name(load_xml(path).tag) != "svg":
            raise RenderError("Output is not an SVG document.")
    return info


def check_pdf_svg(path: Path) -> None:
    root = load_xml(path)
    if any(local_name(node.tag) == "foreignObject" for node in root.iter()):
        raise RenderError(
            "SVG contains HTML labels (foreignObject), which external PDF converters can omit. "
            "Set html=0, remove whiteSpace=wrap, use explicit line breaks and plain text labels, and render again. "
            "The original diagram is not modified."
        )


def choose_pdf_engine(requested: str, config: dict) -> tuple[str, str | None]:
    if requested not in ("auto", "inkscape", "cairosvg"):
        raise RenderError(f"Unsupported PDF backend: {requested}")
    if requested in ("auto", "inkscape"):
        binary = executable("inkscape", os.environ.get("INKSCAPE_BIN") or config.get("inkscape"))
        if binary:
            return "inkscape", binary
        if requested == "inkscape":
            raise RenderError("Inkscape is missing. Install it or select --pdf-engine cairosvg.")
    if importlib.util.find_spec("cairosvg"):
        return "cairosvg", None
    raise RenderError("No SVG-to-PDF backend. Install Inkscape or CairoSVG; run the installer again.")


def drawio_command(binary: str, source: Path, target: Path, fmt: str,
                   scale: float, no_sandbox: bool) -> list[str]:
    command = [binary, "-x", "-f", fmt, "-s", str(scale), "-b", "10", "-o", str(target)]
    if fmt == "svg":
        command.append("-e")
    command.extend([str(source), "--disable-gpu"])
    if no_sandbox:
        command.append("--no-sandbox")
    if sys.platform.startswith("linux"):
        xvfb = shutil.which("xvfb-run")
        if not xvfb:
            raise RenderError("xvfb-run is missing. Install Xvfb and xauth (see docs/linux.md).")
        command = [xvfb, "-a", "--server-args=-screen 0 1280x1024x24", *command]
        # Raise only this subprocess's soft AS limit, and only if its hard limit allows it.
        import resource
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        prlimit = shutil.which("prlimit")
        if prlimit and soft != resource.RLIM_INFINITY and hard == resource.RLIM_INFINITY:
            command = [prlimit, "--as=unlimited:unlimited", "--", *command]
    return command


def render(source: Path, output: Path, *, fmt: str | None = None, scale: float = 2,
           config: dict | None = None, pdf_engine: str | None = None,
           drawio: str | None = None, timeout: float = 90, no_sandbox: bool = False) -> dict:
    config = config or {}
    source, output = source.expanduser().resolve(), output.expanduser().resolve()
    suffix = output.suffix.lower().lstrip(".").replace("jpeg", "jpg")
    fmt = (fmt or suffix).lower().replace("jpeg", "jpg")
    if fmt not in FORMATS or fmt != suffix:
        raise RenderError("Output suffix and format must agree: png, svg, pdf, jpg/jpeg.")
    if not math.isfinite(scale) or scale <= 0 or not math.isfinite(timeout) or timeout <= 0:
        raise RenderError("Scale and timeout must be finite positive numbers.")
    if not source.is_file():
        raise RenderError(f"Input file not found: {source}")
    if source == output:
        raise RenderError("Input and output must be different files.")
    root = load_xml(source)
    svg_input = local_name(root.tag) == "svg"
    if svg_input and fmt != "pdf":
        raise RenderError("SVG input is supported only for SVG-to-PDF conversion.")
    if not svg_input and local_name(root.tag) not in ("mxGraphModel", "mxfile"):
        raise RenderError("Input must be draw.io XML (mxGraphModel/mxfile) or SVG for PDF.")
    if local_name(root.tag) == "mxfile" and len(root.findall("diagram")) != 1:
        raise RenderError("This paper-figure workflow exports one page. Save the desired page separately.")
    engine, converter = choose_pdf_engine(pdf_engine or config.get("pdf_engine", "auto"), config) if fmt == "pdf" else (None, None)
    binary = None if svg_input else executable("drawio", drawio or os.environ.get("DRAWIO_BIN") or config.get("drawio"))
    if not svg_input and not binary:
        raise RenderError("draw.io Desktop not found. Run the platform installer or set DRAWIO_BIN.")
    output.parent.mkdir(parents=True, exist_ok=True)
    log_path = output.with_name(output.name + ".log")
    started = time.monotonic()
    with log_path.open("w", encoding="utf-8") as log, tempfile.TemporaryDirectory(prefix=".drawio-", dir=output.parent) as temp:
        work = Path(temp)
        env = clean_environment(work)
        staged = work / ("result." + fmt)
        try:
            svg = source if svg_input else work / "intermediate.svg"
            if not svg_input:
                target = svg if fmt == "pdf" else staged
                export_fmt = "svg" if fmt == "pdf" else fmt
                command = drawio_command(binary, source, target, export_fmt,
                                         1 if fmt == "pdf" else scale,
                                         no_sandbox or bool(config.get("no_sandbox")))
                run_command(command, env, timeout, log)
                validate_artifact(target, export_fmt)
            if fmt == "pdf":
                check_pdf_svg(svg)
                if engine == "inkscape":
                    command = [converter, str(svg), "--export-type=pdf", "--export-area-page",
                               "--export-filename=" + str(staged)]
                else:
                    command = [sys.executable, "-m", "cairosvg", str(svg), "-f", "pdf", "-o", str(staged)]
                run_command(command, env, timeout, log)
            info = validate_artifact(staged, fmt)
            os.replace(staged, output)
        except (OSError, RenderError) as exc:
            log.write("ERROR " + str(exc) + "\n")
            raise RenderError(f"{exc}\nLog: {log_path}") from exc
    return {"output": str(output), "format": fmt, "pdf_engine": engine,
            "log": str(log_path), "seconds": round(time.monotonic() - started, 3), **info}


def doctor(config: dict, pdf_engine: str | None = None) -> dict:
    result = {"workflow_version": VERSION, "platform": platform.platform(),
              "python": sys.executable, "python_version": platform.python_version(),
              "drawio": executable("drawio", os.environ.get("DRAWIO_BIN") or config.get("drawio")),
              "xvfb_run": shutil.which("xvfb-run") if sys.platform.startswith("linux") else "not required",
              "xauth": shutil.which("xauth") if sys.platform.startswith("linux") else "not required",
              "inkscape": executable("inkscape", os.environ.get("INKSCAPE_BIN") or config.get("inkscape")),
              "cairosvg_installed": importlib.util.find_spec("cairosvg") is not None,
              "no_sandbox": bool(config.get("no_sandbox"))}
    if sys.platform.startswith("linux"):
        import resource
        result["address_space_limits_bytes"] = list(resource.getrlimit(resource.RLIMIT_AS))
    if pdf_engine:
        try:
            result["pdf_engine"] = choose_pdf_engine(pdf_engine, config)[0]
        except RenderError as exc:
            result["pdf_error"] = str(exc)
    result["ready"] = bool(result["drawio"] and result["xvfb_run"] and result["xauth"] and not result.get("pdf_error"))
    return result


def self_test(output_dir: Path, config: dict, pdf: bool = True) -> dict:
    """Exercise real rendering, not just executable discovery."""
    output_dir.mkdir(parents=True, exist_ok=True)
    source = ROOT / "examples" / "pipeline.drawio"
    if not source.is_file():
        raise RenderError(f"Bundled test diagram missing: {source}")
    # A fresh directory prevents old artifacts from being mistaken for a pass.
    destination = Path(tempfile.mkdtemp(prefix="render-test-", dir=output_dir))
    outputs = []
    for fmt in (["png", "svg", "pdf"] if pdf else ["png", "svg"]):
        outputs.append(render(source, destination / ("pipeline." + fmt), config=config,
                              scale=2 if fmt == "png" else 1))
    svg = load_xml(destination / "pipeline.svg")
    labels = " ".join("".join(node.itertext()) for node in svg.iter() if local_name(node.tag) == "text")
    for expected in ("Input", "Encoder", "Prediction"):
        if expected not in labels:
            raise RenderError(f"SVG test label missing: {expected}. Inspect {destination}")
    check_pdf_svg(destination / "pipeline.svg")
    result = {"status": "passed", "directory": str(destination.resolve()),
              "formats_tested": [item["format"] for item in outputs], "outputs": outputs,
              "visual_review": "required: open the files and check labels, arrows and fonts"}
    (destination / "test-report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in ("render", "doctor", "self-test", "--help", "-h", "--version"):
        argv.insert(0, "render")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("render", help="Export .drawio; PDF uses an external SVG converter")
    p.add_argument("input", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("format", nargs="?", choices=sorted(FORMATS | {"jpeg"}))
    p.add_argument("scale", nargs="?", type=float, default=2)
    p.add_argument("--drawio")
    p.add_argument("--timeout", type=float, default=90)
    p.add_argument("--no-sandbox", action="store_true", help="Disable the draw.io Electron sandbox for this export only")
    for command in (p, commands.add_parser("doctor"), commands.add_parser("self-test")):
        command.add_argument("--config")
        command.add_argument("--pdf-engine", choices=("auto", "inkscape", "cairosvg"))
    commands.choices["self-test"].add_argument("--output-dir", type=Path, default=Path("diagrams/out"))
    commands.choices["self-test"].add_argument("--skip-pdf", action="store_true")
    args = parser.parse_args(argv)
    try:
        config = read_config(args.config)
        if args.pdf_engine:
            config["pdf_engine"] = args.pdf_engine
        if args.command == "render":
            result = render(args.input, args.output, fmt=args.format, scale=args.scale,
                            config=config, drawio=args.drawio, timeout=args.timeout,
                            no_sandbox=args.no_sandbox)
        elif args.command == "doctor":
            result = doctor(config, args.pdf_engine)
        else:
            result = self_test(args.output_dir.expanduser(), config, not args.skip_pdf)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ready", True) else 1
    except (RenderError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
