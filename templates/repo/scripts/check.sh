#!/usr/bin/env bash
# このリポジトリの確かめ。PR を出す前とマージの前に、引数なしで通す。
#   scripts/check.sh   プラグインの形（公式ディレクトリと同じ基準）・ハーネスの作り（harness_lint）・テスト
# scripts/harness_lint.py は nok-plugins の plugins/kanna/scripts/ の写し。直すときは向こうを直して写し直す。
# 動かせない検査は「未実行」として落とす（入っていない道具を黙って飛ばさない）。
# eval（claude plugin eval）は利用料がかかるので、ここでは流さない。人が決めたときだけ流す。
set -u; cd "$(dirname "$0")/.."; fail=0
PLUGIN=plugin   # プラグインのフォルダ。リポジトリの直下に置くなら "."
run() { echo "── $*"; "$@" || { fail=1; echo "✗ 落ちた：$*"; }; }
need() { command -v "$1" >/dev/null 2>&1 || { fail=1; echo "✗ 未実行：$1 がありません（$2）"; return 1; }; }

echo "■ 1. プラグインの形"
need claude "npm install -g @anthropic-ai/claude-code" && run claude plugin validate --strict --profile directory "$PLUGIN"

echo "■ 2. ハーネスの作り（スキル・エージェント・フック・eval。流さずに分かる物だけ）"
need python3 "Python 3 を入れる" && run python3 scripts/harness_lint.py "$PLUGIN"

echo "■ 3. テスト"
if [ -d tests ]; then
  need python3 "Python 3 を入れる" && run python3 -m pytest -q tests
else
  fail=1; echo "✗ 未実行：tests/ がありません（落とすべき物を落とすテストも書く）"
fi

[ $fail = 0 ] && echo "OK" || { echo "NG"; exit 1; }
