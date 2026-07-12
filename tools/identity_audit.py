#!/usr/bin/env python3
"""Audit local identity guardrails for the Bache Archive repos."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


EXPECTED_OWNER = "bache-archive"
EXPECTED_NAME = "bache-archive"
EXPECTED_EMAIL = "bache-archive@tuta.com"
EXPECTED_SSH_COMMAND = "ssh -i ~/.ssh/id_ed25519_bache"
EXPECTED_REMOTE_PREFIX = "git@github-bache:bache-archive/"

SECRET_PATHS = (
    ".env",
    "tools/.env",
    "tools/client_secret.json",
    "tools/token.json",
)


def run(args: list[str], cwd: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def git(cwd: Path, *args: str) -> str:
    _, stdout, _ = run(["git", *args], cwd)
    return stdout


def git_config(cwd: Path, key: str) -> str:
    return git(cwd, "config", "--local", "--get", key)


def repo_dirs(parent: Path) -> list[Path]:
    return sorted(path for path in parent.iterdir() if (path / ".git").exists())


def audit_repo(repo: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    name = repo.name

    expected_remote = f"{EXPECTED_REMOTE_PREFIX}{name}.git"
    checks = {
        "user.name": EXPECTED_NAME,
        "user.email": EXPECTED_EMAIL,
        "core.sshCommand": EXPECTED_SSH_COMMAND,
        "remote.origin.url": expected_remote,
    }
    for key, expected in checks.items():
        actual = git_config(repo, key)
        if actual != expected:
            errors.append(f"{name}: {key} is {actual!r}, expected {expected!r}")

    status = git(repo, "status", "--short")
    if status:
        warnings.append(f"{name}: working tree has local changes")

    return errors, warnings


def audit_global_config(root: Path) -> list[str]:
    warnings: list[str] = []
    global_name = git(root, "config", "--global", "--get", "user.name")
    global_email = git(root, "config", "--global", "--get", "user.email")
    if global_name and global_name != EXPECTED_NAME:
        warnings.append("global Git user.name differs from archive identity")
    if global_email and global_email != EXPECTED_EMAIL:
        warnings.append("global Git user.email differs from archive identity")

    _, url_rules, _ = run(
        ["git", "config", "--global", "--get-regexp", r"^url\."],
        root,
    )
    if "x-access-token:" in url_rules:
        warnings.append("global Git config contains a tokenized url.* rewrite")
    return warnings


def audit_secret_paths(root: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    tracked = set(git(root, "ls-files").splitlines())

    for rel in SECRET_PATHS:
        path = root / rel
        if rel in tracked:
            errors.append(f"{rel}: secret path is tracked")
        if path.exists():
            code, ignored_by, _ = run(["git", "check-ignore", "-v", rel], root)
            if code != 0:
                errors.append(f"{rel}: local secret path exists but is not ignored")
            elif not ignored_by:
                warnings.append(f"{rel}: ignored, but ignore source was not reported")

    return errors, warnings


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parent = root.parent
    errors: list[str] = []
    warnings: list[str] = []

    repos = repo_dirs(parent)
    print(f"Auditing {len(repos)} repos under {parent}")
    for repo in repos:
        repo_errors, repo_warnings = audit_repo(repo)
        errors.extend(repo_errors)
        warnings.extend(repo_warnings)

    secret_errors, secret_warnings = audit_secret_paths(root)
    errors.extend(secret_errors)
    warnings.extend(secret_warnings)
    warnings.extend(audit_global_config(root))

    if errors:
        print("\nFAIL")
        for item in errors:
            print(f"- {item}")
    else:
        print("\nPASS: local archive Git identity and remotes match guardrails")

    if warnings:
        print("\nWarnings")
        for item in warnings:
            print(f"- {item}")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
