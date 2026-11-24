# __PROJECT_NAME__ — Claude Code 向けの指示

__DESCRIPTION__

## まず読むもの

- `README.md`：使い方
- `CONTRIBUTING.md`：ブランチ・コミット・PR・確かめの手順（一次情報。ここには要約だけを書く）
- `docs/decisions.md`：ラウンドごとの決定事項（ここに書かれたことが正）
- `.claude/rules/`：パス限定の決まり（`paths` に合うファイルを触るときだけ読まれる）

## 進め方のルール

- **テストは必ず実行する**。通らないものは PR にしない。マージの前にもう一度すべて通す
- `scripts/check.sh` を引数なしで通す。動かせなかった検査は「未実行」で、合格ではない（PR の「確かめ」に分けて書く）
- 通すために弱めない。テストを消す・skip する・しきい値を緩める、をしない。直せないときは理由を書いて判断を仰ぐ
- 不具合を直すときは、先にその不具合で落ちるテストを書き、落ちるのを見てから直す
- 変更はブランチを切って PR にする。`main` に直接 commit・push しない（フック `.claude/hooks/guard_git.py` が止める）
- commit・push・PR・マージは、人に言われるまでしない。コミットと PR のタイトルは Conventional Commits（`feat(範囲): 要約`）
- サブエージェントを使うときは **sonnet か haiku** だけにする（コストのため）
- ラウンドで進める。決めたことは `docs/decisions.md` にラウンド単位で足す。**[案]** は勝手に確定させない
- 秘密（API キー・トークン・`.env`・鍵）と、ユーザー名の入った絶対パスを書かない・コミットしない

## 必ず回すチェック

```sh
scripts/check.sh
```

中で流れるもの：

__CHECK_COMMANDS__

## nok-plugins

`.claude/settings.json` に nok-plugins（`nok-Inc-jp/nok-plugins`）を登録してある。足りないプラグインは会話の中で入れる。

```
/plugin install <名前>@nok-plugins
```

このリポジトリで最初から使うプラグインは `.claude/settings.json` の `enabledPlugins` に書く。非公開のプラグインを入れるときは、GitHub に入れる状態（`gh auth login` など）にしておく。
