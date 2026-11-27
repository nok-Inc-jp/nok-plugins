#!/usr/bin/env node
// kanna の PreToolUse フック。標準入力でイベントの JSON を受け、止めるときだけ permissionDecision を返す。
//   1. claude plugin eval を、--model と --max-cost-usd 無しで流させない（利用料が上限なしに出るのを防ぐ）。
//      上位のモデル（opus・fable）や、本物の MCP サーバーを起こす流し方は、人に確かめる（ask）。
//   2. kanna-eval-writer は、プラグインの evals/ の中（results/ を除く）にしか書けない。
//   3. 読むだけの役（kanna-skill-reviewer・kanna-eval-reviewer）は、書く道具も Bash も使えない。
// 外の依存を使わない。読めない入力では止めない（安全に通す。止めるのは、はっきり分かるときだけ）。
import { readFileSync } from "node:fs";

let event;
try {
  event = JSON.parse(readFileSync(0, "utf8") || "{}");
} catch {
  process.exit(0);
}

const tool = String(event.tool_name || "");
const input = event.tool_input && typeof event.tool_input === "object" ? event.tool_input : {};
// プラグインのエージェントは「kanna:kanna-eval-writer」の形で来ることがある。
const agent = String(event.agent_type || "").split(":").pop();

function decide(decision, reason) {
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: { hookEventName: "PreToolUse", permissionDecision: decision, permissionDecisionReason: reason },
    }),
  );
  process.exit(0);
}

const WRITE_TOOLS = new Set(["Write", "Edit", "MultiEdit", "NotebookEdit"]);
const READ_ONLY_AGENTS = new Set(["kanna-skill-reviewer", "kanna-eval-reviewer"]);
const LARGE_MODEL = /^(?:opus|fable|claude-opus|claude-fable)/i;

if (READ_ONLY_AGENTS.has(agent) && (WRITE_TOOLS.has(tool) || tool === "Bash")) {
  decide("deny", `${agent} は読むだけの役です。見つけたことは返事に書いて、親に返してください。`);
}

if (agent === "kanna-eval-writer" && WRITE_TOOLS.has(tool)) {
  const p = String(input.file_path || input.notebook_path || "").replaceAll("\\", "/");
  const inEvals = /(^|\/)evals\//.test(p) && !/(^|\/)evals\/results\//.test(p) && !p.split("/").includes("..");
  if (!inEvals) {
    decide("deny", `kanna-eval-writer が書けるのは evals/ の中（results/ を除く）だけです：${p || "（パスが無い）"}。スキルや本体を直す案は、返事に書いてください。`);
  }
}

if (tool === "Bash") {
  const cmd = String(input.command || "").replace(/\\\r?\n/g, " "); // 行末の \ でつないだ命令を 1 行にする
  // 複数の命令を ; && | でつないでいても、claude plugin eval の部分ごとに見る。
  for (const part of cmd.split(/;|&&|\|\||\n/)) {
    // kanna_run.py run は中で claude plugin eval を起こす（上限とモデルは kanna_run.py が必ず付ける）。上位のモデルだけ確かめる
    const kr = part.match(/kanna_run\.py["']?\s+run\b(.*)$/);
    if (kr) {
      const km = kr[1].match(/--model[\s=]+([^\s]+)/);
      if (km && LARGE_MODEL.test(km[1])) {
        decide("ask", `上位のモデル（${km[1]}）で eval を流します。下位のモデル（haiku・sonnet）で通ってから上げるのが kanna の手順です。よいですか。`);
      }
      continue;
    }
    const m = part.match(/\bclaude\s+plugins?\s+eval\b(.*)$/);
    if (!m) continue;
    const args = m[1];
    if (/^\s+init\b/.test(args) || /(^|\s)(--help|-h)(\s|$)/.test(args)) continue;
    if (!/--max-cost-usd[\s=]+\d/.test(args)) {
      decide("deny", "claude plugin eval には --max-cost-usd <上限> を付けてください（利用料に上限を置く）。まず --model haiku・--runs 1〜3・--case で絞って流します。");
    }
    const model = args.match(/--model[\s=]+([^\s]+)/);
    if (!model) {
      decide("deny", "claude plugin eval には --model を付けてください（既定のモデルに任せると、回ごとに比べられません）。まず haiku から流します。");
    }
    if (LARGE_MODEL.test(model[1])) {
      decide("ask", `上位のモデル（${model[1]}）で eval を流します。下位のモデル（haiku・sonnet）で通ってから上げるのが kanna の手順です。よいですか。`);
    }
    if (/--allow-real-servers|--mocks[\s=]+off/.test(args)) {
      decide("ask", "本物の MCP サーバーを起こして eval を流します（サンドボックスの外で、あなたとして動きます）。よいですか。");
    }
  }
}

process.exit(0);
