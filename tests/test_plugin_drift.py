"""plugin_drift.py のテスト。決まりごとに、通る物を通すことと、落とすべき物を落とすことを 1 本ずつ確かめる。

公式の検査（claude plugin validate）は、ふだんは偽物の claude で置き換える。本物で確かめるテストは
test_real_claude_* だけで、claude が無ければ落ちる（未実行を合格にしない）。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import plugin_drift as d  # noqa: E402

TEMPLATE = ROOT / "templates" / "plugin"
PARTS = ROOT / "templates" / "parts"
SCRIPT = ROOT / "scripts" / "plugin_drift.py"


# ── 用意 ────────────────────────────────────────────────

def make_png(path: Path, size: int = 512, rgb=(30, 120, 200)) -> None:
    """外の道具を使わずに、単色の PNG を書く（雛形の仮のアイコンと違う物を作るため）。"""
    row = b"\x00" + bytes(rgb) * size
    raw = zlib.compress(row * size)

    def chunk(t: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + t + data + struct.pack(">I", zlib.crc32(t + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", raw) + chunk(b"IEND", b""))


def fill(dst: Path, *, parts: bool = False) -> Path:
    """雛形を写し、印を書き換えた「書き終えたプラグイン」を作る。"""
    shutil.copytree(TEMPLATE, dst)
    if parts:
        shutil.copytree(PARTS, dst, dirs_exist_ok=True)
    for f in dst.rglob("*"):
        if f.is_file() and f.suffix in d.TEXT_SUFFIXES:
            t = f.read_text(encoding="utf-8").replace("【雛形】", "記入済み").replace("plugin-name", "sample-plugin")
            f.write_text(t, encoding="utf-8")
    make_png(dst / ".claude-plugin" / "icon.png")
    if parts:
        m = manifest(dst)
        m["userConfig"] = {"example_api_key": {"type": "string", "title": "鍵", "description": "MCP の鍵",
                                               "sensitive": True, "required": False}}
        m["privacyPolicyUrl"] = "https://example.com/privacy"
        write_manifest(dst, m)
    return dst


def manifest(p: Path) -> dict:
    return json.loads((p / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))


def write_manifest(p: Path, m: dict) -> None:
    (p / ".claude-plugin" / "plugin.json").write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")


@pytest.fixture
def fake_claude(tmp_path: Path):
    """公式の検査の偽物。FAKE_VALIDATE=fail で落ちた結果を返す。"""
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    exe = bin_dir / "claude"
    exe.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "if os.environ.get('FAKE_VALIDATE') == 'fail':\n"
        "    print(json.dumps({'success': False, 'manifest': {'errors': [{'path': 'name', 'message': 'bad'}],"
        " 'warnings': []}, 'contents': [], 'directory': {'findings': [{'code': 'README_MISSING', 'severity': 'error'}]}}))\n"
        "    sys.exit(1)\n"
        "print(json.dumps({'success': True, 'manifest': {'errors': [], 'warnings': []}, 'contents': [], 'directory': {'findings': []}}))\n",
        encoding="utf-8",
    )
    exe.chmod(0o755)
    return str(exe)


def statuses(rep: d.Report) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for r in rep.results:
        out.setdefault(r.rule, set()).add(r.status)
    return out


def ng_rules(rep: d.Report) -> set[str]:
    return {r.rule for r in rep.merged() if r.status in ("ng", "not_run")}


# ── 雛形そのもの ────────────────────────────────────────

def test_template_fails_only_on_placeholders(fake_claude):
    rep = d.check_plugin(TEMPLATE, claude=fake_claude, repo=False)
    assert ng_rules(rep) == {"F07", "F08"}


def test_filled_template_passes_every_rule(tmp_path, fake_claude):
    rep = d.check_plugin(fill(tmp_path / "p"), claude=fake_claude, repo=False)
    assert ng_rules(rep) == set()
    assert rep.counts() == {"must_ng": 0, "should_ng": 0, "not_run": 0}


def test_filled_template_with_parts_passes_and_checks_parts(tmp_path, fake_claude):
    rep = d.check_plugin(fill(tmp_path / "p", parts=True), claude=fake_claude, repo=False)
    assert ng_rules(rep) == set()
    st = statuses(rep)
    for rule in ("A01", "A02", "A03", "H01", "H02", "H03", "H04", "P01", "P02"):
        assert "ok" in st[rule], rule  # 部品があるときは「対象外」でなく、実際に見て合格している


def test_real_claude_validates_template_and_parts(tmp_path):
    """本物の claude で、雛形と、部品を足した物が公式ディレクトリの基準を通ること。"""
    assert shutil.which("claude"), "未実行：claude がありません（npm install -g @anthropic-ai/claude-code）"
    for p in (TEMPLATE, fill(tmp_path / "with-parts", parts=True)):
        r = subprocess.run(["claude", "plugin", "validate", "--strict", "--profile", "directory", str(p)],
                           capture_output=True, text=True, timeout=120)
        assert r.returncode == 0 and "Validation passed" in r.stdout, r.stdout + r.stderr


def test_real_claude_v01_catches_missing_readme(tmp_path):
    assert shutil.which("claude"), "未実行：claude がありません"
    p = fill(tmp_path / "p")
    (p / "README.md").unlink()
    rep = d.check_plugin(p, claude="claude", repo=False)
    assert "ng" in statuses(rep)["V01"]


# ── 決まりごとに、落とすべき物を落とす ──────────────────

def _m(key, value=None, delete=False):
    def f(p: Path):
        m = manifest(p)
        if delete:
            m.pop(key, None)
        else:
            m[key] = value
        write_manifest(p, m)
    return f


def _write(rel, text, mode="w"):
    def f(p: Path):
        q = p / rel
        q.parent.mkdir(parents=True, exist_ok=True)
        if mode == "a":
            q.write_text(q.read_text(encoding="utf-8") + text, encoding="utf-8")
        else:
            q.write_text(text, encoding="utf-8")
    return f


def _rm(*rels):
    def f(p: Path):
        for rel in rels:
            q = p / rel
            shutil.rmtree(q) if q.is_dir() else q.unlink()
    return f


def _both(*fs):
    def f(p: Path):
        for g in fs:
            g(p)
    return f


def _sub(rel, old, new):
    def f(p: Path):
        q = p / rel
        t = q.read_text(encoding="utf-8")
        assert old in t, f"{rel} に {old!r} が無い"
        q.write_text(t.replace(old, new), encoding="utf-8")
    return f


SKILL = "skills/example/SKILL.md"
AGENT_OK = "---\nname: helper\ndescription: 読んで返す\ntools: Read\n---\n本文\n"
HOOK = lambda h: json.dumps({"hooks": {"Stop": [{"hooks": [h]}]}})  # noqa: E731
GOOD_HOOK = {"type": "command", "command": "node", "args": ["${CLAUDE_PLUGIN_ROOT}/hooks/x.mjs"], "timeout": 5}

BREAKS = {
    "M01": _write(".claude-plugin/plugin.json", "{ 壊れた"),
    "M02": _m("name", "claude-helper"),
    "M03": _m("version", "1.0"),
    "M04": _m("description", delete=True),
    "M05": _m("author", delete=True),
    "M06": _m("homepage", delete=True),
    "M07": _both(_m("license", delete=True), _rm("LICENSE")),
    "M08": _m("keywords", []),
    "M09": _m("$schema", delete=True),
    "M10": _m("supportUrl", delete=True),
    "M11": _m("skills", "../outside"),
    "F01": _rm("README.md"),
    "F02": _sub("README.md", "/plugin install", "/plugin なにか"),
    "F03": _sub("README.md", "## 動かすもの・送るもの", "## そのほか"),
    "F04": _rm("LICENSE"),
    "F05": _sub("CHANGELOG.md", "## [0.1.0]", "## [0.0.9]"),
    "F06": _both(_m("icon", delete=True), _rm(".claude-plugin/icon.png")),
    "F07": lambda p: shutil.copy(TEMPLATE / ".claude-plugin" / "icon.png", p / ".claude-plugin" / "icon.png"),
    "F08": _write("README.md", "\n【雛形】書き忘れ\n", mode="a"),
    "F09": _write("CLAUDE.md", "# 読まれない\n"),
    "F10": _write(".DS_Store", "x"),
    "F11": _write("skills/example/references/big.md", "x" * (d.MAX_FILE + 1)),
    "F12": _rm("README.md"),
    "S01": _write(SKILL, "---\nname: example\n---\n本文\n"),
    "S02": _sub(SKILL, "name: example", "name: other"),
    "S03": _both(_rm("skills/example"), _write("skills/claude-tool/SKILL.md", "---\ndescription: 何か\n---\n本文\n")),
    "S04": _write(SKILL, "---\nname: example\ndescription: " + "あ" * (d.DESC_MAX + 1) + "\n---\n本文\n"),
    "S05": _write(SKILL, "---\nname: example\ndescription: 何か\n---\n" + "行\n" * d.SKILL_MAX_LINES),
    "S06": _write(SKILL, "\n- [無い資料](references/none.md)\n", mode="a"),
    "S07": _write("skills/example/references/long.md", "# 長い\n" + "行\n" * (d.TOC_AFTER + 5)),
    "S08": _write(SKILL, "\nscripts\\helper.py を流す\n", mode="a"),
    "A01": _write("agents/helper.md", "---\nname: helper\ntools: Read\n---\n本文\n"),
    "A02": _write("agents/helper.md", "---\nname: helper\ndescription: 読む\n---\n本文\n"),
    "A03": _write("agents/helper.md", "---\nname: helper\ndescription: 読む\ntools: Read\npermissionMode: plan\n---\n本文\n"),
    "H01": _write("hooks/hooks.json", json.dumps({"Stop": []})),
    "H02": _write("hooks/hooks.json", HOOK({"type": "command", "command": "node ./hooks/x.mjs", "timeout": 5})),
    "H03": _write("hooks/hooks.json", HOOK({"type": "command", "command": "node", "args": ["${CLAUDE_PLUGIN_ROOT}/x.mjs"]})),
    "H04": _write("hooks/hooks.json", HOOK({"type": "command", "command": "node ${CLAUDE_PLUGIN_ROOT}/x.mjs", "timeout": 5})),
    "P01": _write(".mcp.json", json.dumps({"mcpServers": {"s": {"command": "npx", "args": ["-y", "some-server"]}}})),
    "P02": _write(".mcp.json", json.dumps({"mcpServers": {"s": {"type": "http", "url": "http://example.com/mcp"}}})),
    "E01": _rm("evals/example-result", "evals/example-guard"),
    "E02": _rm("evals/example-fires/graders"),
}


@pytest.mark.parametrize("rule", sorted(BREAKS))
def test_each_rule_catches_its_break(rule, tmp_path, fake_claude):
    p = fill(tmp_path / "p")
    BREAKS[rule](p)
    rep = d.check_plugin(p, claude=fake_claude, repo=False)
    assert "ng" in statuses(rep).get(rule, set()), [r for r in rep.results if r.rule == rule]


def test_every_plugin_rule_has_a_break_test():
    plugin_rules = {k for k in d.RULES if k[0] in "MFSAHPE"}
    assert plugin_rules == set(BREAKS), plugin_rules ^ set(BREAKS)


def test_good_hook_and_agent_pass(tmp_path, fake_claude):
    p = fill(tmp_path / "p")
    _write("agents/helper.md", AGENT_OK)(p)
    _write("hooks/hooks.json", HOOK(GOOD_HOOK))(p)
    _write("hooks/x.mjs", "process.exit(0)\n")(p)
    _write(".mcp.json", json.dumps({"mcpServers": {"a": {"command": "uvx", "args": ["pkg==1.2.0"]},
                                                     "b": {"command": "npx", "args": ["-y", "@scope/srv@2.0.1"]},
                                                     "c": {"type": "http", "url": "https://x.example/mcp"}}}))(p)
    assert ng_rules(d.check_plugin(p, claude=fake_claude, repo=False)) == set()


def test_shell_form_with_quoted_root_passes_h04(tmp_path, fake_claude):
    p = fill(tmp_path / "p")
    _write("hooks/hooks.json", HOOK({"type": "command", "command": 'node "${CLAUDE_PLUGIN_ROOT}/x.mjs"', "timeout": 5}))(p)
    assert "H04" not in ng_rules(d.check_plugin(p, claude=fake_claude, repo=False))


def test_root_readme_counts_for_f01_but_not_f12(tmp_path, fake_claude):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "README.md").write_text("# 直下の README\n", encoding="utf-8")
    p = fill(repo / "plugin")
    (p / "README.md").unlink()
    st = statuses(d.check_plugin(p, claude=fake_claude, repo=False))
    assert st["F01"] == {"ok"} and st["F12"] == {"ng"}


# ── 公式の検査（V01） ──────────────────────────────────

def test_v01_fails_when_validate_fails(tmp_path, fake_claude, monkeypatch):
    monkeypatch.setenv("FAKE_VALIDATE", "fail")
    rep = d.check_plugin(fill(tmp_path / "p"), claude=fake_claude, repo=False)
    v = [r for r in rep.results if r.rule == "V01"][0]
    assert v.status == "ng" and "README_MISSING" in v.message


def test_v01_is_not_run_without_claude(tmp_path):
    rep = d.check_plugin(fill(tmp_path / "p"), claude=str(tmp_path / "no-such-claude"), repo=False)
    assert statuses(rep)["V01"] == {"not_run"}
    assert rep.counts()["not_run"] == 1


# ── リポジトリ側（R**） ─────────────────────────────────

def make_repo(tmp_path: Path, *, ci: str | None, check_sh: str | None = None, pr=True, tests=True) -> Path:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    if ci is not None:
        (repo / ".github" / "workflows").mkdir(parents=True)
        (repo / ".github" / "workflows" / "check.yml").write_text(ci, encoding="utf-8")
    if check_sh is not None:
        (repo / "scripts").mkdir()
        (repo / "scripts" / "check.sh").write_text(check_sh, encoding="utf-8")
    if pr:
        (repo / ".github").mkdir(exist_ok=True)
        (repo / ".github" / "pull_request_template.md").write_text("## 何を\n", encoding="utf-8")
    if tests:
        (repo / "tests").mkdir()
    return fill(repo / "plugin")


def test_repo_rules_pass_with_ci_calling_check_sh(tmp_path, fake_claude):
    p = make_repo(tmp_path, ci="run: scripts/check.sh\n", check_sh="claude plugin validate --strict plugin\n")
    st = statuses(d.check_plugin(p, claude=fake_claude))
    assert all(st[r] == {"ok"} for r in ("R01", "R02", "R03", "R04")), st


def test_repo_template_satisfies_repo_rules(tmp_path, fake_claude):
    repo = tmp_path / "repo"
    shutil.copytree(ROOT / "templates" / "repo", repo)
    (repo / ".git").mkdir()
    (repo / "tests").mkdir()
    p = fill(repo / "plugin")
    st = statuses(d.check_plugin(p, claude=fake_claude))
    assert all(st[r] == {"ok"} for r in ("R01", "R02", "R03", "R04")), st


@pytest.mark.parametrize("rule,kw", [
    ("R01", dict(ci=None)),
    ("R01", dict(ci="run: pytest\n")),
    ("R02", dict(ci="run: claude plugin validate plugin\n")),
    ("R03", dict(ci="run: claude plugin validate --strict plugin\n", pr=False)),
    ("R04", dict(ci="run: claude plugin validate --strict plugin\n", tests=False)),
])
def test_repo_rules_catch_breaks(rule, kw, tmp_path, fake_claude):
    p = make_repo(tmp_path, **kw)
    assert "ng" in statuses(d.check_plugin(p, claude=fake_claude))[rule]


# ── マーケットプレイス（K**） ───────────────────────────

def make_market(tmp_path: Path, entry: dict) -> Path:
    root = tmp_path / "market"
    (root / ".claude-plugin").mkdir(parents=True)
    fill(root / "plugins" / "sample-plugin")
    (root / ".claude-plugin" / "marketplace.json").write_text(json.dumps({"name": "m", "owner": {"name": "o"},
                                                                         "plugins": [entry]}), encoding="utf-8")
    return root / ".claude-plugin" / "marketplace.json"


def test_marketplace_entry_passes(tmp_path, fake_claude):
    mp = make_market(tmp_path, {"name": "sample-plugin", "source": "./plugins/sample-plugin",
                                "description": "見本", "category": "productivity"})
    [rep] = d.check_marketplace(mp, tmp_path, claude=fake_claude, repo=False)
    assert ng_rules(rep) == set()


@pytest.mark.parametrize("rule,entry", [
    ("K01", {"name": "other-name", "source": "./plugins/sample-plugin", "description": "x", "category": "c"}),
    ("K02", {"name": "sample-plugin", "source": "./plugins/sample-plugin"}),
])
def test_marketplace_rules_catch_breaks(rule, entry, tmp_path, fake_claude):
    [rep] = d.check_marketplace(make_market(tmp_path, entry), tmp_path, claude=fake_claude, repo=False)
    assert "ng" in statuses(rep)[rule]


def test_marketplace_missing_checkout_is_not_run(tmp_path, fake_claude):
    mp = make_market(tmp_path, {"name": "far", "source": {"source": "git-subdir",
                                                         "url": "https://github.com/o/far.git", "path": "plugin"}})
    [rep] = d.check_marketplace(mp, tmp_path, claude=fake_claude, repo=False)
    assert rep.counts()["not_run"] == 1


def test_git_subdir_resolves_into_workspace(tmp_path):
    e = {"source": {"source": "git-subdir", "url": "https://github.com/o/konomi.git", "path": "plugin"}}
    assert d.resolve_entry(e, tmp_path, tmp_path / "ws") == tmp_path / "ws" / "konomi" / "plugin"


# ── 命令としての動き ────────────────────────────────────

def run_cli(*args, env=None):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
                          env={**os.environ, **(env or {})})


def test_cli_exit_codes(tmp_path, fake_claude):
    good = fill(tmp_path / "good")
    assert run_cli("--no-repo", "--claude", fake_claude, str(good)).returncode == 0
    assert run_cli("--no-repo", "--claude", fake_claude, str(TEMPLATE)).returncode == 1
    assert run_cli().returncode == 2
    assert run_cli("--no-repo", "--claude", str(tmp_path / "none"), str(good)).returncode == 1  # 未実行は落とす


def test_cli_strict_fails_on_should(tmp_path, fake_claude):
    p = fill(tmp_path / "p")
    _rm("CHANGELOG.md")(p)  # F05 は推奨
    assert run_cli("--no-repo", "--claude", fake_claude, str(p)).returncode == 0
    assert run_cli("--no-repo", "--strict", "--claude", fake_claude, str(p)).returncode == 1


def test_cli_json_shape(tmp_path, fake_claude):
    r = run_cli("--json", "--no-repo", "--claude", fake_claude, str(TEMPLATE))
    data = json.loads(r.stdout)
    assert data[0]["counts"]["must_ng"] == 2
    assert {x["rule"] for x in data[0]["results"] if x["status"] == "ng"} == {"F07", "F08"}
    assert all(x["source"] for x in data[0]["results"])


# ── 読む道具 ────────────────────────────────────────────

def test_simple_yaml_reads_folded_description_and_lists():
    raw = "name: x\ndescription: 一行目\n  二行目\ntools:\n  - Read\n  - Grep\nflag: true\nlist: [a, \"b\"]"
    assert d._simple_yaml(raw) == {"name": "x", "description": "一行目 二行目", "tools": ["Read", "Grep"],
                                   "flag": True, "list": ["a", "b"]}


def test_frontmatter_without_closing_is_unreadable():
    assert d.parse_frontmatter("---\nname: x\n本文")[0] is None


# ── 文書とのそろい ──────────────────────────────────────

def test_rules_table_in_readme_matches_code():
    text = (ROOT / "templates" / "README.md").read_text(encoding="utf-8")
    rows = dict(re.findall(r"^\| ([A-Z]\d\d) \| (必須|推奨) \|", text, re.M))
    assert rows == {k: d.LEVEL[v[0]] for k, v in d.RULES.items()}


def test_every_rule_has_a_source():
    for k, (level, title, source) in d.RULES.items():
        assert level in (d.MUST, d.SHOULD) and title and source, k
        assert source.startswith("https://") or source == d.D_NOK, k
