#!/usr/bin/env python3
"""SessionStart のフック。いまのブランチと、守りのフックがあることだけを知らせる。

静的な説明は CLAUDE.md に置き、ここでは重複させない。
"""
from __future__ import annotations

import subprocess
import sys


def main() -> int:
    try:
        branch = subprocess.run(
            ["git", "symbolic-ref", "--short", "-q", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip() or "?"
    except (OSError, subprocess.SubprocessError):
        branch = "?"
    print(
        f"[nok] いまのブランチ：{branch}。main / master への直接の commit・push は"
        " .claude/hooks/guard_git.py が止めます。変更は作業ブランチ＋PR で。"
    )
    if branch in ("main", "master"):
        print(f"⚠ いま {branch} にいます。ファイルを変える前に作業ブランチを切ってください。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
