#!/usr/bin/env python3
"""一般のリポジトリの雛形（templates/project/）を組み立てて写す。標準ライブラリだけで動く。

    python3 scripts/new_project.py <写す先> --stack python [--name 名前] [--description 説明]
                                   [--plugins konomi,takumi] [--license proprietary|mit] [--owner nok-Inc-jp] [--codeowner nigoh] [--force]

- 共通の土台（templates/project/base/）に、言語ごとの部品（templates/project/stacks/<stack>/files/）を重ねる。
- .claude/settings.json に nok-plugins のマーケットプレイスを登録し、--plugins の物を最初から有効にする。
  名前は .claude-plugin/marketplace.json と突き合わせ、無い名前は受け付けない。
- 写す先に同じ名前のファイルがあれば、--force が無い限り何も書かずに止まる（.git はそのまま残す）。
- 終わりの値：0 で成功、1 で入力の誤り（何も書かない）。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "project"
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
MARKETPLACE_NAME = "nok-plugins"
NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")  # 先頭は英字（Python のパッケージ名にもなる）
OWNER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
CODEOWNER_RE = re.compile(r"^[A-Za-z0-9-]{1,39}(?:/[A-Za-z0-9_.-]{1,100})?$")
TOKEN_RE = re.compile(r"__[A-Z][A-Z_]*__")
LICENSES = {"proprietary": "UNLICENSED", "mit": "MIT"}  # 名前 → package.json などに書く SPDX
DEFAULT_DESCRIPTION = "【雛形】このリポジトリが何をするかを 2〜3 文で書く。"


class InputError(Exception):
    pass


def stacks() -> list[str]:
    return sorted(p.name for p in (TEMPLATE / "stacks").iterdir() if (p / "stack.json").is_file())


def known_plugins() -> list[str]:
    data = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    return [p["name"] for p in data.get("plugins", [])]


def parse_plugins(raw: str | None) -> list[str]:
    if not raw:
        return []
    names = [n.strip() for n in raw.split(",") if n.strip()]
    known = known_plugins()
    unknown = [n for n in names if n not in known]
    if unknown:
        raise InputError(f"nok-plugins に無いプラグインです：{', '.join(unknown)}（ある物：{', '.join(known)}）")
    return list(dict.fromkeys(names))


def collect(stack: str) -> dict[Path, Path]:
    """写す先の相対パス → 元のファイル。言語ごとの部品が土台より優先する。"""
    files: dict[Path, Path] = {}
    for src_root in (TEMPLATE / "base", TEMPLATE / "stacks" / stack / "files"):
        for src in sorted(src_root.rglob("*")):
            if src.is_file() and "__pycache__" not in src.parts:
                files[src.relative_to(src_root)] = src
    return files


def render(text: str, tokens: dict[str, str]) -> str:
    for k, v in tokens.items():
        text = text.replace(k, v)
    return text


def build(args: argparse.Namespace) -> list[Path]:
    dest = Path(args.dest).resolve()
    name = args.name or dest.name
    if not NAME_RE.match(name):
        raise InputError(f"名前は半角の小文字・数字・ハイフンで 64 字まで：{name!r}")
    if args.stack not in stacks():
        raise InputError(f"スタックは {', '.join(stacks())} のどれか：{args.stack!r}")
    plugins = parse_plugins(args.plugins)
    stack = json.loads((TEMPLATE / "stacks" / args.stack / "stack.json").read_text(encoding="utf-8"))
    description = (args.description or DEFAULT_DESCRIPTION).strip()
    if "\n" in description or "\r" in description:
        raise InputError("説明は 1 行で書く")
    if any(c in description for c in '"\\`') or "__" in description:
        raise InputError('説明に " \\ ` と __ は使えない（JSON・TOML・印を壊さないため）')
    if any(c in args.holder for c in '"\\`\n\r') or "__" in args.holder or not args.holder.strip():
        raise InputError(f"--holder（著作権者）に \" \\ ` __ と改行は使えない：{args.holder!r}")
    if not OWNER_RE.match(args.owner):
        raise InputError(f"--owner は GitHub の名前（英数字とハイフン）：{args.owner!r}")
    if not CODEOWNER_RE.match(args.codeowner):
        raise InputError(f"--codeowner は GitHub の名前か 組織/チーム：{args.codeowner!r}")

    tokens = {
        "__PROJECT_NAME__": name,
        "__PACKAGE__": name.replace("-", "_"),
        "__DESCRIPTION__": description,
        "__OWNER__": args.owner,
        "__CODEOWNER__": args.codeowner,
        "__STACK__": args.stack,
        "__YEAR__": str(dt.date.today().year),
        "__HOLDER__": args.holder.strip(),
        "__LICENSE_SPDX__": LICENSES[args.license],
        "__TODAY__": dt.date.today().isoformat(),
        "__CHECK_COMMANDS__": "\n".join(f"- `{c}`" for c in stack["check_commands"]),
        "__USAGE__": stack["usage"],
        "__DEPENDABOT_STACK__": stack["dependabot"],
    }

    # 先に全部をメモリの上で作る。誤りがあれば 1 つも書かない
    rendered: dict[str, str | Path] = {}
    for rel_raw, src in collect(args.stack).items():
        rel = render(str(rel_raw), tokens)
        try:
            text = src.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            rendered[rel] = src  # 画像など。そのまま写す
            continue
        if rel == ".claude/settings.json":
            text = settings_text(text, stack["allow"], plugins)
        elif rel == ".gitignore":
            text = text.rstrip("\n") + f"\n\n# {stack['title']}\n" + "\n".join(stack["gitignore"]) + "\n"
        rendered[rel] = render(text, tokens)
    rendered["LICENSE"] = render((TEMPLATE / "licenses" / f"{args.license}.txt").read_text(encoding="utf-8"), tokens)
    left = [rel for rel, v in rendered.items() if TOKEN_RE.search(rel) or (isinstance(v, str) and TOKEN_RE.search(v))]
    if left:  # 雛形の誤り。ここに来たら雛形を直す
        raise RuntimeError("置き換えていない印が残りました：" + ", ".join(left))

    links = [rel for rel in rendered if through_symlink(dest, rel)]
    if links:
        raise InputError("写す先にシンボリックリンクがあるので書きません：" + ", ".join(sorted(links)))
    clashes = sorted(rel for rel in rendered if (dest / rel).exists())
    if clashes and not args.force:
        raise InputError("写す先に同じ名前のファイルがあります（--force で上書き）：" + ", ".join(clashes))
    for rel in clashes:
        print(f"  上書き：{rel}")

    written: list[Path] = []
    for rel, v in rendered.items():
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(v, Path):
            shutil.copyfile(v, out)
        else:
            out.write_text(v, encoding="utf-8")
        if rel.endswith(".sh") or rel.startswith(".claude/hooks/"):
            out.chmod(0o755)
        written.append(out)
    return written


def through_symlink(dest: Path, rel: str) -> bool:
    """写す先の中で、rel までの途中かそのものがシンボリックリンクか（リンク先に書かないため）。"""
    p = dest
    for part in Path(rel).parts:
        p = p / part
        if p.is_symlink():
            return True
    return False


def settings_text(text: str, allow: list[str], plugins: list[str]) -> str:
    data = json.loads(text)
    perms = data.setdefault("permissions", {})
    perms["allow"] = list(dict.fromkeys(perms.get("allow", []) + allow))
    data["enabledPlugins"] = {f"{p}@{MARKETPLACE_NAME}": True for p in plugins}
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="一般のリポジトリの雛形を写す")
    ap.add_argument("dest", help="写す先のフォルダ（無ければ作る。clone したばかりのリポジトリでもよい）")
    ap.add_argument("--stack", required=True, help="python・node・rust のどれか")
    ap.add_argument("--name", help="リポジトリの名前（省くと写す先のフォルダ名）")
    ap.add_argument("--description", help="1 行の説明（省くと、書き換える印が残り check.sh が落ちる）")
    ap.add_argument("--plugins", help="最初から有効にする nok-plugins のプラグイン（カンマ区切り）")
    ap.add_argument("--owner", default="nok-Inc-jp", help="GitHub の持ち主（既定：nok-Inc-jp）")
    ap.add_argument("--codeowner", default="nigoh", help="CODEOWNERS に書く人（既定：nigoh）")
    ap.add_argument("--license", choices=sorted(LICENSES), default="proprietary", help="LICENSE（既定：proprietary＝社外での利用を許さない）")
    ap.add_argument("--holder", default="株式会社ノック", help="LICENSE の著作権者（既定：株式会社ノック）")
    ap.add_argument("--force", action="store_true", help="同じ名前のファイルを上書きする")
    args = ap.parse_args(argv)
    try:
        written = build(args)
    except InputError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1
    print(f"✓ {len(written)} 個のファイルを {Path(args.dest)} に写しました（スタック：{args.stack}）")
    print("  次に：scripts/check.sh を引数なしで流す。説明を省いたときは、書き換える印を埋めてから通る。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
