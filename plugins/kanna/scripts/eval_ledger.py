#!/usr/bin/env python3
"""claude plugin eval の結果（aggregate-result.json）を台帳（JSON Lines）に残し、前の回と比べる。

eval は回すたびに点がぶれる。1 回の点だけで「良くなった」と言わないために、回ごとの要約を台帳に足し、
同じモデルの前の回と、ケースごとに比べる（下がった・ぶれた・プラグインが効いていない、を分けて出す）。

使い方:
  python3 eval_ledger.py record <aggregate-result.json> --ledger evals/ledger.jsonl --model haiku [--note "..."]
  python3 eval_ledger.py compare --ledger evals/ledger.jsonl [--model haiku]
  python3 eval_ledger.py show --ledger evals/ledger.jsonl
  オプション: --json（比べた結果を JSON で）・--threshold 0..1（合格の線。既定 1.0。claude plugin eval と同じ）

終わりの値: 0 = 下がったケースが無い。1 = 前の回より下がったケースがある（record と compare）。2 = 使い方の誤り・読めない。
標準ライブラリだけで動く。台帳はコミットしてよい（中身は点と名前だけで、プロンプトや出力は残さない）。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

EPS = 1e-9


def summarize(result: dict, model: str, note: str = "", threshold: float = 1.0) -> dict:
    """aggregate-result.json から、台帳の 1 行を作る。知らない形の所は空にして進める（形は足されていく物なので）。"""
    agg = result.get("aggregates") or {}
    suite = result.get("suite") if isinstance(result.get("suite"), dict) else {}
    if not model:
        model = str(suite.get("modelOverride") or "default")
    if suite.get("threshold") is not None:
        threshold = float(suite["threshold"])
    cases = {}
    for c in result.get("cases") or []:
        name = str(c.get("name") or "")
        if not name:
            continue
        ca = c.get("aggregates") or {}
        arms = c.get("arms") or {}
        with_runs = arms.get("with") or []
        errors = sum(1 for r in with_runs if isinstance(r, dict) and (r.get("error") or r.get("aborted")))
        # 「呼ばない」を見るケース（Skill の max 0）は、プラグイン無しでも同じ点が正しいので、差の判定から外す
        negative = any(isinstance(g, dict) and g.get("type") == "tool_used" and (g.get("config") or {}).get("tool") == "Skill"
                       and (g.get("config") or {}).get("max") == 0 for g in c.get("graders") or [])
        cases[name] = {
            "negative": negative,
            "score": _num(ca.get("score")),
            "pass_rate": _num(ca.get("passRate")),
            "delta": _num(ca.get("delta")),
            "runs": len(with_runs) or None,
            "errors": errors,
        }
    return {
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model": model,
        "judge_model": str(suite.get("judgeModel") or ""),
        "ablation": str(suite.get("ablation") or ""),
        # --case・--tag で絞った回。消えたケースを数えない
        "filtered": bool(suite.get("caseFilter") or any("tag" in k.lower() and suite.get(k) for k in suite)),
        "claude_version": str(result.get("claudeVersion") or ""),
        "overall": _num(agg.get("overallScore")),
        "passed": agg.get("casesPassed"),
        "total": agg.get("casesTotal"),
        "mean_delta": _num(agg.get("meanDelta")),
        "cost_usd": _num(result.get("costUsd")),
        "partial": bool(result.get("partial")),
        "threshold": threshold,
        "note": note,
        "cases": cases,
    }


def _num(v):
    try:
        return None if v is None else round(float(v), 4)
    except (TypeError, ValueError):
        return None


def read_ledger(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{i} が読めない：{e}") from e
    return rows


def compare(prev: dict | None, cur: dict) -> dict:
    """ケースごとに分ける。下がった（regressed）・上がった（improved）・ぶれる（flaky：0 より大きく 1 より小さい）・
    効いていない（no_lift：プラグイン無しと比べて差が 0 以下）・新しい（new）・消えた（gone）・走れなかった（errored）。"""
    th = float(cur.get("threshold") or 1.0)
    out = {k: [] for k in ("regressed", "improved", "flaky", "no_lift", "failing", "new", "gone", "errored")}
    pc = (prev or {}).get("cases") or {}
    for name, c in sorted((cur.get("cases") or {}).items()):
        s = c.get("score")
        if c.get("errors"):
            out["errored"].append(name)
        if s is not None and EPS < s < 1 - EPS:
            out["flaky"].append(name)
        if s is not None and s + EPS < th:
            out["failing"].append(name)
        if c.get("delta") is not None and c["delta"] <= EPS and not c.get("negative"):
            out["no_lift"].append(name)
        if prev is None:
            continue
        if name not in pc:
            out["new"].append(name)
            continue
        ps = pc[name].get("score")
        if s is not None and ps is not None:
            if s + EPS < ps:
                out["regressed"].append(f"{name}（{ps:g} → {s:g}）")
            elif s > ps + EPS:
                out["improved"].append(f"{name}（{ps:g} → {s:g}）")
    if not cur.get("filtered"):
        for name in sorted(set(pc) - set(cur.get("cases") or {})):
            out["gone"].append(name)
    return out


LABELS = {
    "regressed": "前の回より下がった",
    "improved": "前の回より上がった",
    "failing": "合格の線に届かない",
    "flaky": "回ごとにぶれる（点が 0 と 1 の間）",
    "no_lift": "プラグイン無しと差が無い（効いていない）",
    "errored": "走れなかった回がある（点ではなく、流し方を疑う）",
    "new": "新しいケース",
    "gone": "前の回にあって、今回に無いケース",
}


def render(prev: dict | None, cur: dict, diff: dict) -> str:
    lines = [f"■ {cur['at']}  model={cur['model']}  合格 {cur.get('passed')}/{cur.get('total')}  "
             f"全体 {cur.get('overall')}  差 {cur.get('mean_delta')}  費用 ${cur.get('cost_usd')}"
             + ("  （途中で止まった回）" if cur.get("partial") else "")]
    if prev is None:
        lines.append("  同じモデルの前の回が無い。今回を基準にする。")
    else:
        lines.append(f"  比べた回：{prev['at']}（合格 {prev.get('passed')}/{prev.get('total')}・全体 {prev.get('overall')}）")
        if prev.get("claude_version") != cur.get("claude_version"):
            lines.append(f"  注意：Claude Code の版が違う（{prev.get('claude_version')} → {cur.get('claude_version')}）。差は版のせいかもしれない")
    for k, label in LABELS.items():
        if diff[k]:
            lines.append(f"  - {label}：{', '.join(diff[k])}")
    return "\n".join(lines)


def last_for_model(rows: list[dict], model: str) -> dict | None:
    """同じモデルの、途中で止まっていない回を古い順に重ね、ケースごとに最後に測った点を持つ「前の回」を作る。
    ケースを絞った回が挟まっても、絞らなかったケースは、それを最後に測った回の点と比べられる。"""
    same = [r for r in rows if r.get("model") == model and not r.get("partial")]
    if not same:
        return None
    merged: dict = {}
    for r in same:
        merged.update(r.get("cases") or {})
    last = dict(same[-1])
    last["cases"] = merged
    return last


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("result", type=Path)
    r.add_argument("--ledger", type=Path, required=True)
    r.add_argument("--model", default="", help="既定は結果の suite.modelOverride")
    r.add_argument("--note", default="")
    r.add_argument("--threshold", type=float, default=1.0)
    r.add_argument("--json", action="store_true")
    c = sub.add_parser("compare")
    c.add_argument("--ledger", type=Path, required=True)
    c.add_argument("--model")
    c.add_argument("--json", action="store_true")
    s = sub.add_parser("show")
    s.add_argument("--ledger", type=Path, required=True)
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    try:
        rows = read_ledger(a.ledger)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2

    if a.cmd == "show":
        print("| いつ | model | 合格 | 全体 | 差 | 費用 | メモ |\n| --- | --- | --- | --- | --- | --- | --- |")
        for x in rows:
            print(f"| {x['at']} | {x['model']} | {x.get('passed')}/{x.get('total')} | {x.get('overall')} | "
                  f"{x.get('mean_delta')} | {x.get('cost_usd')} | {x.get('note', '')} |")
        return 0

    if a.cmd == "record":
        try:
            result = json.loads(a.result.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"結果が読めない：{a.result}：{e}", file=sys.stderr)
            return 2
        cur = summarize(result, a.model, a.note, a.threshold)
        if not cur["cases"]:
            print("結果にケースが無い。台帳に足さない（流し方を確かめる）。", file=sys.stderr)
            return 2
        prev = last_for_model(rows, cur["model"])
        a.ledger.parent.mkdir(parents=True, exist_ok=True)
        with a.ledger.open("a", encoding="utf-8") as f:
            f.write(json.dumps(cur, ensure_ascii=False, sort_keys=True) + "\n")
    else:
        if not rows:
            print("台帳が空。", file=sys.stderr)
            return 2
        model = a.model or rows[-1].get("model")
        same = [x for x in rows if x.get("model") == model]
        if not same:
            print(f"model={model} の回が無い。", file=sys.stderr)
            return 2
        cur = same[-1]
        prev = last_for_model(same[:-1], model)
    diff = compare(prev, cur)
    if a.json:
        print(json.dumps({"current": cur, "previous": prev, "diff": diff}, ensure_ascii=False, indent=2))
    else:
        print(render(prev, cur, diff))
    return 1 if diff["regressed"] else 0


if __name__ == "__main__":
    sys.exit(main())
