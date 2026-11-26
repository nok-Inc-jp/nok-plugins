---
name: audit-fires
description: 自作のプラグインの eval が甘いという相談で、kanna-audit が呼ばれる
tags: [kanna-audit, trigger, cheap]
expected_outcome: kanna-audit のスキルを使って答える
max_turns: 12
allowed_tools: [Read, Glob, Grep, Skill]
---
社内で作った Claude Code のプラグインがあります。eval は一応あるのですが、甘い気がします。スキルと eval の作りがベストプラクティスに沿っているか、点検してもらえますか。
