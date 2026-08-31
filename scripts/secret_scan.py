"""High-confidence repository secret scan for CI.

This is intentionally conservative: it blocks credential formats that are
unlikely to be legitimate application data, while avoiding broad password
regexes that create noisy false positives.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}
MAX_BYTES = 1_000_000

PATTERNS = [
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{20,}\b")),
    ("Stripe secret key", re.compile(r"\bsk_(?:live|test)_[0-9A-Za-z]{16,}\b")),
    (
        "PostgreSQL credential URL",
        re.compile(r"postgres(?:ql)?://[^\s:@/]+:[^\s@/]+@", re.IGNORECASE),
    ),
    (
        "MySQL credential URL",
        re.compile(r"mysql://[^\s:@/]+:[^\s@/]+@", re.IGNORECASE),
    ),
    (
        "MongoDB credential URL",
        re.compile(r"mongodb(?:\+srv)?://[^\s:@/]+:[^\s@/]+@", re.IGNORECASE),
    ),
]


def iter_text_files():
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        try:
            if path.stat().st_size > MAX_BYTES:
                continue
            data = path.read_bytes()
            if b"\x00" in data:
                continue
            yield path, data.decode("utf-8", errors="strict")
        except (OSError, UnicodeDecodeError):
            continue


def main() -> int:
    findings: list[str] = []
    for path, text in iter_text_files():
        for name, pattern in PATTERNS:
            match = pattern.search(text)
            if match:
                line = text.count("\n", 0, match.start()) + 1
                findings.append(f"{path.relative_to(ROOT)}:{line}: {name}")

    if findings:
        print("Potential credentials detected:")
        print("\n".join(sorted(findings)))
        return 1

    print("Secret scan passed: no high-confidence credential patterns found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
