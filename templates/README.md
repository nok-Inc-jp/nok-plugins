# プラグインの雛形

nok のプラグインの土台。公式の文書と、公式ディレクトリの検査（`claude plugin validate --strict --profile directory`）に合わせてある（2026-11-20、Claude Code 2.1.329 で確かめた）。雛形との差は `scripts/plugin_drift.py` で見る。

| 場所 | 中身 | 使い方 |
| --- | --- | --- |
| `plugin/` | プラグインの本体の雛形（plugin.json・README・CHANGELOG・LICENSE・アイコン・スキル 1 つ・eval 3 件） | そのまま写して、`【雛形】` の印をすべて書き換える |
| `parts/` | 要るときだけ足す部品（エージェント・フック・MCP） | 写したプラグインの同じ場所に足す |
| `repo/` | プラグインを置くリポジトリの部品（CI・`scripts/check.sh`・PR のテンプレート） | リポジトリの直下に写す |
| `project/` | 一般のリポジトリ（プラグインではない物）の雛形 | `scripts/new_project.py` で写す（`project/README.md`） |

## 新しいプラグインを作る

1. `plugin/` を写す（`cp -r templates/plugin <置き場所>`）。リポジトリを分けるなら、`repo/` もそのリポジトリの直下に写し、`scripts/check.sh` の `PLUGIN=` をプラグインのフォルダに合わせる。
2. `plugin.json` の `name`（小文字・数字・ハイフン。`claude-` `anthropic-` で始めない）・`displayName`・`description`・`homepage`・`repository`・`supportUrl`・`keywords` を書く。`plugin-name` をすべて本当の名前に変える。
3. `.claude-plugin/icon.png` を本物に替える（正方形の PNG か JPEG。一辺 512〜2048 px、2 MB 未満。SVG と WebP は使えない）。公式ディレクトリの一覧のアイコンになるのは、最初に保存か申請をしたときの 1 回だけで、あとで替えても変わらない。
4. `skills/example/` を本物のスキルにする（フォルダ名と `name` を合わせる）。eval の 3 件（呼ばれる・呼ばれない・結果の形）も、そのスキルに合わせて書く。
5. `python3 <nok-plugins>/scripts/plugin_drift.py <プラグインのフォルダ>` で、必須の外れと未実行が 0 になるまで直す。

## 部品（parts/）

| 部品 | 足す場所 | 書くときの決まり |
| --- | --- | --- |
| `agents/example-reviewer.md` | `agents/` | `tools` で道具を絞る。プラグインのエージェントでは `hooks`・`mcpServers`・`permissionMode` が無視されるので書かない |
| `hooks/hooks.json`・`hooks/example-gate.mjs` | `hooks/` | `command` と `args` に分ける形（シェルを通さない）で、プラグインの中のファイルは `${CLAUDE_PLUGIN_ROOT}` で指す。`timeout` を書く（書かないと 600 秒）。外の依存を使わない |
| `.mcp.json` | プラグインの直下 | `npx` と `uvx` は版を固定する。リモートは https。鍵は `userConfig` の `sensitive: true` で受け取り、`${user_config.<キー>}` で渡す |

MCP の鍵を受け取るときは、`plugin.json` に次を足す。リモートの MCP や HTTP のフックを使うなら、`privacyPolicyUrl` も足す（公式ディレクトリが求める）。外へつなぐホストは、README の「動かすもの・送るもの」に書く。

```json
"userConfig": {
  "example_api_key": {
    "type": "string",
    "title": "Example の API キー",
    "description": "example-local の MCP サーバーが使う鍵",
    "sensitive": true,
    "required": false
  }
}
```

## 版を上げる

- `version` を書いている限り、上げないと入れた人に更新が届かない（`claude plugin update` が「最新です」と返す）。入れた人に届けたい変更では必ず上げ、`CHANGELOG.md` に書く。
- `claude plugin tag --push` で `<名前>--v<版>` の印（タグ）を付けられる。

## 雛形の決まり

`scripts/plugin_drift.py` が見る決まりの一覧。必須が 1 つでも外れるか、検査が未実行なら落ちる（`--strict` を付けると、推奨の外れでも落ちる）。出典が「nok」の物は、公式の決まりではなく nok で決めた物。

