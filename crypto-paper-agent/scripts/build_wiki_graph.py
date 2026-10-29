#!/usr/bin/env python3
"""Build the wiki dashboard graph; --check only compares captured input bytes.

The installed understand-knowledge parser/merger provide structural navigation.
This adapter preserves authoritative wiki-meta and source-manifest provenance.
AI analysis is an optional, explicitly labelled input, never source verification.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


META = re.compile(r"\A\ufeff?\s*<!-- wiki-meta (.*?) -->", re.DOTALL)
TOOLS = ("parse-knowledge-base.py", "merge-knowledge-graph.py")
SKIP = {".ua", ".understand-anything", "__pycache__", ".pytest_cache"}
INFRA = {"readme.md", "agents.md", "index.md", "log.md"}
PRIVATE = {".git", ".ssh", ".aws", ".codex", ".agents", "credentials", "secrets", "node_modules", ".venv", "venv",
           "__pycache__", ".pytest_cache", "id_rsa", "id_ed25519"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def contained(path: Path, root: Path) -> Path:
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Path escapes allowed root: {path}")
    return path


def ua_directory(root: Path) -> Path:
    ua = contained(root / ".ua", root)
    if ua.resolve() != root.resolve() / ".ua":
        raise ValueError(f"Output directory escapes its exact .ua location: {ua}")
    return ua


def write_json(path: Path, value, *, within: Path | None = None) -> None:
    if within is not None:
        contained(path, within)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def source_path(raw: str, repo: Path) -> Path:
    normalized = raw.replace("\\", "/")
    parts = PurePosixPath(normalized).parts
    if (not raw or normalized.startswith("/") or ":" in normalized or "\x00" in normalized
            or ".." in parts or any(p.rstrip(" .") != p or p.lower() in PRIVATE or p.lower().startswith(".env")
                                     or re.fullmatch(r"(?i)(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", p)
                                     for p in parts)):
        raise ValueError(f"Unsafe source path: {raw!r}")
    resolved = (repo / normalized).resolve()
    if (not resolved.is_relative_to(repo.resolve())
            or any(p.lower() in PRIVATE or p.lower().startswith(".env")
                   for p in resolved.relative_to(repo.resolve()).parts)):
        raise ValueError(f"Unsafe source path outside repository: {raw!r}")
    return resolved


def source_records(root: Path, repo: Path, *, verify: bool = False) -> list[dict]:
    records = read_json(contained(root / "manifests" / "sources.json", root))["sources"]
    seen = set()
    for record in records:
        if record["id"] in seen:
            raise ValueError(f"Duplicate source ID: {record['id']}")
        seen.add(record["id"])
        path = source_path(record["path"], repo)
        if verify and digest(path) != record["sha256"]:
            raise ValueError(f"Source hash changed: {record['id']}; reassess wiki dependents before rebuilding")
    return records


def page_records(root: Path) -> dict[str, dict]:
    pages = {}
    for path in sorted(root.rglob("*.md")):
        relative = path.relative_to(root)
        if any(p in SKIP or p == "templates" for p in relative.parts) or path.name.lower() in INFRA:
            continue
        contained(path, root)
        match = META.match(path.read_text(encoding="utf-8-sig"))
        if not match:
            raise ValueError(f"Missing wiki-meta: {relative}")
        meta = json.loads(match.group(1))
        if meta["id"] in pages:
            raise ValueError(f"Duplicate page ID: {meta['id']}")
        for key in ("source_ids", "page_ids"):
            if not isinstance(meta.get(key), list):
                raise ValueError(f"Invalid {key}: {relative}")
        pages[meta["id"]] = {"path": relative.as_posix(), "meta": meta}
    return pages


def input_manifest(root: Path, repo: Path, skill_dir: Path) -> dict:
    """Capture content, source bytes and tool identities; never create files."""
    entries = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and not any(p in SKIP for p in path.relative_to(root).parts):
            contained(path, root)
            entries["wiki:" + path.relative_to(root).as_posix()] = digest(path)
    for record in source_records(root, repo):
        path = source_path(record["path"], repo)
        entries["source:" + record["path"]] = digest(path) if path.is_file() else None
    for name in TOOLS:
        entries["tool:" + name] = digest(skill_dir / name)
    entries["tool:build_wiki_graph.py"] = digest(Path(__file__))
    ua = ua_directory(root)
    semantic = contained(ua / "semantic-analysis.json", ua)
    if semantic.is_file():
        entries["analysis:semantic-analysis.json"] = digest(semantic)
    encoded = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {"schemaVersion": 1, "sha256": hashlib.sha256(encoded).hexdigest(), "files": entries}


def enrich_graph(graph: dict, root: Path, repo: Path) -> dict:
    pages = page_records(root)
    sources = source_records(root, repo, verify=True)
    paths = {page["path"]: key for key, page in pages.items()}
    page_nodes, removed, nodes = {}, set(), {}
    for node in graph["nodes"]:
        if node["type"] == "article":
            relative = node.get("filePath", "").replace("\\", "/")
            if relative not in paths:
                removed.add(node["id"])
                continue
            page_id = paths[relative]
            page = pages[page_id]
            node["name"] = page["meta"]["title"]
            node["filePath"] = relative
            node.setdefault("knowledgeMeta", {}).update({"wikiMeta": page["meta"], "pageSha256": digest(root / relative),
                                                          "provenance": "explicit_wiki_metadata"})
            page_nodes[page_id] = node["id"]
        node.setdefault("summary", node["name"])
        node.setdefault("tags", [])
        node.setdefault("complexity", "simple")
        nodes[node["id"]] = node
    if set(page_nodes) != set(pages):
        raise ValueError("Parser failed to include all metadata content pages")
    source_ids = set()
    for record in sources:
        nid = "source:" + record["id"]
        source_ids.add(record["id"])
        nodes[nid] = {"id": nid, "type": "source", "name": record["id"], "summary": record["locator"],
                      "filePath": Path(os.path.relpath(source_path(record["path"], repo), root)).as_posix(),
                      "tags": ["source", "byte-identity-only"], "complexity": "simple",
                      "knowledgeMeta": {"sourceRecord": record, "actualSha256": digest(source_path(record["path"], repo)),
                                        "verification": "BYTE_IDENTITY_ONLY", "provenance": "explicit_source_manifest"}}
    edges = []
    for edge in graph["edges"]:
        if edge["source"] in removed or edge["target"] in removed:
            continue
        if edge["source"] not in nodes or edge["target"] not in nodes:
            raise ValueError(f"Dangling graph endpoint: {edge}")
        provenance = edge.setdefault("provenance", {"kind": "deterministic_structure",
                                                   "extractor": "understand-knowledge"})
        if provenance["kind"] == "ai_inference":
            evidence = provenance.get("evidencePageIds", [])
            if not evidence or not set(evidence).issubset(pages) or not provenance.get("rationale"):
                raise ValueError("AI inference requires known evidencePageIds and a rationale")
            provenance["verification"] = "NOT_VERIFIED"
        edges.append(edge)
    for page_id, page in pages.items():
        for field, edge_type, prefix in (("source_ids", "cites", "source:"), ("page_ids", "depends_on", "")):
            for target in page["meta"][field]:
                if field == "source_ids" and target not in source_ids:
                    raise ValueError(f"Unknown source: {target}")
                if field == "page_ids" and target not in page_nodes:
                    raise ValueError(f"Unknown page: {target}")
                edges.append({"source": page_nodes[page_id], "target": prefix + target if prefix else page_nodes[target],
                              "type": edge_type, "direction": "forward", "weight": 1.0,
                              "provenance": {"kind": "explicit_metadata", "field": field, "pageId": page_id,
                                             "path": page["path"], "locator": "wiki-meta"}})
    for node in nodes.values():
        if node.get("knowledgeMeta", {}).get("provenance") == "ai_inference":
            node["knowledgeMeta"]["verification"] = "NOT_VERIFIED"
    # Preserve distinct explicit and inferred relationships, even with equal endpoints/type.
    keyed = {(e["source"], e["target"], e["type"], e["provenance"]["kind"]): e for e in edges}
    graph["nodes"] = sorted(nodes.values(), key=lambda n: n["id"])
    graph["edges"] = [keyed[key] for key in sorted(keyed)]
    for collection in (graph.get("layers", []), graph.get("tour", [])):
        for item in collection:
            item["nodeIds"] = [nid for nid in item["nodeIds"] if nid in nodes]
    graph.setdefault("layers", []).append({"id": "layer:provenance", "name": "Source provenance",
                                           "description": "Original source bytes; hash identity is not factual verification",
                                           "nodeIds": ["source:" + s["id"] for s in sources]})
    graph["provenancePolicy"] = {"authority": "wiki-meta and manifests/sources.json",
                                  "aiInference": "Navigation hypothesis only; NOT_VERIFIED",
                                  "sourceHashes": "Byte identity only; no financial or execution verification"}
    return graph


def save_graph(graph: dict, root: Path, repo: Path, skill_dir: Path, *, expected_manifest: dict | None = None) -> None:
    ua = ua_directory(root)
    manifest = input_manifest(root, repo, skill_dir)
    if expected_manifest is not None and manifest != expected_manifest:
        raise ValueError("Inputs changed during graph build; prior graph preserved")
    graph["inputManifestSha256"] = manifest["sha256"]
    staged = []
    try:
        pending_graph = ua / "knowledge-graph.json.tmp"
        write_json(pending_graph, graph, within=ua)
        outputs = {"input-manifest.json": manifest,
                   "meta.json": {"lastAnalyzedAt": datetime.now(timezone.utc).isoformat(),
                                 "gitCommitHash": graph.get("project", {}).get("gitCommitHash", ""),
                                 "version": "1.0.0", "analyzedFiles": len(page_records(root)),
                                 "inputManifestSha256": manifest["sha256"], "graphSha256": digest(pending_graph)}}
        staged.append((pending_graph, contained(ua / "knowledge-graph.json", ua)))
        for name, value in outputs.items():
            pending = ua / (name + ".tmp")
            write_json(pending, value, within=ua)
            staged.append((pending, contained(ua / name, ua)))
        if input_manifest(root, repo, skill_dir) != manifest:
            raise ValueError("Inputs changed during graph publication; prior graph preserved")
        for pending, target in staged:
            pending.replace(target)
    finally:
        for pending, _ in staged:
            if pending.exists():
                contained(pending, ua).unlink()


def check_freshness(root: Path, repo: Path, skill_dir: Path) -> list[str]:
    try:
        ua = ua_directory(root)
        saved = read_json(contained(ua / "input-manifest.json", ua))
        current = input_manifest(root, repo, skill_dir)
        meta = read_json(contained(ua / "meta.json", ua))
        graph = read_json(contained(ua / "knowledge-graph.json", ua))
        issues = []
        if saved != current:
            issues.extend("input changed: " + key for key in sorted(set(saved["files"]) | set(current["files"]))
                          if saved["files"].get(key) != current["files"].get(key))
        if digest(root / ".ua" / "knowledge-graph.json") != meta.get("graphSha256"):
            issues.append("graph output hash changed")
        if graph.get("inputManifestSha256") != saved["sha256"] or meta.get("inputManifestSha256") != saved["sha256"]:
            issues.append("graph manifest identity mismatch")
        return issues
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f"graph freshness unavailable: {exc}"]


def build(root: Path, repo: Path, skill_dir: Path) -> dict:
    if (root / ".understand-anything").exists():
        raise ValueError("Legacy .understand-anything exists; resolve the output directory before using this .ua adapter")
    # Validate originals before invoking any tool. Parser/merger never execute source text.
    before = input_manifest(root, repo, skill_dir)
    source_records(root, repo, verify=True)
    # Installed tools recurse through the target, including infrastructure.
    # Preflight every resolved entry before allowing those tools to read/write.
    for path in root.rglob("*"):
        contained(path, root)
        if any(p.lower() in PRIVATE or p.lower().startswith(".env")
               for p in path.relative_to(root).parts):
            raise ValueError(f"Private path inside parser input: {path}")
    ua = ua_directory(root)
    intermediate = contained(ua / "intermediate", ua)
    intermediate.mkdir(parents=True, exist_ok=True)
    for name in ("scan-manifest.json", "assembled-graph.json", "analysis-batch-1.json"):
        contained(intermediate / name, ua)
    for path in intermediate.glob("analysis-batch-*.json"):
        contained(path, ua).unlink()
    subprocess.run([sys.executable, str(skill_dir / TOOLS[0]), str(root)], check=True)
    semantic_path = contained(ua / "semantic-analysis.json", ua)
    if semantic_path.is_file():
        batch = read_json(semantic_path)
        pages = page_records(root)
        for page_id, expected in batch.get("evidencePageHashes", {}).items():
            if page_id not in pages or digest(root / pages[page_id]["path"]) != expected:
                raise ValueError(f"AI analysis evidence changed: {page_id}; re-read and update semantic analysis")
        for edge in batch.get("edges", []):
            if edge.get("provenance", {}).get("kind") != "ai_inference":
                raise ValueError("Semantic edges must be labelled ai_inference")
            if not set(edge["provenance"].get("evidencePageIds", [])).issubset(batch.get("evidencePageHashes", {})):
                raise ValueError("Semantic edge evidence must have captured page hashes")
        for node in batch.get("nodes", []):
            if node.get("knowledgeMeta", {}).get("provenance") != "ai_inference":
                raise ValueError("Semantic nodes must be labelled ai_inference")
        write_json(intermediate / "analysis-batch-1.json", batch, within=ua)
    subprocess.run([sys.executable, str(skill_dir / TOOLS[1]), str(root)], check=True)
    graph = enrich_graph(read_json(contained(intermediate / "assembled-graph.json", ua)), root, repo)
    graph["extraction"] = {"parser": "understand-knowledge", "scanStats": read_json(
        contained(intermediate / "scan-manifest.json", ua)).get("stats", {}),
        "contentFilter": "Leading wiki-meta only; README and templates excluded"}
    save_graph(graph, root, repo, skill_dir, expected_manifest=before)
    for name in ("scan-manifest.json", "assembled-graph.json", "analysis-batch-1.json"):
        path = contained(intermediate / name, ua)
        if path.exists():
            path.unlink()
    if not any(intermediate.iterdir()):
        intermediate.rmdir()
    return graph


def main() -> int:
    package = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=package / "knowledge")
    parser.add_argument("--repo", type=Path, default=package.parent)
    parser.add_argument("--skill-dir", type=Path, default=Path.home() / ".agents" / "skills" / "understand-knowledge")
    parser.add_argument("--check", action="store_true", help="Read-only freshness check; exits 1 for changes")
    args = parser.parse_args()
    root, repo, skill_dir = args.root.resolve(), args.repo.resolve(), args.skill_dir.resolve()
    if not root.is_relative_to(repo):
        parser.error("--root must be inside --repo")
    try:
        if args.check:
            issues = check_freshness(root, repo, skill_dir)
            print(json.dumps({"fresh": not issues, "findings": issues}, ensure_ascii=False, indent=2))
            return int(bool(issues))
        graph = build(root, repo, skill_dir)
        print(json.dumps({"saved": str(root / ".ua" / "knowledge-graph.json"), "nodes": len(graph["nodes"]),
                          "edges": len(graph["edges"]), "articles": len(page_records(root)),
                          "layers": len(graph["layers"]), "tourSteps": len(graph["tour"])}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        print(f"Wiki graph error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
