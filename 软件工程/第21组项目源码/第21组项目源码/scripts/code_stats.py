#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_INCLUDE_DIRS = ("backend", "frontend", "scripts", "tests")
DEFAULT_EXCLUDE_DIRS = {
    ".git",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".turbo",
    ".venv",
    ".vite",
    "__pycache__",
    "artifacts",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "playwright-report",
    "test-results",
}
DEFAULT_EXCLUDE_FILES = {
    "npm-shrinkwrap.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
}

LANGUAGES = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript React",
    ".js": "JavaScript",
    ".jsx": "JavaScript React",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".css": "CSS",
    ".scss": "SCSS",
    ".html": "HTML",
    ".json": "JSON",
    ".toml": "TOML",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".md": "Markdown",
    ".sql": "SQL",
}

LINE_COMMENT_PREFIXES = {
    "Python": ("#",),
    "TypeScript": ("//",),
    "TypeScript React": ("//",),
    "JavaScript": ("//",),
    "JavaScript React": ("//",),
    "CSS": (),
    "SCSS": ("//",),
    "HTML": (),
    "JSON": (),
    "TOML": ("#",),
    "YAML": ("#",),
    "Markdown": (),
    "SQL": ("--",),
}

BLOCK_COMMENT_TOKENS = {
    "TypeScript": ("/*", "*/"),
    "TypeScript React": ("/*", "*/"),
    "JavaScript": ("/*", "*/"),
    "JavaScript React": ("/*", "*/"),
    "CSS": ("/*", "*/"),
    "SCSS": ("/*", "*/"),
    "HTML": ("<!--", "-->"),
    "SQL": ("/*", "*/"),
}


@dataclass
class Stats:
    files: int = 0
    total: int = 0
    code: int = 0
    blank: int = 0
    comment: int = 0
    bytes: int = 0

    def add(self, other: "Stats") -> None:
        self.files += other.files
        self.total += other.total
        self.code += other.code
        self.blank += other.blank
        self.comment += other.comment
        self.bytes += other.bytes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Count BookFlow source code lines.")
    parser.add_argument(
        "paths",
        nargs="*",
        help="Paths to scan. Defaults to backend frontend scripts tests.",
    )
    parser.add_argument(
        "--include-docs",
        action="store_true",
        help="Include docs in the default scan and count Markdown files.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of tables.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Number of largest files to show in text mode.",
    )
    parser.add_argument(
        "--all-ext",
        action="store_true",
        help="Count every text-like extension in LANGUAGES, including Markdown by default.",
    )
    parser.add_argument(
        "--include-lockfiles",
        action="store_true",
        help="Include dependency lock files such as package-lock.json.",
    )
    return parser.parse_args()


def should_skip_dir(path: Path, root: Path) -> bool:
    parts = set(path.relative_to(root).parts) if path != root else set()
    return bool(parts & DEFAULT_EXCLUDE_DIRS)


def iter_files(paths: list[Path], root: Path, include_docs: bool, all_ext: bool, include_lockfiles: bool):
    allowed = set(LANGUAGES)
    if not include_docs and not all_ext:
        allowed.discard(".md")

    for start in paths:
        if start.is_file():
            if start.suffix.lower() in allowed and (include_lockfiles or start.name not in DEFAULT_EXCLUDE_FILES):
                yield start
            continue
        if not start.exists():
            continue
        for current_root, dir_names, file_names in start.walk():
            dir_path = Path(current_root)
            dir_names[:] = [name for name in dir_names if not should_skip_dir(dir_path / name, root)]
            for file_name in file_names:
                path = dir_path / file_name
                if not include_lockfiles and path.name in DEFAULT_EXCLUDE_FILES:
                    continue
                if path.suffix.lower() in allowed:
                    yield path


def decode_text(path: Path) -> str | None:
    data = path.read_bytes()
    if b"\x00" in data:
        return None
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def count_file(path: Path) -> Stats:
    language = LANGUAGES.get(path.suffix.lower(), "Other")
    text = decode_text(path)
    if text is None:
        return Stats()

    stats = Stats(files=1, bytes=path.stat().st_size)
    line_prefixes = LINE_COMMENT_PREFIXES.get(language, ())
    block_tokens = BLOCK_COMMENT_TOKENS.get(language)
    in_block = False

    for line in text.splitlines():
        stats.total += 1
        stripped = line.strip()
        if not stripped:
            stats.blank += 1
            continue

        if block_tokens and in_block:
            stats.comment += 1
            if block_tokens[1] in stripped:
                in_block = False
            continue

        if line_prefixes and any(stripped.startswith(prefix) for prefix in line_prefixes):
            stats.comment += 1
            continue

        if block_tokens and stripped.startswith(block_tokens[0]):
            stats.comment += 1
            if block_tokens[1] not in stripped:
                in_block = True
            continue

        stats.code += 1

    return stats


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def print_table(title: str, rows: list[tuple[str, Stats]]) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    print(f"{'name':42} {'files':>7} {'total':>9} {'code':>9} {'blank':>9} {'comment':>9}")
    for name, stats in rows:
        print(f"{name[:42]:42} {stats.files:7d} {stats.total:9d} {stats.code:9d} {stats.blank:9d} {stats.comment:9d}")


def main() -> int:
    args = parse_args()
    include_dirs = list(DEFAULT_INCLUDE_DIRS)
    if args.include_docs:
        include_dirs.append("docs")
    scan_paths = [Path(path).resolve() for path in args.paths] if args.paths else [ROOT / name for name in include_dirs]

    by_language: dict[str, Stats] = {}
    by_top_dir: dict[str, Stats] = {}
    by_file: list[tuple[str, Stats]] = []
    total = Stats()

    for path in sorted(set(iter_files(scan_paths, ROOT, args.include_docs, args.all_ext, args.include_lockfiles))):
        stats = count_file(path)
        if not stats.files:
            continue
        language = LANGUAGES.get(path.suffix.lower(), "Other")
        by_language.setdefault(language, Stats()).add(stats)
        rel = relative(path)
        top_dir = rel.split("/", 1)[0]
        by_top_dir.setdefault(top_dir, Stats()).add(stats)
        by_file.append((rel, stats))
        total.add(stats)

    result = {
        "root": str(ROOT),
        "total": asdict(total),
        "by_language": {key: asdict(value) for key, value in sorted(by_language.items())},
        "by_top_dir": {key: asdict(value) for key, value in sorted(by_top_dir.items())},
        "largest_files": [
            {"path": name, **asdict(stats)}
            for name, stats in sorted(by_file, key=lambda item: item[1].code, reverse=True)[: args.top]
        ],
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print_table("Total", [("BookFlow", total)])
    print_table("By Language", sorted(by_language.items(), key=lambda item: item[1].code, reverse=True))
    print_table("By Top Directory", sorted(by_top_dir.items(), key=lambda item: item[1].code, reverse=True))
    print_table("Largest Files", sorted(by_file, key=lambda item: item[1].code, reverse=True)[: args.top])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
