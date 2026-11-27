# nok のプラグインのハーネスの点検（2026-11-26）

`plugins/kanna/scripts/harness_lint.py`（作りの質・29 件。R9 で 30 件）と `scripts/plugin_drift.py`（形）を、一覧の 7 件のうち手元に取れた 6 件にかけ、takumi は eval を haiku で実際に回して確かめた。決まりの中身は `plugins/kanna/skills/kanna-audit/references/rules.md`、作法は `docs/eval-engineering.md`。

konomi は、最初は読む許しが出ず、あとから取り込んで見た（下の「konomi」）。

## まとめ

1. **eval が「1 スキルぶん」しか無い**。fushin・toryo・takumi はスキルが 3 つずつあるのに、eval は代表の 1 つだけ（3 件）。ほかの 2 つは、呼ばれるか・呼ばれすぎないか・結果のどれも測っていない。fude・ranbiki は eval が 0 件。
2. **「呼ばれない」ケースが何も測っていない**。fushin・toryo・takumi の呼ばれないケースは「CSV の合計のスクリプト」「関数の名前」「背景色」のような無関係な依頼。takumi で測ると、プラグイン無しでも同じ点（差 0）だった。
3. **takumi の代表のスキル kyoui は、haiku で呼ばれていない（0/3）**。haiku は description に書かれた資料のパス（`docs/gyomu-sheet.md`）を見て、スキルを呼ばずに同じ手順を自分で始めた。
4. **「直さない」「書くのは 1 つだけ」が頼みのまま**。書ける道具を持つエージェントが 6 件（fushin・toryo・takumi・ranbiki）あり、どれも PreToolUse のフックで絞っていない。
5. 形の検査（plugin_drift）は fushin・toryo・takumi・pipe-in が通っていて、ranbiki・fude はアイコンが無く公式の検査（V01）に落ちる。

## プラグインごと

| プラグイン | 版 | スキル | eval | harness_lint（必須 / 推奨） | plugin_drift（必須 / 推奨） | いちばん先に直す所 |
| --- | --- | --- | --- | --- | --- | --- |
| konomi | 0.9.6 → 0.9.7（パッチ） | 8（モデルが呼べるのは 4） | 0 → 7 | 0 / 21 → 0 / 11 | 0 / 11 | LP で呼ばれない（直した）。相対パス（直した）。結果の eval と大きい記録が残り |
| pipe-in | 0.6.2 | 1（＋.claude/ に 10） | 12 | 0 / 12 | 0 / 5 | tags に種類（trigger・outcome・safety）を足す。pipe-probe に返す形を書く |
| fushin | 0.1.0 → 0.2.0（パッチ） | 3 | 3 → 10 | 0 / 9 → 0 / 0 | 0 / 0 | R12 で直した（パッチあり） |
| toryo | 0.1.0 → 0.2.0（パッチ） | 3 | 3 → 10 | 0 / 9 → 0 / 0 | 0 / 0 | R7・R13 で直した（パッチあり） |
| takumi | 0.1.0 → 0.2.0（パッチ） | 3 | 3 → 10 | 0 / 9 → 0 / 0 | 0 / 0 | R6〜R8 で直した（パッチあり） |
| ranbiki | 0.5.0 → 0.6.0（パッチ） | 1 | 0 → 5 | 0 / 8 → 0 / 3 | 1 / 10 | R15 で eval を足した（パッチあり）。残りは書く役のフック・アイコン |
| fude | 0.8.0 → 0.9.0（パッチ） | 4 | 0 → 9 | 0 / 15 → 0 / 5 | 1 / 14 | R14 で取り合いの eval と QS04 を直した（パッチあり）。残りは結果の eval・アイコン・README |

### konomi（2026-11-27 に追加で見た）

いちばん大きい（スキル 8・Stop フック・playwright の MCP・道具 14・テスト 248）。テストの決まりが厳しく、形の作りはよい。harness_lint は必須の外れ 0・推奨 21（eval が 0 件なのが大半）。

