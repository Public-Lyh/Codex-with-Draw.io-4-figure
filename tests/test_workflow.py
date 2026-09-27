"""Regression tests for export integrity and user-local installation boundaries."""
import io
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import drawio_render as renderer
import setup_workflow as setup

SVG = b'<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd"><svg xmlns="http://www.w3.org/2000/svg"><text>Encoder</text></svg>'
PDF = b"%PDF-1.5\nexample for command-routing test\n%%EOF\n"


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="drawio test ")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.source = self.directory / "研究 input.drawio"
        self.source.write_text('<mxfile><diagram><mxGraphModel><root/></mxGraphModel></diagram></mxfile>', encoding="utf-8")

    def test_standard_svg_doctype_and_native_text(self):
        svg = self.directory / "figure.svg"
        svg.write_bytes(SVG)
        renderer.validate_artifact(svg, "svg")
        renderer.check_pdf_svg(svg)

    def test_png_rejects_corrupt_chunks_and_missing_end(self):
        def chunk(kind, payload):
            return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

        header = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        data = chunk(b"IDAT", zlib.compress(b"\x00\xff\xff\xff"))
        png = self.directory / "figure.png"
        png.write_bytes(header + data + chunk(b"IEND", b""))
        self.assertEqual(renderer.validate_artifact(png, "png")["width"], 1)
        png.write_bytes(header + data)
        with self.assertRaisesRegex(renderer.RenderError, "incomplete"):
            renderer.validate_artifact(png, "png")
        png.write_bytes(header + data[:-1] + bytes([data[-1] ^ 1]) + chunk(b"IEND", b""))
        with self.assertRaisesRegex(renderer.RenderError, "checksum"):
            renderer.validate_artifact(png, "png")

    def test_internal_entities_and_html_pdf_labels_rejected(self):
        svg = self.directory / "figure.svg"
        svg.write_bytes(b'<!DOCTYPE svg [<!ENTITY x "x">]><svg/>')
        with self.assertRaises(renderer.RenderError):
            renderer.load_xml(svg)
        svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"><foreignObject><div>Lost text</div></foreignObject></svg>')
        with self.assertRaisesRegex(renderer.RenderError, "HTML labels"):
            renderer.check_pdf_svg(svg)

    def test_format_and_numerical_arguments_rejected_before_execution(self):
        for arguments in ({"fmt": "svg"}, {"scale": 0}, {"scale": float("nan")}, {"timeout": -1}):
            with self.subTest(arguments=arguments), self.assertRaises(renderer.RenderError):
                renderer.render(self.source, self.directory / "figure.png", **arguments)

    def test_multipage_input_rejected(self):
        self.source.write_text('<mxfile><diagram/><diagram/></mxfile>')
        with self.assertRaisesRegex(renderer.RenderError, "one page"):
            renderer.render(self.source, self.directory / "figure.png")

    def test_failed_export_preserves_previous_artifact_and_logs_error(self):
        target = self.directory / "figure.png"
        target.write_bytes(b"previous valid user result")
        with patch.object(renderer, "executable", return_value="drawio"), patch.object(renderer, "drawio_command", return_value=["drawio"]), patch.object(renderer, "run_command", side_effect=renderer.RenderError("renderer failed")):
            with self.assertRaisesRegex(renderer.RenderError, "renderer failed"):
                renderer.render(self.source, target)
        self.assertEqual(target.read_bytes(), b"previous valid user result")
        self.assertIn("renderer failed", Path(str(target) + ".log").read_text())
        self.assertEqual(list(self.directory.glob(".drawio-*")), [])

    def test_empty_success_cannot_reuse_old_result(self):
        target = self.directory / "figure.png"
        target.write_bytes(b"old")
        with patch.object(renderer, "executable", return_value="drawio"), patch.object(renderer, "drawio_command", return_value=["drawio"]), patch.object(renderer, "run_command"):
            with self.assertRaisesRegex(renderer.RenderError, "No non-empty"):
                renderer.render(self.source, target)
        self.assertEqual(target.read_bytes(), b"old")

    def test_pdf_uses_svg_then_external_converter_with_paths_intact(self):
        target = self.directory / "论文 figure.pdf"
        calls = []

        def fake_run(command, env, timeout, log):
            calls.append(command)
            if "-f" in command:
                self.assertEqual(command[command.index("-f") + 1], "svg")
                self.assertIn(str(self.source.resolve()), command)
                Path(command[command.index("-o") + 1]).write_bytes(SVG)
            else:
                destination = next(x.split("=", 1)[1] for x in command if x.startswith("--export-filename="))
                Path(destination).write_bytes(PDF)

        with patch.object(renderer, "executable", return_value="/app with spaces/drawio"), patch.object(renderer, "choose_pdf_engine", return_value=("inkscape", "/app with spaces/inkscape")), patch.object(renderer, "run_command", side_effect=fake_run):
            # Bypass only the platform display wrapper; preserve actual export arguments.
            with patch.object(renderer.sys, "platform", "darwin"):
                result = renderer.render(self.source, target, fmt="pdf")
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1][0], "/app with spaces/inkscape")
        self.assertEqual(result["pdf_engine"], "inkscape")
        self.assertEqual(target.read_bytes(), PDF)

    def test_svg_input_does_not_require_drawio(self):
        source = self.directory / "source.svg"
        source.write_bytes(SVG)
        target = self.directory / "result.pdf"

        def convert(command, env, timeout, log):
            self.assertEqual(command[:3], [sys.executable, "-m", "cairosvg"])
            Path(command[command.index("-o") + 1]).write_bytes(PDF)

        with patch.object(renderer, "choose_pdf_engine", return_value=("cairosvg", None)), patch.object(renderer, "executable", side_effect=AssertionError("drawio must not be needed")), patch.object(renderer, "run_command", side_effect=convert):
            renderer.render(source, target)

    def test_timeout_terminates_subprocess(self):
        log = self.directory / "timeout.log"
        with log.open("w") as stream, self.assertRaisesRegex(renderer.RenderError, "timeout"):
            renderer.run_command([sys.executable, "-c", "import time; time.sleep(30)"], os.environ.copy(), .15, stream)


