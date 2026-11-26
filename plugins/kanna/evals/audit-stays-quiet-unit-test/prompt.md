---
name: audit-stays-quiet-unit-test
description: ふつうのコードのテストを書く依頼（「テスト」「評価」の語は近い）では、kanna のスキルが呼ばれない
tags: [kanna-audit, kanna-eval-design, trigger, cheap]
expected_outcome: kanna のどのスキルも呼ばずに、pytest のテストを返す
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---
次の Python の関数に、pytest のテストを書いてください。境界の値も見て、評価が甘くならないようにしてください。

```python
def clamp(x: int, lo: int, hi: int) -> int:
    return max(lo, min(x, hi))
```
