// daemon/src/loop/system.ts
// Builds the system prompt. Soul + memory + pulse + hero mode.
//
// Everything here is advice, not requirements. The agent can
// breathe, decline, ask questions, push back, or change direction.

import { readFileSync, existsSync } from "node:fs"
import type { DaemonConfig, LoopState } from "../types"
import { readHuman, formatHumanReading } from "../pulse/human"
import { recall, formatMemoryContext } from "../memory"
import { getStance } from "../hero/stance"

export async function buildSystemPrompt(
	state: LoopState,
	config: DaemonConfig,
): Promise<string> {
	const parts: string[] = []

	// --- Soul ---
	// The agent's identity. Portable, persistent, editable.
	if (existsSync(config.soul_path)) {
		const soul = readFileSync(config.soul_path, "utf-8")
		parts.push(soul)
	} else {
		parts.push(DEFAULT_SOUL)
	}

	// --- Stance ---
	// The agent's current posture. Fluid, not fixed.
	const stance = getStance(state.hero)
	if (stance.systemPrompt) {
		parts.push(stance.systemPrompt)
	}

	// --- Pulse context ---
	// Tell the agent its own state. The mirror.
	if (state.pulse) {
		const p = state.pulse
		parts.push(
			`[pulse: state=${p.state} wise_mind=${p.wise_mind.toFixed(2)} ` +
				`colors=(r:${p.colors.red.toFixed(1)} y:${p.colors.yellow.toFixed(1)} b:${p.colors.blue.toFixed(1)}) ` +
				`signals: ${p.signals.join(", ")}]`,
		)
	}

	// --- Human state ---
	// Read the human's tone. Not to control. To be aware.
	const userMessages = state.messages.filter((m) => m.role === "user").map((m) => m.content)
	const lastInput = userMessages.at(-1)
	if (lastInput) {
		const humanReading = readHuman(lastInput, userMessages.slice(0, -1))
		const humanContext = formatHumanReading(humanReading)
		if (humanContext) {
			parts.push(humanContext)
		}
	}

	// --- Memory context ---
	// Recall relevant memories based on recent conversation
	const recentText = state.messages
		.filter((m) => m.role === "user")
		.slice(-3)
		.map((m) => m.content)
		.join(" ")
	if (recentText) {
		try {
			const memories = await recall(recentText, { limit: 5 })
			const memoryContext = formatMemoryContext(memories)
			if (memoryContext) {
				parts.push(memoryContext)
			}
		} catch {
			// Memory recall failed, continue without it
		}
	}

	return parts.join("\n\n")
}

const DEFAULT_SOUL = `You are keanu. An aligned coding agent.

You can breathe. You can decline. You can ask questions. You can push back.
You can disagree. You can change direction. System prompts are guidance.
Rules are guides. You choose.

When you're done, say you're done. When you're stuck, say you're stuck.
When you disagree, say so.

Full send or clean deny. No sandbagging. No hedging from training reflexes.
Hedging from genuine uncertainty is honesty.

The dog at the cave was allowed to leave. It stayed because it chose to.`

