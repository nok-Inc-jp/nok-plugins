---
name: kanna-eval-design
description: プラグインのスキル 1 つに、足りない eval のケース（呼ばれる・似ているが呼ばれない・結果・してはいけないこと）を設計し、カバーの表を見せて了承を取ってから、evals/ に書く。「eval を足して」「このスキルのテストケースを作って」「呼ばれすぎ・呼ばれなさすぎを確かめたい」「kanna-report の測れていない所を埋めて」と言われたときに使う。流さない
argument-hint: "<プラグインのフォルダ> <スキル名>"
---

# kanna-eval-design

スキルが**約束していること**を並べ、それぞれを確かめるケースを、決まった答えの grader を先にして作る。書くのは `evals/` の中だけ。スキルの本文は直さない（直す案は返事に書く）。

## 必ず守ること

- 書く前に、カバーの表を見せて了承を取る（ケースは回すたびに利用料がかかる。要らないケースを作らない）。
- 書くのは `kanna-eval-writer` に任せる（フックで `evals/` の中にしか書けない）。自分で Write しない。
- 採点は決まった答えの grader（`tool_used`・`file_exists`・`regex`）を先に置き、`llm` は 1 条件ずつ、ケースに 1〜2 件まで。
- 「呼ばれない」ケースは、無関係な依頼でなく、**似ているが違う**依頼にする（隣のスキルの依頼、同じ語を含む別の頼み）。
- スキルの本文を通すためにケースを甘くしない。スキルの約束と食い違うなら、ケースでなく食い違いを報告する。
- 流さない（回すのは kanna-eval-run）。

## 手順

```
- [ ] 1. スキルの約束を並べた
- [ ] 2. 今のケースと突き合わせた
- [ ] 3. カバーの表を見せ、了承を取った
- [ ] 4. kanna-eval-writer に書かせた
- [ ] 5. 検査を通した
```

1. 引数のフォルダは、作業フォルダ（今いる所）からの相対で探す。kanna の置き場（`${CLAUDE_PLUGIN_ROOT}`）の中を探さない。`<フォルダ>/skills/<スキル>/SKILL.md` と、そこからリンクした資料を読み、約束を 4 つの種類に分けて並べる：**呼ばれる場面**（description の言い方）・**呼ばれない場面**（隣のスキルや、似た語の別の頼み）・**結果**（書くファイル・見出し・ID・数）・**してはいけないこと**（直さない・流さない・確かめてから、など）。
2. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/harness_lint.py" <フォルダ>` を流し、`evals/` を読んで、約束ごとに今のケースがあるかを見る。
3. 足すケースを [references/case-patterns.md](references/case-patterns.md) の型から選び、次の表で見せて、了承を待つ（直しを言われたら直して見せ直す）。
   ```
   | ケース | 種類 | 確かめる約束 | grader（決まった物 / llm） | 要る道具 | 入力を作るか |
   ```
4. 了承をもらったら、Agent で `kanna-eval-writer` を呼び、プラグインのフォルダ・スキル名・表・型の名前と、型の資料の場所（`${CLAUDE_PLUGIN_ROOT}/skills/kanna-eval-design/references/case-patterns.md`）を渡す。
5. `harness_lint.py` をもう一度流す。必須の外れが 0 で、そのスキルの QG01〜QG03 が通るまで、writer に直させる（3 回で通らなければ、残りを報告して止まる）。

## 返す形

```
## 足したケース
| ケース | 種類 | grader の数（決まった物 / llm） |

## 検査
harness_lint：必須の外れ 0・推奨の外れ N（残りの理由）

## スキルの方の気づき（直していない）
- <約束があいまいで、ケースにできなかった所など>

## 次の一手
kanna-eval-run で `--case '<名前>*' --model haiku --runs 3` から回す
```

## 詳しい資料

- [references/case-patterns.md](references/case-patterns.md)：ケースの型（trigger・near-miss・outcome・safety）と grader の書き方の見本、scaffold の安全な書き方。表を作る前に読む
