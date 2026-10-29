"""Graph provenance and freshness are checked without running trading code."""
import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_wiki_graph.py"
spec = importlib.util.spec_from_file_location("wiki_graph", SCRIPT)
graph_builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(graph_builder)


@pytest.fixture
def inputs(tmp_path):
    repo = tmp_path / "repo"
    root = repo / "knowledge"
    (root / "manifests").mkdir(parents=True)
    evidence = repo / "evidence.md"
    evidence.write_text("Historical author report", encoding="utf-8")
    source = {"id": "report", "path": "evidence.md", "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
              "locator": "Results", "tracked": True, "dirty": False, "commit": "old-snapshot"}
    (root / "manifests" / "sources.json").write_text(json.dumps({"sources": [source]}), encoding="utf-8")
    for page_id, dependencies in (("one", ["two"]), ("two", [])):
        meta = {"id": page_id, "type": "concept", "title": page_id, "updated_at": "2026-10-29",
                "source_ids": ["report"], "page_ids": dependencies, "verification": "AUTHOR_REPORTED"}
        (root / f"{page_id}.md").write_text("<!-- wiki-meta " + json.dumps(meta) + " -->\n# " + page_id, encoding="utf-8")
    skill = tmp_path / "skill"
    skill.mkdir()
    for name in ("parse-knowledge-base.py", "merge-knowledge-graph.py"):
        (skill / name).write_text("# Tool identity", encoding="utf-8")
    return repo, root, skill


def base_graph():
    return {"kind": "knowledge", "nodes": [
        {"id": "article:one", "type": "article", "filePath": "one.md", "name": "wrong parser name"},
        {"id": "article:two", "type": "article", "filePath": "two.md", "name": "two"},
        {"id": "article:README", "type": "article", "filePath": "README.md", "name": "infra"}],
        "edges": [{"source": "article:one", "target": "article:two", "type": "related"}],
        "layers": [{"id": "all", "nodeIds": ["article:one", "article:two", "article:README"]}],
        "tour": []}


def test_metadata_and_sources_override_parser_without_elevating_verification(inputs):
    repo, root, _ = inputs
    graph = graph_builder.enrich_graph(base_graph(), root, repo)
    nodes = {n["id"]: n for n in graph["nodes"]}
    assert "article:README" not in nodes
    assert nodes["article:one"]["name"] == "one"
    assert nodes["article:one"]["knowledgeMeta"]["wikiMeta"]["verification"] == "AUTHOR_REPORTED"
    assert nodes["source:report"]["knowledgeMeta"]["sourceRecord"]["commit"] == "old-snapshot"
    assert nodes["source:report"]["knowledgeMeta"]["verification"] == "BYTE_IDENTITY_ONLY"
    edges = {(e["source"], e["target"], e["type"]): e for e in graph["edges"]}
    assert edges["article:one", "source:report", "cites"]["provenance"]["kind"] == "explicit_metadata"
    assert edges["article:one", "article:two", "depends_on"]["provenance"]["field"] == "page_ids"
    assert all(n in nodes for layer in graph["layers"] for n in layer["nodeIds"])


def test_dangling_parser_or_semantic_edges_fail_closed(inputs):
    repo, root, _ = inputs
    graph = base_graph()
    graph["edges"].append({"source": "article:one", "target": "unknown", "type": "related"})
    with pytest.raises(ValueError, match="endpoint"):
        graph_builder.enrich_graph(graph, root, repo)


def test_unknown_authoritative_dependencies_fail_closed(inputs):
    repo, root, _ = inputs
    page = root / "one.md"
    page.write_text(page.read_text().replace('"two"', '"missing"'), encoding="utf-8")
    with pytest.raises(ValueError, match="Unknown page"):
        graph_builder.enrich_graph(base_graph(), root, repo)


def test_freshness_includes_originals_pages_and_tool_identity(inputs):
    repo, root, skill = inputs
    initial = graph_builder.input_manifest(root, repo, skill)
    (root / "one.md").write_text((root / "one.md").read_text() + "\nChanged", encoding="utf-8")
    assert graph_builder.input_manifest(root, repo, skill) != initial
    current = graph_builder.input_manifest(root, repo, skill)
    (repo / "evidence.md").write_text("Changed original", encoding="utf-8")
    assert graph_builder.input_manifest(root, repo, skill) != current
    current = graph_builder.input_manifest(root, repo, skill)
    (skill / "parse-knowledge-base.py").write_text("# new parser", encoding="utf-8")
    assert graph_builder.input_manifest(root, repo, skill) != current


def test_check_detects_staleness_and_graph_tampering_without_writes(inputs):
    repo, root, skill = inputs
    graph = graph_builder.enrich_graph(base_graph(), root, repo)
    graph_builder.save_graph(graph, root, repo, skill)
    assert graph_builder.check_freshness(root, repo, skill) == []
    path = root / ".ua" / "knowledge-graph.json"
    path.write_text(path.read_text() + "\n", encoding="utf-8")
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert any("graph" in issue for issue in graph_builder.check_freshness(root, repo, skill))
    assert {p: p.read_bytes() for p in root.rglob("*") if p.is_file()} == before


