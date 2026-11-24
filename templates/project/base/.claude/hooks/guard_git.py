#!/usr/bin/env python3
"""PreToolUse[Bash] のフック。main / master を直接進める git の操作を止める。

標準ライブラリだけで動く。止めるときは終わりの値 2 と、理由を stderr に返す
（Claude Code はその文を Claude に見せる）。それ以外は 0 で素通しする。

止める物：
- main / master の上での commit・merge・pull・cherry-pick・revert・rebase・am
- main / master へ届く push（refspec の行き先が main、--all・--mirror・ワイルドカード、
  引数の無い push で upstream が main、$ や ` で行き先が読めない push）
迷ったら止める側に倒す。ただしこれは目安で、本当の関所は GitHub のブランチ保護。
alias（git ci など）や git update-ref、gh api での書き換えは見ない。
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys

PROTECTED = ("main", "master")
OPERATORS = {"&&", "||", ";", "|", "&", "(", ")", "{", "}", "\n", ";;", "|&"}
# git の、サブコマンドより前に来る値つきの選択肢（--git-dir=x の形も受ける）
GIT_OPTS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env"}
LOCATION_OPTS = {"-C", "--git-dir", "--work-tree"}
ADVANCES_BRANCH = {"commit", "merge", "pull", "cherry-pick", "revert", "rebase", "am"}
SHELLS = {"bash", "sh", "zsh", "dash"}
DEST = re.compile(r"^\+?(?:refs/heads/)?(main|master)$")


def split_commands(command: str) -> list[list[str]]:
    """引用を守って、コマンドごとの語の並びに分ける。"""
    lex = shlex.shlex(command, posix=True, punctuation_chars=";&|(){}")
    lex.whitespace_split = True
    lex.commenters = ""
    try:
        toks = list(lex)
    except ValueError:  # 閉じていない引用。素朴に分ける（止める側に倒れる）
        toks = re.split(r"\s+|(;|&&|\|\||\||&|\(|\))", command)
        toks = [t for t in toks if t]
    out: list[list[str]] = [[]]
    for t in toks:
        if t in OPERATORS or set(t) <= set(";&|(){}"):
            out.append([])
        else:
            out[-1].append(t)
    return [c for c in out if c]


class Guard:
    def __init__(self, cwd: str | None) -> None:
        self.cwd = cwd or os.getcwd()
        self.assumed_branch: str | None = None  # 同じ行の checkout -b などで変わった後の枝

    def git(self, opts: list[str], *args: str) -> str:
        try:
            r = subprocess.run(["git", *opts, *args], cwd=self.cwd, capture_output=True, text=True, timeout=10)
            return r.stdout.strip() if r.returncode == 0 else ""
        except (OSError, subprocess.SubprocessError):
            return ""

    def branch(self, opts: list[str]) -> str:
        if self.assumed_branch is not None and not opts:
            return self.assumed_branch
        # symbolic-ref は、まだコミットの無いブランチでも名前を返す
        return self.git(opts, "symbolic-ref", "--short", "-q", "HEAD")

    def check(self, command: str, depth: int = 0) -> str | None:
        for words in split_commands(command):
            reason = self.check_words(words, depth)
            if reason:
                return reason
        return None

    def check_words(self, words: list[str], depth: int) -> str | None:
        # 前に付く物（env・VAR=値・command・sudo など）を飛ばす
        i = 0
        while i < len(words) and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[i]) or words[i] in {"env", "command", "sudo", "exec", "nohup", "time"}):
            i += 1
        if i >= len(words):
            return None
        head = os.path.basename(words[i])
        rest = words[i + 1 :]
        if head == "cd":
            target = rest[0] if rest else os.path.expanduser("~")
            self.cwd = os.path.normpath(os.path.join(self.cwd, os.path.expanduser(target)))
            self.assumed_branch = None
            return None
        if head in SHELLS and depth < 3:
            for j, w in enumerate(rest):
                if w == "-c" or (w.startswith("-") and "c" in w[1:] and not w.startswith("--")):
                    if j + 1 < len(rest):
                        return self.check(rest[j + 1], depth + 1)
            return None
        if head == "eval" and depth < 3:
            return self.check(" ".join(rest), depth + 1)
        if head != "git":
            return None
        return self.check_git(rest)

    def check_git(self, args: list[str]) -> str | None:
        opts: list[str] = []
        j = 0
        while j < len(args) and args[j].startswith("-"):
            a = args[j]
            key = a.split("=", 1)[0]
            if key in GIT_OPTS_WITH_VALUE and "=" not in a:
                if key in LOCATION_OPTS and j + 1 < len(args):
                    opts += [a, args[j + 1]]
                j += 2
                continue
            if key in LOCATION_OPTS:
                opts.append(a)
            j += 1
        if j >= len(args):
            return None
        sub, sargs = args[j], args[j + 1 :]

        if sub in ("checkout", "switch") and not opts:
            new = None
            for k, w in enumerate(sargs):
                if w in ("-b", "-B", "-c", "-C", "--orphan") and k + 1 < len(sargs):
                    new = sargs[k + 1]
                    break
            positional = [w for w in sargs if not w.startswith("-")]
            if new is None and len(positional) == 1 and "--" not in sargs:
                new = positional[0]
            if new:
                self.assumed_branch = new
            return None

        branch = self.branch(opts)
        if sub in ADVANCES_BRANCH:
            if branch in PROTECTED:
                return f"いまのブランチが {branch} です。{branch} の上での git {sub} はしません"
            return None
        if sub == "push":
            return self.check_push(sargs, opts, branch)
        return None

    def check_push(self, sargs: list[str], opts: list[str], branch: str) -> str | None:
        flags = [a for a in sargs if a.startswith("-")]
        for f in flags:
            if f in ("--all", "--mirror", "--branches") or f.startswith("--all=") or f.startswith("--mirror"):
                return f"git push {f} は main / master も更新しうるので止めます"
        positional = [a for a in sargs if not a.startswith("-")]
        # --repo=x や -o x の値は位置の引数ではないが、ここでは止める側に倒れるので気にしない
        refspecs = positional[1:]
        for r in refspecs:
            if "$" in r or "`" in r:
                return f"push の行き先（{r}）が実行するまで決まらないので止めます"
            if "*" in r:
                return f"ワイルドカードの refspec（{r}）は main / master も更新しうるので止めます"
            dest = r.split(":", 1)[1] if ":" in r else r
            if dest in ("HEAD", "+HEAD", "@"):
                dest = branch
            if DEST.match(dest):
                return f"{r} は main / master への push です。直接 push しません"
        if not refspecs:
            if branch in PROTECTED:
                return f"いまのブランチが {branch} です。{branch} からの push はしません"
            upstream = self.git(opts, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
            if upstream and DEST.match(upstream.split("/", 1)[-1]):
                return f"いまのブランチの upstream が {upstream} です。引数の無い push は main / master に届きます"
        return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if "git" not in command:
        return 0
    reason = Guard(payload.get("cwd")).check(command)
    if reason is None:
        return 0
    print(f"止めました：{reason}。", file=sys.stderr)
    print("作業ブランチ（例：claude/<名前>）を切って push し、PR を出してください。", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
