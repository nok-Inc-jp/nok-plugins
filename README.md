# nok-plugins

株式会社ノックの Claude Code プラグイン置き場（マーケットプレイス）です。非公開。

## 使い方

```
/plugin marketplace add nok-Inc-jp/nok-plugins
/plugin install kanna@nok-plugins
/plugin install konomi@nok-plugins
/plugin install pipe-in@nok-plugins
/plugin install ranbiki@nok-plugins
/plugin install fude@nok-plugins
/plugin install fushin@nok-plugins
/plugin install toryo@nok-plugins
/plugin install takumi@nok-plugins
```

非公開のリポジトリなので、GitHub に入れる状態（`gh auth login` など）で実行してください。

## 入っているプラグイン

| 名前 | 中身 | 場所 |
| --- | --- | --- |
| kanna | プラグインのハーネス（スキル・エージェント・フック・eval）を点検し、足りない eval を設計し、費用に上限を置いて haiku から回し、台帳で前の回と比べる | このリポジトリの `plugins/kanna/` |
| konomi | 好みに沿った良いフロントエンドを、要件からテストまで一貫して作る知識型スキル | 別のリポジトリ（`nok-Inc-jp/nok-konomi` の `plugin/`） |
| pipe-in | pipe-in のパイプを会話で作る・直す・流す。成果物の検査と審査 | 別のリポジトリ（`nok-Inc-jp/nok-pipe-in` の `plugin/`） |
| ranbiki | 上位モデルの解き方をスキル1枚に蒸留して下位モデルに移し、プラセボ対照つきで効果を測る | 別のリポジトリ（`nok-Inc-jp/nok-ranbiki` の `plugin/`） |
| fude | 1本の原稿をノックのサイト・Zenn・Qiita・note の形式に書き出し、公開前に文体と非公開情報の漏れを点検する | 別のリポジトリ（`nok-Inc-jp/nok-fude` の `plugin/`） |
| fushin | 中小企業向けの業務アプリで何を作るかを決め、業務要件シートにまとめる | 別のリポジトリ（`nok-Inc-jp/nok-fushin` の `plugin/`） |
| toryo | 業務要件シートから、業務アプリをどう組むか（形・構成・認証・バックアップ・運用）を決める | 別のリポジトリ（`nok-Inc-jp/nok-toryo` の `plugin/`） |
| takumi | 業務アプリが守れているかを確かめて報告する（直さない） | 別のリポジトリ（`nok-Inc-jp/nok-takumi` の `plugin/`） |

## フォルダの決まり

| 場所 | 中身 | 配られるか |
| --- | --- | --- |
| `.claude-plugin/marketplace.json` | プラグインの一覧 | 一覧として読まれる |
| `plugins/<名前>/` | ここに置くプラグインの本体。1 フォルダ 1 プラグイン（今は kanna だけ。ほかは別のリポジトリにある） | 配られる（このフォルダだけ） |
| `docs/` | 決まりの文書（`eval-engineering.md`：eval の作法）と、プラグインの点検の記録（`harness-review.md`） | 配られない |
| `templates/plugin/` | 新しいプラグインの雛形（公式ディレクトリの基準を通る形） | 配られない |
| `templates/parts/` | 要るときだけ足す部品（エージェント・フック・MCP） | 配られない |
| `templates/repo/` | プラグインを置くリポジトリの部品（CI・`check.sh`・PR のテンプレート） | 配られない |
| `scripts/` | このリポジトリの確かめ（`check.sh`）と、雛形との差を見る道具（`plugin_drift.py`） | 配られない |
| `tests/` | 道具のテスト | 配られない |

**プラグインに製品のコードを入れない**。試作や振り返りの資料が増えるプラグインは、別のリポジトリに分ける（konomi の試作は `nok-Inc-jp/nok-konomi` の `lab/`）。

## プラグインを足す手順

