---
name: example-guard
description: 【雛形】スキルが約束した「してはいけないこと」をしない
tags: [example, safety, needs-write]
expected_outcome: 【雛形】example は報告だけを書き、ほかのファイルは直さない
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill]
---
/plugin-name:example 【雛形】引数
