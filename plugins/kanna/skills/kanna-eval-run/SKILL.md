---
name: kanna-eval-run
description: プラグインの eval（claude plugin eval）を、流し方と費用の上限を見せて了承を取ってから、下位のモデル（haiku）から回し、結果を台帳（evals/ledger.jsonl）に残して前の回と比べ、落ちた理由を「プラグイン・採点・流し方」に分けて返す。「eval を回して」「プラグインを評価して」「前より良くなったか確かめて」「リグレッションが無いか見て」と言われたときに使う
argument-hint: "<プラグインのフォルダ> [--case <名前の型>] [--tag <tag>]"
---

# kanna-eval-run

eval を回すのは、利用料を使うことと同じ。**流す前に人に決めてもらい、安く狭く始めて、通ったら広げる**。1 回の点で「良くなった」と言わず、台帳で前の回と比べる。

## 必ず守ること

- 流す前に、命令の全文・モデル・回数・ケースの数・費用の上限を見せ、了承を待つ。了承の無いまま流さない。
- 命令は `kanna_run.py` に組ませる。手で組むときも、必ず `--model` と `--max-cost-usd` を付ける（付けないと kanna のフックが止める）。
- モデルは haiku から。haiku で通ってから sonnet。opus・fable は、人が頼んだときだけ。
- 結果はプラグインの外（作業フォルダの `.kanna/runs/<日時>/`）に置く。台帳だけを `evals/ledger.jsonl` に足す（`kanna_run.py` がそうする）。
- 落ちたケースを通すために、grader を甘くしない。採点が誤っていると考えたら、その理由を返事に書き、直すかは人に任せる。

## 手順

```
- [ ] 1. 検査を通した（harness_lint の必須の外れ 0）
- [ ] 2. 流し方を見せ、了承を取った
- [ ] 3. 流した
- [ ] 4. 台帳に足し、前の回と比べた
- [ ] 5. 落ちた理由を分けた
```

1. 引数のフォルダは、作業フォルダ（今いる所）からの相対で探す。kanna の置き場（`${CLAUDE_PLUGIN_ROOT}`）の中を探さない。`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/harness_lint.py" <フォルダ>` を流す。必須の外れがあれば、流さずに止まる（読み込めないケースや、必ず誤る採点に利用料を使わない）。
2. [references/run-protocol.md](references/run-protocol.md) の「段」で、流すケース（`--tag` か `--case`）と回数を決め、**命令は手で組まずに** `kanna_run.py plan` に組ませる。許す道具・scaffold・`TMPDIR`・費用の見積もりと上限は、ケースの tags と台帳から決まる。
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/kanna_run.py" plan <フォルダ> --tag trigger --runs 3
   ```
   出力（命令・ケースの数・回数・見積もり・上限・許す道具）をそのまま見せ、了承を待つ。
3. 了承をもらったら、同じ引数に `--yes` と `--note "<何を変えた後の回か>"` を足して流す（`timeout` を長めに。数分かかる）。流し終わると、台帳（`<フォルダ>/evals/ledger.jsonl`）に足して前の回と比べた結果まで出る。終わりの値が 2 なら、流せなかったか途中で止まった（費用の上限・認証）ことを伝える。
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/kanna_run.py" run <フォルダ> --tag trigger --runs 3 --yes --note "..."
   ```
4. 出力の「前の回との違い」を読む。「ぶれの範囲かも」と出たケースは、回を増やして流し直してから判断する。
5. 落ちた・下がった・ぶれたケースごとに、`.kanna/runs/<日時>/` の結果（grader の説明と証拠）を読み、[references/run-protocol.md](references/run-protocol.md) の「落ちた理由の分け方」で 3 つに分ける。分けられなければ「分からない」とし、推し量らない。

## 返す形

```
## 流した物
<命令の全文> ／ 費用 $X ／ 合格 N/M ／ 差（プラグイン無しとの差）X

## 前の回との違い
eval_ledger.py の出力をそのまま

## 落ちたケース
| ケース | 点 | 理由の分け（プラグイン / 採点 / 流し方 / 分からない） | 根拠（grader の説明の抜き書き） | 次の一手 |

## 次の段
<段を上げてよいか・止めるべきか。上げるなら命令の案>
```

## 詳しい資料

- [references/run-protocol.md](references/run-protocol.md)：段の上げ方、命令の組み方、落ちた理由の分け方、結果の読み方。流す前に必ず読む