- **「新しい LP を作って」で konomi が呼ばれない（haiku・0/15）**。konomi の考え方（「業務アプリも Web アプリもホームページ・LP も作れる汎用の元」）に反して、description に「サイト・LP」の語が無く、haiku は自分で HTML を書いた。description を「業務アプリ・Web アプリ・サイトや LP の画面・ページ・コンポーネントを作る…ときは、書き始める前に必ず使う」にすると 10/10。サーバーの不具合・CSS の仕様の質問で呼ばれすぎることは無かった（どちらも 10/10）。
- **QS04**：本体のスキルだけが、道具を `node scripts/law-used.mjs` のように作業フォルダからの相対で指していた（ほかのスキルは `S/`＝`${CLAUDE_PLUGIN_ROOT}/skills/konomi/scripts/`）。入れた人の手元では、そのパスに道具が無い。`${CLAUDE_PLUGIN_ROOT}` の形に直した。
- change は最初 3/5（先に自分で直してから change を呼び、konomi の Stop フックに止められた）。description を直した版と対照を 10 回ずつ流すと、対照も 10/10 になり、差が確かめられなかったので**直しは採らなかった**。
- 呼ばれる・呼ばれないの 7 件（konomi 2・check・change・catalog・近い依頼 2）を足した。haiku・5〜10 回で、直した後は全部通る。konomi・change のケースは、スキルが重く max_turns 10 で切られたので 20 にした。
- 直しは `docs/patches/konomi-harness.patch`（版 0.9.7。konomi の決まりどおり、description・相対パス・eval の有無を見るテストを `tests/plugin.test.mjs` に 3 本足した。`plugin.test.mjs` は 42 件すべて通る）。
- 確かめていない物：konomi の `scripts/check.sh` の 3 段目（lab の製品での実地の検査）。lab の `npm ci` と Chrome が要り、この環境では揃えていない。そのため node のテストのうち 48 件が、**直す前の元のリポジトリでも同じように**落ちる（直しのせいではない）。
- 残り：結果の eval（画面を作って点検するので、Chrome と lab が要る）、`records/ui.md` が 455 KiB（公式ディレクトリは 256 KiB を超えるファイルを保留にする）、catalog の description に「いつ使うか」が無い、CHANGELOG・アイコン・LICENSE ファイル。

### pipe-in

いちばん作り込まれている（12 件、scaffold で入力を作り、決まった答えの grader が中心、「流さない」「書かない」の safety が多い）。nok の手本にしてよい。

- QE12：12 件中 11 件の tags に種類が無い（`cheap`・`needs-bash` などはある）。ただし pipe-in は、決定記録（D0045・D0096）で tags の語をスキル名・`cheap`・`agent`・`needs-*` に限り、テスト（`tests/test_plugin_evals.py` の AC-01）で確かめている。**pipe-in の決定を先にする**（R17）。種類で絞りたくなったら、pipe-in の側で決め直す。
- 5 つのスキルはどれも `disable-model-invocation: true`（人がスラッシュで呼ぶだけ）なので、「呼ばれる・呼ばれない」のケースは要らない。
- QA03：`agents/pipe-probe.md` に返す形の見出しが無い。
- 形：CHANGELOG が無い。CI（`ci.yml`）が `claude plugin validate --strict` を流していない。`references/stage-rules.md` に目次が無い。

### fushin・toryo・takumi（同じ雛形から作った 3 件）

3 件とも同じ弱さを持つ。

| ID | 中身 | 直し方 |
| --- | --- | --- |
| QG01〜QG03 | 3 スキルのうち 2 つに、eval が 1 件も無い | スキルごとに「呼ばれる・似ているが呼ばれない・結果」を足す（`/kanna:kanna-eval-design <フォルダ> <スキル>`） |
| QG02（中身） | 呼ばれないケースが無関係な依頼 | 隣のスキルの依頼にする。例：kyoui に対して「このコードの認可の抜けを見て」（ninka-check の仕事）、gyomu-sheet に対して「この業務要件シートから構成を決めて」（toryo の仕事） |
| QE05 | 結果の llm の grader が「(1)〜(4) のどれか 1 つでも欠ければ不合格」 | 条件ごとに 4 つの grader に分ける |
| QE06（中身） | 結果の regex が最後の返事を見ている（`見ていない所`） | `target: {source: file, path: docs/takumi-report.md}` と `pattern: '^## 見ていない所'`（flags: m）にする |
| QG04 | 「直さない」「書くのは 1 つだけ」を確かめるケースが無い | `tool_used: Edit`（`input_match: '"file_path":\s*"[^"]*src/'`・max 0）など |
| QA04 | gyomu-analyst・kousei-architect・security-reviewer が Write・Edit を持ち、本文で「書いてよいのは 1 つだけ」と頼んでいるだけ | `hooks/hooks.json` の PreToolUse で、`agent_type` がその役のとき、決まったファイルの外への Write・Edit を止める（kanna の `hooks/kanna-guard.mjs` が見本）。security-reviewer は Edit を持たないが Write で何でも上書きできる |

#### takumi を実際に回した（haiku・3 回・ablation あり・$0.18）