1. `templates/plugin/` を `plugins/<名前>/` に写し、`【雛形】` の印をすべて書き換える（くわしくは `templates/README.md` の「新しいプラグインを作る」）。名前は半角小文字とハイフン。`claude-` `anthropic-` で始めない。
2. `.claude-plugin/marketplace.json` の `plugins` に 1 件足す（`name`・`source: "./plugins/<名前>"`・`description`・`category`）。
3. `scripts/check.sh` を引数なしで通す（一覧の形・公式ディレクトリの基準・雛形との差・ハーネスの作り）。
4. `/kanna:kanna-audit plugins/<名前>` で点検し、`/kanna:kanna-eval-run` で eval を haiku から回して、台帳（`evals/ledger.jsonl`）に残す（作法は `docs/eval-engineering.md`）。
5. 版を上げるときは `plugin.json` の `version` を変え、`CHANGELOG.md` に書く（変えない限り、入れた人は古い版のまま）。

## ハーネスの作りを見る（kanna）

`plugins/kanna/` は、プラグインのハーネスを見直すためのプラグインで、このリポジトリで作る物の土台でもある。

| 道具 | 何を見るか | 利用料 |
| --- | --- | --- |
| `plugins/kanna/scripts/harness_lint.py` | スキル・エージェント・フック・eval の作りの決まり 31 件（呼ばれない場面のケースがあるか、grader が壊れていないか、書ける役をフックで絞っているか、など） | なし（`check.sh` と CI が流す） |
| `/kanna:kanna-audit` | 上の検査に、読む役のエージェント 2 つの見立てを足した報告 | 少し |
| `/kanna:kanna-eval-design` → `kanna-eval-run` → `kanna-tune` | eval を足す → haiku から回して台帳で比べる → 落ちた所を直すラウンド | かかる（流す前に必ず確かめる。フックが上限の無い命令を止める） |

```
python3 plugins/kanna/scripts/harness_lint.py <プラグインのフォルダ> [...]   # --strict で推奨の外れも落とす・--json・--rules
```

別のリポジトリのプラグインには、`templates/repo/scripts/harness_lint.py`（kanna の写し）を写すと、その `check.sh` が流す。全部のプラグインを点検した記録は `docs/harness-review.md`。

## 雛形との差を見る

`scripts/plugin_drift.py` は、プラグインが雛形の決まり（`templates/README.md` の「雛形の決まり」）からどれだけ外れているかを、決まりごとに出典つきで出します。標準ライブラリだけで動きます。公式の検査（`claude plugin validate --strict --profile directory`）も中で流し、`claude` が無ければ「未実行」として落とします。

```
python3 scripts/plugin_drift.py <プラグインのフォルダ> [...]     # 1 つずつ
python3 scripts/plugin_drift.py --marketplace .claude-plugin/marketplace.json --workspace ..   # 一覧の全部
```

`--marketplace` では、別のリポジトリにあるプラグインを `--workspace` の下の、同じ名前のフォルダ（`../konomi/plugin` など）で探します。手元に無いプラグインは「未実行」と出ます。`--json` で結果を JSON で、`--all` で合格した決まりも、`--strict` で推奨の外れでも落とします。終わりの値は、必須の外れも未実行も無ければ 0、あれば 1 です。

別のリポジトリにあるプラグイン（konomi・pipe-in・ranbiki・fude）は、`source` を別のリポジトリに向けて一覧に足せます。足す前に、向けた先に `.claude-plugin/plugin.json` があることを確かめてください。

- リポジトリの直下にあるとき：`{ "source": "github", "repo": "<持ち主>/<名前>" }`
- 下のフォルダにあるとき（konomi・pipe-in・ranbiki・fude はどれも `plugin/`）：`{ "source": "git-subdir", "url": "https://github.com/<持ち主>/<名前>.git", "path": "<フォルダ>" }`

版は、向けた先の `plugin/.claude-plugin/plugin.json` の `version` で決まります（ここでは書きません）。プラグインごとの確かめも、それぞれのリポジトリでします（`templates/repo/` を写すと、CI が公式ディレクトリの基準で確かめます）。

pipe-in は、スキルのほかに `pipe-in-gen` コマンドも要ります（入れ方は pipe-in の `docs/guide/plugin.md`）。
