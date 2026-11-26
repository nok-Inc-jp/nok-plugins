---
name: example-fires
description: 【雛形】スキルを使うべき依頼で、スキルが呼ばれる
tags: [example, trigger, cheap]
expected_outcome: 【雛形】example のスキルを使って答える
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---
【雛形】このスキルを使うべき、ふつうの依頼の文を書く（利用者がそのまま言いそうな言い方で）。スキルの名前は書かない（description を測れなくなる）。作業フォルダに無いファイルを指さない（探し回って時間切れになる）。
