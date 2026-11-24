"""guard_git.py のテスト（標準ライブラリの unittest。どのスタックでも流せる）。

python3 -m unittest discover -s .claude/hooks -p 'test_*.py'
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).with_name("guard_git.py")


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def run_hook(command: str, cwd: Path) -> subprocess.CompletedProcess:
    payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)}
    return subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(payload), capture_output=True, text=True, cwd=cwd, timeout=30
    )


class GuardGitTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def on_branch(self, name: str) -> None:
        git(self.repo, "checkout", "-q", "-b", name)

    def assertBlocked(self, cmd: str) -> None:
        r = run_hook(cmd, self.repo)
        self.assertEqual(r.returncode, 2, f"止まらなかった：{cmd}")
        self.assertIn("止めました", r.stderr)

    def assertAllowed(self, cmd: str) -> None:
        r = run_hook(cmd, self.repo)
        self.assertEqual(r.returncode, 0, f"止めてしまった：{cmd}\n{r.stderr}")

    # ── main の上で枝を進める操作を止める
    def test_main_の上で枝を進める操作を止める(self) -> None:
        for cmd in ('git commit -m "x"', "git merge feat", "git pull", "git cherry-pick abc", "git revert HEAD",
                    "git rebase feat", "git am x.patch"):
            with self.subTest(cmd=cmd):
                self.assertBlocked(cmd)

    def test_main_の上からの引数なしの_push_を止める(self) -> None:
        for cmd in ("git push", "git push origin", "git push origin HEAD", "git push -u origin HEAD"):
            with self.subTest(cmd=cmd):
                self.assertBlocked(cmd)

    # ── 作業ブランチからでも main に届く push を止める
    def test_main_への_push_を止める(self) -> None:
        self.on_branch("feat/a")
        for cmd in ("git push origin main", "git push origin HEAD:main", "git push origin feat/a:refs/heads/main",
                    "git push -f origin +main", "git -C . push origin master", "git push --all", "git push --mirror origin",
                    "git push origin 'refs/heads/*:refs/heads/*'", "git push origin $(echo main)", "M=main; git push origin $M"):
            with self.subTest(cmd=cmd):
                self.assertBlocked(cmd)

    def test_包んだり区切ったりしても止める(self) -> None:
        for cmd in ("(git commit -m x)", "{ git commit -m x; }", "git status & git commit -m x",
                    'bash -c "git commit -m x"', "sh -c 'git push'", "git status && git commit -m x",
                    "env GIT_X=1 git commit -m x", "/usr/bin/git commit -m x", 'eval "git commit -m x"'):
            with self.subTest(cmd=cmd):
                self.assertBlocked(cmd)

    def test_別の場所の_main_も見る(self) -> None:
        other = self.root / "other"
        other.mkdir()
        git(other, "init", "-q", "-b", "main")
        self.on_branch("feat/a")
        for cmd in (f"cd {other} && git commit -m x", "cd ../other && git commit -m x",
                    f"git --git-dir={other}/.git commit -m x", f"git -C {other} commit -m x"):
            with self.subTest(cmd=cmd):
                self.assertBlocked(cmd)

    def test_upstream_が_main_の枝からの引数なしの_push_を止める(self) -> None:
        git(self.repo, "commit", "-q", "--allow-empty", "-m", "init")
        git(self.repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        git(self.repo, "config", "remote.origin.url", "https://example.invalid/x.git")
        git(self.repo, "config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*")
        git(self.repo, "checkout", "-q", "-b", "feat/a", "--track", "origin/main")
        self.assertBlocked("git push")

    # ── 通す
    def test_作業ブランチの_commit_と_push_は通す(self) -> None:
        self.on_branch("claude/x")
        for cmd in ('git commit -m "main を直す"', "git push -u origin claude/x", "git push origin claude/maintenance",
                    "git push origin feature/main", "git push origin HEAD:release/main", "git push origin HEAD", "git push"):
            with self.subTest(cmd=cmd):
                self.assertAllowed(cmd)

    def test_main_の上でも_枝を切ってからなら通す(self) -> None:
        for cmd in ("git checkout -b feat && git commit -m x", "git switch -c feat; git commit -m x",
                    "git push origin feat", "git push origin HEAD:feat"):
            with self.subTest(cmd=cmd):
                self.assertAllowed(cmd)

    def test_読むだけの操作と_引用の中の文字は通す(self) -> None:
        for cmd in ("ls", "git status", "git log main", "git diff main", 'echo "x; git push origin main; y"',
                    "git branch --show-current"):
            with self.subTest(cmd=cmd):
                self.assertAllowed(cmd)

    def test_壊れた入力は通す(self) -> None:
        r = subprocess.run([sys.executable, str(HOOK)], input="not json", capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
