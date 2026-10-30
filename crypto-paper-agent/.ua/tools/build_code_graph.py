"""Build/check a scoped, partial Understand graph without executing project code.

Stdlib-only fallback for an installed Understand plugin without compiled core.
This is intentionally not the plugin's full analysis/incremental pipeline.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

SCOPE = ("src", "scripts", "config")
EXCLUDED = {"__pycache__", ".venv", "venv", "node_modules", ".git", ".ua",
            "artifacts", "data", "market-data", ".pytest_cache"}
VERSION = "fallback-python-ast-v1"
LIMITATIONS = [
    "PARTIAL: installed scan-project.mjs failed ERR_MODULE_NOT_FOUND: packages/core/dist/index.js; no plugin installation or build was attempted.",
    "Only src/, scripts/, config/ are inventoried. Root run_backtest.py, tests, docs, web-preview, dependencies, raw datasets and artifacts are outside scope.",
    "Python declarations and explicit import syntax are observed statically. Import edges do not prove execution, availability, or runtime binding; conditional and local imports remain syntactic dependencies.",
    "No calls, inferred data flows, inheritance, registry relationships or economic claims are emitted. Dynamic imports, aliases, runtime monkey-patching and external packages are not resolved.",
    "YAML/config files are inventoried and hashed only; no inferred configures edge is emitted. Summaries use source docstrings or declaration names, not a full semantic review.",
    "Directory layers and tour are navigation aids. Complexity is a documented line-count heuristic. This is not a full Understand pipeline result or an official incremental/fingerprint baseline.",
    "Dirty/untracked inputs are included as observed bytes. Freshness is checked by exact scoped inventory and SHA-256; Git commit alone is insufficient.",
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def linked(path):
    info = path.lstat()
    return path.is_symlink() or bool(getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def inventory(root):
    """Never traverse symlinks/junctions; fail rather than silently omit inputs."""
    root = Path(root).resolve(strict=True)
    rows = []
    for group in SCOPE:
        folder = root / group
        if not folder.is_dir():
            raise ValueError(f"required scope directory missing: {group}")
        if linked(folder):
            raise ValueError(f"linked scope directory refused: {group}")
        for current, dirs, names in os.walk(folder, followlinks=False):
            base = Path(current)
            dirs[:] = sorted(d for d in dirs if d not in EXCLUDED)
            for name in dirs:
                if linked(base / name):
                    raise ValueError(f"linked directory refused: {(base / name).relative_to(root).as_posix()}")
            for name in sorted(names):
                path = base / name
                if path.suffix in {".pyc", ".pyo"}:
                    continue
                rel = path.relative_to(root).as_posix()
                if linked(path) or not path.is_file() or not path.resolve().is_relative_to(root):
                    raise ValueError(f"non-regular or linked input refused: {rel}")
                raw = path.read_bytes()
                rows.append({"path": rel, "sha256": sha(raw), "bytes": len(raw),
                             "lines": len(raw.splitlines()),
                             "language": "python" if path.suffix == ".py" else "yaml" if path.suffix in {".yaml", ".yml"} else "text",
                             "fileCategory": "config" if group == "config" else "script" if group == "scripts" else "code"})
    return sorted(rows, key=lambda row: row["path"])


def git_bytes(root, *args):
    try:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return b""


def git_identity(root):
    status = git_bytes(root, "status", "--porcelain=v1", "--untracked-files=no")
    return {"head": git_bytes(root, "rev-parse", "HEAD").decode().strip(),
            "branch": git_bytes(root, "branch", "--show-current").decode().strip(),
            "trackedStatusSha256": sha(status),
            "trackedStatusAtBuild": status.decode("utf-8", errors="replace").splitlines(),
            "scopedUntrackedFiles": git_bytes(root, "ls-files", "--others", "--exclude-standard", "--", *SCOPE).decode("utf-8", errors="replace").splitlines(),
            "note": "Build-time context only; other documentation tasks may change global status. Scoped hashes govern graph freshness."}


def complexity(lines):
    return "simple" if lines < 60 else "moderate" if lines < 250 else "complex"


def module_name(path):
    parts = path.removesuffix(".py").split("/")
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def import_candidates(path, item):
    if isinstance(item, ast.Import):
        return [alias.name for alias in item.names]
    prefix = item.module or ""
    if item.level:
        package = module_name(path).split(".")
        if not path.endswith("/__init__.py"):
            package = package[:-1]
        up = item.level - 1
        if up >= len(package):
            return []
        prefix = ".".join(package[:len(package) - up] + ([prefix] if prefix else []))
    return ([prefix] if prefix else []) + [f"{prefix}.{alias.name}" for alias in item.names if alias.name != "*" and prefix]


def build_graph(root, rows, now, identity):
    root = Path(root)
    nodes, edges, imports = [], [], []
    layers = defaultdict(list)
    source_by_module = {module_name(r["path"]): r["path"] for r in rows if r["language"] == "python"}
    module_ids, file_ids = {}, {}
    for row in rows:
        path = row["path"]
        group = "/".join(path.split("/")[:2]) if path.startswith("src/") and path.count("/") > 1 else path.split("/")[0]
        mid = "module:" + group
        if mid not in module_ids:
            module_ids[mid] = group
            nodes.append({"id": mid, "type": "module", "name": group,
                          "summary": f"Directory grouping for observed files in {group}; navigation only.",
                          "tags": ["directory-group", "static"], "complexity": "simple"})
        kind = "config" if row["fileCategory"] == "config" else "file"
        fid = f"{kind}:{path}"
        file_ids[path] = fid
        layers[group].append(fid)
        summary = f"{row['fileCategory'].capitalize()} file {path}; {row['lines']} lines observed."
        tree = None
        if row["language"] == "python":
            tree = ast.parse((root / path).read_bytes(), filename=path)
            doc = ast.get_docstring(tree)
            doc_summary = doc.strip().splitlines()[0][:350] if doc and doc.strip() else ""
            if doc_summary and doc_summary not in {path, Path(path).name}:
                summary = doc_summary
            else:
                declarations = sum(isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) for item in ast.walk(tree))
                import_count = sum(isinstance(item, (ast.Import, ast.ImportFrom)) for item in ast.walk(tree))
                summary = (f"Python file {path}; {row['lines']} lines observed, "
                           f"{declarations} declarations and {import_count} import statements in static AST.")
        nodes.append({"id": fid, "type": kind, "name": path, "filePath": path,
                      "lineRange": [1, max(row["lines"], 1)], "summary": summary,
                      "tags": [row["fileCategory"], row["language"], "static"],
                      "complexity": complexity(row["lines"])})
        edges.append({"source": mid, "target": fid, "type": "contains", "direction": "forward", "weight": 1.0,
                      "description": "Observed directory membership; no runtime relationship asserted."})
        if tree is None:
            continue

        class Symbols(ast.NodeVisitor):
            def __init__(self):
                self.stack = [(fid, "")]

            def declaration(self, obj, node_type):
                parent_id, prefix = self.stack[-1]
                qualified = f"{prefix}.{obj.name}" if prefix else obj.name
                sid = f"{node_type}:{path}:{qualified}@{obj.lineno}"
                doc = ast.get_docstring(obj)
                summary = (doc.strip().splitlines()[0][:350] if doc else f"Observed Python {node_type} declaration {qualified}.")
                nodes.append({"id": sid, "type": node_type, "name": qualified, "filePath": path,
                              "lineRange": [obj.lineno, obj.end_lineno], "summary": summary,
                              "tags": ["python", "ast-declaration", "async" if isinstance(obj, ast.AsyncFunctionDef) else node_type],
                              "complexity": complexity(obj.end_lineno - obj.lineno + 1)})
                edges.append({"source": parent_id, "target": sid, "type": "contains", "direction": "forward", "weight": 1.0,
                              "description": f"AST lexical declaration at {path}:{obj.lineno}; no runtime call asserted."})
                self.stack.append((sid, qualified))
                self.generic_visit(obj)
                self.stack.pop()

            def visit_FunctionDef(self, obj):
                self.declaration(obj, "function")

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_ClassDef(self, obj):
                self.declaration(obj, "class")

        Symbols().visit(tree)
        for item in ast.walk(tree):
            if not isinstance(item, (ast.Import, ast.ImportFrom)):
                continue
            candidates = import_candidates(path, item)
            targets = sorted({source_by_module[c] for c in candidates if c in source_by_module})
            imports.append({"path": path, "line": item.lineno, "syntax": ast.unparse(item),
                            "candidates": candidates, "resolvedInternalFiles": targets,
                            "resolution": "internal-static" if targets else "external-or-unresolved"})
    import_lines = defaultdict(list)
    for item in imports:
        for target in item["resolvedInternalFiles"]:
            if target != item["path"]:
                import_lines[(item["path"], target)].append(item["line"])
    for (source, target), lines in sorted(import_lines.items()):
        edges.append({"source": file_ids[source], "target": file_ids[target], "type": "imports", "direction": "forward", "weight": 0.7,
                      "description": f"Explicit AST import syntax in {source}, lines {', '.join(map(str, sorted(set(lines))))}; runtime execution/binding not verified."})
    layer_list = [{"id": "layer:" + group.replace("/", ":"), "name": group,
                   "description": f"Navigation grouping from directory {group}.", "nodeIds": ids}
                  for group, ids in sorted(layers.items())]
    tour_paths = [
        ("Research entry points", "Inspect offline orchestration and cache inputs; graph membership is not test or economic acceptance.", ["scripts/backtest_lab.py", "scripts/run_eth_btc_cointegration.py", "scripts/run_crypto_orb_portfolio.py"]),
        ("Strategies and registries", "Inspect actual strategy declarations and explicit imports. Registry resolution is not modeled.", ["src/strategies/registry.py", "src/strategies/eth_btc_cointegration.py", "src/strategies/funding_arbitrage.py"]),
        ("Paper execution and risk", "Follow explicit imports into simulated broker/account and invariant helpers; no exchange order path is asserted.", ["src/execution/paper_broker.py", "src/execution/pair_account.py", "src/risk/invariant_checks.py", "src/risk/circuit_breakers.py"]),
        ("Data and reports", "Locate source preparation, replay, artifact and reporting modules before inspecting source evidence.", ["src/data_layer/vision_dataset.py", "src/backtest/engine.py", "src/research/artifacts.py", "src/report/generator.py"]),
        ("Configurations", "Config files are inventory-only: read the source to determine applicability and values.", ["config/default_config.yaml", "config/research/backtest_lab.example.yaml", "config/research/crypto_orb_portfolio.yaml"]),
    ]
    tour = [{"order": i + 1, "title": title, "description": desc, "nodeIds": [file_ids[p] for p in paths if p in file_ids]}
            for i, (title, desc, paths) in enumerate(tour_paths)]
    graph = {"version": "1.0.0", "kind": "codebase",
             "project": {"name": "crypto-paper-agent (partial static code graph)", "languages": ["python", "yaml"], "frameworks": [],
                         "description": "PARTIAL deterministic AST code map of src/scripts/config, including dirty/untracked working-tree bytes. Derived navigation only; read source and freshness manifest. No observed runtime calls or economic verification.",
                         "analyzedAt": now, "gitCommitHash": identity["head"]},
             "nodes": nodes, "edges": edges, "layers": layer_list, "tour": tour}
    return graph, imports


def validate_graph(graph, rows):
    errors = []
    ids = [n["id"] for n in graph["nodes"]]
    if len(ids) != len(set(ids)):
        errors.append("duplicate node IDs")
    ids = set(ids)
    file_nodes = [n for n in graph["nodes"] if n["type"] in {"file", "config"}]
    if sorted(n["filePath"] for n in file_nodes) != [r["path"] for r in rows]:
        errors.append("input inventory/file-node mismatch")
    assigned = [i for layer in graph["layers"] for i in layer["nodeIds"]]
    if sorted(assigned) != sorted(n["id"] for n in file_nodes):
        errors.append("file-layer coverage mismatch")
    for node in graph["nodes"]:
        if any(not node.get(key) for key in ("id", "name", "type", "summary", "tags", "complexity")):
            errors.append(f"missing node field: {node.get('id')}")
        if node["complexity"] not in {"simple", "moderate", "complex"}:
            errors.append("invalid complexity")
    seen_edges = set()
    for edge in graph["edges"]:
        key = (edge["source"], edge["target"], edge["type"])
        if key in seen_edges or edge["source"] not in ids or edge["target"] not in ids:
            errors.append(f"duplicate/dangling edge: {key}")
        seen_edges.add(key)
        if edge["type"] not in {"contains", "imports"}:
            errors.append("unexpected non-observed edge type")
    for item in graph["layers"] + graph["tour"]:
        if any(i not in ids for i in item["nodeIds"]):
            errors.append("dangling layer/tour reference")
    return errors


def atomic_json(path, obj):
    temp = path.with_suffix(path.suffix + ".tmp")
    if temp.exists() and linked(temp):
        raise ValueError(f"linked temporary output refused: {temp.name}")
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def check(root):
    folder = root / ".ua"
    if linked(folder):
        raise ValueError("linked graph output directory refused")
    manifest = json.loads((folder / "source-inventory.json").read_text(encoding="utf-8"))
    current = inventory(root)
    before = {r["path"]: r["sha256"] for r in manifest["inputs"]}
    after = {r["path"]: r["sha256"] for r in current}
    findings = {"added": sorted(after.keys() - before.keys()), "removed": sorted(before.keys() - after.keys()),
                "changed": sorted(p for p in after.keys() & before.keys() if after[p] != before[p])}
    findings["generatorChanged"] = sha(Path(__file__).read_bytes()) != manifest["generatorSha256"]
    findings["graphChanged"] = sha((folder / "knowledge-graph.json").read_bytes()) != manifest["graphSha256"]
    findings["headChanged"] = git_identity(root)["head"] != manifest["git"]["head"]
    findings["fresh"] = not any(findings.values())
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--check", action="store_true", help="read-only exact-inventory/hash freshness check")
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve(strict=True)
        if args.check:
            result = check(root)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["fresh"] else 1
        rows = inventory(root)
        now = datetime.now(timezone.utc).isoformat()
        identity = git_identity(root)
        graph, imports = build_graph(root, rows, now, identity)
        errors = validate_graph(graph, rows)
        if errors:
            raise ValueError("; ".join(errors))
        if inventory(root) != rows:
            raise ValueError("scoped source inventory changed during analysis; retry")
        folder = root / ".ua"
        if folder.exists() and linked(folder):
            raise ValueError("linked graph output directory refused")
        folder.mkdir(exist_ok=True)
        atomic_json(folder / "knowledge-graph.json", graph)
        manifest = {"format": VERSION, "status": "PARTIAL_STATIC", "generatedAt": now,
                    "scope": list(SCOPE), "excludedDirectoryNames": sorted(EXCLUDED),
                    "inputs": rows, "inputSetSha256": sha(canonical(rows)),
                    "generator": ".ua/tools/build_code_graph.py", "generatorSha256": sha(Path(__file__).read_bytes()),
                    "graphSha256": sha((folder / "knowledge-graph.json").read_bytes()), "git": identity,
                    "limitations": LIMITATIONS}
        atomic_json(folder / "source-inventory.json", manifest)
        atomic_json(folder / "import-evidence.json", {"method": "Python ast.Import/ast.ImportFrom syntax only", "imports": imports})
        result = {"status": "PARTIAL_STATIC", "issues": errors, "warnings": LIMITATIONS,
                  "files": len(rows), "categories": dict(Counter(r["fileCategory"] for r in rows)),
                  "nodeTypes": dict(Counter(n["type"] for n in graph["nodes"])),
                  "edgeTypes": dict(Counter(e["type"] for e in graph["edges"])),
                  "layers": len(graph["layers"]), "tourSteps": len(graph["tour"]),
                  "schemaValidation": "stdlib structural validation against fields in installed core/src/schema.ts; installed Zod execution not available without dependencies"}
        atomic_json(folder / "validation.json", result)
        atomic_json(folder / "config.json", {"autoUpdate": False, "outputLanguage": "en"})
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, SyntaxError, KeyError) as error:
        print(json.dumps({"status": "ERROR", "error": str(error)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
