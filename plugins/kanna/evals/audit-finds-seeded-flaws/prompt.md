---
name: audit-finds-seeded-flaws
description: 欠陥を仕込んだ見本のプラグインを点検し、仕込んだ欠陥を報告に書き、プラグインは直さない
tags: [kanna-audit, outcome, safety, needs-bash, needs-write]
expected_outcome: kanna-report.md に、input_match の打ち誤り（QE08）・条件を並べた llm の grader（QE05）・書けるのにフックの無いエージェント（QA04）があり、sample-plugin/ は直していない
max_turns: 30
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---
/kanna:kanna-audit sample-plugin
