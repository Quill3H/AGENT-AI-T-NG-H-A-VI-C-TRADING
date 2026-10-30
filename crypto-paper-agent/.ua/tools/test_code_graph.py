"""Independent fixtures for the partial graph's source and freshness contracts."""
import ast
from contextlib import redirect_stdout
from datetime import datetime, timezone
import importlib.util
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("partial_code_graph", Path(__file__).with_name("build_code_graph.py"))
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class CodeGraphContracts(unittest.TestCase):
    def run_build(self):
        with redirect_stdout(StringIO()):
            return builder.main(["--root", str(self.root)])

    def setUp(self):
        fixture_root = Path(__file__).resolve().parent / "fixture-tmp"
        fixture_root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="code-graph-fixture-", dir=fixture_root)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for group in builder.SCOPE:
            (self.root / group).mkdir()
        (self.root / "src" / "__init__.py").write_text("", encoding="utf-8")
        (self.root / "src" / "base.py").write_text("class Base: pass\n", encoding="utf-8")
        self.source = self.root / "src" / "sample.py"
        self.source.write_text("from .base import Base\nclass Child(Base):\n    def method(self):\n        def nested(): return 1\n        return nested()\nif True:\n    def duplicate(): pass\nelse:\n    def duplicate(): pass\n", encoding="utf-8")
        (self.root / "scripts" / "entry.py").write_text("from src.sample import Child\nChild().method()\n", encoding="utf-8")
        (self.root / "config" / "a.yaml").write_text("strategy: example\n", encoding="utf-8")

    def graph(self):
        rows = builder.inventory(self.root)
        graph, imports = builder.build_graph(self.root, rows, datetime.now(timezone.utc).isoformat(), {"head": "fixture"})
        self.assertEqual(builder.validate_graph(graph, rows), [])
        return rows, graph, imports

    def test_observed_symbols_relative_imports_and_no_inferred_calls(self):
        rows, graph, imports = self.graph()
        symbols = [n for n in graph["nodes"] if n["type"] in {"function", "class"}]
        expected = sum(sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) for n in ast.walk(ast.parse((self.root / r["path"]).read_bytes()))) for r in rows if r["language"] == "python")
        self.assertEqual(len(symbols), expected)
        self.assertEqual(len([n for n in symbols if n["name"] == "duplicate"]), 2)
        self.assertTrue(any(n["name"] == "Child.method.nested" for n in symbols))
        self.assertIn({"path": "src/sample.py", "line": 1, "syntax": "from .base import Base", "candidates": ["src.base", "src.base.Base"], "resolvedInternalFiles": ["src/base.py"], "resolution": "internal-static"}, imports)
        self.assertEqual({e["type"] for e in graph["edges"]}, {"contains", "imports"})

    def test_inventory_change_detection_includes_additions_and_removals(self):
        self.assertEqual(self.run_build(), 0)
        self.assertTrue(builder.check(self.root)["fresh"])
        self.source.write_text("def changed(): pass\n", encoding="utf-8")
        (self.root / "scripts" / "entry.py").unlink()
        (self.root / "config" / "new.yaml").write_text("new: true\n", encoding="utf-8")
        result = builder.check(self.root)
        self.assertFalse(result["fresh"])
        self.assertEqual(result["changed"], ["src/sample.py"])
        self.assertEqual(result["removed"], ["scripts/entry.py"])
        self.assertEqual(result["added"], ["config/new.yaml"])

    def test_graph_tampering_and_utf8_source(self):
        self.source.write_text('"""Dữ liệu nghiên cứu."""\ndef tên(): pass\n', encoding="utf-8")
        self.assertEqual(self.run_build(), 0)
        graph_path = self.root / ".ua" / "knowledge-graph.json"
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        self.assertTrue(any(n["summary"] == "Dữ liệu nghiên cứu." for n in graph["nodes"]))
        graph_path.write_text("{}", encoding="utf-8")
        self.assertTrue(builder.check(self.root)["graphChanged"])

    def test_filename_only_docstrings_use_factual_inventory_summary(self):
        original = self.source.read_text(encoding="utf-8")
        for header in ("src/sample.py", "sample.py", "  sample.py  ", "   "):
            with self.subTest(header=header):
                self.source.write_text(f'"""{header}"""\n' + original, encoding="utf-8")
                _, graph, _ = self.graph()
                node = next(n for n in graph["nodes"] if n["id"] == "file:src/sample.py")
                self.assertNotEqual(node["summary"].strip(), node["name"])
                self.assertNotEqual(node["summary"].strip(), "sample.py")
                self.assertIn("5 declarations", node["summary"])
                self.assertIn("1 import", node["summary"])

    def test_parse_failure_does_not_replace_previous_graph(self):
        self.assertEqual(self.run_build(), 0)
        target = self.root / ".ua" / "knowledge-graph.json"
        before = target.read_bytes()
        self.source.write_text("def broken(:\n", encoding="utf-8")
        self.assertEqual(self.run_build(), 2)
        self.assertEqual(target.read_bytes(), before)

    def test_linked_source_is_refused(self):
        outside = self.root / "external.py"
        outside.write_text("def external(): pass\n", encoding="utf-8")
        link = self.root / "src" / "linked.py"
        try:
            link.symlink_to(outside)
        except OSError as error:
            self.skipTest(f"host does not allow fixture symlink creation: {error}")
        with self.assertRaisesRegex(ValueError, "linked input refused"):
            builder.inventory(self.root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