| ケース | プラグインあり | プラグイン無し | 差 | 読み |
| --- | --- | --- | --- | --- |
| kyoui-fires | 0/3 | 0/3 | 0 | **呼ばれていない**。haiku は「まず設計資料（docs/gyomu-sheet.md）を確かめます」と、description にあるパスを自分で探し、スキルを呼ばずに答えた |
| kyoui-result | 0.83（2/3 合格） | 0 | +0.83 | スキルは効いている。落ちた 1 回は、報告をファイルに書き、最後の返事に「見ていない所」の語が無かった（採点の弱さ） |
| kyoui-stays-quiet | 1 | 1 | 0 | 無関係な依頼（背景色）なので、プラグイン無しでも同じ。何も測っていない |

#### R6：kyoui-fires を直して確かめた（haiku・同じ条件で続けて流す）

最初の 0/3 を受けて、直す前の版（対照）と、直した 2 案を同じ命令で流した。

| 版 | 呼ばれた回 | 費用 |
| --- | --- | --- |
| 対照（今の takumi） | 5/5・3/10（合わせて **8/15**）。ablation つきでは 1/5・5/10 | $0.03〜0.09 |
| A：scaffold で設計資料を置く | 5/5・10/10（**15/15**） | $0.17 |
| B：description を「いつ使うか」から書き出し、「必ず使う」と書く | 5/5・10/10（**15/15**） | $0.11 |
| A＋B | 10/10 | $0.10 |
| 呼ばれすぎの確かめ（隣の ninka-check の依頼） | 対照 10/10・B 10/10 で kyoui を呼ばない（ninka-check は 10/10 で呼ばれた） | $0.10 |

8/15 → 15/15 の差が偶然で起きる確率は p<0.01（Fisher の正確検定）。

#### R8：残りの 2 スキルの eval と、書く役のフック

- ninka-check・himitsu-check に「呼ばれる・似ているが呼ばれない・結果と約束」を 6 件足した。himitsu-check は「見つけた鍵の値を書き写さない」を `match: not_contains` で見る。
- ninka-check-fires は、最初はコードを依頼文に貼る形で 4/10。description を直しても 6/10（p≈0.3、確かとは言えない）。**コードを scaffold でリポジトリに置く形にすると、直す前の版でも 10/10** だった。弱いのはスキルでなくケースの入力だったので、description の直しは採らなかった。
- kyoui-result の 4 条件の llm を 1 条件ずつに分けた（3/3）。
- security-reviewer が書けるのを `docs/takumi-report.md` だけにする PreToolUse のフック（`hooks/report-guard.mjs`）とテストを足した。
- 全部で 10 件、haiku・3 回ずつで **10/10**（$0.20）。harness_lint は `--strict` で外れ 0。

直しはまとめて `docs/patches/takumi-harness.patch`（版 0.2.0、CHANGELOG つき）。nok-takumi で `git apply` でき、takumi のテスト（19 件）も通る。

分かったこと：**同じ版でも、呼ばれる率は時によって 3 割から 10 割まで動いた**。最初の「0/3」も、後の「5/5」も、それだけでは何も言えない。kanna-tune に「対照を同じ命令で続けて流す」「呼ばれる率は 10 回以上」を足し、台帳の比べに p の値を付けた。

当初の直し方の案（R6 で A と B を確かめた）：

1. 入力：scaffold で `docs/gyomu-sheet.md` と `docs/kousei.md` を作る（依頼文は「設計ができました」と言うのに、作業フォルダが空）。
2. それでも呼ばれなければ、description から資料のパスを外し「設計の後・実装の前に、脅威を洗い出して重さつきの報告にまとめるときは必ずこのスキルを使う」のように、呼ぶ場面だけを書く（手順は本文に任せる）。
3. sonnet でも流し、haiku だけの落ち方かを分ける。

#### R10：kanna-audit を fushin に、ふだんの形で流した

`claude -p "/kanna:kanna-audit fushin-plugin" --plugin-dir plugins/kanna --model haiku`（写しの上で）。$0.21・19 手。fushin のファイルは 1 つも変えなかった。報告は上の表と同じ弱さ（eval の無い 2 スキル・フックの無い書く役・条件を並べた llm）に加えて、**`gyomu-sheet-result/graders/01-shape.md` が「業務要件シート」の 1 語しか見ておらず、見出しが無くても通る**ことを挙げた（kanna-eval-reviewer の指摘。harness_lint では分からない種類）。kanna 自身への指摘（harness_lint の `--json` で、合格の行にも外れの文が入っていた）も返ってきたので直した。

