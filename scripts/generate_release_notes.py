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
from typing import Optional


# Conventional commit / PR title prefix translation (fallback)
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


def translate_titles(titles: list) -> Optional[list]:
    """Translate a list of PR titles to Chinese using a free translator.

    Returns None if translation fails, so the caller can omit the Chinese section
    instead of failing the whole release.
    """
    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        return None

    try:
        translator = GoogleTranslator(source="en", target="zh-CN")
        # Translate in one batch to reduce the chance of hitting rate limits.
        joined = "\n---TITLE---\n".join(titles)
        translated = translator.translate(joined)
        return [t.strip() for t in translated.split("---TITLE---")]
    except Exception:
        return None


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
    """Split auto-generated release notes into prefix, what's changed, and suffix.

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


def build_chinese_section(whats_changed_lines: list) -> Optional[str]:
    """Build the Chinese '更新内容' section from the English PR list.

    Returns None if translation fails, so the release can fall back to English only.
    """
    titles = []
    for line in whats_changed_lines:
        stripped = line.strip()
        if stripped.startswith("* "):
            titles.append(stripped[2:])

    if not titles:
        return None

    translated = translate_titles(titles)
    if translated is None:
        return None

    chinese_lines = ["## 更新内容", ""]
    for t in translated:
        chinese_lines.append(f"* {t}")
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

    main_body = english_section
    if chinese_section:
        main_body = main_body + "\n\n" + chinese_section
    if prefix:
        main_body = prefix + "\n\n" + main_body

    # Match the format used for existing releases when Chinese is present:
    # English section, blank line, Chinese section, two blank lines, Full Changelog.
    # When Chinese is omitted, use one blank line before Full Changelog.
    if suffix:
        separator = "\n\n\n" if chinese_section else "\n\n"
        output = main_body + separator + suffix
    else:
        output = main_body
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
