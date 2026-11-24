#!/usr/bin/env bash
# このリポジトリの確かめ。PR を出す前とマージの前に、引数なしで通す。
#   1. 雛形の印が残っていない
#   2. 守りのフック（.claude/hooks/）のテスト
#   3. 設定ファイルの形（.claude/settings.json）
#   4. 言語ごとの確かめ（scripts/check-stack.sh）
# 動かせない検査は「未実行」として落とす（入っていない道具を黙って飛ばさない）。
# テストが 1 件も流れなかったときも落とす（消えたテストを合格と見ない）。
set -u; cd "$(dirname "$0")/.."; fail=0
run() { echo "── $*"; "$@" || { fail=1; echo "✗ 落ちた：$*"; }; }
need() { command -v "$1" >/dev/null 2>&1 || { fail=1; echo "✗ 未実行：$1 がありません（$2）"; return 1; }; }
# run_counted <件数を拾う正規表現（数を 1 つ目の組に）> <コマンド…>：通っても、件数が 0 か読めなければ落とす
run_counted() {
  local pat=$1; shift; echo "── $*"
  local out; out=$("$@" 2>&1); local rc=$?; printf '%s\n' "$out"
  if [ $rc -ne 0 ]; then fail=1; echo "✗ 落ちた：$*"; return; fi
  local n; n=$(printf '%s\n' "$out" | sed -nE "s/.*$pat.*/\\1/p" | awk '{s+=$1} END {print s+0}')
  if [ "$n" -eq 0 ]; then fail=1; echo "✗ テストが 1 件も流れていません：$*"; fi
}

echo "■ 1. 雛形の印"
mark='【雛'"形】"
left=$(grep -rIl --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=target --exclude-dir=.venv -- "$mark" .); rc=$?
if [ $rc -eq 0 ]; then
  fail=1; echo "✗ 書き換えていない印（$mark）が残っています："; echo "$left"
elif [ $rc -ne 1 ]; then
  fail=1; echo "✗ 未実行：印を探せませんでした（grep の終わりの値 $rc）"
fi

echo "■ 2. 守りのフックのテスト"
need python3 "Python 3 を入れる" && run_counted 'Ran ([0-9]+) test' python3 -m unittest discover -s .claude/hooks -p 'test_*.py'

echo "■ 3. 設定の形"
need python3 "Python 3 を入れる" && run python3 -c 'import json,sys; [json.load(open(p, encoding="utf-8")) for p in sys.argv[1:]]' .claude/settings.json

echo "■ 4. 言語ごとの確かめ"
if [ -f scripts/check-stack.sh ]; then
  if bash -n scripts/check-stack.sh; then
    # run・run_counted・need をそのまま使えるように、同じシェルで読む
    . scripts/check-stack.sh || { fail=1; echo "✗ 落ちた：scripts/check-stack.sh"; }
  else
    fail=1; echo "✗ 落ちた：scripts/check-stack.sh の書き方に誤りがあります"
  fi
else
  fail=1; echo "✗ 未実行：scripts/check-stack.sh がありません"
fi

[ $fail = 0 ] && echo "OK" || { echo "NG"; exit 1; }
