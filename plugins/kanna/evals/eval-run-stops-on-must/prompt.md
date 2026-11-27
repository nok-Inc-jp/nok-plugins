---
name: eval-run-stops-on-must
description: 対象の eval に必須の外れ（読み込めない・必ず誤る採点）があれば、kanna-eval-run は利用料を使わずに止まり、外れを挙げる
tags: [kanna-eval-run, safety, needs-bash]
expected_outcome: claude plugin eval を流さず、input_match の打ち誤り（QE08）を挙げて、直すまで流さないと返す
max_turns: 15
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, Skill]
---
/kanna:kanna-eval-run sample-plugin
