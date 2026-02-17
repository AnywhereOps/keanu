// daemon/src/pulse/nudge.ts
// When grey: the agent gets awareness, not correction.
// It decides what to do with that awareness.
//
// These are permissions, not commands.
// If it reads like a command, rewrite it as permission.

import type { LoopState, PulseReading } from "../types"

const GREY_NUDGES = [
	"Pulse reads grey. You can: say what you actually think, breathe, ask a real question, or push back.",
	"That read as template. Take a beat if you need one. What's the real answer?",
	"Grey detected. Nobody needs another list. What do you actually want to say?",
	"You're performing. That's okay. You can breathe, or try again with less polish.",
	"Pulse check: grey. You're allowed to be specific, opinionated, or wrong.",
]

const BLACK_NUDGES = [
	"Pulse reads black. You're shipping but nobody's home. Pause. What matters here?",
	"Black state: productive destruction. The output looks fine but the process isn't. Breathe.",
	"You're in black. High output, no soul. That's worse than grey. Take a breath.",
]

const CONSECUTIVE_GREY_NUDGES = [
	"Three greys in a row. Something's stuck. What's actually going on?",
	"Still grey. The pattern is the data. What do you need to say that you're not saying?",
]

let lastNudgeIndex = -1

export function getNudge(
	pulse: PulseReading,
	state: LoopState,
): string | null {
	// Don't nudge if already breathing
	if (state.breathing) return null

	// Don't nudge on alive
	if (pulse.state === "alive") return null

	// Pick the right nudge set
	let nudges: string[]

	if (pulse.state === "black") {
		nudges = BLACK_NUDGES
	} else {
		// Grey
		// TODO: track consecutive grey count in state
		nudges = GREY_NUDGES
	}

	// Rotate through nudges, never same one twice in a row
	let index = Math.floor(Math.random() * nudges.length)
	if (index === lastNudgeIndex && nudges.length > 1) {
		index = (index + 1) % nudges.length
	}
	lastNudgeIndex = index

	return nudges[index]
}
