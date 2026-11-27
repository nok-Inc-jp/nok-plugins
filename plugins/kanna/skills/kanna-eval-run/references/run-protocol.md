# eval の流し方

## 目次

- [段の上げ方](#段の上げ方)
- [命令の組み方](#命令の組み方)
- [落ちた理由の分け方](#落ちた理由の分け方)
- [結果の読み方](#結果の読み方)

## 段の上げ方

安く狭く始めて、通ったら広げる。前の段が通らないうちに次へ進まない。

| 段 | 何を流すか | 命令の要（ほかは「命令の組み方」） | 上限の目安 |
| --- | --- | --- | --- |
| 0 | 採点だけを確かめる | `--case <1 件> --runs 1 --ablation none` | $0.3 |
| 1 | 呼ばれる・呼ばれない | `--tag trigger --runs 3 --ablation none`（呼ばれる率を決めるときは `--runs 10`） | $1 |
| 2 | 結果と約束 | `--tag outcome --tag safety --runs 3`（ablation あり） | $3 |
| 3 | 全部を haiku で | `--runs 3` | $5 |
| 4 | 全部を sonnet で | `--model sonnet --runs 3` | $10 |

- モデルは haiku → sonnet の順。opus・fable は人が頼んだときだけ（kanna のフックが確かめを出す）。
- 判定役（`--judge-model`）は haiku のまま。llm の grader で「スキルは呼ばれたのに、差が負」なら、判定役を疑って `--judge-model sonnet` で同じケースだけを流し直す。
- 前の段の上限を超えそうなら、ケースを `--case` で絞る。上限を上げるのは人が決める。

## 命令の組み方

ふだんは `scripts/kanna_run.py plan` に組ませる（下の決まりを、ケースの tags と台帳から決める）。ここに書くのは、その中身と、手で組むときの決まり。

```bash
claude plugin eval <フォルダ> \
  --model haiku --judge-model haiku --runs 3 --max-cost-usd 1 \
  --tag trigger \
  --json .kanna/runs/<日時>/result.json --output-dir .kanna/runs/<日時> --no-publish
```

- `--case` は 1 つの型（glob）だけ。2 回書くと後の方だけが効き、`'{a,b}'` の形は 0 件になる。いくつかを選ぶときは `--tag` を使う（`--tag` は何回でも書ける）。0 件の回は台帳に足さない。
- `--allow-tools`：流すケースの `tags` に `needs-bash` があれば `Bash`、`needs-write` があれば `Write Edit`、`needs-web` があれば `WebFetch(domain:<ホスト>)`。無ければ付けない。
- **一時フォルダ**：Bash で書く道具（スクリプトがファイルを作る）を流すケースが、どれも「Read-only file system」で落ちるなら、`TMPDIR` を `/tmp` の外に向けて流す（`TMPDIR=$HOME/.eval-tmp claude plugin eval ...`）。eval のサンドボックスは `/tmp` 全体を書けない所にし、作業フォルダも既定では `/tmp` の下に作るので、Bash からは作業フォルダに書けなくなる（kanna の R20）。Write・Edit の道具は影響を受けない。
- `--scaffold`：流すケースに `case.yaml` の `scaffold_script` があるときだけ。scaffold は作者が書いた bash を、あなたとして流す。自分たちで書いたケースのときだけ付ける。
- `--trust-plugin`：自分たちのプラグインで、人がそう決めたときだけ（初めての回は確かめの問いが出る）。
- `--mocks off`・`--allow-real-servers`：本物の MCP サーバーがサンドボックスの外で動く。人が頼んだときだけ（フックが確かめを出す）。
- `--threshold`：既定は 1.0（全部の grader が全部の回で通る）。下げるのは、ぶれる grader を直すまでの間だけにし、台帳の `--threshold` にも同じ値を渡す。
- 日時は `date -u +%Y%m%dT%H%M%SZ`。`.kanna/` はコミットしない（`.gitignore` に足す）。

## 落ちた理由の分け方

ケースの点が 1 に届かなかったら、grader の説明（explanation）と証拠（evidence）を読み、次の順に当てる。最初に当たった物にする。

| 分け | 見分け方 | 次の一手 |
| --- | --- | --- |
| 流し方 | `error`・`aborted` がある／`max_turns` か `timeout_seconds` で切られた／scaffold が落ちた／要る道具を許していない（Bash を求めるのに `--allow-tools Bash` が無い） | 命令かケースの上限を直して、同じケースだけを流し直す（点の比べには入れない） |
| 採点 | 返事や書いたファイルは約束どおりなのに grader が落とした／判定役が条件を読み違えた／言い方の揺れを regex が拾えない | grader を直す案を書く。**直すかは人が決める**。直したら、流す前に `scripts/kanna_replay.py <result.json> --plugin <フォルダ>` で、`--keep-temp` で残した回に当て直し、前に通していた正しい答えを落とさないか・誤った答えを通さないかを 0 円で確かめる |
| プラグイン | 約束どおりでない（呼ばれるべきで呼ばれない、見出しが無い、直してはいけないファイルを直した） | kanna-tune でスキルの本文か description を 1 か所直し、そのケースを流し直す |
| 分からない | 上のどれにも決めきれない | 推し量らず、grader の証拠の抜き書きを付けて、人に渡す |

**走れなかった回（`error` がある回）の点は信じない**。走らなかった回でも、「呼ばない」「書かない」（max 0）の grader は空振りで通るので、0.5 のような点が出る。台帳の「走れなかった回がある」に出たケースは、点の比べから外して流し直す。Bash を許す回は、手元にサンドボックス（Linux なら bubblewrap と socat）が要る。無いと全部の回が走らない。

点が 0 と 1 の間（ぶれる）のケースは、`--runs 5` でそのケースだけを流し、ぶれがプラグインのせいか採点のせいかを分ける。

## 結果の読み方

- `aggregates.overallScore`：ケースの点の平均。`casesPassed / casesTotal`：合格の線を越えたケースの数。
- `cases[].aggregates.delta`：プラグインあり − プラグイン無しの点。0 以下なら、そのケースでプラグインは効いていない（プラグイン無しでも同じことができる・ケースが易しすぎる、のどちらか）。
- `tool_used: Skill` の grader は、ablation のとき点に入らない（「スキルが呼ばれたか」の印として出る）。
- `partial: true` は途中で止まった回。台帳の比べ（同じモデルの前の回）には使われない。
- Claude Code の版（`claudeVersion`）が前の回と違うと、差が版のせいかもしれない。台帳の比べが注意を出す。
