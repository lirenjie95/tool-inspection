#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate bilingual release notes for GitHub releases.

为 GitHub Release 生成英文在前、中文在后的双语发布正文。
Generates a bilingual release body with the English section first,
followed by a separate Chinese section.

Environment variables:
    GITHUB_REPOSITORY: owner/repo
    GITHUB_REF_NAME: tag name (e.g. v0.2.5)
    GITHUB_TOKEN: token with contents:write permission
"""

import json
import os
import re
import sys
import urllib.request
import urllib.error


# Conventional commit / PR title prefix translation
PREFIX_MAP = {
    "feat(build)": "功能（构建）",
    "feat": "功能",
    "fix": "修复",
    "docs": "文档",
    "ci": "CI",
    "test": "测试",
    "refactor": "重构",
    "style": "风格",
    "perf": "性能",
    "chore": "杂项",
    "build": "构建",
}


def translate_prefix(title: str) -> str:
    """Translate the leading conventional-commit prefix of a PR title to Chinese.

    Examples:
        "feat: add foo" -> "功能：add foo"
        "feat(build): add foo" -> "功能（构建）：add foo"
    """
    match = re.match(r"^([a-z]+(?:\([a-z]+\))?)\s*:\s*(.*)$", title, re.DOTALL)
    if not match:
        return title
    prefix, rest = match.groups()
    zh_prefix = PREFIX_MAP.get(prefix, prefix)
    return f"{zh_prefix}：{rest}"


def generate_notes(repo: str, tag: str, token: str) -> str:
    """Call GitHub API to generate release notes for the given tag."""
    url = f"https://api.github.com/repos/{repo}/releases/generate-notes"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }
    data = json.dumps({"tag_name": tag}).encode()

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())["body"]
    except urllib.error.HTTPError as e:
        print(f"Failed to generate release notes: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)


def split_sections(body: str) -> tuple:
    """Split auto-generated release notes into header, what's changed, and footer.

    Returns (prefix, whats_changed_lines, suffix).
    """
    lines = body.splitlines()
    whats_changed_idx = None
    full_changelog_idx = None
    for i, line in enumerate(lines):
        if re.match(r"^##\s+What's Changed\b", line, re.IGNORECASE):
            whats_changed_idx = i
        elif "**Full Changelog**" in line:
            full_changelog_idx = i

    if whats_changed_idx is None:
        return "", lines, ""

    prefix_lines = lines[:whats_changed_idx]
    if full_changelog_idx is None:
        changed_lines = lines[whats_changed_idx:]
        suffix_lines = []
    else:
        changed_lines = lines[whats_changed_idx:full_changelog_idx]
        suffix_lines = lines[full_changelog_idx:]

    return (
        "\n".join(prefix_lines).strip(),
        changed_lines,
        "\n".join(suffix_lines).strip(),
    )


def build_chinese_section(whats_changed_lines: list) -> str:
    """Build the Chinese '更新内容' section from the English PR list."""
    chinese_lines = ["## 更新内容", ""]
    for line in whats_changed_lines:
        stripped = line.strip()
        if stripped.startswith("* "):
            title = stripped[2:]
            chinese_lines.append(f"* {translate_prefix(title)}")
    return "\n".join(chinese_lines)


def main() -> int:
    repo = os.environ.get("GITHUB_REPOSITORY")
    tag = os.environ.get("GITHUB_REF_NAME")
    token = os.environ.get("GITHUB_TOKEN")

    if not repo or not tag or not token:
        print(
            "Error: GITHUB_REPOSITORY, GITHUB_REF_NAME and GITHUB_TOKEN are required.",
            file=sys.stderr,
        )
        return 1

    body = generate_notes(repo, tag, token)
    prefix, whats_changed_lines, suffix = split_sections(body)

    english_section = "\n".join(whats_changed_lines).strip()
    chinese_section = build_chinese_section(whats_changed_lines)

    main_body = english_section + "\n\n" + chinese_section
    if prefix:
        main_body = prefix + "\n\n" + main_body

    # Match the format used for existing releases:
    # English section, blank line, Chinese section, two blank lines, Full Changelog.
    output = main_body + "\n\n\n" + suffix if suffix else main_body
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