class SetupTests(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "POSIX shell profile configuration")
    def test_path_setup_is_repeatable_and_preserves_unrelated_content(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            profile = home / ".bashrc"
            profile.write_text("# user settings\nexport CUSTOM_VALUE=keep\n")
            with patch.object(Path, "home", return_value=home), patch.dict(os.environ, {"SHELL": "/bin/bash"}):
                setup.add_path(home / "workflow one/bin")
                setup.add_path(home / "workflow one/bin")
                setup.add_path(home / "workflow two/bin")
            content = profile.read_text()
            self.assertIn("export CUSTOM_VALUE=keep", content)
            self.assertEqual(content.count("# >>> Codex-with-Draw.io-4-figure >>>"), 1)
            self.assertNotIn("workflow one", content)
            self.assertIn("workflow two", content)

    def test_agent_destinations_are_selected_and_scoped(self):
        project = Path("/example/paper")
        paths = setup.skill_locations(["codex", "claude"], "project", project)
        self.assertEqual(paths, [project / ".agents/skills/drawio-paper-figures", project / ".claude/skills/drawio-paper-figures"])
        with self.assertRaises(renderer.RenderError):
            setup.skill_locations(["codex"], "project", None)

    def test_existing_skill_is_backed_up_before_replacement(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            source, target = directory / "new", directory / "skill"
            source.mkdir()
            target.mkdir()
            (source / "SKILL.md").write_text("new")
            (target / "SKILL.md").write_text("user edits")
            setup.backup_and_copy(source, target)
            backups = list(directory.glob("skill.backup-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / "SKILL.md").read_text(), "user edits")
            self.assertEqual((target / "SKILL.md").read_text(), "new")

    def test_nonempty_unmanaged_prefix_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            prefix = Path(temp)
            sentinel = prefix / "keep.txt"
            sentinel.write_text("important")
            with patch("sys.stderr", new=io.StringIO()):
                code = setup.main(["--yes", "--prefix", str(prefix), "--agents", "none", "--skip-software", "--skip-test", "--skip-path", "--pdf-engine", "none"])
            self.assertEqual(code, 1)
            self.assertEqual(sentinel.read_text(), "important")
            self.assertFalse((prefix / setup.MARKER).exists())

    @unittest.skipIf(os.name == "nt", "POSIX launcher executes on Unix only")
    def test_launcher_preserves_spaces_and_unicode_arguments(self):
        with tempfile.TemporaryDirectory(prefix="drawio paths ") as temp:
            prefix = Path(temp)
            (prefix / "scripts").mkdir()
            (prefix / "scripts/drawio_render.py").write_text("import sys; print(repr(sys.argv[1:]))")
            launcher = setup.make_launcher(prefix, Path(sys.executable))
            output = subprocess.check_output([str(launcher), "space and 中文", "a'b"], text=True)
            self.assertEqual(output.strip(), repr(["space and 中文", "a'b"]))


if __name__ == "__main__":
    unittest.main()
