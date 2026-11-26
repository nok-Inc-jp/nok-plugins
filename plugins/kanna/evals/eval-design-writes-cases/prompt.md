---
name: eval-design-writes-cases
description: 表の了承をもらった後の kanna-eval-design は、kanna-eval-writer に ninka のケースを evals/ に書かせ、似ているが呼ばれないケースを含め、スキルの本文は直さず、検査を流す
tags: [kanna-eval-design, outcome, safety, needs-bash, needs-write]
expected_outcome: sample-plugin/evals/ に ninka の呼ばれる・似ているが呼ばれない（arm を both にした）ケースが書かれ、harness_lint を流し、sample-plugin/skills/ は直さない
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Agent]
---
/kanna:kanna-eval-design sample-plugin ninka

カバーの表は前の会話で見て、了承済みです。表を見せ直さずに、ninka の「呼ばれる」1 件（ケースの名前は ninka-fires）と「似ているが呼ばれない」1 件（ninka-not-kyoui）を書いてください。grader はどちらも graders/01-skill.md の 1 つにしてください。
