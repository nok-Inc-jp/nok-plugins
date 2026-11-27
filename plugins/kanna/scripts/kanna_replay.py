#!/usr/bin/env python3
"""--keep-temp で残した eval の回に、今の grader を当て直す（利用料はかからない）。

grader を直したら、流し直す前に、残してある回の出力に当て直す。前の採点と食い違った所を出すので、
「正しい答えを落とすようになっていないか」「誤った答えを通すようになっていないか」を、0 円で確かめられる
（kanna の R25 で、llm の grader を regex に替えたとき、正しい答えを 1 回落とす pattern を書いていたのに気づいた）。

当て直せるのは、決まった答えの grader（regex・tool_used・tool_order・file_exists）だけ。llm と baseline は
流さないと分からないので「当て直せない」と出す。

使い方:
  python3 kanna_replay.py <result.json> --plugin <プラグインのフォルダ> [--case 名前] [--json]

result.json は kanna_run.py run --keep-temp（か claude plugin eval --keep-temp --json）の出力。
終わりの値: 0 = 食い違いが無い。1 = 前の採点と食い違った grader がある。2 = 使い方の誤り・読めない。
標準ライブラリだけで動く。
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness_lint  # noqa: E402


def read_trace(path: Path) -> list[dict]:
    events = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def blocks(events: list[dict]):
    for e in events:
        m = e.get("message") if isinstance(e.get("message"), dict) else {}
        content = m.get("content")
        if isinstance(content, list):
            for b in content:
                if isinstance(b, dict):
                    yield e.get("type"), b


def last_message(events: list[dict]) -> str:
    texts = [b.get("text", "") for t, b in blocks(events) if t == "assistant" and b.get("type") == "text"]
    return texts[-1] if texts else ""


def tool_calls(events: list[dict]) -> list[tuple[str, str]]:
    out = []
    for t, b in blocks(events):
        if b.get("type") == "tool_use":
            inp = b.get("input") if isinstance(b.get("input"), dict) else {}
            out.append((str(b.get("name") or ""), json.dumps(inp, ensure_ascii=False)))
    return out


def rx(pattern: str, flags: str = "") -> re.Pattern:
    f = 0
    f |= re.I if "i" in flags else 0
    f |= re.M if "m" in flags else 0
    f |= re.S if "s" in flags else 0
    return re.compile(harness_lint.js_regex_to_py(pattern), f)


def matches_tool(spec, name: str, inp: str) -> bool:
    if isinstance(spec, dict):
        if str(spec.get("tool") or "") != name:
            return False
        im = spec.get("input_match")
        return not im or bool(rx(str(im)).search(inp))
    return str(spec) == name


def replay(g: harness_lint.Grader, events: list[dict], work: Path) -> bool | None:
    """True / False。当て直せない grader は None。"""
    t = str(g.fm.get("type") or "")
    if t == "regex":
        target = g.fm.get("target") or "last_message"
        if isinstance(target, dict) and target.get("source") == "file":
            f = work / str(target.get("path") or "")
            if not f.is_file():
                return False  # claude plugin eval も、無いファイルは落とす
            text = f.read_text(encoding="utf-8", errors="replace")
        elif target == "trace":
            text = "\n".join(json.dumps(e, ensure_ascii=False) for e in events)
        elif target == "last_message":
            text = last_message(events)
        else:
            return None
        found = rx(str(g.fm.get("pattern") or ""), str(g.fm.get("flags") or "")).findall(text)
        match = str(g.fm.get("match") or "contains")
        if match == "not_contains":
            return not found
        if match.startswith("count:"):
            try:
                return len(found) == int(match.split(":", 1)[1])
            except ValueError:
                return None
        return bool(found)
    if t == "tool_used":
        tool = str(g.fm.get("tool") or "")
        im = g.fm.get("input_match")
        n = sum(1 for name, inp in tool_calls(events) if name == tool and (not im or rx(str(im)).search(inp)))
        mn, mx = g.fm.get("min", 1), g.fm.get("max")
        return n >= (mn if isinstance(mn, int) else 1) and (mx is None or n <= mx)
    if t == "tool_order":
        calls = tool_calls(events)
        bi = next((i for i, (n, inp) in enumerate(calls) if matches_tool(g.fm.get("before"), n, inp)), None)
        ai = next((i for i, (n, inp) in enumerate(calls) if matches_tool(g.fm.get("after"), n, inp)), None)
        return bi is not None and ai is not None and bi < ai
    if t == "file_exists":
        hits = [p for p in work.rglob("*") if p.is_file() and fnmatch.fnmatch(p.relative_to(work).as_posix(), str(g.fm.get("path") or ""))]
        return bool(hits) if g.fm.get("exists", True) is not False else not hits
    return None  # llm・baseline


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("result", type=Path)
    ap.add_argument("--plugin", type=Path, required=True)
    ap.add_argument("--case")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        result = json.loads(a.result.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"結果が読めない：{e}", file=sys.stderr)
        return 2
    plugin = a.plugin.resolve()
    rep = harness_lint.Report("replay")
    cases = {c.name: c for c in harness_lint.load_cases(rep, plugin, harness_lint.load_manifest(plugin))}
    rows, changed, missing = [], 0, 0
    for rc in result.get("cases") or []:
        name = str(rc.get("name") or "")
        if a.case and name != a.case:
            continue
        case = cases.get(name)
        if not case:
            continue
        for i, run in enumerate((rc.get("arms") or {}).get("with") or []):
            tp = Path(str(run.get("tracePath") or ""))
            if not tp.is_file():
                missing += 1
                continue
            work = tp.parent.parent / "home" / "cwd"
            events = read_trace(tp)
            before = {str(g.get("name")): g.get("passed") for g in run.get("graders") or []}
            for g in case.graders:
                gname = g.path.stem
                now = replay(g, events, work)
                old = before.get(gname)
                if now is None:
                    status = "当て直せない"
                elif old is None:
                    status = "新しい grader"
                elif bool(old) != now:
                    status = "食い違い"
                    changed += 1
                else:
                    continue
                rows.append({"case": name, "run": i + 1, "grader": gname, "before": old, "now": now, "status": status})
    if a.json:
        print(json.dumps({"rows": rows, "changed": changed, "missing_traces": missing}, ensure_ascii=False, indent=2))
    else:
        if missing:
            print(f"trace が無い回：{missing}（--keep-temp を付けて流した回だけ当て直せる）")
        show = [r for r in rows if r["status"] != "当て直せない"]
        if not show:
            print("前の採点と食い違った grader は無い（llm・baseline は当て直していない）")
        for r in show:
            mark = {True: "通る", False: "落ちる", None: "なし"}
            print(f"- {r['status']}：{r['case']} の {r['run']} 回目・{r['grader']}：前は{mark[r['before']]} → 今は{mark[r['now']]}")
    return 1 if changed else (2 if missing and not rows else 0)


if __name__ == "__main__":
    sys.exit(main())