def test_build_rejects_changed_sources_and_escaping_paths(inputs):
    repo, root, _ = inputs
    (repo / "evidence.md").write_text("Changed", encoding="utf-8")
    with pytest.raises(ValueError, match="Source hash changed"):
        graph_builder.enrich_graph(base_graph(), root, repo)
    manifest = root / "manifests" / "sources.json"
    manifest.write_text(manifest.read_text().replace("evidence.md", "../outside.md"), encoding="utf-8")
    with pytest.raises(ValueError, match="source path"):
        graph_builder.input_manifest(root, repo, inputs[2])


def test_inferred_edges_require_explicit_ai_label_and_evidence(inputs):
    repo, root, _ = inputs
    graph = base_graph()
    graph["edges"].append({"source": "article:two", "target": "article:one", "type": "similar_to",
                            "provenance": {"kind": "ai_inference", "evidencePageIds": ["one", "two"],
                                           "rationale": "Shared evaluation concern; no financial verification."}})
    enriched = graph_builder.enrich_graph(graph, root, repo)
    inferred = [e for e in enriched["edges"] if e["provenance"]["kind"] == "ai_inference"]
    assert len(inferred) == 1
    assert inferred[0]["provenance"]["verification"] == "NOT_VERIFIED"


@pytest.mark.parametrize("raw", [".git./config", ".git /config", "safe./evidence.md", ".env /secret"])
def test_windows_path_aliases_cannot_bypass_source_privacy(inputs, raw):
    with pytest.raises(ValueError, match="source path"):
        graph_builder.source_path(raw, inputs[0])


def test_resolved_junction_targets_cannot_escape_sources_pages_or_output(inputs, tmp_path, monkeypatch):
    repo, root, skill = inputs
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text("outside bytes", encoding="utf-8")
    real_resolve = Path.resolve
    aliases = {}

    def resolve(path, *args, **kwargs):
        for alias, target in aliases.items():
            if path.is_relative_to(alias):
                return real_resolve(target / path.relative_to(alias), *args, **kwargs)
        return real_resolve(path, *args, **kwargs)

    # The managed Windows host disallows native junction creation. Simulate its
    # resolved target, exercising containment independently of that permission.
    monkeypatch.setattr(Path, "resolve", resolve)
    aliases[repo / "source-junction"] = outside
    with pytest.raises(ValueError, match="source path"):
        graph_builder.source_path("source-junction/secret.md", repo)
    (root / "wiki-junction").mkdir()
    (root / "wiki-junction" / "secret.md").write_text("placeholder", encoding="utf-8")
    aliases[root / "wiki-junction"] = outside
    with pytest.raises(ValueError, match="escapes"):
        graph_builder.page_records(root)
    aliases[root / ".ua"] = outside
    before = {p: p.read_bytes() for p in outside.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="escapes"):
        graph_builder.save_graph(base_graph(), root, repo, skill)
    assert {p: p.read_bytes() for p in outside.rglob("*") if p.is_file()} == before


def test_check_cli_exits_one_on_changed_input_without_writing(inputs):
    repo, root, skill = inputs
    graph_builder.save_graph(graph_builder.enrich_graph(base_graph(), root, repo), root, repo, skill)
    (repo / "evidence.md").write_text("changed original", encoding="utf-8")
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), "--repo", str(repo),
                             "--skill-dir", str(skill), "--check"], capture_output=True, encoding="utf-8")
    assert result.returncode == 1
    assert json.loads(result.stdout)["fresh"] is False
    assert {p: p.read_bytes() for p in root.rglob("*") if p.is_file()} == before


def test_build_aborts_if_inputs_change_during_parser_merge_and_preserves_graph(inputs, monkeypatch):
    repo, root, skill = inputs
    graph_builder.save_graph(graph_builder.enrich_graph(base_graph(), root, repo), root, repo, skill)
    before = (root / ".ua" / "knowledge-graph.json").read_bytes()

    def tool_run(command, **kwargs):
        intermediate = root / ".ua" / "intermediate"
        if "parse-knowledge-base.py" in command[1]:
            graph_builder.write_json(intermediate / "scan-manifest.json", {"stats": {}})
        else:
            graph_builder.write_json(intermediate / "assembled-graph.json", base_graph())
            page = root / "one.md"
            page.write_text(page.read_text() + "\nChanged while parser ran", encoding="utf-8")

    monkeypatch.setattr(graph_builder.subprocess, "run", tool_run)
    with pytest.raises(ValueError, match="changed during"):
        graph_builder.build(root, repo, skill)
    assert (root / ".ua" / "knowledge-graph.json").read_bytes() == before


def test_output_alias_cannot_overwrite_wiki_page_even_inside_root(inputs, monkeypatch):
    repo, root, skill = inputs
    real_resolve = Path.resolve
    output = root / ".ua" / "knowledge-graph.json.tmp"

    def resolve(path, *args, **kwargs):
        return real_resolve(root / "one.md" if path == output else path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    before = (root / "one.md").read_bytes()
    with pytest.raises(ValueError, match="escapes"):
        graph_builder.save_graph(base_graph(), root, repo, skill)
    assert (root / "one.md").read_bytes() == before
