// daemon/src/hero/shift.ts
// Stance shifting. The agent signals, the loop permits.
//
// Inspired by keanu-0.0.1/src/keanu/hero/coordinate.py — agents shift roles
// as the situation demands. Permission, not control.
//
// The agent includes [stance: name] in its response to request a shift.
// The loop detects it, validates, and applies. No forbidden transitions.

import type { HeroMode, LoopState, StanceTransition } from "../types"

const VALID_STANCES = new Set<string>([
	"chat",
	"do",
	"craft",
	"prove",
	"dream",
	"speak",
])

// Match [stance: name] in agent response
const STANCE_SIGNAL = /\[stance:\s*(\w+)\]/i

/**
 * Detect a stance shift signal in the agent's response.
 * Returns the requested stance name, or null if no shift requested.
 */
export function detectShift(
	response: string,
	currentStance: string,
): HeroMode | null {
	const match = response.match(STANCE_SIGNAL)
	if (!match) return null

	const requested = match[1].toLowerCase()
	if (!VALID_STANCES.has(requested)) return null
	if (requested === currentStance) return null // already there

	return requested as HeroMode
}

/**
 * Apply a stance shift to the loop state.
 * Logs the transition and checks for thrashing.
 */
export function applyShift(
	state: LoopState,
	newStance: HeroMode,
): { state: LoopState; signals: string[] } {
	const signals: string[] = []

	const transition: StanceTransition = {
		from: state.hero,
		to: newStance,
		turn: state.turn,
		timestamp: new Date().toISOString(),
	}

	// Initialize history if needed
	if (!state.stanceHistory) {
		state.stanceHistory = []
	}

	state.stanceHistory.push(transition)
	state.hero = newStance

	// Check for thrashing: >3 shifts in last 5 turns
	const recentShifts = state.stanceHistory.filter(
		(t) => t.turn > state.turn - 5,
	)
	if (recentShifts.length > 3) {
		signals.push("stance_thrashing")
	}

	return { state, signals }
}
