#!/usr/bin/env python3
"""Offline, read-only checks for the research wiki. No source commands execute."""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit


VERIFICATIONS = {"NOT_VERIFIED", "AUTHOR_REPORTED", "INDEPENDENTLY_VERIFIED", "CONFLICTED", "STALE"}
META = re.compile(r"\A\ufeff?\s*<!-- wiki-meta (.*?) -->", re.DOTALL)
SKIP_DIRS = {"templates", ".git", ".ua", "__pycache__", ".pytest_cache", ".venv", "venv"}
SKIP_PAGES = {"readme.md", "agents.md", "index.md", "log.md"}
PRIVATE_PARTS = {".git", ".aws", ".ssh", ".codex", ".agents", "secrets", "credentials", "venv", ".venv",
                 "__pycache__", ".pytest_cache", "node_modules"}


def private_path(path: Path) -> bool:
    return any(part.lower() in PRIVATE_PARTS or part.lower().startswith(".env")
               or part.lower() in {"id_rsa", "id_ed25519"} for part in path.parts)


def prose(text: str) -> str:
    """Exclude metadata, comments and fenced/inline code from link extraction."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    lines, fence = [], None
    for line in text.splitlines():
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if marker:
            run = marker.group(1)
            if fence is None:
                fence = run
            elif run[0] == fence[0] and len(run) >= len(fence):
                fence = None
            continue
        if fence is None:
            lines.append(line)
    return re.sub(r"(`+).*?\1", "", "\n".join(lines))


def anchors(text: str) -> set[str]:
    found, counts = set(), {}
    for heading in re.findall(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", prose(text), re.MULTILINE):
        slug = re.sub(r"[^\w\-\s]", "", heading.lower()).replace(" ", "-")
        ordinal = counts.get(slug, 0)
        counts[slug] = ordinal + 1
        found.add(slug + (f"-{ordinal}" if ordinal else ""))
    found.update(re.findall(r'<(?:a|span)\s+[^>]*(?:id|name)=["\']([^"\']+)', text))
    return found


class Wiki:
    def __init__(self, root: Path, repo: Path):
        self.root, self.repo = root.resolve(), repo.resolve()
        if not self.repo.is_dir() or not self.root.is_dir() or not self.root.is_relative_to(self.repo):
            raise ValueError("--root must be an existing directory inside --repo")
        self.findings: list[dict] = []
        self.pages: dict[str, dict] = {}
        self.texts: dict[Path, str] = {}
        self.sources: dict[str, dict] = {}
        self.load_pages()
        self.load_sources()
        self.dependencies()
        self.links()

    def add(self, code: str, message: str, path: Path | str = "") -> None:
        if isinstance(path, Path):
            path = path.relative_to(self.repo).as_posix() if path.is_relative_to(self.repo) else "<outside-root>"
        self.findings.append({"code": code, "message": message, "path": path})

    def load_pages(self) -> None:
        paths = []
        for directory, dirs, files in os.walk(self.root, followlinks=False):
            base = Path(directory)
            retained = []
            for name in dirs:
                child = base / name
                if name in SKIP_DIRS or private_path(Path(name)):
                    continue
                try:
                    if not child.resolve().is_relative_to(self.root):
                        self.add("unsafe-page", "Directory resolves outside wiki root", child)
                        continue
                    if child.is_symlink() or child.is_junction():
                        self.add("unsafe-page", "Wiki directory links are not traversed", child)
                        continue
                except (OSError, RuntimeError) as exc:
                    self.add("unsafe-page", str(exc), child)
                    continue
                retained.append(name)
            dirs[:] = retained
            paths.extend(base / name for name in files if name.lower().endswith(".md"))
        for path in sorted(paths):
            try:
                resolved = path.resolve()
                if not resolved.is_relative_to(self.root) or private_path(resolved.relative_to(self.repo)):
                    self.add("unsafe-page", "Page resolves outside wiki or into private path", path)
                    continue
                text = path.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeError, RuntimeError) as exc:
                self.add("unreadable-page", str(exc), path)
                continue
            self.texts[path] = text
            if path.name.lower() in SKIP_PAGES:
                continue
            match = META.match(text)
            try:
                meta = json.loads(match.group(1)) if match else None
                if not isinstance(meta, dict):
                    raise ValueError("metadata object must begin the page")
                for field in ("id", "type", "title", "updated_at", "verification"):
                    if not isinstance(meta.get(field), str) or not meta[field].strip():
                        raise ValueError(f"{field} must be a nonempty string")
                date.fromisoformat(meta["updated_at"])
                if meta["verification"] not in VERIFICATIONS:
                    raise ValueError("unknown verification state")
                for field in ("source_ids", "page_ids"):
                    if not isinstance(meta.get(field), list) or any(not isinstance(v, str) or not v for v in meta[field]):
                        raise ValueError(f"{field} must be a list of nonempty strings")
                if meta["id"] in self.pages:
                    self.add("duplicate-id", f"Duplicate page id: {meta['id']}", path)
                    continue
                self.pages[meta["id"]] = {**meta, "path": path.relative_to(self.repo).as_posix(), "stale": False}
            except (ValueError, TypeError) as exc:
                self.add("metadata", str(exc), path)

    def result(self, command: str) -> dict:
        return {"command": command, "findings": self.findings,
                "pages": list(self.pages.values()), "sources": list(self.sources.values())}

    def load_sources(self) -> None:
        manifest = self.root / "manifests" / "sources.json"
        try:
            self.safe_path(manifest.relative_to(self.repo).as_posix(), self.repo, source=True)
            if not manifest.resolve().is_relative_to(self.root):
                raise ValueError("manifest resolves outside wiki root")
            data = json.loads(manifest.read_text(encoding="utf-8-sig"))
            if not isinstance(data, dict) or not isinstance(data.get("sources"), list):
                raise ValueError("manifest must be an object with a sources list")
        except (OSError, ValueError) as exc:
            self.add("manifest", str(exc), manifest)
            return
        for entry in data["sources"]:
            if not isinstance(entry, dict) or any(not isinstance(entry.get(k), str) or not entry[k].strip()
                                                   for k in ("id", "path", "sha256", "locator")):
                self.add("source-schema", "source needs id/path/sha256/locator strings", manifest)
                continue
            if not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]):
                self.add("source-schema", f"Invalid SHA-256 for {entry['id']}", manifest)
                continue
            if entry["id"] in self.sources:
                self.add("duplicate-source", f"Duplicate source id: {entry['id']}", manifest)
                continue
            source = {**entry, "state": "CURRENT"}
            self.sources[entry["id"]] = source
            try:
                path = self.safe_path(entry["path"], self.repo, source=True)
                source["actual_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
                if source["actual_sha256"] != entry["sha256"]:
                    source["state"] = "CHANGED"
                    self.add("source-changed", f"Source hash changed: {entry['id']}", path)
            except OSError as exc:
                source["state"] = "MISSING"
                self.add("source-missing", f"{entry['id']}: {exc}", manifest)
            except (ValueError, RuntimeError) as exc:
                source["state"] = "UNSAFE"
                self.add("unsafe-source", f"{entry['id']}: {exc}", manifest)

    def safe_path(self, raw: str, base: Path, *, source: bool = False) -> Path:
        normalized = raw.replace("\\", "/")
        parts = PurePosixPath(normalized).parts
        if not raw or normalized.startswith("/") or ":" in normalized or "\x00" in normalized:
            raise ValueError("absolute, drive, device and alternate-stream paths are forbidden")
        if source and ".." in parts:
            raise ValueError("source paths must be repo-relative without parent traversal")
        for part in parts:
            if part in {".", ".."}:
                continue
            if (part.endswith((".", " ")) or any(ord(char) < 32 for char in part)
                    or re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", part)):
                raise ValueError("Windows device names, aliases and control characters are forbidden")
        if private_path(Path(normalized)):
            raise ValueError("private or runtime path is forbidden")
        path = (base / normalized).resolve()
        if not path.is_relative_to(self.repo) or private_path(path.relative_to(self.repo)):
            raise ValueError("resolved path escapes the repository or enters a private directory")
        return path

    def dependencies(self) -> None:
        for page in self.pages.values():
            page["stale"] = page["verification"] == "STALE" or any(
                self.sources.get(s, {}).get("state") != "CURRENT" for s in page["source_ids"])
            for source in page["source_ids"]:
                if source not in self.sources:
                    self.add("unknown-source", f"Unknown source id: {source}", page["path"])
            for dependency in page["page_ids"]:
                if dependency not in self.pages:
                    self.add("unknown-page", f"Unknown page id: {dependency}", page["path"])
                    page["stale"] = True
        changed = True
        while changed:
            changed = False
            for page in self.pages.values():
                if not page["stale"] and any(self.pages.get(p, {}).get("stale", False) for p in page["page_ids"]):
                    page["stale"] = True
                    changed = True
        for page in self.pages.values():
            if page["stale"]:
                self.add("stale-page", f"Page needs source review: {page['id']}", page["path"])
        # Kahn's traversal avoids recursion limits on large or cyclic wikis.
        incoming = {key: 0 for key in self.pages}
        for page in self.pages.values():
            for dependency in set(page["page_ids"]):
                if dependency in incoming:
                    incoming[dependency] += 1
        ready = [key for key, degree in incoming.items() if degree == 0]
        while ready:
            key = ready.pop()
            for dependency in set(self.pages[key]["page_ids"]):
                if dependency in incoming:
                    incoming[dependency] -= 1
                    if incoming[dependency] == 0:
                        ready.append(dependency)
        cyclic = sorted(key for key, degree in incoming.items() if degree)
        if cyclic:
            self.add("dependency-cycle", "Dependency cycle affects: " + ", ".join(cyclic))

    def wiki_target(self, target: str, origin: Path) -> Path | None:
        target = target.strip()
        if not target:
            return origin
        if target in self.pages:
            return self.repo / self.pages[target]["path"]
        try:
            candidate = self.safe_path(target, self.root)
            if not candidate.is_relative_to(self.root):
                raise ValueError("wikilink escapes wiki root")
        except (ValueError, OSError, RuntimeError) as exc:
            self.add("unsafe-link", str(exc), origin)
            return None
        if candidate.suffix.lower() != ".md":
            candidate = candidate.with_suffix(".md")
        if candidate in self.texts:
            return candidate
        matches = [path for path in self.texts if path.stem == target or path.name == target]
        if len(matches) == 1:
            return matches[0]
        self.add("ambiguous-wikilink" if matches else "broken-wikilink", f"Unresolved wikilink: {target}", origin)
        return None

    def check_anchor(self, target: Path, fragment: str, origin: Path) -> None:
        if not fragment or target.suffix.lower() != ".md" or not target.is_file():
            return
        try:
            text = self.texts.get(target)
            if text is None:
                text = target.read_text(encoding="utf-8-sig")
            if unquote(fragment) not in anchors(text):
                self.add("broken-anchor", f"Missing heading anchor: {fragment}", origin)
        except (OSError, UnicodeError) as exc:
            self.add("broken-link", str(exc), origin)

    def links(self) -> None:
        indexed: set[Path] = set()
        index = self.root / "index.md"
        if index not in self.texts:
            self.add("missing-index", "Wiki needs index.md", index)
        for origin, text in self.texts.items():
            content = prose(text)
            for raw in re.findall(r"\[\[([^\]\n]+)\]\]", content):
                target, _, fragment = raw.split("|", 1)[0].partition("#")
                resolved = self.wiki_target(target, origin)
                if resolved:
                    self.check_anchor(resolved, fragment, origin)
                    if origin == index:
                        indexed.add(resolved)
            destinations = re.findall(r"(?<!!)\[[^\]\n]*\]\(\s*(<[^>]*>|[^\s)]*)", content)
            destinations += re.findall(r"!\[[^\]\n]*\]\(\s*(<[^>]*>|[^\s)]*)", content)
            destinations += re.findall(r"^\s{0,3}\[[^\]\n]+\]:\s*(<[^>]*>|\S+)", content, re.MULTILINE)
            for raw in destinations:
                raw = unquote(raw.strip("<>"))
                try:
                    url = urlsplit(raw)
                    if url.scheme:
                        if url.scheme.lower() not in {"http", "https", "mailto"}:
                            raise ValueError(f"Forbidden link scheme: {url.scheme}")
                        continue
                    if url.netloc:
                        raise ValueError("Network paths are forbidden")
                    resolved = self.safe_path(url.path, origin.parent) if url.path else origin
                    if not resolved.is_file():
                        self.add("broken-link", f"Missing local link: {raw}", origin)
                        continue
                    self.check_anchor(resolved, url.fragment, origin)
                    if origin == index:
                        indexed.add(resolved)
                except (ValueError, OSError, RuntimeError) as exc:
                    self.add("unsafe-link", str(exc), origin)
        for page in self.pages.values():
            if self.repo / page["path"] not in indexed:
                self.add("unindexed-page", f"Page not linked in index.md: {page['id']}", page["path"])

    def handoff(self) -> dict | None:
        latest = self.root / "handoff" / "latest.md"
        page = next((p for p in self.pages.values() if self.repo / p["path"] == latest), None)
        if page is None:
            self.add("missing-handoff", "A valid content page is required at handoff/latest.md", latest)
            return None
        required = {"git_head": r"[0-9a-f]{40}|[0-9a-f]{64}", "git_status_sha256": r"[0-9a-f]{64}",
                    "git_branch": r".+"}
        for field, pattern in required.items():
            if not isinstance(page.get(field), str) or not re.fullmatch(pattern, page[field]):
                self.add("handoff-metadata", f"Missing or invalid {field}", latest)

        def git(*args: str) -> bytes:
            return subprocess.run(["git", "--no-optional-locks", "-C", str(self.repo), *args],
                                  check=True, capture_output=True, timeout=30).stdout

        try:
            top = Path(git("rev-parse", "--show-toplevel").decode("utf-8").strip()).resolve()
            if top != self.repo:
                raise ValueError("--repo must identify the actual Git top-level directory")
            current = {"git_head": git("rev-parse", "HEAD").decode("ascii").strip(),
                       "git_branch": git("rev-parse", "--abbrev-ref", "HEAD").decode("utf-8").strip(),
                       "git_status_sha256": hashlib.sha256(git("status", "--porcelain=v1", "--untracked-files=no")).hexdigest(),
                       "untracked_paths": sorted(p.decode("utf-8", "replace") for p in
                                                 git("ls-files", "--others", "--exclude-standard", "-z").split(b"\0") if p)}
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            self.add("git-unavailable", f"Cannot read Git identity: {exc}", latest)
            return None
        for field in required:
            if field in page and page[field] != current[field]:
                self.add("handoff-" + field, f"Handoff {field} differs from current checkout", latest)
        return current


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "lint", "check-sources", "handoff-check"):
        commands.add_parser(name)
    commands.add_parser("search").add_argument("query")
    args = parser.parse_args(argv)
    try:
        if args.command == "search" and not args.query.strip():
            raise ValueError("search query must not be empty")
        wiki = Wiki(args.root, args.repo)
        result = wiki.result(args.command)
        if args.command == "handoff-check" or (args.command == "status" and (wiki.root / "handoff" / "latest.md").exists()):
            result["git"] = wiki.handoff()
        if args.command == "search":
            query = args.query.casefold()
            result["matches"] = [{"path": path.relative_to(wiki.repo).as_posix(), "line": number, "text": line}
                                 for path, text in wiki.texts.items()
                                 for number, line in enumerate(text.splitlines(), 1)
                                 if query in line.casefold()]
    except (OSError, ValueError) as exc:
        result = {"command": args.command, "error": str(exc), "findings": []}
        code = 2
    else:
        code = int(bool(result["findings"]))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{args.command}: {len(result.get('pages', []))} pages, "
              f"{len(result.get('sources', []))} sources, {len(result['findings'])} findings")
        if "error" in result:
            print(result["error"])
        for finding in result["findings"]:
            print(f"{finding['code']}: {finding['path']}: {finding['message']}")
        for match in result.get("matches", []):
            print(f"{match['path']}:{match['line']}: {match['text']}")
    return code


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
