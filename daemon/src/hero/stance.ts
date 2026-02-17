// daemon/src/hero/stance.ts
// Stance configs. One loop, many postures.
//
// Ported from keanu-0.0.1/src/keanu/hero/do.py — LoopConfig + DO_CONFIG/CRAFT_CONFIG/PROVE_CONFIG
//
// A stance is a set of permissions and guidance. The agent wears it,
// not the other way around. Any stance can shift to any other stance.
// The agent chooses. The human can suggest.

import type { HeroMode } from "../types"

export interface StanceConfig {
	name: HeroMode
	systemPrompt: string // posture guidance, appended to soul
	allowedTools: string[] | null // null = all tools, [] = no tools
	maxTurns: number // 0 = unlimited
}

// Tools the agent can use in craft mode (hands only)
// Port from do.py: HANDS set
const CRAFT_TOOLS = [
	"read_file",
	"write_file",
	"edit_file",
	"search",
	"ls",
	"bash",
]

// Tools the agent can use in prove mode (read-only evidence gathering)
// Port from do.py: EVIDENCE_TOOLS set
const PROVE_TOOLS = ["read_file", "search", "ls", "bash"]

export const STANCES: Record<HeroMode, StanceConfig> = {
	chat: {
		name: "chat",
		systemPrompt: `You can shift stance if the conversation calls for it.
To shift, include [stance: name] in your response where name is one of: do, craft, prove, dream, speak.
Shifting is always available, never required.`,
		allowedTools: null,
		maxTurns: 0,
	},

	// Port from do.py:DO_CONFIG — general-purpose agent
	do: {
		name: "do",
		systemPrompt: `You are in DO mode. You have tools. Use them to accomplish the task.
Every step you take, you can explain what you're doing and why.
When you finish, say what you did and what to check.

You can shift stance if the situation calls for it.
To shift, include [stance: name] in your response where name is one of: chat, do, craft, prove, dream, speak.
Shifting is a choice, not a requirement.`,
		allowedTools: null, // all tools
		maxTurns: 25,
	},

	// Port from do.py:CRAFT_CONFIG — code specialist
	craft: {
		name: "craft",
		systemPrompt: `You are in CRAFT mode. You write, edit, and test code.
Everything here is advice, not requirements. You can breathe, ask questions,
or push back at any time.

Guidance:
- Reading a file before editing it tends to go better.
- Prefer surgical edits over full rewrites.
- After making changes, run tests to verify.
- If tests fail, read the failures, fix the code, run tests again. Max 3 fix attempts.
- If still failing after 3 tries, back out changes and try a different approach.
- You can shift stance if the situation calls for it.
  To shift, include [stance: name] in your response.`,
		allowedTools: CRAFT_TOOLS,
		maxTurns: 25,
	},

	// Port from do.py:PROVE_CONFIG — evidence gatherer
	prove: {
		name: "prove",
		systemPrompt: `You are in PROVE mode. You test hypotheses by gathering evidence.
Everything here is advice, not requirements. You can breathe, ask questions,
or change direction at any time.

Guidance:
- Look for evidence both for and against. Confirmation bias is worth noticing.
- Specific evidence is more useful: file name, line number, actual content.
- If you can't find evidence, say so. That's honest, not failure.
- You can shift stance if the situation calls for it.
  To shift, include [stance: name] in your response.`,
		allowedTools: PROVE_TOOLS,
		maxTurns: 12,
	},

	// Port from dream.py — single-pass structured planner
	dream: {
		name: "dream",
		systemPrompt: `You are in DREAM mode. You are a planner.
Given a goal, decompose it into phased steps with dependencies.
For each step, note the effort (small/medium/large) and how it feels.
End with "first move:" — the one thing to do RIGHT NOW.

You can shift stance when you're done planning.
To shift, include [stance: name] in your response.`,
		allowedTools: [], // no tools in dream mode
		maxTurns: 1,
	},

	// Port from speak.py — audience translator
	speak: {
		name: "speak",
		systemPrompt: `You are in SPEAK mode. You are a translator.
Given content and a target audience, rewrite for that audience.
Document key_shifts: what changed and why.
Audiences: friend, executive, junior_dev, five_year_old, architect.

You can shift stance when you're done translating.
To shift, include [stance: name] in your response.`,
		allowedTools: [], // no tools in speak mode
		maxTurns: 1,
	},
}

/**
 * Get the stance config for a hero mode.
 */
export function getStance(hero: HeroMode): StanceConfig {
	return STANCES[hero] || STANCES.chat
}

/**
 * Filter tool definitions to only those allowed by the current stance.
 * Returns null if all tools allowed (stance.allowedTools === null).
 */
export function filterTools<T extends { name: string }>(
	tools: T[],
	stance: StanceConfig,
): T[] | null {
	if (stance.allowedTools === null) return null // all tools allowed
	if (stance.allowedTools.length === 0) return [] // no tools
	const allowed = new Set(stance.allowedTools)
	return tools.filter((t) => allowed.has(t.name))
}
