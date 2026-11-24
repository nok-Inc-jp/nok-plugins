#!/usr/bin/env bash
# GitHub の側の準備（ラベル）。リポジトリを作ったあとに 1 回だけ、人が流す。
#   scripts/setup_github.sh            何をするかを見せるだけ
#   scripts/setup_github.sh --apply    本当に作る（gh auth login が要る）
# ブランチ保護はここでは変えない。Settings → Rules で、main に「PR を必須」「CODEOWNERS の承認」「check を必須」を入れる。
set -euo pipefail
apply=0; [ "${1:-}" = "--apply" ] && apply=1
labels=(
  "ci|0e8a16|PR に付けると CI（check）が流れる"
  "round|5319e7|ラウンドで決めること・作ること"
  "enhancement|a2eeef|足す・変える提案"
  "bug|d73a4a|思ったとおりに動かない"
  "dependencies|0366d6|依存の更新"
  "breaking|b60205|壊す変更"
  "skip-changelog|cccccc|リリースノートに載せない"
)
for l in "${labels[@]}"; do
  IFS='|' read -r name color desc <<<"$l"
  if [ $apply = 1 ]; then
    gh label create "$name" --color "$color" --description "$desc" --force
  else
    echo "gh label create \"$name\" --color $color --description \"$desc\" --force"
  fi
done
[ $apply = 1 ] || echo "（見せただけ。作るときは --apply）"
