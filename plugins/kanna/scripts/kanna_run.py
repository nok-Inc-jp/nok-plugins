#!/usr/bin/env python3
"""claude plugin eval の命令を、ケースの tags から組み、費用を見積もり、流して台帳に足す。

eval の命令を手で組むと、決まった所でつまずく（kanna の R1〜R20 で全部起きた）：
  - TMPDIR が /tmp の下だと、Bash の道具が作業フォルダに書けない
  - --allow-tools を、ケースの needs-* の tags から組み忘れる
  - --case は 1 つの型しか取れない（2 回書くと後の方だけ、'{a,b}' は 0 件）
  - 費用の上限を決める根拠が無い
ここでは、それを推し量らずに決める。

使い方:
  python3 kanna_run.py plan <プラグイン> [--tag T ...] [--case 型] [--model haiku] [--runs 3] [--ablation none]
  python3 kanna_run.py run  <プラグイン> （plan と同じ引数） --yes [--note "..."]
  オプション: --json（plan の結果を JSON で）・--max-cost-usd（見積もりより上限を上げたいとき）・--keep-temp（trace を残す）
             --allow-large（opus・fable で流すとき。人が頼んだときだけ）・--claude <命令>（テスト用）

run は --yes が無いと流さない（費用を使う前に、plan を人に見せて了承を取るため）。
終わりの値: 0 = 流した（または plan）。1 = 台帳の比べで下がったケースがある・eval が合格の線に届かない。
           2 = 使い方の誤り・流せない（0 件・上位のモデルを --allow-large 無しで・--yes が無い）。
標準ライブラリだけで動く。
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import math
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import eval_ledger  # noqa: E402
import harness_lint  # noqa: E402

# 1 回あたりの費用の目安（USD）。台帳に同じモデルの回があれば、そちらを使う。
# 値は kanna の R1〜R20 の実測（haiku：11 件×3 回で $0.67〜0.87、sonnet：11 件×1 回で $1.21）から。
DEFAULT_PER_RUN = {"haiku": 0.03, "sonnet": 0.12, "opus": 0.6, "fable": 0.6}
LARGE = ("opus", "fable", "claude-opus", "claude-fable")
TOOLS_FOR_TAG = {"needs-bash": ["Bash"], "needs-write": ["Write", "Edit"], "needs-web": ["WebFetch", "WebSearch"]}


def select_cases(plugin: Path, tags: list[str], case_glob: str | None) -> list[harness_lint.Case]:
    m = harness_lint.load_manifest(plugin)
    rep = harness_lint.Report("plan")
    cases = harness_lint.load_cases(rep, plugin, m)
    out = []
    for c in cases:
        ctags = set(harness_lint.as_list(c.meta.get("tags")))
        if tags and not (ctags & set(tags)):   # --tag は、どれかに当たれば選ぶ（claude plugin eval と同じ）
            continue
        if case_glob and not fnmatch.fnmatchcase(c.name, case_glob):
            continue
        out.append(c)
    return out


def case_costs(plugin: Path, model: str) -> dict[str, float]:
    """台帳の同じモデルの回から、ケースごとの 1 回あたりの費用（最後に測った物）を出す。"""
    ledger = harness_lint.eval_dir(plugin, harness_lint.load_manifest(plugin)) / "ledger.jsonl"
    try:
        rows = eval_ledger.read_ledger(ledger)
    except ValueError:
        return {}
    out = {}
    for r in rows:
        if r.get("model") == model:
            for name, c in (r.get("cases") or {}).items():
                if c.get("cost_per_run"):
                    out[name] = float(c["cost_per_run"])
    return out


def per_run_cost(plugin: Path, model: str) -> tuple[float, str]:
    """台帳の同じモデルの回から、1 回あたりの費用を出す（ケースごとの費用が無いケースに使う）。無ければ目安。"""
    ledger = harness_lint.eval_dir(plugin, harness_lint.load_manifest(plugin)) / "ledger.jsonl"
    try:
        rows = eval_ledger.read_ledger(ledger)
    except ValueError:
        rows = []
    samples = []
    for r in rows:
        if r.get("model") != model or not r.get("cost_usd"):
            continue
        n = sum((c.get("runs") or 0) for c in (r.get("cases") or {}).values())
        arms = 2 if r.get("ablation") not in ("none", "") else 1
        if n:
            samples.append(float(r["cost_usd"]) / (n * arms))
    if samples:
        samples.sort()
        return samples[len(samples) // 2], f"台帳の {len(samples)} 回の中央値"
    key = next((k for k in DEFAULT_PER_RUN if model.startswith(k) or k in model), None)
    return DEFAULT_PER_RUN.get(key or "sonnet", 0.12), "目安（台帳に同じモデルの回が無い）"


def build(args) -> dict:
    plugin = Path(args.plugin).resolve()
    if not (plugin / ".claude-plugin" / "plugin.json").exists() and not (plugin / "skills").is_dir():
        raise SystemExit(f"プラグインのフォルダでない：{plugin}")
    if args.case and any(ch in args.case for ch in "{},"):
        raise SystemExit("--case は 1 つの型だけ（'{a,b}' や、で区切る形は 0 件になる）。いくつかを選ぶときは --tag を使う")
    if any(args.model.startswith(p) for p in LARGE) and not args.allow_large:
        raise SystemExit(f"上位のモデル（{args.model}）は、人が頼んだときだけ。--allow-large を付ける（下位のモデルで通ってから）")
    cases = select_cases(plugin, args.tag, args.case)
    if not cases:
        raise SystemExit("選んだケースが 0 件。--tag と --case を確かめる")
    tags = set()
    for c in cases:
        tags |= set(harness_lint.as_list(c.meta.get("tags")))
    allow = sorted({t for tag in tags for t in TOOLS_FOR_TAG.get(tag, [])})
    scaffold = any(isinstance(c.meta.get("context"), dict) and c.meta["context"].get("scaffold_script") for c in cases)
    arms = 1 if args.ablation == "none" else 2
    runs_total = sum(int(args.runs or c.meta.get("runs") or 3) for c in cases) * arms
    per, source = per_run_cost(plugin, args.model)
    known = case_costs(plugin, args.model)
    # 結果や約束のケースは、呼ばれるだけのケースより 10 倍ほど高い（R19）。ケースごとに測った費用を先に使う
    estimate = sum(known.get(c.name, per) * int(args.runs or c.meta.get("runs") or 3) * arms for c in cases)
    measured = sum(1 for c in cases if c.name in known)
    if measured:
        source = f"{measured}/{len(cases)} 件は台帳のケースごとの費用、残りは{source}"
    # 見積もりは実際より 4 割ほど低く出ることがある（R27：$0.74 → $1.17）。途中で止まると比べに使えないので 2 倍を上限にする
    cap = args.max_cost_usd or max(0.3, math.ceil(estimate * 2 / 0.1) * 0.1)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.out_root).resolve() / stamp
    cmd = [args.claude, "plugin", "eval", str(plugin), "--model", args.model, "--judge-model", args.judge_model,
           "--runs", str(args.runs), "--ablation", args.ablation, "-j", str(args.concurrency),
           "--max-cost-usd", f"{cap:.2f}", "--no-publish", "--trust-plugin",
           "--json", str(out_dir / "result.json"), "--output-dir", str(out_dir)]
    for t in args.tag:
        cmd += ["--tag", t]
    if args.case:
        cmd += ["--case", args.case]
    if allow:
        cmd += ["--allow-tools", *allow]
    if scaffold:
        cmd += ["--scaffold"]
    if getattr(args, "keep_temp", False):
        cmd += ["--keep-temp"]
    env = {}
    tmp = os.environ.get("TMPDIR") or "/tmp"
    if "Bash" in allow and (tmp == "/tmp" or tmp.startswith("/tmp/")):
        # eval のサンドボックスは /tmp 全体を書けない所にする。作業フォルダが /tmp の下だと、Bash から書けない（R20）
        cand = Path(args.out_root).resolve().parent / "tmp"
        if str(cand) == "/tmp" or str(cand).startswith("/tmp/"):
            cand = Path.home() / ".kanna" / "tmp"
        env["TMPDIR"] = str(cand)
    return {
        "plugin": str(plugin), "cases": [c.name for c in cases], "runs_total": runs_total,
        "per_run_usd": round(per, 4), "per_run_source": source, "estimate_usd": round(estimate, 2),
        "max_cost_usd": round(cap, 2), "allow_tools": allow, "scaffold": scaffold, "env": env,
        "out_dir": str(out_dir), "command": cmd,
        "shell": " ".join([f"{k}={shlex.quote(v)}" for k, v in env.items()] + [shlex.quote(x) for x in cmd]),
    }


def render(plan: dict) -> str:
    lines = [
        f"命令：{plan['shell']}",
        f"ケース {len(plan['cases'])} 件（{', '.join(plan['cases'][:6])}{' ほか' if len(plan['cases']) > 6 else ''}）",
        f"回数 {plan['runs_total']} 回 ／ 見積もり ${plan['estimate_usd']}（1 回 ${plan['per_run_usd']}：{plan['per_run_source']}）"
        f" ／ 上限 ${plan['max_cost_usd']}",
        f"許す道具：{', '.join(plan['allow_tools']) or 'なし'} ／ scaffold：{'流す（作者の bash）' if plan['scaffold'] else 'なし'}",
    ]
    if plan["env"]:
        lines.append(f"TMPDIR を {plan['env']['TMPDIR']} にする（Bash の道具が作業フォルダに書けるように）")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["plan", "run"])
    ap.add_argument("plugin")
    ap.add_argument("--tag", action="append", default=[])
    ap.add_argument("--case")
    ap.add_argument("--model", default="haiku")
    ap.add_argument("--judge-model", default="haiku")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--ablation", choices=["none", "with-without"], default="none")
    ap.add_argument("--concurrency", "-j", type=int, default=4)
    ap.add_argument("--max-cost-usd", type=float)
    ap.add_argument("--allow-large", action="store_true")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--keep-temp", action="store_true", help="trace を残す（落ちた理由を読むとき）")
    ap.add_argument("--note", default="")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out-root", default=".kanna/runs")
    ap.add_argument("--claude", default="claude")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    try:
        plan = build(args)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 2
    if args.cmd == "plan":
        print(json.dumps(plan, ensure_ascii=False, indent=2) if args.json else render(plan))
        return 0
    if not args.yes:
        print("run は --yes が無いと流さない。plan を見せて、了承を取ってから --yes を付ける", file=sys.stderr)
        return 2
    print(render(plan), flush=True)
    out = Path(plan["out_dir"])
    out.mkdir(parents=True, exist_ok=True)
    if plan["env"]:
        Path(plan["env"]["TMPDIR"]).mkdir(parents=True, exist_ok=True)
    env = {**os.environ, **plan["env"]}
    with (out / "log.txt").open("w", encoding="utf-8") as log:
        code = subprocess.call(plan["command"], env=env, stdout=log, stderr=subprocess.STDOUT)
    result = out / "result.json"
    if not result.exists():
        print(f"結果が無い（終わりの値 {code}）。{out / 'log.txt'} を読む", file=sys.stderr)
        return 2
    ledger = harness_lint.eval_dir(Path(plan["plugin"]), harness_lint.load_manifest(Path(plan["plugin"]))) / "ledger.jsonl"
    lcode = eval_ledger.main(["record", str(result), "--ledger", str(ledger), "--model", args.model, "--note", args.note])
    print(f"結果：{result}")
    if code == 2:
        print("eval が途中で止まった（費用の上限か、認証）。止まった回は台帳の比べに使わない", file=sys.stderr)
    return 1 if (lcode == 1 or code == 1) else (2 if lcode == 2 else 0)


if __name__ == "__main__":
    sys.exit(main())
