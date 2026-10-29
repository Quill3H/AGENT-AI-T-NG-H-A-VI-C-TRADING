"""Exercise the read-only wiki CLI against isolated, real filesystem fixtures."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "research_wiki.py"


def page(path, page_id, *, sources=None, pages=None, body="", **extra):
    meta = {"id": page_id, "type": "concept", "title": "Nghiên cứu tiếng Việt",
            "updated_at": "2026-10-29", "source_ids": sources or [],
            "page_ids": pages or [], "verification": "AUTHOR_REPORTED", **extra}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("<!-- wiki-meta " + json.dumps(meta, ensure_ascii=False) + " -->\n" + body,
                    encoding="utf-8")


@pytest.fixture
def wiki(tmp_path):
    repo = tmp_path / "repo"
    root = repo / "knowledge"
    (root / "manifests").mkdir(parents=True)
    (repo / "evidence.md").write_bytes(b"evidence\n")
    (root / "manifests" / "sources.json").write_text(json.dumps({"sources": [{
        "id": "evidence", "path": "evidence.md", "sha256":
        "bdcf4c994585af6dd6cb1cfbff78bcc73ab27dc30a299db5bb83766ca05b5de4", "locator": "whole file"}]}), encoding="utf-8")
    page(root / "concepts" / "first.md", "first", sources=["evidence"], body="# Khái niệm\nNghiên cứu [nguồn](../../evidence.md).\n")
    (root / "index.md").write_text("# Index\n[[first]]\n", encoding="utf-8")
    return repo, root


def run(wiki, command, *args):
    repo, root = wiki
    result = subprocess.run([sys.executable, str(SCRIPT), "--repo", str(repo),
                             "--root", str(root), "--json", command, *args],
                            capture_output=True, encoding="utf-8")
    assert result.stdout, result.stderr
    return result.returncode, json.loads(result.stdout)


def test_lint_accepts_sourced_utf8_wiki_without_writing(wiki):
    before = {str(p): p.read_bytes() for p in wiki[0].rglob("*") if p.is_file()}
    code, result = run(wiki, "lint")
    assert code == 0, result
    assert result["findings"] == []
    assert result["pages"][0]["verification"] == "AUTHOR_REPORTED"
    assert {str(p): p.read_bytes() for p in wiki[0].rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("bad", [None, [], {"id": "bad"}, {"verification": "VERIFIED"},
                                {"page_ids": "first"}, {"updated_at": "yesterday"}])
def test_malformed_metadata_is_a_finding(wiki, bad):
    target = wiki[1] / "concepts" / "bad.md"
    if isinstance(bad, dict) and len(bad) == 1 and "id" not in bad:
        page(target, "bad", **bad)
    else:
        target.write_text("<!-- wiki-meta " + json.dumps(bad) + " -->", encoding="utf-8")
    code, result = run(wiki, "lint")
    assert code == 1
    assert "metadata" in {item["code"] for item in result["findings"]}


def test_source_change_makes_all_dependent_pages_stale_without_promoting_verification(wiki):
    page(wiki[1] / "concepts" / "second.md", "second", pages=["first"])
    page(wiki[1] / "concepts" / "third.md", "third", pages=["second"])
    (wiki[1] / "index.md").write_text("[[first]] [[second]] [[third]]", encoding="utf-8")
    (wiki[0] / "evidence.md").write_text("changed evidence", encoding="utf-8")
    code, result = run(wiki, "check-sources")
    assert code == 1
    assert {p["id"] for p in result["pages"] if p["stale"]} == {"first", "second", "third"}
    assert {p["verification"] for p in result["pages"]} == {"AUTHOR_REPORTED"}
    assert {s["state"] for s in result["sources"]} == {"CHANGED"}


@pytest.mark.parametrize("source_path", ["../outside.md", "../repo/evidence.md", "..\\outside.md",
                                         "C:/private/file.md", "//server/share/file.md",
                                         ".git/config", ".env", "evidence.md:private"])
def test_source_paths_reject_escape_and_private_locations(wiki, source_path):
    path = wiki[1] / "manifests" / "sources.json"
    manifest = json.loads(path.read_text())
    manifest["sources"][0]["path"] = source_path
    path.write_text(json.dumps(manifest), encoding="utf-8")
    code, result = run(wiki, "check-sources")
    assert code == 1
    assert "unsafe-source" in {item["code"] for item in result["findings"]}


def test_source_symlink_escape_is_rejected(wiki, tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("private", encoding="utf-8")
    target = wiki[0] / "evidence.md"
    target.unlink()
    try:
        target.symlink_to(outside)
    except OSError:
        pytest.skip("Host does not allow symlink creation")
    code, result = run(wiki, "check-sources")
    assert code == 1
    assert "unsafe-source" in {item["code"] for item in result["findings"]}


def test_missing_and_malformed_sources_report_findings(wiki):
    (wiki[0] / "evidence.md").unlink()
    code, result = run(wiki, "check-sources")
    assert code == 1
    assert result["sources"][0]["state"] == "MISSING"
    assert result["pages"][0]["stale"] is True
    (wiki[1] / "manifests" / "sources.json").write_text('{"sources": false}', encoding="utf-8")
    code, result = run(wiki, "lint")
    assert code == 1
    assert "manifest" in {item["code"] for item in result["findings"]}


def test_cycles_duplicates_and_unknown_dependencies_are_findings(wiki):
    page(wiki[1] / "concepts" / "first.md", "first", pages=["second"])
    page(wiki[1] / "concepts" / "second.md", "second", pages=["first", "unknown"], sources=["unknown"])
    page(wiki[1] / "concepts" / "zzduplicate.md", "first")
    code, result = run(wiki, "lint")
    assert code == 1
    assert {"dependency-cycle", "duplicate-id", "unknown-source", "unknown-page"} <= {
        item["code"] for item in result["findings"]}


def test_wikilinks_resolve_ids_aliases_paths_anchors_and_index_membership(wiki):
    page(wiki[1] / "concepts" / "second.md", "second", body="[[first#khái-niệm|đọc]]\n[[concepts/first]]")
    (wiki[1] / "index.md").write_text("[[first]] [second](concepts/second.md)", encoding="utf-8")
    code, result = run(wiki, "lint")
    assert code == 0, result
    (wiki[1] / "index.md").write_text("[[first]] second", encoding="utf-8")
    code, result = run(wiki, "lint")
    assert code == 1
    assert "unindexed-page" in {item["code"] for item in result["findings"]}


def test_wikilinks_detect_missing_ambiguous_targets_and_missing_anchors(wiki):
    page(wiki[1] / "a" / "shared.md", "a", body="[[missing]] [[shared]] [[first#absent]]")
    page(wiki[1] / "b" / "shared.md", "b")
    code, result = run(wiki, "lint")
    assert code == 1
    assert {"broken-wikilink", "ambiguous-wikilink", "broken-anchor"} <= {
        item["code"] for item in result["findings"]}


@pytest.mark.parametrize("destination", ["../../../../private.md", "file:///C:/private.md", "javascript:alert(1)",
                                         "../../.git/config", "..%2f..%2f..%2fprivate.md", "//host/share/file"])
def test_markdown_links_reject_escape_and_unsafe_schemes(wiki, destination):
    page(wiki[1] / "concepts" / "first.md", "first", body=f"[unsafe]({destination})")
    code, result = run(wiki, "lint")
    assert code == 1
    assert "unsafe-link" in {item["code"] for item in result["findings"]}


def test_fenced_code_links_are_examples_and_reference_links_are_checked(wiki):
    page(wiki[1] / "concepts" / "first.md", "first", body="```md\n[[missing]]\n[x](file:///private)\n```\n[real][ref]\n\n[ref]: ../../missing.md\n")
    code, result = run(wiki, "lint")
    assert code == 1
    assert {item["code"] for item in result["findings"]} == {"broken-link"}


def test_search_is_literal_case_insensitive_and_reports_line_numbers(wiki):
    page(wiki[1] / "concepts" / "first.md", "first", body="# Nghiên cứu\nLiteral [a.*] token\n")
    code, result = run(wiki, "search", "[A.*]")
    assert code == 0, result
    assert result["matches"] == [{"path": "knowledge/concepts/first.md", "line": 3,
                                   "text": "Literal [a.*] token"}]
    code, result = run(wiki, "search", "this will not match")
    assert code == 0
    assert result["matches"] == []


def test_excluded_operational_pages_and_templates_do_not_need_metadata(wiki):
    (wiki[1] / "README.md").write_text("# Read me", encoding="utf-8")
    (wiki[1] / "AGENTS.md").write_text("# Contract", encoding="utf-8")
    (wiki[1] / "log.md").write_text("# Events", encoding="utf-8")
    (wiki[1] / "templates").mkdir()
    (wiki[1] / "templates" / "page.md").write_text("<!-- wiki-meta {invalid} -->", encoding="utf-8")
    code, result = run(wiki, "status")
    assert code == 0, result
    assert [p["id"] for p in result["pages"]] == ["first"]


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True).stdout


@pytest.fixture
def git_wiki(wiki):
    repo, root = wiki
    git(repo, "init", "--initial-branch=fixture")
    git(repo, "config", "user.name", "Fixture")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "add", "evidence.md")
    git(repo, "-c", "commit.gpgsign=false", "commit", "-m", "fixture source")
    page(root / "handoff" / "latest.md", "latest", type="handoff",
         git_head=git(repo, "rev-parse", "HEAD").decode().strip(),
         git_branch="fixture", git_status_sha256=hashlib.sha256(b"").hexdigest())
    (root / "index.md").write_text("[[first]] [[latest]]", encoding="utf-8")
    return wiki


def test_handoff_checks_head_branch_tracked_bytes_and_lists_untracked_separately(git_wiki):
    code, result = run(git_wiki, "handoff-check")
    assert code == 0, result
    assert result["git"]["git_branch"] == "fixture"
    assert "knowledge/handoff/latest.md" in result["git"]["untracked_paths"]
    # A tracked content change is detected even though branch and HEAD are unchanged.
    (git_wiki[0] / "evidence.md").write_text("dirty", encoding="utf-8")
    code, result = run(git_wiki, "handoff-check")
    assert code == 1
    assert "handoff-git_status_sha256" in {item["code"] for item in result["findings"]}


def test_handoff_rejects_wrong_head_branch_and_incomplete_metadata(git_wiki):
    path = git_wiki[1] / "handoff" / "latest.md"
    page(path, "latest", type="handoff", git_head="0" * 40, git_branch="wrong", git_status_sha256="0" * 64)
    code, result = run(git_wiki, "handoff-check")
    assert code == 1
    assert {"handoff-git_head", "handoff-git_branch", "handoff-git_status_sha256"} <= {
        item["code"] for item in result["findings"]}
    page(path, "latest", type="handoff")
    code, result = run(git_wiki, "handoff-check")
    assert code == 1
    assert "handoff-metadata" in {item["code"] for item in result["findings"]}


def test_handoff_missing_is_a_finding(wiki):
    code, result = run(wiki, "handoff-check")
    assert code == 1
    assert "missing-handoff" in {item["code"] for item in result["findings"]}


@pytest.mark.parametrize("args", [[], ["--root", "missing", "--repo", "missing", "status"],
                                  ["--root", ".", "--repo", ".", "search"],
                                  ["--root", ".", "--repo", ".", "unknown"]])
def test_malformed_cli_input_returns_two_without_traceback(args):
    result = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, encoding="utf-8")
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_empty_search_is_invalid_input(wiki):
    code, result = run(wiki, "search", " ")
    assert code == 2
    assert "error" in result


def test_directory_junction_cannot_expose_external_sources_or_wiki_pages(wiki, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    page(outside / "private.md", "private", body="SECRET DO NOT READ")
    junction = wiki[1] / "external"
    if os.name == "nt":
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(outside)], capture_output=True)
        if result.returncode:
            pytest.skip("Host does not allow junction creation")
    else:
        junction.symlink_to(outside, target_is_directory=True)
    manifest = wiki[1] / "manifests" / "sources.json"
    data = json.loads(manifest.read_text())
    data["sources"][0]["path"] = "knowledge/external/private.md"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    code, result = run(wiki, "search", "SECRET")
    assert code == 1
    assert result["matches"] == []
    assert {"unsafe-source", "unsafe-page"} <= {f["code"] for f in result["findings"]}


@pytest.mark.parametrize("path", [".git./config", "evidence.md ", "NUL", "aux.txt", "folder\x01/file.md"])
def test_windows_alias_and_device_source_paths_are_rejected(wiki, path):
    manifest = wiki[1] / "manifests" / "sources.json"
    data = json.loads(manifest.read_text())
    data["sources"][0]["path"] = path
    manifest.write_text(json.dumps(data), encoding="utf-8")
    code, result = run(wiki, "check-sources")
    assert code == 1
    assert "unsafe-source" in {f["code"] for f in result["findings"]}


def test_explicit_stale_page_propagates_and_is_a_health_finding(wiki):
    page(wiki[1] / "concepts" / "first.md", "first", verification="STALE")
    page(wiki[1] / "concepts" / "second.md", "second", pages=["first"])
    (wiki[1] / "index.md").write_text("[[first]] [[second]]", encoding="utf-8")
    code, result = run(wiki, "status")
    assert code == 1
    assert {p["id"] for p in result["pages"] if p["stale"]} == {"first", "second"}
    assert "stale-page" in {f["code"] for f in result["findings"]}


def test_invalid_utf8_page_is_reported_without_crashing_or_disclosing_bytes(wiki):
    (wiki[1] / "concepts" / "broken.md").write_bytes(b"\xff\x80")
    code, result = run(wiki, "lint")
    assert code == 1
    assert "unreadable-page" in {f["code"] for f in result["findings"]}
