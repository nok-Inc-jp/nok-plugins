---
name: kanna-audit
description: Claude Code のプラグインのハーネス（スキル・エージェント・フック・eval）の作りを点検し、直す順に並べた報告（kanna-report.md）を書く。決まった検査（harness_lint）と、読む役のエージェント 2 つの見立てを合わせる。「プラグインを見直したい」「スキルや eval の作りを点検して」「eval が甘い気がする」「公式のベストプラクティスに沿っているか見て」と言われたとき、またはプラグインを出す前・版を上げる前に使う。直さない
argument-hint: "<プラグインのフォルダ（.claude-plugin/plugin.json がある所）>"
---

# kanna-audit

プラグインのフォルダを受け取り、ハーネスの弱い所を、直す順に並べて `kanna-report.md` に書く。**プラグインのファイルは直さない**。直すのは、報告を読んだ人が決める（eval を足すなら kanna-eval-design、回すなら kanna-eval-run）。

## 必ず守ること

- 書いてよいのは `kanna-report.md`（作業フォルダの直下）だけ。プラグインの中は読むだけ。
- `claude plugin eval` を流さない（利用料がかかる。回すのは kanna-eval-run で、人が決めてから）。
- 指摘には、決まりの ID（`QE05` など）か、読む役が挙げた理由を必ず付ける。「なんとなく弱い」と書かない。
- 決まった検査で分かることを、読む役に推し量らせない。検査の結果を先に渡し、読む役には「検査では分からないこと」だけを頼む。
- 見ていない所（読めなかったファイル、流していない検査）を必ず書く。

## 手順

この表を写して、済んだら印を付けながら進める。

```
- [ ] 1. 対象を確かめた
- [ ] 2. 決まった検査を流した
- [ ] 3. 読む役 2 つに頼んだ（並べて）
- [ ] 4. 報告を書いた
- [ ] 5. 報告を確かめた
```

1. `$ARGUMENTS` のフォルダに `.claude-plugin/plugin.json` か `skills/` があるかを確かめる。引数のフォルダは、作業フォルダ（今いる所）からの相対で探す。kanna の置き場（`${CLAUDE_PLUGIN_ROOT}`）の中を探さない。無ければ、何が無いかを伝えて止まる。
2. 決まった検査を流す（どれも利用料はかからない）。
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/harness_lint.py" <フォルダ> --json
   claude plugin validate --strict <フォルダ>        # claude が無ければ「未実行」と報告に書く
   ```
   nok-plugins を手元に置いているなら `python3 <nok-plugins>/scripts/plugin_drift.py <フォルダ>` も流す（形の決まり）。
3. Agent で、`kanna-skill-reviewer` と `kanna-eval-reviewer` を**同じ返事の中で並べて**呼ぶ。どちらにも、フォルダのパスと、手順 2 の結果（外れた決まりの一覧）を渡す。
4. [references/report-template.md](references/report-template.md) の様式で `kanna-report.md` を書く。並べ方は「壊れている → 測れていない → 守らせていない → 読みにくい」の順。同じ所を検査と読む役の両方が挙げたら、1 件にまとめて両方の根拠を書く。
5. 返す前に確かめる：どの件にも「場所」「なぜ困るか」「直し方」がある。決まりの ID は [references/rules.md](references/rules.md) にある物だけ。`## 見ていない所` が空でない（全部見たなら、そう言える理由を書く）。

## 返す形

```
## 書いたもの
kanna-report.md

## 数
壊れている N ／ 測れていない N ／ 守らせていない N ／ 読みにくい N

## 先に直してほしいもの（3 件まで）
- <ID>：<1 行>

## 次の一手
kanna-eval-design で <スキル> の eval を足す、など 1〜2 行
```

## 詳しい資料

- [references/rules.md](references/rules.md)：harness_lint の決まりの一覧と、決まりごとの直し方。指摘を書くときに読む
- [references/report-template.md](references/report-template.md)：報告の様式。書く前に必ず読む
