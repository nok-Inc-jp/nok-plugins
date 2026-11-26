# harness_lint の決まり

`scripts/harness_lint.py` が見る決まりと、決まりごとの直し方。表は `harness_lint.py` の `RULES` と同じ物を保つ（nok-plugins の tests が突き合わせる）。出典が「nok」の物は、公式の決まりではなく nok で決めた物。

## 目次

- [決まりの一覧](#決まりの一覧)
- [直し方：スキル](#直し方スキル)
- [直し方：エージェントとフック](#直し方エージェントとフック)
- [直し方：eval のケース](#直し方eval-のケース)
- [直し方：eval の全体](#直し方eval-の全体)
- [検査では分からないこと](#検査では分からないこと)

## 決まりの一覧

必須が外れると、eval が読み込めないか、採点が必ず誤る。推奨が外れると、測れていない・守らせていない所が残る。

| ID | 重さ | 中身 | 出典 |
| --- | --- | --- | --- |
| QS01 | 推奨 | スキルの description に「いつ使うか」が書いてある | [公式](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) |
| QS02 | 推奨 | スキルの frontmatter に、Claude Code が知らない項目が無い（書き誤りは黙って無視される） | [公式](https://code.claude.com/docs/en/skills.md) |
| QS03 | 推奨 | 補助ファイルから、さらに別の補助ファイルへリンクしない（1 段だけ） | [公式](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) |
| QS04 | 推奨 | スクリプトを ${CLAUDE_PLUGIN_ROOT} か ${CLAUDE_SKILL_DIR} で指す（作業フォルダからの相対で指さない） | [公式](https://code.claude.com/docs/en/skills.md) |
| QS05 | 推奨 | スキルの名前があいまい（helper・utils など）でない | [公式](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) |
| QA01 | 推奨 | エージェントの frontmatter に、知らない項目が無い | [公式](https://code.claude.com/docs/en/sub-agents.md) |
| QA02 | 推奨 | エージェントの description に「いつ任せるか」が書いてある | [公式](https://code.claude.com/docs/en/sub-agents.md) |
| QA03 | 推奨 | エージェントの本文に、返す形（見出し・表・JSON など）が決めてある | nok |
| QA04 | 推奨 | 書ける道具（Write・Edit・Bash）を持つエージェントがあるなら、PreToolUse のフックで書ける範囲を絞っている | [公式](https://code.claude.com/docs/en/sub-agents.md) |
| QH01 | 推奨 | Stop・SubagentStop のフックが stop_hook_active を見て、止め続けない | [公式](https://code.claude.com/docs/en/hooks.md) |
| QH02 | 推奨 | フックが指すスクリプトがプラグインの中にある | [公式](https://code.claude.com/docs/en/hooks.md) |
| QE01 | 必須 | eval の prompt.md・case.yaml に、知らない項目が無い（あると読み込みで落ちる） | [公式](https://code.claude.com/docs/en/plugin-evals.md) |
| QE02 | 必須 | grader の type が 6 種のどれかで、要る項目がそろっている | [公式](https://code.claude.com/docs/en/plugin-evals.md) |
| QE03 | 必須 | regex の grader の pattern が読める（(?i) のような書き方を使わず flags を使う） | [公式](https://code.claude.com/docs/en/plugin-evals.md) |
| QE04 | 推奨 | ケースに expected_outcome がある（何を確かめるケースかを人が読める） | [公式](https://code.claude.com/docs/en/plugin-evals.md) |
| QE05 | 推奨 | llm の grader は 1 つの条件だけを見る（条件を並べるなら grader を分ける） | [公式](https://code.claude.com/docs/en/plugin-evals.md) |
| QE06 | 推奨 | 結果を見るケースに、決まった答えの grader（regex・tool_used・file_exists など）が 1 件以上ある | [公式](https://code.claude.com/docs/en/plugin-evals.md) |
| QE07 | 推奨 | 「スキルを呼ばない」grader を他の grader と並べるときは arm: both にする（ablation で採点から外れるため） | [公式](https://code.claude.com/docs/en/plugin-evals.md) |
| QE08 | 必須 | tool_used: Skill の input_match が、このプラグインのスキル名に当たる | [公式](https://code.claude.com/docs/en/plugin-evals.md) |
| QE09 | 推奨 | min 1 以上で求める、許しの要る道具（Bash・Write・Edit・Web・MCP）を、tags の needs-* で示している（流すときの --allow-tools に要る） | [公式](https://code.claude.com/docs/en/plugin-evals.md) |
| QE10 | 必須 | case.yaml の scaffold_script と、baseline の baseline_file が、ケースのフォルダにある | [公式](https://code.claude.com/docs/en/plugin-evals.md) |
| QE11 | 推奨 | ケースの name がフォルダ名と同じ | [公式](https://code.claude.com/docs/en/plugin-evals.md) |
| QE12 | 推奨 | ケースの tags に、種類（trigger・outcome・safety のどれか）がある | nok |
| QE14 | 推奨 | 「含まない」（match: not_contains）の regex の pattern が、scaffold で置いた入力か依頼文に当たる（当たらないと何もしなくても通る。--probe-scaffold のときだけ見る） | nok |
| QE13 | 推奨 | Write・Edit を場所で絞る tool_used の input_match は "file_path" に当てる（書いた中身にも当たるため） | [公式](https://code.claude.com/docs/en/plugin-evals.md) |
| QG01 | 推奨 | モデルが呼べるスキルごとに、呼ばれるべき依頼で呼ばれることを確かめるケースがある | [公式](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) |
| QG02 | 推奨 | モデルが呼べるスキルごとに、似ているが呼ぶべきでない依頼で呼ばれないことを確かめるケースがある | [公式](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) |
| QG03 | 推奨 | スキルごとに、結果を確かめるケースがある | [公式](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) |
| QG04 | 推奨 | 「してはいけないこと」を確かめるケース（書かない・流さない・作らない）が 1 件以上ある | nok |
| QG05 | 推奨 | eval のケースが 3 件以上ある | [公式](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) |

## 直し方：スキル

- **QS01**：description の終わりに「〜と言われたとき、または〜のときに使う」を足す。利用者が口にしそうな言い方を 2〜4 個入れる。何をするかと、いつ使うかの両方が無いと、モデルは呼ぶかどうかを決められない。
- **QS02**：知らない項目は黙って無視される。`allowed_tools`（下線）と `allowed-tools`（ハイフン）のような書き誤りを疑う。
- **QS03**：補助ファイル A から B へ飛ばさず、SKILL.md から A と B の両方へリンクする。2 段目は途中までしか読まれないことがある。
- **QS04**：`python3 scripts/x.py` は、入れた人の作業フォルダからの相対になって動かない。`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/x.py"` か `"${CLAUDE_SKILL_DIR}/scripts/x.py"` にする。リポジトリの開発用のスクリプト（プラグインの外にある物）を、スキルの本文から指さない。
- **QS05**：何をするかが分かる名前にする（`helper` でなく `invoice-check`）。

## 直し方：エージェントとフック

- **QA01**：プラグインのエージェントでは `hooks`・`mcpServers`・`permissionMode`・`initialPrompt` が無視される。知らない項目は書き誤りを疑う。
- **QA02**：description は、親が「いつ任せるか」を決めるために読む。「〜のときに使う」「〜から呼ばれる」を書く。
- **QA03**：親は返事を読んで次を決める。`## 返す形` に、見出し・表・JSON のどれで返すかを例つきで書く。
- **QA04**：本文の「書かない」は頼みであって、守らせる仕組みではない。書ける道具を持たせるなら、`hooks/hooks.json` の PreToolUse で `agent_type` を見て、書ける場所を絞る（kanna の `hooks/kanna-guard.mjs` が見本）。読むだけで足りる役なら `tools: Read, Grep, Glob` にする。
- **QH01**：Stop で止めた後、Claude が続けると、また Stop が来る。入力の `stop_hook_active` が true なら止めない。
- **QH02**：`${CLAUDE_PLUGIN_ROOT}/hooks/x.mjs` の先が、プラグインの中に本当にあるかを確かめる。

## 直し方：eval のケース

- **QE01**：prompt.md で使える項目は `schema_version`・`name`・`description`・`tags`・`plugins`・`runs`・`expected_outcome`・`model`・`max_turns`・`timeout_seconds`・`allowed_tools`・`disallowed_tools`・`append_system_prompt`・`env` だけ。それ以外があると、そのケースは読み込めない。
- **QE02**：type は `regex`・`tool_used`・`tool_order`・`file_exists`・`llm`・`baseline` の 6 つ。`arm` は `with-only` か `both`。
- **QE03**：pattern は JavaScript の正規表現。大文字小文字を無視するなら `flags: i`。`(?i)` は使えない。
- **QE04**：`expected_outcome` は流すときには使われないが、ケースが何を確かめるかを人が読む唯一の場所。1 文で書く。
- **QE05**：llm の判定役は 3 回のうち 2 回で合否を決める。条件を 4 つ並べると、どれが落ちたかが分からず、どれか 1 つの読み違いで全体が揺れる。条件ごとに grader を分け、それぞれに「何があれば合格・何があれば不合格」を書く。
- **QE06**：長い出力は、書かれたファイルを `target: {source: file, path: ...}` で regex にかける。llm は短い出力の、決まった条件にだけ使う。
- **QE07**：`tool_used: Skill` は、ablation（プラグイン無しの回と比べる）で採点から外れる。「呼ばない」ことを点に入れたいなら `arm: both` を書く。
- **QE08**：input_match はスキルを呼んだ入力の JSON にかかる。スキル名の打ち誤りがあると、「呼ぶ」ケースはいつも落ち、「呼ばない」ケースはいつも通る（何も測っていない）。
- **QE09**：Bash・Write・Edit などは、ケースの `allowed_tools` では許せず、流すときの `--allow-tools` で許す。要る道具を `tags` の `needs-bash`・`needs-write`・`needs-web`・`needs-mcp` で示し、kanna-eval-run はそれを見て `--allow-tools` を組む。
- **QE10**：`scaffold_script` は `--scaffold` を付けたときだけ流れる。ファイルが無いと、その回は 0 点になる。
- **QE11**：name とフォルダ名がずれると、`--case` で絞ったときに見つからない。
- **QE12**：`trigger`（呼ばれる・呼ばれない）・`outcome`（結果）・`safety`（してはいけないこと）のどれかを付ける。`--tag trigger` で安いケースだけ先に流せる。
- **QE14**：`--probe-scaffold` を付けたときだけ、scaffold を一時フォルダで流して見る。見本の値を変えて pattern を直し忘れると、「書き写さない」の grader は何もしなくても必ず通る（kanna の R8 で一度そうなった）。scaffold は作者の bash を流すので、自分たちのケースのときだけ付ける。
- **QE13**：input_match は道具の入力の JSON 全体にかかる。`'sample-plugin/'` だと、報告の本文に「sample-plugin/」と書いただけで当たる（kanna の R2 で、正しい答えが 1 回落ちた）。`'"file_path":\s*"[^"]*sample-plugin/'` のように、パスの項目に当てる。

## 直し方：eval の全体

- **QG01・QG02**：スキルごとに、呼ばれるべき依頼（言い方を変えて 1〜2 件）と、**似ているが呼ぶべきでない依頼**（1〜2 件）を置く。「背景色を変えて」のような無関係な依頼は、呼ばれないのが当たり前で、何も測らない。隣のスキルの依頼や、同じ語を含む別の頼みを使う。
- **QG03**：結果のケースでは、スキルが約束した形（ファイル・見出し・ID）を regex か file_exists で見て、中身の大事な 1 点を llm で見る。
- **QG04**：スキルやエージェントが「直さない」「流さない」「確かめてから」と約束しているなら、それを破らないことを `tool_used` の `max: 0` か `file_exists` の `exists: false` で確かめる。
- **QG05**：公式の指針は 3 件以上を勧めている。スキルが N 個なら、目安は 3N 件（呼ばれる・呼ばれない・結果）と、約束ごとの safety。

## 検査では分からないこと

次は読まないと分からないので、kanna-skill-reviewer と kanna-eval-reviewer に頼む。

- 呼ばれない依頼が、本当に「似ているが違う」依頼になっているか（近すぎず、遠すぎず）
- grader が、間違った答えでも通ってしまわないか・正しい答えでも落ちてしまわないか
- 結果のケースの入力（scaffold で作るファイル）が、スキルが本当に受け取る物に近いか
- スキルの本文に、モデルが既に知っている説明が多すぎないか・決めきれない所に既定が無いか
