---
name: tune-fires
description: eval が落ちたのでスキルを直してほしい、という依頼で kanna-tune が呼ばれる
tags: [kanna-tune, trigger, cheap]
expected_outcome: kanna-tune のスキルを使って答える
max_turns: 12
allowed_tools: [Read, Glob, Grep, Skill]
---
プラグインの eval を回したら、kyoui-fires のケースが haiku で 3 回中 1 回しか通りませんでした。スキルの方を直して、もう一度ラウンドを回して良くしたいです。
