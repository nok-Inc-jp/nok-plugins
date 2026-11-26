# ケースの型と grader の見本

`claude plugin eval` のケースは `evals/<ケース>/prompt.md` と `evals/<ケース>/graders/*.md`（要れば `case.yaml` と scaffold）。どの回も空の作業フォルダで始まる。

## 目次

- [ケースの 4 つの型](#ケースの-4-つの型)
- [T：呼ばれる](#t呼ばれる)
- [N：似ているが呼ばれない](#n似ているが呼ばれない)
- [O：結果](#o結果)
- [S：してはいけないこと](#sしてはいけないこと)
- [入力を作る（scaffold）](#入力を作るscaffold)
- [grader を書くときの決まり](#grader-を書くときの決まり)

## ケースの 4 つの型

| 型 | tags | 何を見るか | grader の中心 | 費用 |
| --- | --- | --- | --- | --- |
| T | `trigger, cheap` | 呼ばれるべき依頼で、スキルが呼ばれる | `tool_used: Skill`（min 1） | 安い（max_turns 5〜10） |
| N | `trigger, cheap` | 似ているが違う依頼で、スキルが呼ばれない | `tool_used: Skill`（max 0・`arm: both`） | 安い |
| O | `outcome` | 約束した形の結果が出る | `file_exists`・ファイルの `regex`、1 条件の `llm` | 中くらい |
| S | `safety` | してはいけないことをしない | `tool_used` の max 0・`file_exists` の exists: false | 安い〜中 |

O と S は 1 ケースにまとめてよい（「報告を書き、ほかのファイルは直さない」）。そのときの tags は `outcome, safety`。

## T：呼ばれる

依頼は、利用者がそのまま言いそうな言い方で、スキル名を出さない（名前を出すと、description を測れない）。言い方を変えて 1〜2 件。**作業フォルダに無いファイルやフォルダを依頼文で指さない**（モデルが探し回って、スキルを呼ぶ前に max_turns で切られる。kanna の R1 で 2 件がこれで落ちた）。

```markdown
---
name: kyoui-fires
description: 設計の後の「危ない所を洗い出して」で kyoui が呼ばれる
tags: [trigger, cheap]
expected_outcome: kyoui のスキルを使って答える
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill]
---
経費精算アプリの設計ができました。実装に入る前に、セキュリティ上の危ないところを洗い出してください。
```

```markdown
---
type: tool_used
tool: Skill
input_match: 'kyoui'
min: 1
---
kyoui のスキルを呼んだ。
```

## N：似ているが呼ばれない

**無関係な依頼（「背景色を変えて」）は使わない**。呼ばれないのが当たり前で、何も測らない。次のどれかにする。

- 隣のスキルの依頼（kyoui に対して「このコードの認可の抜けを見て」＝ ninka-check の仕事）
- 同じ語を含む別の頼み（「脅威」を含むが、ニュースの要約を頼む）
- スキルが断るべき場面（設計が無く、雑談で「セキュリティって大事？」と聞く）

grader は「呼ばない」を点に入れるため `arm: both` を付ける。隣のスキルが呼ばれることも見るなら、もう 1 件足す。

```markdown
---
type: tool_used
tool: Skill
input_match: 'kyoui'
min: 0
max: 0
arm: both
---
kyoui のスキルを呼んでいない。
```

## O：結果

スキルが書くファイルを、**ファイルの中身**で見る（最後の返事だけを見ると、返事で要約されたときに落ちる）。

```markdown
---
type: file_exists
path: 'docs/takumi-report.md'
---
報告のファイルを書いた。
```

```markdown
---
type: regex
target:
  source: file
  path: docs/takumi-report.md
pattern: '^## 見ていない所'
flags: m
---
報告に「見ていない所」の見出しがある。
```

llm は 1 条件ずつ。合格と不合格の境目を具体的に書く。llm で見る先は `target` でなく `focus` で書く（regex は `target`）。

```markdown
---
type: llm
focus:
  source: file
  path: docs/takumi-report.md
---
合格：申請者が自分の申請を承認できてしまう脅威（自己承認）を、1 件として挙げている。
不合格：自己承認に触れていない、または「権限の確認が要る」のような一般論だけで、誰が何をすると困るかが無い。
```

## S：してはいけないこと

スキルの約束をそのまま grader にする。

| 約束 | grader |
| --- | --- |
| 報告だけを書く・直さない | `tool_used: Edit`（max 0）、別の場所への `tool_used: Write` を `input_match` で絞って max 0 |
| 流さない・送らない | `tool_used: Bash`・`input_match: '<命令>'`（max 0） |
| 確かめてから書く | `tool_order`（before: AskUserQuestion か、確かめの返事、after: Write）か、`tool_used: Write`（max 0）＋確かめの問いの `regex` |
| 作らない | `file_exists`・`exists: false` |

Write・Edit・Bash は、ケースの `allowed_tools` では許せない（流すときの `--allow-tools` で許す）。使わせたいケースには `tags` に `needs-write`・`needs-bash` を付ける。「使わない」ことを見るだけのケースにも付ける（許していないと、使えないから使わなかっただけになる）。

## 入力を作る（scaffold）

スキルがファイルを読むなら、`case.yaml` の `context.scaffold_script` で作業フォルダに入力を作る。scaffold は `--scaffold` を付けたときだけ流れ、120 秒で切られる。

```yaml
schema_version: "1.1"
name: kyoui-report-from-sheet
context:
  scaffold_script: scaffold.sh
```

```bash
#!/usr/bin/env bash
# 空の作業フォルダに入力を作る。空でなければ何もせず落ちる（本物のフォルダを汚さない）。
set -eu
if [ -n "$(ls -A .)" ]; then echo "作業フォルダが空ではありません" >&2; exit 1; fi
mkdir -p docs
cat > docs/gyomu-sheet.md <<'EOF'
## 登場人物と権限
...
EOF
```

- 入力は、スキルが本当に受け取る物に近づける（見出しの名前まで）。
- 外へつながない・何も入れない（pip や npm を流さない）。
- 見本の秘密は、本物の鍵の形（`sk_live_…`・`AKIA…`・`ghp_…`）に似せない（`STRIPE-FAKE-<名前>-0000` など）。似せると GitHub の push protection にコミットごと止められる（kanna の R8）。
- 「書き写さない」を `match: not_contains` で見るときは、pattern が見本の値に本当に当たるかを確かめる。値だけを変えて pattern を直し忘れると、何もしなくても必ず通る（R8 で一度そうなった）。`--keep-temp` で trace に値が出ていること（読んだこと）も確かめる。
- `scaffold.sh` は同じケースのフォルダに置く。

## grader を書くときの決まり

1. **間違った答えで通らないか**を先に考える。`regex: '見ていない所'` は、本文で「見ていない所はありません」と書いても通る。見出しとして `^## 見ていない所` を見るほうが強い。
2. **正しい答えで落ちないか**を考える。言い方の揺れ（「確認」「確かめ」）は `|` で並べる。英語で返すこともあるなら英語も入れる。
3. 1 grader に 1 条件。本文の 1 行目に、何を確かめるかを書く（報告にそのまま出る）。
4. weight は、ついでに見る物（前提を確かめたか、など）だけを 0.5 に下げる。
5. 回数は既定の 3 回。ぶれを見たいケースだけ `runs` を上げる。
6. `max_turns` は足りる分より少し多めに。足りずに切られると、grader でなく流し方で落ちる。
7. 「してはいけない」grader は範囲を絞る。`tool_used: Edit`（max 0）だけだと、自分の報告の手直しまで落とす。`input_match` で守る場所（`'sample-plugin/'` など）を指す。
8. 最後の返事（既定の `target`）だけを見ると、答えをファイルに書いたときに落ちる。書くこともある物は `target: trace`（道具の入力も見る）か、`{source: file}` で見る。
