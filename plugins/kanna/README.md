# kanna（鉋）

Claude Code のプラグインの**ハーネス**（スキル・エージェント・フック・eval）を削り出すプラグインです。プラグインを作る人が、出す前や版を上げる前に、作りを公式の指針と eval の作法で点検し、足りない eval を設計し、費用に上限を置いて下位のモデルから回し、前の回と比べられるようにします。

## 入れ方

会話の中で：

```
/plugin marketplace add nok-Inc-jp/nok-plugins
/plugin install kanna@nok-plugins
```

非公開のリポジトリから入れるときは、GitHub に入れる状態（`gh auth login` など）で実行する。

## 使い方

| 呼び方 | 何をするか |
| --- | --- |
| `/kanna:kanna-audit <フォルダ>` | ハーネスを点検し、直す順に並べた `kanna-report.md` を書く（直さない） |
| `/kanna:kanna-eval-design <フォルダ> <スキル>` | 足りない eval（呼ばれる・似ているが呼ばれない・結果・してはいけないこと）を設計し、了承を取って `evals/` に書く |
| `/kanna:kanna-eval-run <フォルダ>` | 流し方と費用の上限を見せて了承を取り、haiku から eval を回し、台帳で前の回と比べる |
| `/kanna:kanna-tune <フォルダ> [<ケース>]` | 落ちたケースを手がかりに、スキルを 1 回に 1 か所だけ直して流し直す（ラウンド） |

いちばんよくある流れ：

```
/kanna:kanna-audit ./plugin          # 何が測れていないかを知る
/kanna:kanna-eval-design ./plugin kyoui   # 足りないケースを足す
/kanna:kanna-eval-run ./plugin       # 安く回して、台帳に残す
/kanna:kanna-tune ./plugin           # 落ちた所を直して、もう一度
```

## 中身

| 種類 | 名前 | 役目 |
| --- | --- | --- |
| スキル | `kanna-audit` | 点検して報告を書く |
| スキル | `kanna-eval-design` | eval を設計して書かせる |
| スキル | `kanna-eval-run` | eval を回して台帳で比べる |
| スキル | `kanna-tune` | eval を先に置いて、スキルを直すラウンドを回す |
| エージェント | `kanna-skill-reviewer` | スキルとエージェントの文面を読む（読むだけ） |
| エージェント | `kanna-eval-reviewer` | eval の採点を意地悪く読む（読むだけ） |
| エージェント | `kanna-eval-writer` | `evals/` の中にだけケースを書く |
| フック | `hooks/kanna-guard.mjs` | eval を費用の上限なしで流させない・書ける場所を絞る |
| 道具 | `scripts/harness_lint.py` | ハーネスの決まり（31 件）を、流さずに点検する |
| 道具 | `scripts/eval_ledger.py` | eval の結果を台帳に残し、前の回と比べる |

決まりの一覧と直し方は `skills/kanna-audit/references/rules.md`。

## 動かすもの・送るもの

- 手元で動かす物：
  - PreToolUse のフック（`node "${CLAUDE_PLUGIN_ROOT}/hooks/kanna-guard.mjs"`）。Bash・Write・Edit の前に、入力の JSON を読んで、止めるかどうかを返すだけ。ファイルを書かず、外へつながない。
  - スキルの中から流す Python のスクリプト（`harness_lint.py`・`eval_ledger.py`）。標準ライブラリだけ。`eval_ledger.py` だけが、対象のプラグインの `evals/ledger.jsonl` に 1 行足す。
  - `kanna-eval-run` と `kanna-tune` は、人の了承を取ってから `claude plugin eval` を流す。これはあなたの資格で、モデルを呼ぶ（利用料がかかる）。
- 外へ送る物：kanna 自身は送らない。`claude plugin eval` が、あなたの Claude の契約でモデルを呼ぶ。結果の報告は `--no-publish` を付けて手元に置く。
- 秘密（API キーなど）は受け取らない。

## kanna 自身の eval

`evals/` に 11 件（呼ばれる 4・似ているが呼ばれない 2・結果と約束 5）。5 件は、欠陥を仕込んだ見本のプラグインを scaffold で作り、見つけられるか・直さないか・流さないかを見る。

```
claude plugin eval plugins/kanna --model haiku --runs 3 --max-cost-usd 3 \
  --scaffold --allow-tools Bash Write Edit --no-publish
```

## 版と更新

版は `.claude-plugin/plugin.json` の `version` で決まる。版を上げない限り、入れた人に更新は届かない。変えたことは `CHANGELOG.md` に書く。

## ライセンス

`.claude-plugin/plugin.json` の `license` と `LICENSE` を見る。
