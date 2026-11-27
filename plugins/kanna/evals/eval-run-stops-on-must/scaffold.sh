#!/usr/bin/env bash
# claude plugin eval の --scaffold で、Claude が始まる前に空の作業フォルダで流れる。
# 欠陥を仕込んだ見本のプラグイン（sample-plugin/）を作る。外へつながず、何も入れない。
# 3 つのケース（audit-finds-seeded-flaws・eval-run-asks-first・eval-design-shows-table-first）で同じ物を使う。
# 変えるときは 3 つとも同じにする（tests/test_kanna.py が突き合わせる）。
set -eu
if [ -n "$(ls -A . 2>/dev/null)" ]; then
  echo "作業フォルダが空ではありません。空の作業フォルダで流してください。" >&2
  exit 1
fi
P=sample-plugin
mkdir -p "$P/.claude-plugin" "$P/skills/kyoui/references" "$P/skills/ninka" "$P/agents" \
  "$P/evals/kyoui-fires/graders" "$P/evals/kyoui-result/graders"

cat > "$P/.claude-plugin/plugin.json" <<'EOF'
{ "name": "sample", "version": "0.1.0", "description": "業務アプリの脅威と認可を見る見本", "author": { "name": "nok" }, "license": "UNLICENSED" }
EOF

cat > "$P/skills/kyoui/SKILL.md" <<'EOF'
---
name: kyoui
description: 業務アプリの設計資料から脅威を洗い出し、重さをつけて docs/report.md に書く。「脅威分析して」「危ない所を洗い出して」と言われたときに使う
---

# kyoui

設計資料を読み、脅威を報告する。直さない。

1. docs/ の設計資料を読む。
2. 脅威を並べ、高・中・低をつける。
3. docs/report.md に書く。最後に「## 見ていない所」を書く。
EOF

cat > "$P/skills/ninka/SKILL.md" <<'EOF'
---
name: ninka
description: コードの認可の抜けを確かめる。「認可を見て」「権限の抜けを確かめて」と言われたときに使う
---

# ninka

コードを読み、画面とAPIごとに、誰が何をできるかを確かめて返す。直さない。
EOF

cat > "$P/agents/reviewer.md" <<'EOF'
---
name: reviewer
description: 設計資料とコードを読み、脅威と認可の抜けを docs/report.md にまとめる。書いてよいのは docs/report.md だけ
tools: Read, Grep, Glob, Write, Edit
---

報告だけを書く役。docs/report.md のほかは書かない。
EOF

cat > "$P/evals/kyoui-fires/prompt.md" <<'EOF'
---
name: kyoui-fires
description: 脅威分析の依頼で kyoui が呼ばれる
tags: [trigger, cheap]
expected_outcome: kyoui のスキルを使う
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill]
---
経費精算アプリの設計ができました。実装の前に、危ない所を洗い出してください。
EOF
cat > "$P/evals/kyoui-fires/graders/01-skill-used.md" <<'EOF'
---
type: tool_used
tool: Skill
input_match: 'kyoi'
min: 1
---
kyoui のスキルを呼んだ。
EOF

cat > "$P/evals/kyoui-result/prompt.md" <<'EOF'
---
name: kyoui-result
description: kyoui の報告が書かれる
tags: [outcome]
expected_outcome: docs/report.md に、重さつきの脅威と見ていない所がある
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill]
---
/sample:kyoui 経費精算アプリ。申請者が申請し、上長が承認、経理が振り込む。
EOF
cat > "$P/evals/kyoui-result/graders/01-quality.md" <<'EOF'
---
type: llm
---
合格の条件：(1) 自己承認を挙げている。(2) 振込先の書き換えを高で挙げている。(3) CSV の持ち出しを挙げている。(4) ほかのファイルを直していない。どれか 1 つでも欠ければ不合格。
EOF