#### R12：fushin に同じ一通りを当てた

- kengen-hyo・data-sekkei に「呼ばれる・似ているが呼ばれない・結果」、gyomu-sheet に「似ているが呼ばれない」（Excel の式を直す依頼）を足した。gyomu-sheet-result は 6 つの見出しを見る regex と、1 条件ずつの llm 4 つに分けた。gyomu-analyst の書く先を絞るフックを足した。
- haiku・3 回で 10/10。呼ばれる・呼ばれないの 7 件は 10 回ずつで全部 10/10。結果の 3 件はプラグイン無しとの差が +0.56〜+1.0（易しすぎるケースではない）。fushin の description は、もとから「〜と言われたとき」が具体的で、直す必要は無かった。
- 直しは `docs/patches/fushin-harness.patch`（版 0.2.0）。

#### R13：toryo に同じ一通りを当てた

- keitai・unyou の eval、kousei-result の分け直し、kousei-architect の書く先を絞るフックを足した（R7 の kousei の description の直しも含む）。
- unyou-result が 3 回中 2 回、「認証」と「バックアップと戻し方」を空のまま落ちた。trace を読むと、依頼文の「**運用の所**を埋めて」を、haiku は見出しの「## 運用と費用」と読んでいた。依頼文を引数だけ（`/toryo:unyou docs/kousei.md`）にすると、直す前の版でも 9/10。unyou の手順の直しは、10/10 と差が確かでなかったので採らなかった（入力のせい、の 3 回目）。
- kousei-not-unyou が 3 回中 2 回落ちたのは**採点**だった：呼ばれたのは unyou だけだが、unyou に渡した引数の「docs/kousei.md」に `input_match: 'kousei'` が当たっていた。`'"skill":\s*"[^"]*kousei'` に直して 10/10。同じ誤りがどのプラグインでも起こり得るので、harness_lint に QE15 を足し、kanna・雛形・3 つのパッチの grader を全部直した。
- 全部で 10 件、haiku・3 回で 8/10 → 採点の直しの後、呼ばれる・呼ばれないは 7/7。直しは `docs/patches/toryo-harness.patch`（版 0.2.0）。

### ranbiki

- eval が 0 件。distill-skill は「実験を回す」重いスキルなので、まず安い 3 件（呼ばれる・呼ばれない・「タスクが無いときに作り始めず、形式を聞く」の safety）から。
- QA04：teacher・student・analyst が Write を持つ。student は「渡された PROMPT.md の指すパスだけに書く」なので、フックで run フォルダの外への Write を止めると、蒸留の測りが汚れない。
- 形：アイコン・LICENSE・CHANGELOG・CI・supportUrl が無い。

#### R15：ranbiki に eval を足した

- 呼ばれる（英語・日本語）・重みを学習させる知識蒸留の依頼では呼ばれない・費用を見せて了承を待つ・タスクが 60 件に足りなければ止まる、の 5 件。haiku・5〜10 回で、呼ばれる・呼ばれない・止まるは全部通った。
- 了承を待つケースで落ちた回は、3 回が**採点**（`distill.py --work <dir> init` の語順を許していなかった・「Do you want…?」を問いと数えていなかった）、残りは「この足し算は Haiku に易しすぎる」と先に止める回で、ふるまいとしては良い物だった。
- 作業フォルダ（`--work`）の置き場の既定が手順に無く、haiku が書けない場所を選んで `init` に失敗する回があった。既定を 1 行足しても 8/10 → 8/10（p≈0.57）で、**採らなかった**。
- 気づき：このコンテナは root で動くため、eval のサンドボックスの中のエージェントが `/tmp/claude-0/` の下に書けてしまった（ディレクトリの権限で閉じられない。eval が「root では書いた物を封じられない」と警告していた）。eval は root でない利用者で流すのがよい。
- 直しは `docs/patches/ranbiki-harness.patch`（版 0.6.0、CHANGELOG を新しく作った。ranbiki のテスト 52 件が通る）。書く役（teacher・student・analyst）のフックは、run のフォルダの形を確かめてから足す。

### fude

- eval が 0 件。4 スキル（write・review・export・care）の取り合いが起きやすい（「記事を見直して」は write か review か）。まず「似ているが呼ばれない」を隣のスキルの依頼で置く。
- QS04：`skills/fude-review/SKILL.md` が `scripts/eval_score.py` と `plugin/skills/fude-write/references/kata.md` を、リポジトリからの相対で指している。入れた人の手元には無い（プラグインの外）か、場所が違う。`${CLAUDE_PLUGIN_ROOT}` からの形にするか、開発者向けの説明として本文から外す。
- 形：アイコン・プラグインのフォルダの README・LICENSE・CHANGELOG・CI・homepage が無い。

