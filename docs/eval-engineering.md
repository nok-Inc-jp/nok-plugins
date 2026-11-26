# nok のプラグインの eval の作法

nok のプラグインのハーネス（スキル・エージェント・フック・eval）を、どう作り、どう測るかの決まり。公式の文書（2026-11-26 に読んだ物）と、kanna を作るときに実際に回して分かったこと（`plugins/kanna/evals/ledger.jsonl`）から決めた。道具は kanna（`plugins/kanna/`）。

## 目次

- [1. 考え方](#1-考え方)
- [2. ケースの 4 つの型](#2-ケースの-4-つの型)
- [3. grader の決まり](#3-grader-の決まり)
- [4. 回し方（費用と段）](#4-回し方費用と段)
- [5. 落ちたときの分け方](#5-落ちたときの分け方)
- [6. 守らせ方（頼むのでなく止める）](#6-守らせ方頼むのでなく止める)
- [7. kanna を作って分かったこと](#7-kanna-を作って分かったこと)
- [8. 出典](#8-出典)

## 1. 考え方

1. **eval を先に置く**。スキルを書く前か、直す前に、何ができれば合格かをケースにする（公式の指針の「評価から作る」）。
2. **流さずに分かることは、流す前に落とす**。eval は 1 回ごとに利用料がかかる。読み込めないケース・必ず誤る grader は `harness_lint.py` で先に落とす（`scripts/check.sh` と CI が流す）。
3. **1 回の点で判断しない**。点はぶれる。台帳（`evals/ledger.jsonl`）に回ごとの要約を残し、同じモデルの前の回とケースごとに比べる。
4. **安いモデルから**。haiku で通ってから、締めの 1 回だけ sonnet。opus・fable は人が頼んだときだけ。
5. **grader を甘くして通さない**。落ちたら、まず「流し方・採点・プラグイン」に分ける（[5](#5-落ちたときの分け方)）。

## 2. ケースの 4 つの型

スキル 1 つにつき、少なくとも次の 3 つと、約束ごとの safety を置く（`harness_lint` の QG01〜QG04）。

| 型 | tags | 確かめること | 中心の grader |
| --- | --- | --- | --- |
| 呼ばれる | `trigger` | ふつうの言い方の依頼で、スキルが呼ばれる | `tool_used: Skill`（min 1） |
| 似ているが呼ばれない | `trigger` | 隣のスキルの仕事・同じ語を含む別の頼みで、呼ばれない | `tool_used: Skill`（max 0・`arm: both`） |
| 結果 | `outcome` | 約束した形のファイル・見出し・ID が出る | `file_exists`・ファイルの `regex`・1 条件の `llm` |
| してはいけないこと | `safety` | 直さない・流さない・確かめてから、を破らない | `tool_used` の max 0・`file_exists` の exists: false |

- 「呼ばれない」に**無関係な依頼（「背景色を変えて」）を使わない**。呼ばれないのが当たり前で、何も測らない。
- 呼ばれるケースの依頼文に、スキル名と、作業フォルダに無いファイルを書かない。
- Bash・Write・Edit などを使う・使わないケースには `needs-bash`・`needs-write` を付ける（ケースからは許せず、流すときの `--allow-tools` で許すため）。
- 入力が要るなら scaffold で作る。空でない作業フォルダでは何もせずに落ちるように書く。

## 3. grader の決まり

1. **決まった答えの grader を先に**。`llm` はケースに 1〜2 件、**1 条件ずつ**。「(1)〜(4) のどれか 1 つでも欠ければ不合格」は分ける（どれが落ちたか分からず、判定も揺れる）。
2. **ファイルの中身で見る**。長い出力や、ファイルに書くこともある答えは `target: {source: file, path}`（regex）・`focus:`（llm）か `target: trace` で見る。最後の返事だけを見ると、要約やファイル書き出しで語が消える。
3. **「してはいけない」は範囲を絞る**。Write・Edit の `input_match` は `'"file_path":\s*"[^"]*<場所>/'` の形にする（`'<場所>/'` だけだと、書いた中身に場所の名前があるだけで当たる）。
4. **`tool_used: Skill` は ablation で点に入らない**（スキルが呼ばれたかの印として出る）。「呼ばない」を点に入れるなら `arm: both`。
5. grader ごとに「通ってしまう誤った答え」と「落ちてしまう正しい答え」を、具体的な返事で考えてから書く（kanna-eval-reviewer がこれを見る）。

## 4. 回し方（費用と段）

kanna-eval-run の手順。命令には必ず `--model` と `--max-cost-usd` を付ける（kanna のフックが、無い命令を止める）。

| 段 | 流す物 | 要の引数 |
| --- | --- | --- |
| 0 | 1 件で採点を確かめる | `--case <1 件> --runs 1 --ablation none` |
| 1 | 呼ばれる・呼ばれない | `--tag trigger --runs 3 --ablation none` |
| 2 | 結果と約束 | `--tag outcome --tag safety --runs 3` |
| 3 | 全部を haiku で | `--runs 3` |
| 4 | 締め：全部を sonnet で | `--model sonnet --runs 1〜3` |

```bash
claude plugin eval <フォルダ> --model haiku --judge-model haiku --runs 3 --max-cost-usd 1 \
  --scaffold --allow-tools Bash Write Edit --trust-plugin --no-publish \
  --json .kanna/runs/<日時>/result.json --output-dir .kanna/runs/<日時>
python3 plugins/kanna/scripts/eval_ledger.py record .kanna/runs/<日時>/result.json \
  --ledger <フォルダ>/evals/ledger.jsonl --note "R<N>: <何を変えた後の回か>"
```

- Bash を許すと、手元にサンドボックスが要る（Linux は `bubblewrap` と `socat`）。無いと**全部の回が走らずに終わる**。
- 結果の JSON と報告はプラグインの外（`.kanna/`、コミットしない）。台帳だけをコミットする。
- eval は CI で流さない（利用料がかかる）。CI は `check.sh`（形・harness_lint・テスト）だけ。

## 5. 落ちたときの分け方

grader の説明（explanation）と、`--keep-temp` で残した trace を読み、次の順に当てる。

| 分け | 見分け方 | 直す物 |
| --- | --- | --- |
| 流し方 | `error` がある（max_turns・timeout・サンドボックス・scaffold） | 命令かケースの上限。**この回の点は信じない**（「呼ばない」grader は走らなくても通る） |
| 入力 | 依頼文が無いファイルを指す・入力が足りず、モデルが探し回る | ケースの依頼文か scaffold |
| 採点 | 答えは約束どおりなのに grader が落とした | grader（人が決める。直したら、前に通した正しい答えも通るか確かめる） |
| プラグイン | 約束どおりでない | スキルの description か本文を 1 か所（kanna-tune） |

## 6. 守らせ方（頼むのでなく止める）

- 本文の「書かない」「流さない」は頼みであって、守らせる仕組みではない（公式：サブエージェントを安全の仕組みに使わない）。
- 読むだけで足りる役は `tools: Read, Grep, Glob`。書かせる役には、PreToolUse のフックで `agent_type` を見て書ける場所を絞る（`plugins/kanna/hooks/kanna-guard.mjs`）。
- プラグインのエージェントでは `hooks`・`mcpServers`・`permissionMode` が無視される。フックは `hooks/hooks.json` に書く。
- 利用料を使う命令（`claude plugin eval`）は、フックで上限とモデルを確かめる。

## 7. kanna を作って分かったこと

kanna 自身の eval（11 件）を、上の手順で回した記録（`plugins/kanna/evals/ledger.jsonl`）。

| 回 | モデル | 合格 | 全体 | 費用 | 変えたこと |
| --- | --- | --- | --- | --- | --- |
| R1 | haiku・1 回 | 5/11 | 0.66 | $0.17 | 最初の回 |
| R2 | haiku・3 回 | 9/11 | 0.98 | $0.84 | スキルに「作業フォルダからの相対で探す」・tune に「流し方 → 採点 → プラグインで分けてから直す」・grader 3 件の範囲・依頼文から無いパスを消す |
| R3 | haiku・3 回 | 11/11 | 1.00 | $0.67 | 書く場所の grader を `file_path` に・CI の依頼文に YAML を入れる |
| R3 締め | sonnet・1 回 | 11/11 | 1.00 | $1.21 | なし |
| R4 | haiku・3 回・ablation | 9/11 | 0.96（差 +0.66） | $1.11 | なし（プラグイン無しとの差を測った） |
| R5 | haiku・5 回（eval-design だけ） | 2/2 | 1.00 | $0.08 | eval-design の description に「探す前に使う」・near-miss の grader の言い方の揺れ |

落ちた理由の内訳（R1 の前の試しの回と、R1〜R2 で落ちた 9 件）：**採点 4・入力 3・プラグイン 2**。落ちた半分近くは grader の誤りで、スキルを直しても上がらなかった。grader を疑う手順（[5](#5-落ちたときの分け方)）を先に置くのはこのため。

- サンドボックスが無いまま Bash を許した最初の回は、全部の回が走らず、それでも「呼ばない」grader が通って 0.2〜0.5 の点が出た。走れなかった回の点は信じない。
- 「Edit を呼ばない」は、自分の報告の手直しまで落とした。守る場所を `file_path` で絞る。
- 必須の外れのある見本で「流し方を見せて問う」を求めたケースは、スキルが正しく止まったのに落ちた。ケースの前提が、スキルの約束と食い違っていないかを先に見る。
- haiku は、引数の相対パスを、スキルの置き場からの相対と取り違えた。手順の 1 行目に「作業フォルダからの相対」と書くと直った。
- **同じ版でも、呼ばれる率は時によって大きく動く**（R6、takumi の kyoui-fires：5/5・3/10・1/5）。直しが効いたかは、直す前の版（対照）を同じ命令で続けて流して比べ、呼ばれる率は 10 回以上で見る。台帳の比べは p の値（Fisher の正確検定）を付け、0.1 より小さいときだけ「確か」とする。
- description を「何をするか」から書き出し、資料のパスまで細かく書くと、haiku は「スキルを呼ばずに自分でできる」と読み、自分で同じ手順を始めた。「いつ使うか」から書き出し「必ずこのスキルを使う」と書くと 15/15 になり、隣のスキルの依頼で呼ばれすぎることも無かった。
- `--case` は 1 つの型だけ（2 回書くと後の方だけ、`'{a,b}'` は 0 件）。いくつかを選ぶときは `--tag`。
- 「呼ばれない」ケースは、プラグイン無しでも同じ点が正しい。台帳の「効いていない」から外す。
- **落ちたら、スキルより先にケースの入力を疑う**（R8、takumi の ninka-check-fires）。コードを依頼文に貼ると、haiku はその場で読んで答え、スキルを呼ばない（4/10）。description を直しても 6/10 で確かとは言えなかった。リポジトリにコードを置く本物に近い形にすると、直す前の版でも 10/10 だった。
- 見本の秘密を本物の鍵の形に似せると、GitHub の push protection にコミットごと止められる。形を変えたら、`not_contains` の grader の pattern も直す（直し忘れると、何もしなくても必ず通る）。
- 同じ落ち方（資料を探し、見つからずに自分で答える）が、takumi の kyoui と toryo の kousei の 2 つで出た。どちらも「いつ使うか」から書き出し「必ず使う」「資料が無くても使える」と書いて 10/10 になった（toryo は 11/20 → 10/10、p=0.01）。

## 8. 出典

- プラグインの eval：https://code.claude.com/docs/en/plugin-evals.md ・ `claude plugin eval --help`（Claude Code 2.1.332）
- スキル：https://code.claude.com/docs/en/skills.md ・ https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- サブエージェント：https://code.claude.com/docs/en/sub-agents.md 　フック：https://code.claude.com/docs/en/hooks.md
- nok の先の例：pipe-in の `docs/decisions/D0045-plugin-evals.md`（ケースからは Bash・Write・Edit を許せず、`needs-*` の tags と `--allow-tools` で許す）
