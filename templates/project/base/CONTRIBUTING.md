# 開発の手順

進め方の一次情報。Claude Code 向けの決まりの要約は `CLAUDE.md`、決めたことは `docs/decisions.md`。

## ブランチ（GitHub Flow）

- `main` に直接 commit・push しない（`.claude/hooks/guard_git.py` と、GitHub のブランチ保護で止める）
- 作業ブランチの名前は `claude/<話題>`（Claude の作業）か `feat/<話題>`・`fix/<話題>`・`docs/<話題>`
- force push はしない。履歴を書き換えるときは人が明示して行う

## コミットと PR

- コミットの 1 行目と PR のタイトルは Conventional Commits：`feat|fix|docs|test|refactor|chore|ci(範囲): 要約`（壊す変更は `feat(範囲)!: 要約`）
- 1 つの機能を 1 つのコミットにする
- PR は `.github/pull_request_template.md` の形で書く。実行した確かめと、していない物（未実行）を分ける
- CI は PR に `ci` ラベルを付けたときに流れる（Actions の利用枠のため）。マージの前に付ける

## 確かめ

- 入口は `scripts/check.sh` の 1 つだけ。手元でも CI でも同じ物を流す
- テストを足さない機能の PR は出さない。不具合を直すときは、先に落ちるテストを書く
- 確かめを足す・変えるときは `scripts/check.sh`（言語ごとの物は `scripts/check-stack.sh`）を直す

## 決めること

- 設計・道具の選び方・進め方の決定は、ラウンドごとに `docs/decisions.md` に書く
- 大きく変える前（3 つ以上のファイルの形を変える、壊す変更）は、先に issue（「ラウンド」か「提案」）で決める

## 依存を足す

- 足す理由を PR に書き、ロックファイル（`package-lock.json`・`Cargo.lock` など）も一緒にコミットする
- 更新は dependabot が月 1 回まとめて出す（`.github/dependabot.yml`）

## 弱いところ（脆弱性）の報告

公開の issue に書かず、Security タブの「Report a vulnerability」から知らせる（`nok-Inc-jp/.github` の SECURITY.md）。
