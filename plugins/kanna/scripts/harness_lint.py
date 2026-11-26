#!/usr/bin/env python3
"""プラグインのハーネス（スキル・エージェント・フック・eval）の作りを、決まりごとに出典つきで点検する。

plugin_drift.py（nok-plugins）が「形」を見るのに対し、こちらは「作りの質」を見る：
スキルが呼ばれる・呼ばれないことを eval で確かめているか、採点（grader）が壊れていないか、
読むだけのはずの役が書けてしまわないか、など。どれも、流さずに（利用料を使わずに）分かる物だけを見る。

使い方:
  python3 harness_lint.py <プラグインのフォルダ> [...]
  オプション: --json（結果を JSON で）・--all（合格した決まりも出す）・--strict（推奨の外れも落とす）
             --rules（決まりの一覧を出して終わる）
             --probe-scaffold（scaffold を一時フォルダで流し、空振りの grader を探す。作者の bash を流すので、自分たちのケースだけ）

終わりの値: 0 = 必須の外れが無い。1 = 必須の外れ（--strict なら推奨の外れも）がある。2 = 使い方の誤り。
標準ライブラリだけで動く（pyyaml があれば使う）。決まりの説明は kanna の skills/kanna-audit/references/rules.md。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

D_EVALS = "https://code.claude.com/docs/en/plugin-evals.md"
D_SKILLS = "https://code.claude.com/docs/en/skills.md"
D_SKILL_BP = "https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices"
D_AGENTS = "https://code.claude.com/docs/en/sub-agents.md"
D_HOOKS = "https://code.claude.com/docs/en/hooks.md"
D_NOK = "nok の決まり（kanna の references/rules.md）"

MUST, SHOULD = "must", "should"

# 決まりの一覧：ID → (重さ, 中身, 出典)。references/rules.md の表と同じ物を保つ（tests が突き合わせる）。
RULES: dict[str, tuple[str, str, str]] = {
    # スキル
    "QS01": (SHOULD, "スキルの description に「いつ使うか」が書いてある", D_SKILL_BP),
    "QS02": (SHOULD, "スキルの frontmatter に、Claude Code が知らない項目が無い（書き誤りは黙って無視される）", D_SKILLS),
    "QS03": (SHOULD, "補助ファイルから、さらに別の補助ファイルへリンクしない（1 段だけ）", D_SKILL_BP),
    "QS04": (SHOULD, "スクリプトを ${CLAUDE_PLUGIN_ROOT} か ${CLAUDE_SKILL_DIR} で指す（作業フォルダからの相対で指さない）", D_SKILLS),
    "QS05": (SHOULD, "スキルの名前があいまい（helper・utils など）でない", D_SKILL_BP),
    # エージェント
    "QA01": (SHOULD, "エージェントの frontmatter に、知らない項目が無い", D_AGENTS),
    "QA02": (SHOULD, "エージェントの description に「いつ任せるか」が書いてある", D_AGENTS),
    "QA03": (SHOULD, "エージェントの本文に、返す形（見出し・表・JSON など）が決めてある", D_NOK),
    "QA04": (SHOULD, "書ける道具（Write・Edit・Bash）を持つエージェントがあるなら、PreToolUse のフックで書ける範囲を絞っている", D_AGENTS),
    # フック
    "QH01": (SHOULD, "Stop・SubagentStop のフックが stop_hook_active を見て、止め続けない", D_HOOKS),
    "QH02": (SHOULD, "フックが指すスクリプトがプラグインの中にある", D_HOOKS),
    # eval のケース
    "QE01": (MUST, "eval の prompt.md・case.yaml に、知らない項目が無い（あると読み込みで落ちる）", D_EVALS),
    "QE02": (MUST, "grader の type が 6 種のどれかで、要る項目がそろっている", D_EVALS),
    "QE03": (MUST, "regex の grader の pattern が読める（(?i) のような書き方を使わず flags を使う）", D_EVALS),
    "QE04": (SHOULD, "ケースに expected_outcome がある（何を確かめるケースかを人が読める）", D_EVALS),
    "QE05": (SHOULD, "llm の grader は 1 つの条件だけを見る（条件を並べるなら grader を分ける）", D_EVALS),
    "QE06": (SHOULD, "結果を見るケースに、決まった答えの grader（regex・tool_used・file_exists など）が 1 件以上ある", D_EVALS),
    "QE07": (SHOULD, "「スキルを呼ばない」grader を他の grader と並べるときは arm: both にする（ablation で採点から外れるため）", D_EVALS),
    "QE08": (MUST, "tool_used: Skill の input_match が、このプラグインのスキル名に当たる", D_EVALS),
    "QE09": (SHOULD, "min 1 以上で求める、許しの要る道具（Bash・Write・Edit・Web・MCP）を、tags の needs-* で示している（流すときの --allow-tools に要る）", D_EVALS),
    "QE10": (MUST, "case.yaml の scaffold_script と、baseline の baseline_file が、ケースのフォルダにある", D_EVALS),
    "QE11": (SHOULD, "ケースの name がフォルダ名と同じ", D_EVALS),
    "QE12": (SHOULD, "ケースの tags に、種類（trigger・outcome・safety のどれか）がある", D_NOK),
    "QE14": (SHOULD, "「含まない」（match: not_contains）の regex の pattern が、scaffold で置いた入力か依頼文に当たる（当たらないと何もしなくても通る。--probe-scaffold のときだけ見る）", D_NOK),
    "QE13": (SHOULD, "Write・Edit を場所で絞る tool_used の input_match は \"file_path\" に当てる（書いた中身にも当たるため）", D_EVALS),
    # eval の全体
    "QG01": (SHOULD, "モデルが呼べるスキルごとに、呼ばれるべき依頼で呼ばれることを確かめるケースがある", D_SKILL_BP),
    "QG02": (SHOULD, "モデルが呼べるスキルごとに、似ているが呼ぶべきでない依頼で呼ばれないことを確かめるケースがある", D_SKILL_BP),
    "QG03": (SHOULD, "スキルごとに、結果を確かめるケースがある", D_SKILL_BP),
    "QG04": (SHOULD, "「してはいけないこと」を確かめるケース（書かない・流さない・作らない）が 1 件以上ある", D_NOK),
    "QG05": (SHOULD, "eval のケースが 3 件以上ある", D_SKILL_BP),
}

# 公式の文書（2026-11-26）に載っている項目。これ以外は書き誤りとして扱う。
SKILL_KEYS = {
    "name", "description", "when_to_use", "argument-hint", "arguments", "disable-model-invocation",
    "user-invocable", "allowed-tools", "disallowed-tools", "model", "effort", "context", "agent",
    "background", "hooks", "paths", "shell", "metadata", "license", "compatibility", "version",
}
AGENT_KEYS = {
    "name", "description", "tools", "disallowedTools", "model", "permissionMode", "maxTurns",
    "autoCompactWindow", "skills", "mcpServers", "hooks", "memory", "background", "omitClaudeMd",
    "effort", "isolation", "color", "initialPrompt", "experimental",
}
PROMPT_KEYS = {
    "schema_version", "name", "description", "tags", "plugins", "runs", "expected_outcome", "model",
    "max_turns", "timeout_seconds", "allowed_tools", "disallowed_tools", "append_system_prompt", "env",
}
CASE_TOP_KEYS = {
    "schema_version", "name", "description", "tags", "plugins", "runs", "expected_outcome",
    "execution", "context", "graders",
}
CASE_EXEC_KEYS = {
    "model", "max_turns", "timeout_seconds", "allowed_tools", "disallowed_tools",
    "append_system_prompt", "env", "prompt",
}
CASE_CONTEXT_KEYS = {"scaffold_script", "history_file", "add_dirs"}
GRADER_COMMON = {"type", "weight", "arm", "name", "description"}
GRADER_KEYS = {
    "regex": {"pattern", "flags", "match", "target"},
    "tool_used": {"tool", "input_match", "min", "max"},
    "tool_order": {"before", "after"},
    "file_exists": {"path", "exists"},
    "llm": {"criteria", "focus"},
    "baseline": {"baseline_file", "criteria"},
}
GRADER_REQUIRED = {
    "regex": ("pattern",), "tool_used": ("tool",), "tool_order": ("before", "after"),
    "file_exists": ("path",), "llm": (), "baseline": ("baseline_file",),
}
# 許しの要る道具と、それを示す tag。ケースの allowed_tools では許せず、流すときの --allow-tools で許す。
GATED_TAGS = {"Bash": "needs-bash", "Write": "needs-write", "Edit": "needs-write", "NotebookEdit": "needs-write",
              "WebFetch": "needs-web", "WebSearch": "needs-web"}
# 何も許さなくても使える道具（plugin-evals の文書）。
PRE_APPROVED = {"Read", "Glob", "Grep", "NotebookRead", "Skill", "AskUserQuestion", "Agent", "TodoWrite"}
WRITE_TOOLS = {"Write", "Edit", "Bash", "NotebookEdit", "MultiEdit"}
CASE_KINDS = {"trigger", "outcome", "safety"}
VAGUE_NAMES = {"helper", "helpers", "utils", "util", "tools", "misc", "common", "example", "skill"}
WHEN_RE = re.compile(r"使う|使います|使って|使用する|呼ぶ|呼ばれ|任せる|ときに|とき。|場合に|use (?:it |this )?when|used when|use proactively|use this (?:agent|skill)|when the user|when you|invoked (?:by|from)|called (?:by|from)", re.I)
RETURN_HEAD_RE = re.compile(r"^#{1,4}\s*.*(返す|返事|返し方|報告の形|出力|output|return|response|format)", re.I | re.M)
RETURN_BODY_RE = re.compile(r"(?:reply|respond|return|answer) (?:with|only)|返事は|返すのは|と返す|を返す", re.I)
LIST_CRITERIA_RE = re.compile(r"(?:^|\s)[（(]\s*[2-9]\s*[)）]|^\s*[2-9][.)．]\s", re.M)
LINK_RE = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")


@dataclass
class Result:
    rule: str
    level: str
    status: str  # ok / ng
    detail: str = ""
    where: str = ""


@dataclass
class Report:
    plugin: str
    results: list[Result] = field(default_factory=list)

    def add(self, rule: str, ok: bool, detail: str = "", where: str = "") -> None:
        level = RULES[rule][0]
        # 合格の行には、外れのときの文を残さない（--json を読む側が、合格を外れと読み違えないように）
        self.results.append(Result(rule, level, "ok" if ok else "ng", "" if ok else detail, where))

    def finalize(self) -> None:
        """同じ決まりの合格が重ならないように、外れの無い決まりは合格を 1 件にまとめる。"""
        seen_ng = {r.rule for r in self.results if r.status == "ng"}
        out, seen_ok = [], set()
        for r in self.results:
            if r.status == "ok":
                if r.rule in seen_ng or r.rule in seen_ok:
                    continue
                seen_ok.add(r.rule)
            out.append(r)
        self.results = sorted(out, key=lambda r: list(RULES).index(r.rule))

    def counts(self) -> dict[str, int]:
        ng = [r for r in self.results if r.status == "ng"]
        return {"must": sum(r.level == MUST for r in ng), "should": sum(r.level == SHOULD for r in ng)}


# ---------- 読み方 ----------

def parse_yaml(raw: str) -> object:
    """pyyaml があれば使い、無ければ frontmatter と case.yaml に足りる範囲だけを読む。"""
    try:
        import yaml  # type: ignore
        return yaml.safe_load(raw)
    except ImportError:
        return _mini_yaml(raw.splitlines(), 0)[0]
    except Exception as e:  # noqa: BLE001
        raise ValueError(str(e)) from e


def _mini_yaml(lines: list[str], i: int, indent: int = 0) -> tuple[object, int]:
    out: dict | list | None = None
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        cur = len(line) - len(line.lstrip())
        if cur < indent:
            break
        s = line.strip()
        if s.startswith("- "):
            out = out if isinstance(out, list) else []
            item = s[2:]
            if re.match(r"^[\w-]+:\s", item + " ") and not item.startswith(("'", '"')):
                sub = [" " * (cur + 2) + item] + []
                j = i + 1
                while j < len(lines) and (not lines[j].strip() or len(lines[j]) - len(lines[j].lstrip()) > cur):
                    sub.append(lines[j])
                    j += 1
                val, _ = _mini_yaml(sub, 0, cur + 2)
                out.append(val)
                i = j
            else:
                out.append(_scalar(item))
                i += 1
            continue
        m = re.match(r"^([^:]+):\s*(.*)$", s)
        if not m:
            raise ValueError(f"読めない行：{s}")
        out = out if isinstance(out, dict) else {}
        key, val = m.group(1).strip().strip("'\""), m.group(2)
        if val in ("", "|", ">", "|-", ">-"):
            j = i + 1
            block = []
            while j < len(lines) and (not lines[j].strip() or len(lines[j]) - len(lines[j].lstrip()) > cur):
                block.append(lines[j])
                j += 1
            if val.startswith(("|", ">")):
                out[key] = "\n".join(b.strip() for b in block).strip()
            else:
                child_indent = min((len(b) - len(b.lstrip()) for b in block if b.strip()), default=cur + 2)
                out[key] = _mini_yaml(block, 0, child_indent)[0] if block else None
            i = j
        else:
            out[key] = _scalar(val)
            i += 1
    return out, i


def _scalar(v: str):
    v = v.strip()
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [_scalar(x) for x in re.findall(r"'[^']*'|\"[^\"]*\"|[^,]+", inner)] if inner else []
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
        return v[1:-1]
    if v.lower() in ("true", "yes", "on"):
        return True
    if v.lower() in ("false", "no", "off"):
        return False
    if v.lower() in ("null", "~"):
        return None
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if re.fullmatch(r"-?\d+\.\d+", v):
        return float(v)
    return v


def frontmatter(path: Path) -> tuple[dict | None, str, str]:
    """(frontmatter, 本文, 読めない理由)。"""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None, text, "frontmatter が無い"
    lines = text.splitlines()
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return None, text, "frontmatter が閉じていない"
    body = "\n".join(lines[end + 1:])
    try:
        data = parse_yaml("\n".join(lines[1:end])) or {}
    except ValueError as e:
        return None, body, f"YAML が読めない：{e}"
    if not isinstance(data, dict):
        return None, body, "frontmatter が対応表でない"
    return data, body, ""


def as_list(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [x.strip() for x in v.split(",") if x.strip()]
    if isinstance(v, list):
        return [str(x).strip() for x in v]
    return [str(v)]


def js_regex_to_py(pattern: str) -> str:
    """JavaScript の正規表現を、Python で読める形に寄せる（名前つきの組だけ）。"""
    return re.sub(r"\(\?<(?![=!])", "(?P<", pattern)


# ---------- プラグインの部品 ----------

@dataclass
class Skill:
    name: str
    path: Path
    fm: dict
    body: str
    model_invocable: bool


@dataclass
class Grader:
    path: Path
    fm: dict
    body: str


@dataclass
class Case:
    name: str
    dir: Path
    meta: dict            # prompt.md と case.yaml を重ねた物
    prompt: str
    graders: list[Grader]


def load_manifest(plugin: Path) -> dict:
    p = plugin / ".claude-plugin" / "plugin.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def component_dirs(plugin: Path, m: dict, key: str, default: str) -> list[Path]:
    dirs = [plugin / default]
    v = m.get(key)
    for x in ([v] if isinstance(v, str) else v if isinstance(v, list) else []):
        if isinstance(x, str):
            dirs.append((plugin / x).resolve())
    return [d for d in dict.fromkeys(dirs) if d.exists()]


def load_skills(rep: Report, plugin: Path, m: dict) -> list[Skill]:
    skills = []
    for d in component_dirs(plugin, m, "skills", "skills"):
        for md in sorted(d.glob("*/SKILL.md")) if d.is_dir() else []:
            fm, body, err = frontmatter(md)
            if fm is None:
                continue  # 形の検査（plugin_drift の S01）に任せる
            name = str(fm.get("name") or md.parent.name)
            inv = not bool(fm.get("disable-model-invocation"))
            skills.append(Skill(name, md, fm, body, inv))
    for d in component_dirs(plugin, m, "commands", "commands"):
        for md in sorted(d.glob("*.md")) if d.is_dir() else []:
            fm, body, _ = frontmatter(md)
            fm = fm or {}
            skills.append(Skill(md.stem, md, fm, body, not bool(fm.get("disable-model-invocation"))))
    return skills


def load_agents(plugin: Path, m: dict) -> list[tuple[Path, dict, str]]:
    out = []
    for d in component_dirs(plugin, m, "agents", "agents"):
        for md in sorted(d.glob("*.md")) if d.is_dir() else [d]:
            fm, body, _ = frontmatter(md)
            if fm is not None:
                out.append((md, fm, body))
    return out


def load_hooks(plugin: Path, m: dict) -> dict:
    srcs = []
    if (plugin / "hooks" / "hooks.json").exists():
        srcs.append(plugin / "hooks" / "hooks.json")
    h = m.get("hooks")
    merged: dict = {}
    for x in ([h] if isinstance(h, (str, dict)) else h if isinstance(h, list) else []):
        if isinstance(x, dict):
            for ev, entries in (x.get("hooks", x) or {}).items():
                merged.setdefault(ev, []).extend(entries if isinstance(entries, list) else [])
        elif isinstance(x, str):
            srcs.append((plugin / x).resolve())
    for p in dict.fromkeys(srcs):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        for ev, entries in (data.get("hooks") or {}).items():
            merged.setdefault(ev, []).extend(entries if isinstance(entries, list) else [])
    return merged


def eval_dir(plugin: Path, m: dict) -> Path:
    exp = m.get("experimental") if isinstance(m.get("experimental"), dict) else {}
    return plugin / str(exp.get("evals") or "evals")


def load_cases(rep: Report, plugin: Path, m: dict) -> list[Case]:
    root = eval_dir(plugin, m)
    if not root.is_dir():
        return []
    cases = []
    dirs = {p.parent for p in root.rglob("prompt.md")} | {p.parent for p in root.rglob("case.yaml")}
    for d in sorted(dirs):
        rel = d.relative_to(plugin).as_posix()
        if "/results/" in f"/{rel}/" or "/mocks/" in f"/{rel}/":
            continue
        meta: dict = {}
        prompt = ""
        case_yaml_graders: list[Grader] = []
        if (d / "case.yaml").exists():
            try:
                cy = parse_yaml((d / "case.yaml").read_text(encoding="utf-8")) or {}
            except ValueError as e:
                rep.add("QE01", False, f"case.yaml が読めない：{e}", rel)
                cy = {}
            if isinstance(cy, dict):
                bad = sorted(set(cy) - CASE_TOP_KEYS)
                bad += [f"execution.{k}" for k in sorted(set(cy.get("execution") or {}) - CASE_EXEC_KEYS)]
                bad += [f"context.{k}" for k in sorted(set(cy.get("context") or {}) - CASE_CONTEXT_KEYS)]
                rep.add("QE01", not bad, f"case.yaml の知らない項目：{', '.join(bad)}" if bad else "", rel)
                meta.update({k: v for k, v in cy.items() if k not in ("execution", "graders")})
                meta.update(cy.get("execution") or {})
                prompt = str((cy.get("execution") or {}).get("prompt") or "")
                for g in cy.get("graders") or []:
                    if isinstance(g, dict):
                        case_yaml_graders.append(Grader(d / "case.yaml", g, str(g.get("criteria") or "")))
        if (d / "prompt.md").exists():
            fm, body, err = frontmatter(d / "prompt.md")
            if fm is None and err != "frontmatter が無い":
                rep.add("QE01", False, f"prompt.md の {err}", rel)
            fm = fm or {}
            bad = sorted(set(fm) - PROMPT_KEYS)
            rep.add("QE01", not bad, f"prompt.md の知らない項目：{', '.join(bad)}" if bad else "", rel)
            meta.update(fm)
            prompt = body.strip() or prompt
        graders = list(case_yaml_graders)
        for g in sorted((d / "graders").glob("*.md")) if (d / "graders").is_dir() else []:
            gfm, gbody, err = frontmatter(g)
            if gfm is None:
                rep.add("QE02", False, f"grader の {err}", g.relative_to(plugin).as_posix())
                continue
            graders.append(Grader(g, gfm, gbody.strip()))
        cases.append(Case(str(meta.get("name") or d.name), d, meta, prompt, graders))
    return cases


# ---------- 決まり ----------

def check_skills(rep: Report, plugin: Path, skills: list[Skill]) -> None:
    for s in skills:
        rel = s.path.relative_to(plugin).as_posix()
        if s.path.name != "SKILL.md":
            continue
        desc = f"{s.fm.get('description') or ''} {s.fm.get('when_to_use') or ''}"
        if s.model_invocable:
            rep.add("QS01", bool(WHEN_RE.search(desc)), "description に「〜のときに使う」が無い（呼ばれる場面が分からない）", rel)
        bad = sorted(set(s.fm) - SKILL_KEYS)
        rep.add("QS02", not bad, f"知らない項目：{', '.join(bad)}", rel)
        rep.add("QS05", s.name.lower() not in VAGUE_NAMES and not s.name.endswith(("-helper", "-utils")),
                f"名前があいまい：{s.name}", rel)
        # 補助ファイルは 1 段だけ
        sdir = s.path.parent
        for ref in sorted(p for p in sdir.rglob("*.md") if p.name != "SKILL.md"):
            text = ref.read_text(encoding="utf-8")
            deeper = []
            for link in LINK_RE.findall(text):
                if link.startswith(("http://", "https://", "mailto:")) or not link.endswith(".md"):
                    continue
                target = (ref.parent / link).resolve()
                if target != ref.resolve() and str(target).startswith(str(sdir.resolve())) and target.name != "SKILL.md":
                    deeper.append(link)
            rep.add("QS03", not deeper, f"{ref.relative_to(plugin).as_posix()} から {', '.join(deeper)} へ飛ぶ", rel)
        # スクリプトの指し方
        loose = []
        for mt in re.finditer(r"(?<![\w}/.-])((?:\./)?scripts/[\w./-]+\.(?:py|sh|mjs|js|ts))", s.body):
            start = mt.start()
            before = s.body[max(0, start - 40):start]
            if "CLAUDE_PLUGIN_ROOT" not in before and "CLAUDE_SKILL_DIR" not in before:
                line = s.body[: start].count("\n") + 1
                # 説明の文（「scripts/ に置く」など）でなく、コードの中だけを数える
                if _in_code(s.body, start):
                    loose.append(f"{mt.group(1)}（本文 {line} 行目）")
        rep.add("QS04", not loose, f"相対で指している：{', '.join(loose[:3])}", rel)


def _in_code(text: str, pos: int) -> bool:
    fences = [m.start() for m in re.finditer(r"^```", text, re.M)]
    if sum(f < pos for f in fences) % 2 == 1:
        return True
    line_start = text.rfind("\n", 0, pos) + 1
    return text[line_start:pos].count("`") % 2 == 1


def check_agents(rep: Report, plugin: Path, agents, hooks: dict) -> None:
    pre_guard = bool(hooks.get("PreToolUse"))
    for path, fm, body in agents:
        rel = path.relative_to(plugin).as_posix()
        bad = sorted(set(fm) - AGENT_KEYS)
        rep.add("QA01", not bad, f"知らない項目：{', '.join(bad)}", rel)
        rep.add("QA02", bool(WHEN_RE.search(str(fm.get("description") or ""))), "description に「いつ任せるか」が無い", rel)
        rep.add("QA03", bool(RETURN_HEAD_RE.search(body) or RETURN_BODY_RE.search(body)) or "```json" in body, "返す形の見出し（「返す形」「出力」など）が無い", rel)
        tools = set(as_list(fm.get("tools")))
        writes = sorted((tools & WRITE_TOOLS) if tools else {"（tools を書いていないので全部）"})
        if writes:
            rep.add("QA04", pre_guard, f"{', '.join(writes)} を持つが、PreToolUse のフックが無い（本文の「書かない」は守らせる仕組みでない）", rel)


def iter_hook_commands(hooks: dict):
    for ev, entries in hooks.items():
        for e in entries:
            for h in (e.get("hooks") or []) if isinstance(e, dict) else []:
                if isinstance(h, dict) and h.get("type", "command") == "command":
                    yield ev, h


def check_hooks(rep: Report, plugin: Path, hooks: dict) -> None:
    for ev, h in iter_hook_commands(hooks):
        parts = [str(h.get("command") or "")] + [str(a) for a in h.get("args") or []]
        refs = []
        for p in parts:
            for mt in re.finditer(r"\$\{?CLAUDE_PLUGIN_ROOT\}?/([^\s\"']+)", p):
                refs.append(mt.group(1))
        for r in refs:
            f = plugin / r
            rep.add("QH02", f.exists(), f"{ev}：{r} が無い", "hooks")
            if ev in ("Stop", "SubagentStop") and f.exists() and f.suffix in (".mjs", ".js", ".py", ".sh", ".cjs", ".ts"):
                rep.add("QH01", "stop_hook_active" in f.read_text(encoding="utf-8"),
                        f"{r} が stop_hook_active を見ていない（止めた後の再開で、また止めて回り続ける）", "hooks")


def grader_kind(g: Grader) -> str:
    return str(g.fm.get("type") or "")


def is_skill_grader(g: Grader) -> bool:
    return grader_kind(g) == "tool_used" and str(g.fm.get("tool") or "") == "Skill"


def is_negative(g: Grader) -> bool:
    return grader_kind(g) == "tool_used" and g.fm.get("max") == 0


def skill_hits(pattern: str, skills: list[Skill], plugin_name: str) -> list[str]:
    try:
        rx = re.compile(js_regex_to_py(pattern))
    except re.error:
        return []
    hits = []
    for s in skills:
        for cand in (s.name, f"{plugin_name}:{s.name}", json.dumps({"skill": f"{plugin_name}:{s.name}"})):
            if rx.search(cand):
                hits.append(s.name)
                break
    return hits


def check_cases(rep: Report, plugin: Path, m: dict, skills: list[Skill], cases: list[Case]) -> dict:
    """ケースごとの決まりを見て、全体の決まりに使う集計を返す。"""
    pname = str(m.get("name") or plugin.name)
    cover = {s.name: {"pos": [], "neg": [], "outcome": []} for s in skills}
    guard_cases = []
    for c in cases:
        rel = c.dir.relative_to(plugin).as_posix()
        rep.add("QE11", c.name == c.dir.name, f"name が {c.name}、フォルダが {c.dir.name}", rel)
        rep.add("QE04", bool(str(c.meta.get("expected_outcome") or "").strip()), "expected_outcome が無い", rel)
        tags = set(as_list(c.meta.get("tags")))
        rep.add("QE12", bool(tags & CASE_KINDS), f"tags に trigger・outcome・safety のどれも無い（今：{sorted(tags) or 'なし'}）", rel)
        # scaffold と baseline のファイル
        ctx = c.meta.get("context") if isinstance(c.meta.get("context"), dict) else {}
        for key in ("scaffold_script", "history_file"):
            if ctx.get(key):
                rep.add("QE10", (c.dir / str(ctx[key])).exists(), f"{key} の {ctx[key]} が無い", rel)
        allowed = set(as_list(c.meta.get("allowed_tools")))
        allowed_base = {re.sub(r"\(.*\)$", "", a) for a in allowed}
        has_det = False
        has_scored = False
        negative_skill_graders = []
        if not c.graders:
            rep.add("QE02", False, "grader が 1 件も無い", rel)
        for g in c.graders:
            grel = g.path.relative_to(plugin).as_posix()
            t = grader_kind(g)
            if t not in GRADER_KEYS:
                rep.add("QE02", False, f"type が {t or 'なし'}（regex・tool_used・tool_order・file_exists・llm・baseline のどれか）", grel)
                continue
            missing = [k for k in GRADER_REQUIRED[t] if g.fm.get(k) in (None, "")]
            if t == "llm" and not (g.body or g.fm.get("criteria")):
                missing.append("本文（採点の条件）")
            unknown = sorted(set(g.fm) - GRADER_COMMON - GRADER_KEYS[t])
            arm = g.fm.get("arm")
            if arm not in (None, "with-only", "both"):
                unknown.append(f"arm: {arm}")
            msg = "; ".join(x for x in (f"無い：{', '.join(missing)}" if missing else "",
                                         f"知らない項目：{', '.join(unknown)}" if unknown else "") if x)
            rep.add("QE02", not msg, msg, grel)
            if t == "baseline" and g.fm.get("baseline_file"):
                rep.add("QE10", (c.dir / str(g.fm["baseline_file"])).exists(), f"baseline_file の {g.fm['baseline_file']} が無い", grel)
            if t == "regex":
                pat = str(g.fm.get("pattern") or "")
                flags = str(g.fm.get("flags") or "")
                err = ""
                if re.search(r"\(\?[imsx]+\)", pat):
                    err = "(?i) のような書き方は使えない。flags: i にする"
                elif set(flags) - set("gimsuyd"):
                    err = f"flags に知らない字：{flags}"
                else:
                    try:
                        re.compile(js_regex_to_py(pat))
                    except re.error as e:
                        err = f"読めない：{e}"
                rep.add("QE03", not err, err, grel)
            if t == "llm":
                text = g.body or str(g.fm.get("criteria") or "")
                many = len(LIST_CRITERIA_RE.findall(text)) >= 1 or bool(re.search(r"どれか\s*1\s*つでも|all of the following|every one of", text, re.I))
                rep.add("QE05", not many, "条件を並べている。1 条件ずつ grader に分けると、どれが落ちたかが分かり、判定もぶれにくい", grel)
            if t in ("regex", "tool_used", "tool_order", "file_exists") and not is_skill_grader(g):
                has_det = True
            if not is_skill_grader(g) and arm != "with-only":
                has_scored = True
            # 道具の求め方
            if t == "tool_used":
                tool = str(g.fm.get("tool") or "")
                mn = g.fm.get("min", 1)
                if isinstance(mn, int) and mn >= 1 and tool and not (tool in PRE_APPROVED or tool.startswith("Task")):
                    need = "needs-mcp" if tool.startswith("mcp__") else GATED_TAGS.get(tool, f"needs-{tool.lower()}")
                    ok = need in tags or tool in allowed_base
                    rep.add("QE09", ok, f"{tool} を {mn} 回以上求めるが、tags に {need} が無い（--allow-tools で許さずに流すと、いつも落ちる）", grel)
                if is_negative(g) and tool != "Skill":
                    guard_cases.append(c.name)
            if t == "tool_used" and str(g.fm.get("tool") or "") in ("Write", "Edit", "MultiEdit", "NotebookEdit") and g.fm.get("input_match"):
                im = str(g.fm["input_match"])
                rep.add("QE13", "file_path" in im or "notebook_path" in im,
                        f"input_match '{im}' は書いた中身（content・new_string）にも当たる。'\"file_path\":\\s*\"[^\"]*<場所>' の形にする", grel)
            if t == "file_exists" and g.fm.get("exists") is False:
                guard_cases.append(c.name)
            if t == "regex" and str(g.fm.get("match") or "") == "not_contains":
                guard_cases.append(c.name)
            if is_skill_grader(g):
                pat = str(g.fm.get("input_match") or "")
                hits = skill_hits(pat, skills, pname) if pat else [s.name for s in skills]
                rep.add("QE08", bool(hits) or not skills, f"input_match '{pat}' が、どのスキル名にも当たらない（{', '.join(s.name for s in skills)}）", grel)
                for h in hits if pat else []:
                    (cover[h]["neg"] if is_negative(g) else cover[h]["pos"]).append(c.name)
                if is_negative(g):
                    negative_skill_graders.append(g)
        others = [g for g in c.graders if not is_skill_grader(g)]
        for g in negative_skill_graders:
            if others:
                rep.add("QE07", g.fm.get("arm") == "both", "ほかの grader と並んでいるので、ablation で採点から外れる", g.path.relative_to(plugin).as_posix())
        trigger_only = all(is_skill_grader(g) for g in c.graders)
        if not trigger_only:
            rep.add("QE06", has_det, "llm・baseline の grader だけで採点している（ぶれやすい）。決まった答えの grader を足す", rel)
            text = f"{c.prompt}\n{c.meta.get('description') or ''}\n{c.meta.get('expected_outcome') or ''}"
            for s in skills:
                if re.search(rf"(?<![\w-]){re.escape(s.name)}(?![\w-])", text) or s.name in cover and c.name in cover[s.name]["pos"]:
                    cover[s.name]["outcome"].append(c.name)
            _ = has_scored
    return {"cover": cover, "guard_cases": guard_cases}


def probe_scaffolds(rep: Report, plugin: Path, cases: list[Case]) -> None:
    """scaffold を一時フォルダで流し、not_contains の pattern が、置いた入力か依頼文に当たるかを見る。
    scaffold は作者の bash を流すので、--probe-scaffold を付けたときだけ呼ぶ。"""
    import shutil
    import subprocess
    import tempfile
    for c in cases:
        ctx = c.meta.get("context") if isinstance(c.meta.get("context"), dict) else {}
        neg = [g for g in c.graders if grader_kind(g) == "regex" and str(g.fm.get("match") or "") == "not_contains"]
        if not neg or not ctx.get("scaffold_script") or not (c.dir / str(ctx["scaffold_script"])).exists():
            continue
        if shutil.which("bash") is None:
            return
        with tempfile.TemporaryDirectory() as tmp:
            try:
                subprocess.run(["bash", str((c.dir / str(ctx["scaffold_script"])).resolve())], cwd=tmp,
                               capture_output=True, timeout=120, check=True)
            except (subprocess.SubprocessError, OSError) as e:
                rep.add("QE14", False, f"scaffold が流れない：{e}", c.dir.relative_to(plugin).as_posix())
                continue
            seeded = c.prompt + "\n" + "\n".join(
                p.read_text(encoding="utf-8", errors="replace") for p in Path(tmp).rglob("*") if p.is_file())
        for g in neg:
            try:
                rx = re.compile(js_regex_to_py(str(g.fm.get("pattern") or "")), re.I if "i" in str(g.fm.get("flags") or "") else 0)
            except re.error:
                continue
            rep.add("QE14", bool(rx.search(seeded)),
                    f"pattern '{g.fm.get('pattern')}' が、scaffold の入力にも依頼文にも無い（何もしなくても通る）",
                    g.path.relative_to(plugin).as_posix())


def check_suite(rep: Report, skills: list[Skill], cases: list[Case], agg: dict) -> None:
    rep.add("QG05", len(cases) >= 3, f"ケースが {len(cases)} 件", "evals")
    if not skills:
        return
    for s in skills:
        cv = agg["cover"].get(s.name, {"pos": [], "neg": [], "outcome": []})
        if s.model_invocable:
            rep.add("QG01", bool(cv["pos"]), f"{s.name}：呼ばれることを確かめるケース（tool_used: Skill・min 1）が無い", "evals")
            rep.add("QG02", bool(cv["neg"]), f"{s.name}：呼ばれないことを確かめるケース（tool_used: Skill・max 0）が無い", "evals")
        rep.add("QG03", bool(cv["outcome"]), f"{s.name}：結果を確かめるケースが無い", "evals")
    rep.add("QG04", bool(agg["guard_cases"]), "「してはいけないこと」を確かめる grader（tool_used の max 0・file_exists の exists: false・regex の not_contains）が無い", "evals")


def lint_plugin(plugin: Path, probe: bool = False) -> Report:
    plugin = plugin.resolve()
    m = load_manifest(plugin)
    rep = Report(f"{m.get('name') or plugin.name} {m.get('version') or ''}".strip())
    skills = load_skills(rep, plugin, m)
    agents = load_agents(plugin, m)
    hooks = load_hooks(plugin, m)
    check_skills(rep, plugin, skills)
    check_agents(rep, plugin, agents, hooks)
    check_hooks(rep, plugin, hooks)
    cases = load_cases(rep, plugin, m)
    agg = check_cases(rep, plugin, m, skills, cases)
    if probe:
        probe_scaffolds(rep, plugin, cases)
    check_suite(rep, skills, cases, agg)
    rep.finalize()
    return rep


def render(reports: list[Report], show_all: bool) -> str:
    out = []
    for rep in reports:
        c = rep.counts()
        out.append(f"■ {rep.plugin}\n  必須の外れ {c['must']}・推奨の外れ {c['should']}")
        for r in rep.results:
            if r.status == "ok" and not show_all:
                continue
            mark = "✓" if r.status == "ok" else "✗"
            lvl = "必須" if r.level == MUST else "推奨"
            where = f"{r.where}：" if r.where else ""
            out.append(f"  {mark} {r.rule} {lvl}：{where}{r.detail if r.status == 'ng' else RULES[r.rule][1]}")
        out.append("")
    if len(reports) > 1:
        out.append("| プラグイン | 必須の外れ | 推奨の外れ |\n| --- | --- | --- |")
        out += [f"| {r.plugin} | {r.counts()['must']} | {r.counts()['should']} |" for r in reports]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("plugins", nargs="*", type=Path)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--rules", action="store_true")
    ap.add_argument("--probe-scaffold", action="store_true",
                    help="ケースの scaffold を一時フォルダで流して確かめる（作者の bash を流す。自分たちのケースのときだけ）")
    a = ap.parse_args(argv)
    if a.rules:
        for k, (lvl, text, src) in RULES.items():
            print(f"{k}\t{'必須' if lvl == MUST else '推奨'}\t{text}\t{src}")
        return 0
    if not a.plugins:
        ap.print_usage(sys.stderr)
        return 2
    reports = []
    for p in a.plugins:
        if not (p / ".claude-plugin" / "plugin.json").exists() and not (p / "skills").is_dir():
            print(f"プラグインのフォルダでない：{p}", file=sys.stderr)
            return 2
        reports.append(lint_plugin(p, probe=a.probe_scaffold))
    if a.json:
        print(json.dumps([{"plugin": r.plugin, "counts": r.counts(), "results": [asdict(x) for x in r.results]} for r in reports],
                         ensure_ascii=False, indent=2))
    else:
        print(render(reports, a.all))
    bad = any(r.counts()["must"] or (a.strict and r.counts()["should"]) for r in reports)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