| ID | 重さ | 中身 | 出典 |
| --- | --- | --- | --- |
| V01 | 必須 | 公式の検査（claude plugin validate --strict --profile directory）を通る | [公式](https://code.claude.com/docs/en/plugins/cli-reference.md#plugin-validate) |
| M01 | 必須 | .claude-plugin/plugin.json があり、JSON として読める | [公式](https://code.claude.com/docs/en/plugins/manifest-reference.md) |
| M02 | 必須 | name が小文字・数字・ハイフンで 64 字まで、予約語で始まらない | [公式](https://claude.com/docs/plugins/pre-submission-checklist) |
| M03 | 必須 | version が semver（x.y.z）で書いてある | [公式](https://code.claude.com/docs/en/plugins/publish.md) |
| M04 | 必須 | description がある | [公式](https://code.claude.com/docs/en/plugins/manifest-reference.md) |
| M05 | 必須 | author.name がある | [公式](https://code.claude.com/docs/en/plugins/manifest-reference.md) |
| M06 | 推奨 | homepage と repository がある | [公式](https://code.claude.com/docs/en/plugins/manifest-reference.md) |
| M07 | 必須 | license がある（または LICENSE ファイル） | [公式](https://claude.com/docs/plugins/pre-submission-checklist) |
| M08 | 推奨 | keywords がある | [公式](https://code.claude.com/docs/en/plugins/manifest-reference.md) |
| M09 | 推奨 | $schema が公式の雛形（claude plugin init）と同じ URL | nok |
| M10 | 推奨 | supportUrl がある | [公式](https://code.claude.com/docs/en/plugins/manifest-reference.md) |
| M11 | 必須 | コンポーネントのパスが ./ で始まり、.. を含まない | [公式](https://code.claude.com/docs/en/plugins/manifest-reference.md) |
| F01 | 必須 | README.md がある（プラグインのフォルダか、リポジトリの直下） | [公式](https://claude.com/docs/plugins/pre-submission-checklist) |
| F02 | 推奨 | README に入れ方（/plugin install）が書いてある | [公式](https://code.claude.com/docs/en/plugins/cli-reference.md#plugin-validate) |
| F03 | 推奨 | README に、手元で動かす物・外へ送る物の節がある | [公式](https://claude.com/docs/plugins/pre-submission-checklist) |
| F04 | 推奨 | LICENSE ファイルがある | [公式](https://claude.com/docs/plugins/pre-submission-checklist) |
| F05 | 推奨 | CHANGELOG.md に、今の版の見出しがある | nok |
| F06 | 推奨 | アイコン（.claude-plugin/icon.png など）がある | [公式](https://claude.com/docs/plugins/pre-submission-checklist) |
| F07 | 必須 | アイコンが雛形の仮の物のままでない | nok |
| F08 | 必須 | 雛形の印（【雛形】）と仮の名前（plugin-name）が残っていない | nok |
| F09 | 推奨 | プラグインの直下に CLAUDE.md と bin/ を置かない（読まれない・claude.ai で入れられない） | [公式](https://code.claude.com/docs/en/plugins/manifest-reference.md) |
| F10 | 必須 | 要らないファイル（.DS_Store・Thumbs.db・__MACOSX）とシンボリックリンクが無い | [公式](https://claude.com/docs/plugins/pre-submission-checklist) |
| F11 | 推奨 | 256 KiB を超えるファイルが無い | [公式](https://claude.com/docs/plugins/pre-submission-checklist) |
| F12 | 推奨 | プラグインのフォルダの中に README.md がある（入れた人の手元に届くのはフォルダの中だけ） | [公式](https://code.claude.com/docs/en/plugins/loading.md) |
| S01 | 必須 | スキルの frontmatter が読め、description がある | [公式](https://code.claude.com/docs/en/skills.md) |
| S02 | 推奨 | スキルの name がフォルダ名と同じ | [公式](https://code.claude.com/docs/en/skills.md) |
| S03 | 必須 | スキルの name が小文字・数字・ハイフンで 64 字まで、claude・anthropic を含まない | [公式](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) |
| S04 | 必須 | スキルの description が 1,024 字まで | [公式](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) |
| S05 | 必須 | SKILL.md が 500 行未満 | [公式](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) |
| S06 | 必須 | SKILL.md からリンクした補助ファイルがある | [公式](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) |
| S07 | 推奨 | 100 行を超える補助ファイルの先頭に目次がある | [公式](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) |
| S08 | 推奨 | パスにバックスラッシュを使わない | [公式](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) |
| A01 | 必須 | エージェントに name と description がある | [公式](https://code.claude.com/docs/en/sub-agents.md) |
| A02 | 推奨 | エージェントの tools を絞っている（書かないと全部の道具を使える） | [公式](https://code.claude.com/docs/en/sub-agents.md) |
| A03 | 推奨 | プラグインでは無視される項目（hooks・mcpServers・permissionMode）を書かない | [公式](https://code.claude.com/docs/en/sub-agents.md) |
| H01 | 必須 | hooks.json が JSON で、最上位に hooks がある | [公式](https://code.claude.com/docs/en/hooks.md) |
| H02 | 必須 | フックがプラグインの中のファイルを ${CLAUDE_PLUGIN_ROOT} で指す | [公式](https://code.claude.com/docs/en/hooks.md) |
| H03 | 推奨 | フックに timeout を書いている | [公式](https://code.claude.com/docs/en/hooks.md) |
| H04 | 推奨 | シェルの形で ${CLAUDE_PLUGIN_ROOT} を使うときは二重引用符で囲む（または args を使う） | [公式](https://code.claude.com/docs/en/hooks.md) |
| P01 | 必須 | MCP の npx・uvx は版を固定している | [公式](https://claude.com/docs/plugins/pre-submission-checklist) |
| P02 | 必須 | リモートの MCP は https | [公式](https://claude.com/docs/plugins/pre-submission-checklist) |
| E01 | 推奨 | eval のケースが 3 件以上ある | [公式](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) |
| E02 | 必須 | eval の各ケースに prompt.md と graders/ の 1 件以上がある | [公式](https://code.claude.com/docs/en/plugin-evals.md) |
| R01 | 推奨 | リポジトリの CI が claude plugin validate を流す | [公式](https://code.claude.com/docs/en/plugins/cli-reference.md#plugin-validate) |
| R02 | 推奨 | リポジトリの検査が --strict で流れる | [公式](https://code.claude.com/docs/en/plugins/cli-reference.md#plugin-validate) |
| R03 | 推奨 | リポジトリに PR のテンプレートがある | nok |
| R04 | 推奨 | リポジトリに tests/ がある | nok |
| K01 | 必須 | 一覧（marketplace.json）の name と plugin.json の name が同じ | [公式](https://code.claude.com/docs/en/plugins/marketplace-reference.md) |
| K02 | 推奨 | 一覧の項目に description と category がある | [公式](https://code.claude.com/docs/en/plugins/marketplace-reference.md) |

### 決まりの補足

- `$schema` の URL（M09）は、公式の CLI（`claude plugin init`）が書く物に合わせた。2026-11-20 時点でこの URL を開くと 404 なので、エディタの補完は効かない。読み込むときは無視される。
- `network.hosts`（外へつなぐホストの宣言）と `engines`（対応する Claude Code の版）は、雛形に入れていない。古い版の Claude Code は知らない項目として受け付けない（`engines` は 2.1.323 以降、`network` は 2.1.328 以降）。入れた人の版がそろったら足す。
- eval（`claude plugin eval`）は利用料がかかるので、`check.sh` でも CI でも流さない。人が決めたときに、下位のモデル（`--model haiku`）から流す。
- 公式のスキルの指針は、Haiku・Sonnet・Opus のそれぞれで試すことを勧めている。

### 調べた出典

- プラグインの定義：https://code.claude.com/docs/en/plugins/manifest-reference.md ・ https://code.claude.com/docs/en/plugins/components.md
- 配り方と版：https://code.claude.com/docs/en/plugins/publish.md ・ https://code.claude.com/docs/en/plugins/loading.md ・ https://code.claude.com/docs/en/plugins/marketplace-reference.md
- 公式ディレクトリに出す前の点検表：https://claude.com/docs/plugins/pre-submission-checklist
- スキル：https://code.claude.com/docs/en/skills.md ・ https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- エージェント：https://code.claude.com/docs/en/sub-agents.md 　フック：https://code.claude.com/docs/en/hooks.md
- 検査と eval：https://code.claude.com/docs/en/plugins/cli-reference.md#plugin-validate ・ https://code.claude.com/docs/en/plugin-evals.md
- 公式のプラグインの実物：https://github.com/anthropics/claude-plugins-official （43 件すべてに LICENSE、41 件に README があり、スキルは `references/`・`examples/`・`scripts/` に分けている）
- 手元の Claude Code 2.1.329 の `claude plugin init`（公式の雛形）・`claude plugin validate --help`・`claude plugin eval --help`
