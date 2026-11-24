"""scripts/new_project.py と templates/project/ のテスト。

通る場合だけでなく、落とすべき物を落とすこと（知らないスタック・知らないプラグイン・上書き・印の残り）も確かめる。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import new_project  # noqa: E402

STACKS = ["python", "node", "rust"]
TOKEN = re.compile(r"__[A-Z][A-Z_]*__")


def make(dest: Path, *extra: str) -> int:
    return new_project.main([str(dest), *extra])


def git_init(path: Path, branch: str = "feat/x") -> None:
    subprocess.run(["git", "init", "-q", "-b", branch], cwd=path, check=True)


def test_スタックの一覧は雛形の物と同じ() -> None:
    assert new_project.stacks() == sorted(STACKS)


@pytest.mark.parametrize("stack", STACKS)
def test_写した物に置き換え忘れの印が無く_設定が読める(tmp_path: Path, stack: str) -> None:
    dest = tmp_path / "demo-app"
    assert make(dest, "--stack", stack, "--description", "試しのリポジトリ", "--plugins", "konomi,takumi") == 0

    for p in dest.rglob("*"):
        if p.is_file():
            assert not TOKEN.search(p.read_text(encoding="utf-8")), p
            assert not TOKEN.search(str(p.relative_to(dest))), p

    settings = json.loads((dest / ".claude/settings.json").read_text(encoding="utf-8"))
    assert settings["extraKnownMarketplaces"]["nok-plugins"]["source"] == {"source": "github", "repo": "nok-Inc-jp/nok-plugins"}
    assert settings["enabledPlugins"] == {"konomi@nok-plugins": True, "takumi@nok-plugins": True}
    assert "Bash(git status:*)" in settings["permissions"]["allow"]
    assert len(settings["permissions"]["allow"]) == len(set(settings["permissions"]["allow"]))
    assert any("guard_git.py" in h["command"] for m in settings["hooks"]["PreToolUse"] for h in m["hooks"])

    assert (dest / "scripts/check.sh").stat().st_mode & 0o111
    assert (dest / "scripts/check-stack.sh").is_file()
    assert (dest / ".github/workflows/check.yml").is_file()
    assert "package-ecosystem" in (dest / ".github/dependabot.yml").read_text(encoding="utf-8")
    assert "試しのリポジトリ" in (dest / "CLAUDE.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("stack", STACKS)
def test_CI_は_ci_ラベルか手動のときだけ流れ_権限は読むだけ(tmp_path: Path, stack: str) -> None:
    dest = tmp_path / "demo"
    make(dest, "--stack", stack, "--description", "x")
    wf = (dest / ".github/workflows/check.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch" in wf and "labeled" in wf and "'ci')" in wf
    assert "contents: read" in wf and "persist-credentials: false" in wf
    for line in wf.splitlines():
        if "uses:" in line:
            assert re.search(r"@[0-9a-f]{40}\b", line), f"SHA で固定していない：{line}"


def test_プラグインを選ばなければ_登録だけして何も有効にしない(tmp_path: Path) -> None:
    dest = tmp_path / "demo"
    make(dest, "--stack", "node", "--description", "x")
    settings = json.loads((dest / ".claude/settings.json").read_text(encoding="utf-8"))
    assert settings["enabledPlugins"] == {}
    assert "nok-plugins" in settings["extraKnownMarketplaces"]


def test_知らないプラグインは何も書かずに落とす(tmp_path: Path) -> None:
    dest = tmp_path / "demo"
    assert make(dest, "--stack", "python", "--plugins", "konomi,nai-plugin") == 1
    assert not dest.exists()


def test_知らないスタックは落とす(tmp_path: Path) -> None:
    assert make(tmp_path / "demo", "--stack", "go") == 1


@pytest.mark.parametrize("name", ["Demo", "demo_app", "-demo", "あ"])
def test_決まりに合わない名前は落とす(tmp_path: Path, name: str) -> None:
    assert make(tmp_path / "x", "--stack", "python", f"--name={name}") == 1


def test_同じ名前のファイルがあれば上書きせずに落とし_force_なら上書きする(tmp_path: Path) -> None:
    dest = tmp_path / "demo"
    dest.mkdir()
    (dest / "README.md").write_text("元の README", encoding="utf-8")
    assert make(dest, "--stack", "python", "--description", "x") == 1
    assert (dest / "README.md").read_text(encoding="utf-8") == "元の README"
    assert not (dest / "CLAUDE.md").exists()  # 1 つも書いていない

    assert make(dest, "--stack", "python", "--description", "x", "--force") == 0
    assert (dest / "README.md").read_text(encoding="utf-8") != "元の README"


def test_clone_したばかりのリポジトリ_git_だけ_にも写せる(tmp_path: Path) -> None:
    dest = tmp_path / "demo"
    dest.mkdir()
    git_init(dest)
    assert make(dest, "--stack", "python", "--description", "x") == 0
    assert (dest / ".git").is_dir()


def test_説明が複数行なら落とす(tmp_path: Path) -> None:
    assert make(tmp_path / "demo", "--stack", "python", "--description", "1行目\n2行目") == 1


# 写した物の check.sh を実際に流す（道具が無ければ skip ではなく、check.sh 自体が「未実行」で落ちることを確かめる）

def run_check(dest: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", "scripts/check.sh"], cwd=dest, capture_output=True, text=True, timeout=600)


@pytest.mark.parametrize("stack", STACKS)
def test_写した物の_check_sh_が通る(tmp_path: Path, stack: str) -> None:
    tool = {"python": "python3", "node": "npm", "rust": "cargo"}[stack]
    dest = tmp_path / f"demo-{stack}"
    make(dest, "--stack", stack, "--description", "x")
    git_init(dest)
    r = run_check(dest)
    if shutil.which(tool) is None:
        assert r.returncode == 1 and "未実行" in r.stdout
    else:
        assert r.returncode == 0, r.stdout + r.stderr
        assert r.stdout.rstrip().endswith("OK")


def test_説明を省くと_書き換える印が残り_check_sh_が落ちる(tmp_path: Path) -> None:
    dest = tmp_path / "demo"
    make(dest, "--stack", "python")
    git_init(dest)
    r = run_check(dest)
    assert r.returncode == 1
    assert "書き換えていない印" in r.stdout and "CLAUDE.md" in r.stdout


def test_check_stack_sh_が無ければ未実行で落ちる(tmp_path: Path) -> None:
    dest = tmp_path / "demo"
    make(dest, "--stack", "python", "--description", "x")
    git_init(dest)
    (dest / "scripts/check-stack.sh").unlink()
    r = run_check(dest)
    assert r.returncode == 1 and "未実行" in r.stdout


def test_写した物のテストが落ちれば_check_sh_も落ちる(tmp_path: Path) -> None:
    dest = tmp_path / "demo"
    make(dest, "--stack", "python", "--description", "x")
    git_init(dest)
    (dest / "tests/test_smoke.py").write_text("def test_落ちる():\n    assert False\n", encoding="utf-8")
    r = run_check(dest)
    assert r.returncode == 1 and "落ちた" in r.stdout


def test_守りのフックのテストが雛形のままで通る() -> None:
    hooks = ROOT / "templates/project/base/.claude/hooks"
    r = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", str(hooks), "-p", "test_*.py"],
        capture_output=True, text=True, timeout=120,
    )
    assert r.returncode == 0, r.stderr


# ── Round 3 のレビューで見つかった穴

@pytest.mark.parametrize("desc", ['say "hi"', "back\\slash", "a `b`", "x __OWNER__ y"])
def test_JSON_や_TOML_を壊す説明は何も書かずに落とす(tmp_path: Path, desc: str) -> None:
    dest = tmp_path / "demo"
    assert make(dest, "--stack", "node", "--description", desc) == 1
    assert not dest.exists()


@pytest.mark.parametrize("opt", ["--owner=a b", "--owner=x\ny", "--codeowner=a\nb", "--codeowner=@nigoh"])
def test_持ち主の名前の誤りは落とす(tmp_path: Path, opt: str) -> None:
    assert make(tmp_path / "demo", "--stack", "python", "--description", "x", opt) == 1


def test_先頭が数字の名前は落とす(tmp_path: Path) -> None:
    assert make(tmp_path / "x", "--stack", "python", "--name=1abc") == 1


def test_force_でもシンボリックリンクの先には書かない(tmp_path: Path) -> None:
    victim = tmp_path / "victim.txt"
    victim.write_text("守る", encoding="utf-8")
    dest = tmp_path / "demo"
    dest.mkdir()
    (dest / "README.md").symlink_to(victim)
    assert make(dest, "--stack", "python", "--description", "x", "--force") == 1
    assert victim.read_text(encoding="utf-8") == "守る"


def test_生成した_package_json_と_pyproject_が読める(tmp_path: Path) -> None:
    import tomllib
    make(tmp_path / "n", "--stack", "node", "--description", "説明（かっこ）・記号 & < >")
    json.loads((tmp_path / "n/package.json").read_text(encoding="utf-8"))
    make(tmp_path / "p", "--stack", "python", "--description", "説明 'single' & <x>")
    tomllib.loads((tmp_path / "p/pyproject.toml").read_text(encoding="utf-8"))


@pytest.mark.parametrize("stack,tests_path", [("python", "tests/test_smoke.py"), ("node", "tests/index.test.mjs")])
def test_テストを消すと_check_sh_が落ちる(tmp_path: Path, stack: str, tests_path: str) -> None:
    dest = tmp_path / "demo"
    make(dest, "--stack", stack, "--description", "x")
    git_init(dest)
    (dest / tests_path).unlink()
    r = run_check(dest)
    assert r.returncode == 1, r.stdout


def test_rust_のテストを消すと_check_sh_が落ちる(tmp_path: Path) -> None:
    if shutil.which("cargo") is None:
        pytest.skip("cargo が無い（CI の rust のジョブで確かめる）")
    dest = tmp_path / "demo"
    make(dest, "--stack", "rust", "--description", "x")
    git_init(dest)
    (dest / "src/lib.rs").write_text("pub fn f() {}\n", encoding="utf-8")
    r = run_check(dest)
    assert r.returncode == 1 and "1 件も" in r.stdout, r.stdout


def test_check_stack_sh_の書き間違いで落ちる(tmp_path: Path) -> None:
    dest = tmp_path / "demo"
    make(dest, "--stack", "python", "--description", "x")
    git_init(dest)
    with (dest / "scripts/check-stack.sh").open("a", encoding="utf-8") as f:
        f.write("\nif then fi (\n")
    r = run_check(dest)
    assert r.returncode == 1 and "誤り" in r.stdout


def test_ほかのラベルでは_CI_が走り直さない() -> None:
    for s in STACKS:
        wf = (ROOT / f"templates/project/stacks/{s}/files/.github/workflows/check.yml").read_text(encoding="utf-8")
        assert "github.event.label.name == 'ci'" in wf
        top = wf.split("jobs:")[0]
        assert "concurrency" not in top, "飛ばされた実行が走っている確かめを止める"


def test_枝を消す操作は許可に入れない() -> None:
    s = json.loads((ROOT / "templates/project/base/.claude/settings.json").read_text(encoding="utf-8"))
    assert "Bash(git branch:*)" not in s["permissions"]["allow"]
    assert "Bash(git branch -D:*)" in s["permissions"]["ask"]


# ── Round 4：nigoh のリポジトリと GitHub の推奨から足した物

GITHUB_RECOMMENDED = [
    "README.md", "LICENSE", "CONTRIBUTING.md", "CHANGELOG.md", ".env.example",
    ".github/pull_request_template.md", ".github/ISSUE_TEMPLATE/bug.yml", ".github/ISSUE_TEMPLATE/feature.yml",
    ".github/ISSUE_TEMPLATE/round.yml", ".github/ISSUE_TEMPLATE/config.yml", ".github/CODEOWNERS",
    ".github/dependabot.yml", ".github/release.yml", ".claude/rules/tests.md", "scripts/setup_github.sh",
]


@pytest.mark.parametrize("stack", STACKS)
def test_GitHub_が推すファイルがそろう(tmp_path: Path, stack: str) -> None:
    dest = tmp_path / "demo"
    make(dest, "--stack", stack, "--description", "x")
    missing = [f for f in GITHUB_RECOMMENDED if not (dest / f).is_file()]
    assert not missing
    assert not (dest / "SECURITY.md").exists()  # Organization の .github の物が効く


def test_ライセンスを選べて_既定は社外で使わせない物(tmp_path: Path) -> None:
    make(tmp_path / "p", "--stack", "node", "--description", "x")
    assert "All rights reserved" in (tmp_path / "p/LICENSE").read_text(encoding="utf-8")
    assert json.loads((tmp_path / "p/package.json").read_text(encoding="utf-8"))["license"] == "UNLICENSED"
    make(tmp_path / "m", "--stack", "node", "--description", "x", "--license", "mit", "--holder", "nigoh")
    lic = (tmp_path / "m/LICENSE").read_text(encoding="utf-8")
    assert lic.startswith("MIT License") and "nigoh" in lic
    assert json.loads((tmp_path / "m/package.json").read_text(encoding="utf-8"))["license"] == "MIT"


def test_GitHub_の_LICENSE_つきで作ったリポジトリは_force_が要る(tmp_path: Path) -> None:
    dest = tmp_path / "demo"
    dest.mkdir()
    (dest / "LICENSE").write_text("MIT License\n", encoding="utf-8")
    assert make(dest, "--stack", "python", "--description", "x") == 1


def test_著作権者の誤りは落とす(tmp_path: Path) -> None:
    assert make(tmp_path / "d", "--stack", "python", "--description", "x", "--holder", 'a"b') == 1


@pytest.mark.parametrize("stack", STACKS)
def test_PR_のタイトルを見る_job_も_ci_ラベルのときだけ(tmp_path: Path, stack: str) -> None:
    wf = (ROOT / f"templates/project/stacks/{stack}/files/.github/workflows/check.yml").read_text(encoding="utf-8")
    pr = wf.split("pr-title:")[1]
    assert "'ci'" in pr and "Conventional Commits" in pr
    assert "github.event.action != 'edited'" in wf.split("pr-title:")[0]  # タイトルの書き換えで check を流し直さない


def test_setup_github_sh_は既定では何も変えない(tmp_path: Path) -> None:
    dest = tmp_path / "demo"
    make(dest, "--stack", "python", "--description", "x")
    r = subprocess.run(["bash", "scripts/setup_github.sh"], cwd=dest, capture_output=True, text=True,
                       env={"PATH": "/usr/bin:/bin"}, timeout=30)  # gh を見えなくしても動く＝呼んでいない
    assert r.returncode == 0 and "gh label create \"ci\"" in r.stdout and "--apply" in r.stdout


def test_パス限定の決まりに_paths_がある() -> None:
    text = (ROOT / "templates/project/base/.claude/rules/tests.md").read_text(encoding="utf-8")
    assert text.startswith("---\npaths:\n")
