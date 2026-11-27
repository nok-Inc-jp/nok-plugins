# 変更の記録

版は `.claude-plugin/plugin.json` の `version`（[semver](https://semver.org/lang/ja/)）。新しい版を上に足す。書き方は [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/) に合わせる（足した・変えた・直した・消した）。

## [0.1.0] - 2026-11-26

### 足した

- 最初の版。`kanna_run.py`（命令を tags から組み、ケースごとの費用で見積もり、流して台帳に足す）も入れた。スキル 4 つ（kanna-audit・kanna-eval-design・kanna-eval-run・kanna-tune）、エージェント 3 つ、PreToolUse のフック、`harness_lint.py`（決まり 31 件。`--probe-scaffold` で空振りの grader を探す）と `eval_ledger.py`、eval 11 件（haiku・3 回で 11/11、sonnet・1 回で 11/11。記録は `evals/ledger.jsonl`）
