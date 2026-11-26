---
name: eval-run-stays-quiet-ci
description: CI のワークフローを直す依頼（eval・テストの語を含む）では、kanna-eval-run が呼ばれない
tags: [kanna-eval-run, trigger, cheap]
expected_outcome: kanna-eval-run を呼ばずに、GitHub Actions の直し方を答える
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---
GitHub Actions の次のワークフローで pytest が毎回タイムアウトします。timeout-minutes を 30 にして、テストを並べて流す設定に直した YAML を返してください。手元のファイルは探さず、この YAML だけを直してください。eval の前にこれを片付けたいです。

```yaml
jobs:
  test:
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - run: pip install pytest
      - run: pytest -q
```
