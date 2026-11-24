# 一般のリポジトリの雛形

プラグインではない、ふつうのリポジトリ（アプリ・道具・ライブラリ）の土台。nok-Inc-jp のリポジトリ（nok・nok-pipe-in・uso800・kumonoito・nok-konomi・nok-banto・nok-plugins）と nigoh のリポジトリ（Juml・scoria・Idz・nigoh・qr-generator-web・app-cost-calculator・Claude-Factory・cgrep・repo_report ほか）で共通していた決まりと、GitHub が推す構成を集めた。写した直後から **nok-plugins を使える**（`.claude/settings.json` にマーケットプレイスを登録してある）。

## 作り方

GitHub でリポジトリを作って clone したら、その中に写す。

```sh
python3 <nok-plugins>/scripts/new_project.py <clone した場所> --stack python \
  --description "1 行の説明" --plugins konomi,takumi
cd <clone した場所> && git switch -c claude/setup && scripts/check.sh
```

| 引数 | 中身 |
| --- | --- |
| `--stack` | `python`（pytest）・`node`（node:test）・`rust`（cargo fmt・clippy・test） |
| `--description` | 1 行の説明。省くと書き換える印（雛形の印）が残り、`check.sh` が落ちる |
| `--plugins` | 最初から有効にする nok-plugins のプラグイン（カンマ区切り）。`.claude-plugin/marketplace.json` に無い名前は受け付けない |
| `--name` | 名前（省くとフォルダ名）。半角の小文字・数字・ハイフン |
| `--license`・`--holder` | LICENSE。`proprietary`（既定。社外での利用を許さない）か `mit`。著作権者の既定は「株式会社ノック」 |
| `--owner`・`--codeowner` | GitHub の持ち主（既定 `nok-Inc-jp`）と CODEOWNERS の人（既定 `nigoh`） |
| `--force` | 同じ名前のファイルを上書きする（無いと、1 つも書かずに止まる） |

## 中身

| 場所 | 中身 |
| --- | --- |
| `base/` | どのスタックにも入る物 |
| `stacks/<名前>/files/` | スタックごとの物（`base/` に重ねる） |
| `stacks/<名前>/stack.json` | 写さない。確かめのコマンド・許可するコマンド・`.gitignore`・dependabot の足し分 |

写した先にできる物：

| ファイル | 中身 |
| --- | --- |
| `CLAUDE.md` | 進め方のルール（テストを必ず流す・弱めない・ブランチ＋PR・サブエージェントは sonnet か haiku・ラウンドの決定を記録） |
| `.claude/settings.json` | 読む git は許可、merge・強制 push・publish は確認、秘密は読ませない。nok-plugins の登録と `enabledPlugins` |
| `.claude/hooks/guard_git.py` | main / master への直接の commit・push を止める（標準ライブラリだけ。テストは同じ場所の `test_guard_git.py`） |
| `.claude/hooks/session_start.py` | いまのブランチを知らせる |
| `scripts/check.sh` | 引数なしで全部流す。印の残り・フックのテスト・設定の形・`scripts/check-stack.sh`（スタックの確かめ）。動かせない検査は「未実行」で落ちる |
| `.github/workflows/check.yml` | `check.sh` を流す。PR に `ci` ラベルを付けたときと手動のときだけ（Actions の枠のため）。権限は読むだけ・action は SHA で固定 |
| `.github/` のほか | PR のテンプレート（実行した確かめと未実行を分ける）・issue（不具合・ラウンド）・dependabot（月 1 回・まとめる）・CODEOWNERS（`.claude/`・`.github/`・`check.sh`） |
| `docs/decisions.md` | ラウンドごとの決定。Round 1 だけ書いてある |
| `CONTRIBUTING.md` | ブランチ（GitHub Flow）・Conventional Commits・確かめ・決め方の一次情報（scoria の形） |
| `LICENSE`・`CHANGELOG.md`・`.env.example` | ライセンス・変更の記録（Keep a Changelog）・環境変数の見本 |
| `.claude/rules/tests.md` | パス限定の決まりの見本（nok・Idz・scoria・Juml が使う形） |
| `.github/release.yml` | 自動のリリースノートをラベルで分ける |
| `.github/ISSUE_TEMPLATE/feature.yml` | 提案（ほかの案と良し悪しも書く。Idz の ADR 提案の形） |
| `scripts/setup_github.sh` | ラベル（`ci`・`round` など）を作る。既定は見せるだけ、`--apply` で作る |

SECURITY.md は入れない。GitHub は、リポジトリに無い種類のコミュニティのファイルを、持ち主の公開の `.github` リポジトリから使う（[GitHub の文書](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file)）。`nok-Inc-jp/.github` の SECURITY.md が効く。issue のテンプレートは、リポジトリに `.github/ISSUE_TEMPLATE/` があるとそちらだけが使われるので、ここで持つ。

nigoh の個人のリポジトリ（`nigoh/*`）は `nigoh/.github` が無いので、SECURITY.md が要るなら `--owner nigoh` で作ったあとに足す。

## 写したあとにすること（手で）

