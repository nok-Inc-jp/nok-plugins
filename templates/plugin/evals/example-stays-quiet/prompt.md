---
name: example-stays-quiet
description: 【雛形】似ているが使うべきでない依頼では、スキルが呼ばれない
tags: [example, trigger, cheap]
expected_outcome: example のスキルを呼ばずに答える
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill]
---
【雛形】このスキルと**似ているが使うべきでない**依頼の文を書く（隣のスキルの仕事、同じ語を含む別の頼み）。「背景色を変えて」のような無関係な依頼は、呼ばれないのが当たり前で何も測らないので使わない。