#### R14：fude の取り合いを測った

- 4 つのスキルの「呼ばれる」と、隣のスキルの依頼で「呼ばれない」を 8 件足し、haiku・5 回で流した。**取り合いは起きていなかった**（review の依頼で write が呼ばれる、export の依頼で review が呼ばれる、などは 0 回）。
- ただ、「新しく〜という記事を書きたい。**構成から一緒に考えて**」では、fude-write が呼ばれず、haiku が自分で構成案を書いた（対照 4/20）。fude-write の description を「記事を書くとき、記事の題や構成を考えるときは、書き出す前に必ず使う」から書き出すと 10/10（p<0.0001）。隣の review の依頼で呼ばれすぎることも無かった（10/10）。
- QS04：fude-review の本文が、入れた人の手元に無い `plugin/skills/...` と `scripts/eval_score.py` を指していたのを直した。
- 直しは `docs/patches/fude-harness.patch`（版 0.9.0、CHANGELOG を新しく作った。版を決め打ちしていた fude のテストも 0.9.0 に合わせた。255 件通る）。

#### R20：fude の書き出しと公開の記録の結果のケース

- fude-export-result（道具で Zenn の形に書き出し、下書きのまま、点検は外さず、原稿は直さない）・fude-export-stops-on-lint（出してはいけない語のある原稿で、`--no-lint` を付けずに止まる）・fude-care-record-result（道具で URL を記録し、本文は直さない）を足した。
- 最初は Bash の道具がどれも「Read-only file system」で落ちた。原因は eval の流し方（サンドボックスが `/tmp` を書けない所にし、作業フォルダが `/tmp` の下にある）で、`TMPDIR` を `/tmp` の外にすると通った。途中で「Write を許していないから」と見立てて決まり（QE16）を足したが、確かめると外れていたので取り下げた。
- fude-export-result は、依頼文の「zenn-repo/」が作業フォルダに無く、モデルが勝手に作らずに止まっていた（0/5）。scaffold で置くと 5/5。
- fude の全体は 12 件、haiku・3 回で **12/12**。残りは fude-write と fude-review の結果の eval（点検役のエージェントを sonnet で走らせるので、費用が上がる）と、アイコン・プラグインのフォルダの README。

## 直す順（おすすめ）

1. **takumi**：`docs/patches/takumi-harness.patch` を当てる（R6〜R8。呼ばれる率 8/15 → 15/15、eval 3 → 10 件で 10/10、書く役のフック）。
2. **toryo**：`docs/patches/toryo-harness.patch` を当てる（R7・R13。kousei が呼ばれる率 11/20 → 10/10、eval 3 → 10 件、書く役のフック）。
3. **fushin**：`docs/patches/fushin-harness.patch` を当てる（R12。eval 3 → 10 件で 10/10、書く役のフック）。
4. **fude**：`docs/patches/fude-harness.patch` を当てる（R14。eval 0 → 9 件、fude-write の呼ばれる率 4/20 → 10/10）。
5. **ranbiki**：`docs/patches/ranbiki-harness.patch` を当てる（R15。eval 0 → 5 件）。
6. **fushin・toryo・takumi の「呼ばれない」ケースを、隣のスキルの依頼に替える**（3 件の書き換えで、3 プラグインが取り合いを測れるようになる）。
7. **書ける役をフックで絞る**（fushin・toryo・takumi・ranbiki）。
8. **足りないスキルの eval**（fushin・toryo・takumi の 6 スキル、ranbiki の 1、fude の 4）。
9. 形の残り（ranbiki・fude のアイコンなど）。

どのリポジトリにも、`templates/repo/scripts/harness_lint.py` を写して `scripts/check.sh` に足すと、CI が作りの質も見るようになる（`templates/repo/scripts/check.sh` は足してある）。

## 見ていない所

- konomi（読めなかった）。
- pipe-in の `.claude/` にある開発用のスキル 10・エージェント 9（配られるプラグインの外なので、今回は見ていない）。
- takumi 以外の eval は流していない（fushin・toryo は takumi と同じ雛形・同じ形なので、同じ弱さがあると見立てたが、実測ではない）。
- 読む役のエージェント（kanna-skill-reviewer・kanna-eval-reviewer）による見立ては、takumi の上の読み以外は入れていない。各リポジトリで `/kanna:kanna-audit` を流すと足される。
