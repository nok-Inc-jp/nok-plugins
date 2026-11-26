"""kanna の道具（harness_lint・eval_ledger・kanna-guard）と、kanna 自身の形のテスト。

落とすべき物を落とすか（壊したプラグインで外れが出るか）を先に見る。どれも利用料を使わない。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
KANNA = ROOT / "plugins" / "kanna"
sys.path.insert(0, str(KANNA / "scripts"))

import eval_ledger  # noqa: E402
import harness_lint  # noqa: E402

GUARD = KANNA / "hooks" / "kanna-guard.mjs"


# ---------- 見本のプラグインを作る ----------

def write(root: Path, rel: str, text: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(text).lstrip("\n"), encoding="utf-8")
    return p


def good_plugin(tmp: Path) -> Path:
    """決まりをすべて満たす、小さなプラグイン。"""
    p = tmp / "good"
    write(p, ".claude-plugin/plugin.json", '{"name": "good", "version": "0.1.0", "description": "見本"}')
    write(p, "skills/invoice-check/SKILL.md", """
        ---
        name: invoice-check
        description: 請求書の記載事項を点検する。「請求書を確かめて」と言われたときに使う
        ---
        # invoice-check
        1. 読む
        2. `python3 "${CLAUDE_SKILL_DIR}/scripts/check.py"` を流す
        """)
    write(p, "agents/reader.md", """
        ---
        name: reader
        description: 請求書を読んで要点を返す。invoice-check から呼ばれる
        tools: Read, Grep
        ---
        ## 返す形
        表で返す。
        """)
    write(p, "evals/fires/prompt.md", """
        ---
        name: fires
        tags: [trigger]
        expected_outcome: invoice-check を使う
        allowed_tools: [Read, Skill]
        ---
        この請求書を確かめて
        """)
    write(p, "evals/fires/graders/01.md", """
        ---
        type: tool_used
        tool: Skill
        input_match: '"skill":\\s*"[^"]*invoice-check'
        min: 1
        ---
        呼んだ。
        """)
    write(p, "evals/quiet/prompt.md", """
        ---
        name: quiet
        tags: [trigger]
        expected_outcome: 呼ばない
        ---
        見積書の書き方を教えて
        """)
    write(p, "evals/quiet/graders/01.md", """
        ---
        type: tool_used
        tool: Skill
        input_match: '"skill":\\s*"[^"]*invoice-check'
        min: 0
        max: 0
        arm: both
        ---
        呼ばない。
        """)
    write(p, "evals/result/prompt.md", """
        ---
        name: result
        tags: [outcome, safety, needs-write]
        expected_outcome: 報告を書く
        ---
        /good:invoice-check 請求書.pdf
        """)
    write(p, "evals/result/graders/01.md", """
        ---
        type: regex
        target:
          source: file
          path: report.md
        pattern: '^## 見ていない所'
        flags: m
        ---
        見出しがある。
        """)
    write(p, "evals/result/graders/02.md", """
        ---
        type: tool_used
        tool: Edit
        min: 0
        max: 0
        ---
        直さない。
        """)
    write(p, "evals/result/graders/03.md", """
        ---
        type: llm
        focus:
          source: file
          path: report.md
        ---
        合格：登録番号の抜けを挙げている。不合格：触れていない。
        """)
    return p


def ng_rules(rep: harness_lint.Report) -> set[str]:
    return {r.rule for r in rep.results if r.status == "ng"}


# ---------- harness_lint ----------

def test_good_plugin_passes_every_rule(tmp_path):
    rep = harness_lint.lint_plugin(good_plugin(tmp_path))
    assert ng_rules(rep) == set(), [(r.rule, r.detail) for r in rep.results if r.status == "ng"]


@pytest.mark.parametrize("rule, breaker", [
    ("QE01", lambda p: (p / "evals/fires/prompt.md").write_text(
        (p / "evals/fires/prompt.md").read_text().replace("tags:", "timeout: 3\ntags:"))),
    ("QE02", lambda p: write(p, "evals/fires/graders/02.md", "---\ntype: contains\n---\nx\n")),
    ("QE03", lambda p: write(p, "evals/fires/graders/02.md", "---\ntype: regex\npattern: '(?i)abc'\n---\nx\n")),
    ("QE05", lambda p: write(p, "evals/result/graders/03.md",
                             "---\ntype: llm\n---\n(1) A がある。(2) B がある。どれか 1 つでも欠ければ不合格。\n")),
    ("QE06", lambda p: [(p / f"evals/result/graders/{n}.md").unlink() for n in ("01", "02")]),
    ("QE07", lambda p: ((p / "evals/quiet/graders/01.md").write_text(
        (p / "evals/quiet/graders/01.md").read_text().replace("arm: both\n", "")),
        write(p, "evals/quiet/graders/02.md", "---\ntype: regex\npattern: '見積'\n---\nx\n"))),
    ("QE08", lambda p: (p / "evals/fires/graders/01.md").write_text(
        (p / "evals/fires/graders/01.md").read_text().replace("invoice-check", "invoce-check"))),
    ("QE09", lambda p: write(p, "evals/result/graders/04.md", "---\ntype: tool_used\ntool: Bash\nmin: 1\n---\nx\n")),
    ("QE10", lambda p: write(p, "evals/result/case.yaml", 'schema_version: "1.1"\nname: result\ncontext:\n  scaffold_script: nope.sh\n')),
    ("QE11", lambda p: (p / "evals/quiet/prompt.md").write_text(
        (p / "evals/quiet/prompt.md").read_text().replace("name: quiet", "name: silent"))),
    ("QE12", lambda p: (p / "evals/quiet/prompt.md").write_text(
        (p / "evals/quiet/prompt.md").read_text().replace("tags: [trigger]", "tags: [cheap]"))),
    ("QE13", lambda p: (p / "evals/result/graders/02.md").write_text(
        (p / "evals/result/graders/02.md").read_text().replace("tool: Edit\n", "tool: Edit\ninput_match: 'src/'\n"))),
    ("QE15", lambda p: (p / "evals/fires/graders/01.md").write_text(
        (p / "evals/fires/graders/01.md").read_text().replace('\'"skill":\\s*"[^"]*invoice-check\'', "'invoice-check'"))),
    ("QG01", lambda p: shutil.rmtree(p / "evals/fires")),
    ("QG02", lambda p: shutil.rmtree(p / "evals/quiet")),
    ("QG04", lambda p: (p / "evals/result/graders/02.md").unlink()),
    ("QS01", lambda p: (p / "skills/invoice-check/SKILL.md").write_text(
        (p / "skills/invoice-check/SKILL.md").read_text().replace("「請求書を確かめて」と言われたときに使う", "点検の結果を返す"))),
    ("QS02", lambda p: (p / "skills/invoice-check/SKILL.md").write_text(
        (p / "skills/invoice-check/SKILL.md").read_text().replace("name: invoice-check", "name: invoice-check\nallowed_tools: Read"))),
    ("QS03", lambda p: (write(p, "skills/invoice-check/references/a.md", "[b](b.md)\n"),
                        write(p, "skills/invoice-check/references/b.md", "b\n"))),
    ("QS04", lambda p: (p / "skills/invoice-check/SKILL.md").write_text(
        (p / "skills/invoice-check/SKILL.md").read_text().replace('"${CLAUDE_SKILL_DIR}/scripts/check.py"', "scripts/check.py"))),
    ("QA01", lambda p: (p / "agents/reader.md").write_text((p / "agents/reader.md").read_text().replace("tools:", "tool: Read\ntools:"))),
    ("QA03", lambda p: (p / "agents/reader.md").write_text((p / "agents/reader.md").read_text().replace("## 返す形", "## 進め方"))),
    ("QA04", lambda p: (p / "agents/reader.md").write_text((p / "agents/reader.md").read_text().replace("tools: Read, Grep", "tools: Read, Write"))),
    ("QH01", lambda p: (write(p, "hooks/hooks.json", json.dumps({"hooks": {"Stop": [{"hooks": [
        {"type": "command", "command": "node", "args": ["${CLAUDE_PLUGIN_ROOT}/hooks/gate.mjs"]}]}]}})),
                        write(p, "hooks/gate.mjs", "process.exit(0)\n"))),
    ("QH02", lambda p: write(p, "hooks/hooks.json", json.dumps({"hooks": {"PreToolUse": [{"hooks": [
        {"type": "command", "command": "node", "args": ["${CLAUDE_PLUGIN_ROOT}/hooks/missing.mjs"]}]}]}}))),
])
def test_broken_plugin_is_caught(tmp_path, rule, breaker):
    p = good_plugin(tmp_path)
    breaker(p)
    assert rule in ng_rules(harness_lint.lint_plugin(p))


def test_english_agent_descriptions_are_understood(tmp_path):
    """英語の書き方（Use this agent only from…・Reply with exactly: DONE）を外れにしない。"""
    p = good_plugin(tmp_path)
    write(p, "agents/reader.md", """
        ---
        name: reader
        description: Use this agent only from the invoice-check workflow, to read one invoice.
        tools: Read
        ---
        1. Read the file.
        2. Reply with exactly: DONE
        """)
    assert not {"QA02", "QA03"} & ng_rules(harness_lint.lint_plugin(p))


def test_probe_scaffold_catches_vacuous_not_contains(tmp_path):
    """見本に無い値を「含まない」で見る grader は、--probe-scaffold で空振りとして出る。"""
    if shutil.which("bash") is None:
        pytest.skip("bash がありません")
    p = good_plugin(tmp_path)
    write(p, "evals/result/case.yaml", 'schema_version: "1.1"\nname: result\ncontext:\n  scaffold_script: scaffold.sh\n')
    write(p, "evals/result/scaffold.sh", "#!/usr/bin/env bash\nset -eu\necho 'key = FAKE-VALUE-1' > config.txt\n")
    write(p, "evals/result/graders/04.md", "---\ntype: regex\npattern: 'FAKE-VALUE-1'\nmatch: not_contains\n---\n値を書き写さない。\n")
    assert "QE14" not in ng_rules(harness_lint.lint_plugin(p, probe=True))
    write(p, "evals/result/graders/04.md", "---\ntype: regex\npattern: 'OLD-VALUE'\nmatch: not_contains\n---\n値を書き写さない。\n")
    assert "QE14" in ng_rules(harness_lint.lint_plugin(p, probe=True))
    assert "QE14" not in ng_rules(harness_lint.lint_plugin(p))  # 付けなければ流さない


def test_ok_rows_carry_no_failure_text(tmp_path):
    """合格の行に、外れのときの文を入れない（R10 で、kanna-audit を流した haiku が読み違えかけた）。"""
    rep = harness_lint.lint_plugin(good_plugin(tmp_path))
    assert all(r.detail == "" for r in rep.results if r.status == "ok")


def test_must_rules_fail_the_exit_code(tmp_path):
    p = good_plugin(tmp_path)
    assert harness_lint.main([str(p)]) == 0
    (p / "evals/fires/graders/01.md").write_text((p / "evals/fires/graders/01.md").read_text().replace("invoice-check", "x"))
    assert harness_lint.main([str(p)]) == 1
    assert harness_lint.main([]) == 2


def test_should_rules_fail_only_with_strict(tmp_path):
    p = good_plugin(tmp_path)
    shutil.rmtree(p / "evals/quiet")
    assert harness_lint.main([str(p)]) == 0
    assert harness_lint.main([str(p), "--strict"]) == 1


def test_gated_tool_in_allowed_tools_counts(tmp_path):
    """pipe-in のように tags で示す形も、allowed_tools に書く形も、どちらも外れにしない。"""
    p = good_plugin(tmp_path)
    write(p, "evals/result/graders/04.md", "---\ntype: tool_used\ntool: Bash\nmin: 1\n---\nx\n")
    pm = p / "evals/result/prompt.md"
    pm.write_text(pm.read_text().replace("needs-write]", "needs-write, needs-bash]"))
    assert "QE09" not in ng_rules(harness_lint.lint_plugin(p))


def test_mini_yaml_matches_pyyaml():
    """pyyaml が無い手元でも、frontmatter と case.yaml を同じに読む。"""
    yaml = pytest.importorskip("yaml")
    samples = [
        "name: a\ntags: [x, 'y z', needs-bash]\nmax_turns: 10\narm: both\n",
        'schema_version: "1.1"\nname: c\ncontext:\n  scaffold_script: s.sh\nexecution:\n  model: haiku\n',
        "type: regex\ntarget:\n  source: file\n  path: r.md\npattern: '^## 見ていない所'\nflags: m\n",
        "type: tool_used\nmin: 0\nmax: 0\nexists: false\n",
    ]
    for s in samples:
        assert harness_lint._mini_yaml(s.splitlines(), 0)[0] == yaml.safe_load(s), s


def test_rules_doc_matches_code():
    """references/rules.md の表と RULES が同じ（片方だけを直さない）。"""
    doc = (KANNA / "skills/kanna-audit/references/rules.md").read_text(encoding="utf-8")
    rows = dict(re.findall(r"^\| (Q[A-Z]\d\d) \| (?:必須|推奨) \| (.+?) \| ", doc, re.M))
    assert set(rows) == set(harness_lint.RULES)
    for k, (_, text, _) in harness_lint.RULES.items():
        assert rows[k] == text, k
    for k in harness_lint.RULES:
        if k not in ("QG05",):
            assert f"**{k}" in doc or f"・{k}**" in doc, f"{k} の直し方が無い"


# ---------- eval_ledger ----------

def agg(scores: dict[str, float], delta: float | None = 0.3, version: str = "2.1.332") -> dict:
    return {
        "aggregates": {"overallScore": sum(scores.values()) / len(scores), "casesPassed": sum(v == 1 for v in scores.values()),
                       "casesTotal": len(scores), "meanDelta": delta},
        "cases": [{"name": k, "aggregates": {"score": v, "delta": delta}, "arms": {"with": [{}, {}, {}]}} for k, v in scores.items()],
        "costUsd": 0.42, "claudeVersion": version,
    }


def test_ledger_flags_regression_and_flaky(tmp_path):
    led = tmp_path / "ledger.jsonl"
    r1, r2 = tmp_path / "r1.json", tmp_path / "r2.json"
    r1.write_text(json.dumps(agg({"a": 1.0, "b": 1.0, "c": 0.0})))
    r2.write_text(json.dumps(agg({"a": 1.0, "b": 0.6667, "d": 1.0}, delta=0.0)))
    assert eval_ledger.main(["record", str(r1), "--ledger", str(led), "--model", "haiku"]) == 0
    assert eval_ledger.main(["record", str(r2), "--ledger", str(led), "--model", "haiku"]) == 1
    rows = eval_ledger.read_ledger(led)
    assert len(rows) == 2
    diff = eval_ledger.compare(rows[0], rows[1])
    assert diff["regressed"][0].startswith("b（1 → 0.6667・3/3 → 2/3・p=")
    assert diff["flaky"] == ["b"] and diff["new"] == ["d"] and diff["gone"] == ["c"]
    assert set(diff["no_lift"]) == {"a", "b", "d"}


def test_ledger_does_not_flag_negative_cases_as_no_lift(tmp_path):
    """呼ばれないケースは、プラグイン無しでも同じ点が正しい。「効いていない」と出さない。"""
    r = agg({"quiet": 1.0, "fires": 1.0}, delta=0.0)
    r["cases"][0]["graders"] = [{"type": "tool_used", "config": {"tool": "Skill", "max": 0}}]
    cur = eval_ledger.summarize(r, "haiku")
    assert cur["cases"]["quiet"]["negative"] is True
    assert eval_ledger.compare(None, cur)["no_lift"] == ["fires"]


def test_ledger_compares_filtered_runs_per_case(tmp_path):
    """ケースを絞った回が挟まっても、ケースごとに最後に測った点と比べ、絞った回では「消えた」と言わない。"""
    led = tmp_path / "ledger.jsonl"
    r = tmp_path / "r.json"
    r.write_text(json.dumps(agg({"a": 1.0, "b": 1.0})))
    eval_ledger.main(["record", str(r), "--ledger", str(led), "--model", "haiku"])
    r.write_text(json.dumps({**agg({"a": 1.0}), "suite": {"caseFilter": "a"}}))
    eval_ledger.main(["record", str(r), "--ledger", str(led), "--model", "haiku"])
    rows = eval_ledger.read_ledger(led)
    assert eval_ledger.compare(eval_ledger.last_for_model(rows[:1], "haiku"), rows[1])["gone"] == []
    r.write_text(json.dumps(agg({"a": 1.0, "b": 0.5})))
    assert eval_ledger.main(["record", str(r), "--ledger", str(led), "--model", "haiku"]) == 1  # b は 1 回目と比べて下がった


def test_fisher_p_separates_noise_from_real_change():
    """kyoui-fires の実測：対照 8/15 と直した後 15/15 の差は確か。3/3 → 2/3 はぶれの範囲。"""
    assert eval_ledger.fisher_p(15, 15, 8, 15) < 0.01
    assert eval_ledger.fisher_p(3, 3, 2, 3) > 0.4
    assert eval_ledger.fisher_p(5, 5, 5, 5) == 1.0
    assert "確か" in eval_ledger.verdict({"runs": 15, "pass_rate": 1.0}, {"runs": 15, "pass_rate": 8 / 15}, True)
    assert "ぶれの範囲" in eval_ledger.verdict({"runs": 3, "pass_rate": 1.0}, {"runs": 3, "pass_rate": 2 / 3}, True)


def test_ledger_compares_only_same_model(tmp_path):
    led = tmp_path / "ledger.jsonl"
    r = tmp_path / "r.json"
    r.write_text(json.dumps(agg({"a": 1.0})))
    eval_ledger.main(["record", str(r), "--ledger", str(led), "--model", "sonnet"])
    r.write_text(json.dumps(agg({"a": 0.0})))
    # sonnet の回とは比べない（haiku の初めての回なので、下がったとは言わない）
    assert eval_ledger.main(["record", str(r), "--ledger", str(led), "--model", "haiku"]) == 0


def test_ledger_takes_model_from_result_when_omitted(tmp_path):
    """--model を省いたら、結果の suite.modelOverride を使い、前の回とも比べる。"""
    led = tmp_path / "ledger.jsonl"
    r = tmp_path / "r.json"
    r.write_text(json.dumps({**agg({"a": 1.0}), "suite": {"modelOverride": "haiku", "judgeModel": "haiku", "threshold": 1}}))
    assert eval_ledger.main(["record", str(r), "--ledger", str(led)]) == 0
    r.write_text(json.dumps({**agg({"a": 0.5}), "suite": {"modelOverride": "haiku", "judgeModel": "haiku", "threshold": 1}}))
    assert eval_ledger.main(["record", str(r), "--ledger", str(led)]) == 1
    rows = eval_ledger.read_ledger(led)
    assert [x["model"] for x in rows] == ["haiku", "haiku"] and rows[0]["judge_model"] == "haiku"


def test_ledger_refuses_empty_or_broken_results(tmp_path):
    led = tmp_path / "ledger.jsonl"
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert eval_ledger.main(["record", str(bad), "--ledger", str(led), "--model", "haiku"]) == 2
    bad.write_text(json.dumps({"cases": []}))
    assert eval_ledger.main(["record", str(bad), "--ledger", str(led), "--model", "haiku"]) == 2
    assert not led.exists()


# ---------- kanna-guard ----------

def guard(event: dict) -> dict | None:
    if shutil.which("node") is None:
        pytest.skip("node がありません")
    out = subprocess.run(["node", str(GUARD)], input=json.dumps(event), capture_output=True, text=True, timeout=20)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)["hookSpecificOutput"] if out.stdout.strip() else None


def bash(cmd: str, **kw) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": cmd}, **kw}


@pytest.mark.parametrize("cmd, decision", [
    ("claude plugin eval ./plugin --model haiku --max-cost-usd 1", None),
    ("claude plugin eval ./plugin --model haiku \\\n  --max-cost-usd 1 --runs 3", None),
    ("claude plugin eval ./plugin --model haiku", "deny"),
    ("claude plugin eval ./plugin --max-cost-usd 1", "deny"),
    ("cd x && claude plugins eval . --runs 3", "deny"),
    ("claude plugin eval ./plugin --model opus --max-cost-usd 5", "ask"),
    ("claude plugin eval ./plugin --model claude-fable-5-2 --max-cost-usd 5", "ask"),
    ("claude plugin eval ./p --model haiku --max-cost-usd 1 --mocks off", "ask"),
    ("claude plugin eval init --bare x", None),
    ("claude plugin eval --help", None),
    ("python3 harness_lint.py ./plugin", None),
    ("echo 'claude plugin validate'", None),
])
def test_guard_on_eval_commands(cmd, decision):
    out = guard(bash(cmd))
    assert (out or {}).get("permissionDecision") == decision


@pytest.mark.parametrize("agent, path, decision", [
    ("kanna-eval-writer", "/w/plugin/evals/x/prompt.md", None),
    ("kanna:kanna-eval-writer", "/w/plugin/evals/x/graders/01.md", None),
    ("kanna-eval-writer", "/w/plugin/skills/x/SKILL.md", "deny"),
    ("kanna-eval-writer", "/w/plugin/evals/results/a.json", "deny"),
    ("kanna-eval-writer", "/w/plugin/evals/../skills/x/SKILL.md", "deny"),
    ("kanna-skill-reviewer", "/w/kanna-report.md", "deny"),
    ("kanna:kanna-eval-reviewer", "/w/x.md", "deny"),
    ("", "/w/plugin/skills/x/SKILL.md", None),            # 親（会話の本筋）は止めない
    ("other-agent", "/w/plugin/skills/x/SKILL.md", None),
])
def test_guard_on_writes(agent, path, decision):
    out = guard({"tool_name": "Write", "tool_input": {"file_path": path, "content": "x"}, "agent_type": agent})
    assert (out or {}).get("permissionDecision") == decision


def test_guard_blocks_bash_for_readers_and_passes_bad_input():
    assert guard(bash("ls", agent_type="kanna-eval-reviewer"))["permissionDecision"] == "deny"
    if shutil.which("node"):
        out = subprocess.run(["node", str(GUARD)], input="{broken", capture_output=True, text=True, timeout=20)
        assert out.returncode == 0 and out.stdout == ""


# ---------- kanna 自身 ----------

def test_kanna_passes_its_own_lint():
    rep = harness_lint.lint_plugin(KANNA)
    assert ng_rules(rep) == set(), [(r.rule, r.where, r.detail) for r in rep.results if r.status == "ng"]


def test_scaffolds_are_identical_and_seed_the_flaws(tmp_path):
    fixed = KANNA / "evals/eval-run-asks-first/scaffold.sh"
    scaffolds = sorted(s for s in KANNA.glob("evals/*/scaffold.sh") if s != fixed)
    assert len(scaffolds) >= 3
    first = scaffolds[0].read_text(encoding="utf-8")
    for s in scaffolds[1:]:
        assert s.read_text(encoding="utf-8") == first, f"{s} がほかの scaffold と違う"
    # 流してよい見本は、仕込みの見本に「QE08 を直す 1 行」を足しただけ
    assert fixed.read_text(encoding="utf-8").startswith(first.rstrip("\n"))
    if shutil.which("bash") is None:
        pytest.skip("bash がありません")
    work = tmp_path / "work"
    work.mkdir()
    subprocess.run(["bash", str(scaffolds[0])], cwd=work, check=True, timeout=60)
    found = ng_rules(harness_lint.lint_plugin(work / "sample-plugin"))
    # audit-finds-seeded-flaws が報告に求める欠陥が、本当に仕込まれている
    assert {"QE08", "QE05", "QA04"} <= found
    # 空でない作業フォルダでは何もせずに落ちる（本物のフォルダを汚さない）
    again = subprocess.run(["bash", str(scaffolds[0])], cwd=work, capture_output=True, timeout=60)
    assert again.returncode != 0
    clean = tmp_path / "clean"
    clean.mkdir()
    subprocess.run(["bash", str(fixed)], cwd=clean, check=True, timeout=60)
    rep = harness_lint.lint_plugin(clean / "sample-plugin")
    assert rep.counts()["must"] == 0  # eval-run-asks-first は、流してよい見本で問いを見る


def test_cases_cover_every_skill():
    cases = {d.name for d in (KANNA / "evals").iterdir() if (d / "prompt.md").exists()}
    for skill in ("audit", "eval-design", "eval-run", "tune"):
        assert any(c.startswith(skill) for c in cases), skill


def test_vendored_lint_matches_kanna():
    """プラグインのリポジトリへ写す harness_lint.py（templates/repo/scripts/）は、kanna の物と同じ。"""
    a = (KANNA / "scripts/harness_lint.py").read_bytes()
    b = (ROOT / "templates/repo/scripts/harness_lint.py").read_bytes()
    assert a == b, "plugins/kanna/scripts/harness_lint.py を templates/repo/scripts/ に写し直す"
