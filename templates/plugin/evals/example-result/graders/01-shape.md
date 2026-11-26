---
type: regex
target:
  source: file
  path: 【雛形】スキルが書くファイル（例：docs/report.md）
pattern: '【雛形】^## 決まった見出し'
flags: m
---
【雛形】書いたファイルに、決まった見出しがある。返事でなくファイルの中身を見る（返事は要約されて語が消えることがある）。返事だけを返すスキルなら target を消す。