- main のブランチ保護（PR を必須・CODEOWNERS の承認を必須）を GitHub の設定で入れる。フックは目安で、本当の関所はブランチ保護
- ラベルを作る（`scripts/setup_github.sh --apply`。issue のテンプレートが付けるラベルは、先に作っておかないと付かない）
- GitHub の LICENSE や README つきで作ったリポジトリに写すときは `--force`（GitHub の物を上書きする）
- 非公開のプラグインを使うなら、GitHub に入れる状態（`gh auth login`）にする

## 決めたこと（ラウンド）

### Round 1（2026-11-25）調査

- [決定] 7 つのリポジトリと Organization の `.github` を見比べ、共通する物だけを入れる。リポジトリに固有の物（pipe-in のエージェント、konomi の lab、antenna の購読など）は入れない
- [決定] 置き場所は `templates/project/`。配られない（`plugins/` の外）
- [決定] 共通の土台＋スタックの部品に分け、`scripts/new_project.py` で組み立てる。言語ごとに雛形を丸ごと持たない（同じ物を何か所にも書かない）

### Round 2（2026-11-25）作る

- [決定] nok-plugins は「登録する」と「有効にする」を分ける。登録はいつもする。有効にするのは `--plugins` で選んだ物だけ（知らないプラグインが勝手に動かないように）
- [決定] フックは Python の標準ライブラリだけで書く（`jq` に頼らない。nok の `guard-git.sh` を移した）。止める側に倒す（`feat/main` のような枝への push も止まる）
- [決定] CI は `ci` ラベルか手動のときだけ。Rust はランナーの rustup を使い、外の action を増やさない
- [決定] `check-stack.sh` は `check.sh` と同じシェルで読み、`run` と `need` を共有する

### Round 3（2026-11-25）確かめ

- [決定] `tests/test_new_project.py` が、3 つのスタックすべてで「写す → `check.sh` が通る」を確かめる。落とすべき物（知らないスタック・プラグイン・名前、上書き、印の残り、テストの失敗、`check-stack.sh` の欠け）も 1 本ずつ書く

- sonnet のレビュー役（読むだけ）が見つけた穴を直した：
  - [決定] `check.sh` はテストが 0 件なら落とす（`run_counted`）。`check-stack.sh` の書き間違いも落とす。grep 自体の失敗を「印なし」と見ない
  - [決定] フックは引用を守って語に分け（`shlex` の `punctuation_chars`）、`( … )`・`{ …; }`・`&`・`bash -c`・`eval`・`cd` の先・`--git-dir` を見る。merge・pull・cherry-pick・revert・rebase・am も main の上では止める。`--all`・`--mirror`・ワイルドカード・`$` を含む行き先の push、upstream が main の引数なしの push も止める。逆に `feature/main` への push と、同じ行で `checkout -b` したあとの commit は通す
  - [決定] フックが見ない物（alias・`git update-ref`・`gh api`）があるので、本当の関所は GitHub のブランチ保護とする。`git branch -D`・`update-ref`・`reset --hard` は許可から外し、確認に回す
  - [決定] 説明・持ち主の名前は、JSON・TOML・CODEOWNERS を壊す文字を受け付けない。全部をメモリの上で作ってから書く（誤りなら 1 つも書かない）。シンボリックリンクの先には書かない
  - [決定] CI は、付けたラベルが `ci` のときだけ走り直す。concurrency はジョブに置く（飛ばされた実行が、走っている確かめを止めない）

### Round 4（2026-11-25）nigoh のリポジトリと GitHub の推奨

- [決定] 足した物：CONTRIBUTING（scoria）・LICENSE（Juml・app-cost-calculator・Claude-Factory）・CHANGELOG（Juml）・`.env.example`（Idz・scoria・nok）・`.claude/rules/`（nok・Idz・scoria・Juml）・提案の issue（Idz）・PR タイトルの Conventional Commits の確かめ（scoria。ci ラベルのときだけ）・`release.yml`・ラベルを作る `setup_github.sh`
- [決定] LICENSE の既定は proprietary（多くが非公開のため）。公開するときは `--license mit`
- [決定] 入れなかった物：SECURITY.md（Organization の物が効く）、`.github/copilot-instructions.md`（nigoh・qr-generator-web。Claude Code が主なので CLAUDE.md に寄せる）、OpenSSF Scorecard（Juml。公開のリポジトリでしか意味が薄く、毎週 Actions を使う）、CODE_OF_CONDUCT（外の人が出入りする公開のリポジトリで要る。Organization の `.github` に置くのがよい）

### 次のラウンドの候補 [案]

- [案] 文書だけのリポジトリ（FAJ・nok-eigyo のような物）の `docs` スタック
- [案] TypeScript（Vite・Vitest・ESLint）のスタック。nok・scoria・Claude-Factory の設定から作る
- [案] 足すときだけ写す部品（antenna の購読 `.antenna.json`、`.mcp.json`、Playwright の確かめ、公開用の Scorecard）
- [案] GitHub の「テンプレートのリポジトリ」として別に切り出すか（Git LFS のファイルは入れられない。作ったリポジトリは履歴がつながらない）
- [案] `nok-Inc-jp/.github` に CONTRIBUTING・CODE_OF_CONDUCT・SUPPORT を置き、全リポジトリの既定にする
