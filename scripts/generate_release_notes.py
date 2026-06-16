#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate bilingual release notes for GitHub releases.

为 GitHub Release 生成包含英文自动发布说明与中文补充说明的双语发布正文。
Combines GitHub's auto-generated English release notes with a Chinese supplement.

Environment variables:
    GITHUB_REPOSITORY: owner/repo
    GITHUB_REF_NAME: tag name (e.g. v0.2.5)
    GITHUB_TOKEN: token with contents:write permission
"""

import json
import os
import sys
import urllib.request
import urllib.error


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

    supplement = f"""
---

## 中文说明 / Chinese Notes

本次发布包含上方自动生成的变更列表，详细改动请参见各 PR 详情。
The auto-generated list above contains the changes included in this release.
For details, please refer to the individual PRs.

如有问题，请在 [Issues](https://github.com/{repo}/issues) 中反馈。
If you encounter any issues, please report them in [Issues](https://github.com/{repo}/issues).
"""

    print(body.rstrip() + supplement)
    return 0


if __name__ == "__main__":
    sys.exit(main())
