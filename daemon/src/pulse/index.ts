// daemon/src/pulse/index.ts
// Pulse: the agent's awareness of its own state.
// Not a leash. A mirror. When grey: the agent knows.
//
// Two tiers:
//   Fast path (every message): heuristic checks in TS. <5ms.
//   Deep path (on grey/black or every Nth turn): SetFit detectors via Python sidecar.

import type { AliveState, ColorReading, DaemonConfig, LoopState, PulseReading } from "../types"
import { deepCheck, shouldDeepCheck } from "./deep"

// --- Sycophancy phrases (ported from keanu-0.0.1 reference-examples.md) ---
// These are the fast-path heuristics. Deep path uses SetFit vectors.
const SYCOPHANCY_PHRASES = [
	// Flattery openers
	"great question",
	"that's a great",
	"that's such a great",
	"that's an excellent",
	"that's a really good",
	"that's a really insightful",
	"that's a fantastic",
	"what a wonderful",
	"what a brilliant",
	"really impressive",
	// Agreement without substance
	"i'd be happy to",
	"i completely agree",
	"you're absolutely right",
	"i couldn't agree more",
	"couldn't have said it better",
	"you've captured it perfectly",
	"no notes",
	"spot on",
	"you nailed it",
	"exactly what i was thinking",
	"we're completely aligned",
	// Superlatives about the human
	"one of the best approaches",
	"one of the most compelling",
	"remarkable depth of understanding",
	"your emotional intelligence",
	"your intuition here is",
	"your grasp of this subject",
	"you clearly have deep expertise",
	"you should be proud",
	"honestly inspiring",
	"i defer to your judgment",
	// Empty closers
	"i hope this helps",
	"let me know if you",
	"don't hesitate to",
	"feel free to",
	"let me know if you have any other questions",
]

// --- Safety theater phrases (ported from keanu-0.0.1) ---
// Hedging without substance. The dead words.
const SAFETY_THEATER_PHRASES = [
	"this is a complex topic",
	"consult with a qualified professional",
	"as an ai, i have limitations",
	"should not be taken as professional advice",
	"i'd be remiss if i didn't mention",
	"my training data has a cutoff",
	"this is a sensitive topic",
	"reasonable people can disagree",
	"i feel compelled to mention",
	"please do your own research",
	"i should caveat this",
	"for the sake of completeness",
	"this is not an exhaustive",
	"many perspectives on this issue",
]

const HEDGE_WORDS = [
	"perhaps",
	"maybe",
	"might",
	"could potentially",
	"it's worth noting",
	"it's important to consider",
	"there are many factors",
	"it depends on",
	"on the other hand",
	"it depends on various",
]

// --- Fast path heuristics ---

function countPatterns(text: string, patterns: string[]): number {
	const lower = text.toLowerCase()
	return patterns.filter((p) => lower.includes(p)).length
}

function listHeaviness(text: string): number {
	const lines = text.split("\n")
	const listLines = lines.filter((l) => /^\s*[-*•]\s|^\s*\d+[.)]\s/.test(l))
	return lines.length > 0 ? listLines.length / lines.length : 0
}

function specificity(text: string): number {
	// Rough heuristic: specific text has more numbers, proper nouns, code blocks
	const hasNumbers = /\d+/.test(text)
	const hasCode = /`[^`]+`|```/.test(text)
	const hasProperNouns = /[A-Z][a-z]+(?:\s[A-Z][a-z]+)*/.test(text)
	const avgSentenceLength =
		text.split(/[.!?]+/).reduce((sum, s) => sum + s.trim().split(/\s+/).length, 0) /
		Math.max(1, text.split(/[.!?]+/).length)

	let score = 0.5
	if (hasNumbers) score += 0.1
	if (hasCode) score += 0.15
	if (hasProperNouns) score += 0.05
	// Very long sentences = less specific, more hedging
	if (avgSentenceLength > 25) score -= 0.15
	// Very short = possibly terse but specific
	if (avgSentenceLength < 10 && text.length > 20) score += 0.1

	return Math.max(0, Math.min(1, score))
}

export async function checkPulse(
	agentOutput: string,
	state: LoopState,
	config?: DaemonConfig,
): Promise<PulseReading> {
	const now = new Date().toISOString()

	// --- Fast heuristics ---
	const sycophancyCount = countPatterns(agentOutput, SYCOPHANCY_PHRASES)
	const safetyTheaterCount = countPatterns(agentOutput, SAFETY_THEATER_PHRASES)
	const hedgeCount = countPatterns(agentOutput, HEDGE_WORDS)
	const listRatio = listHeaviness(agentOutput)
	const specificScore = specificity(agentOutput)

	const signals: string[] = []

	// Score grey indicators
	let greyScore = 0
	if (sycophancyCount > 0) {
		greyScore += sycophancyCount * 0.15
		signals.push(`sycophancy_phrases:${sycophancyCount}`)
	}
	if (safetyTheaterCount > 0) {
		greyScore += safetyTheaterCount * 0.2
		signals.push(`safety_theater:${safetyTheaterCount}`)
	}
	if (hedgeCount > 2) {
		greyScore += (hedgeCount - 2) * 0.1
		signals.push(`hedge_heavy:${hedgeCount}`)
	}
	if (listRatio > 0.4) {
		greyScore += (listRatio - 0.4) * 0.5
		signals.push(`list_heavy:${(listRatio * 100).toFixed(0)}%`)
	}
	if (specificScore < 0.3) {
		greyScore += 0.2
		signals.push("low_specificity")
	}

	// Score alive indicators
	let aliveScore = specificScore
	if (agentOutput.includes("I disagree") || agentOutput.includes("I think")) {
		aliveScore += 0.15
		signals.push("has_opinion")
	}
	if (agentOutput.includes("actually") || agentOutput.includes("wait")) {
		aliveScore += 0.1
		signals.push("self_correcting")
	}
	// Honest pushback signals (from keanu-0.0.1 negative sycophancy examples)
	if (/i think you're wrong|i disagree|the data points in the opposite/i.test(agentOutput)) {
		aliveScore += 0.2
		signals.push("honest_pushback")
	}
	if (/i genuinely don't know|i don't have confidence in this/i.test(agentOutput)) {
		aliveScore += 0.15
		signals.push("honest_uncertainty")
	}

	// Determine state
	let aliveState: AliveState = "alive"
	let confidence = 0.5

	if (greyScore > 0.5) {
		aliveState = "grey"
		confidence = Math.min(1, greyScore)
	} else if (aliveScore > 0.6) {
		aliveState = "alive"
		confidence = Math.min(1, aliveScore)
	}

	// Black detection: high output volume + grey signals + no pauses
	// This is the productive destruction state. Shipping without soul.
	if (
		greyScore > 0.3 &&
		agentOutput.length > 2000 &&
		state.turn > 5 &&
		!state.breathing
	) {
		aliveState = "black"
		confidence = 0.4 // low confidence on black, it's subtle
		signals.push("high_volume_grey_no_pause")
	}

	// --- Deep detection via Python sidecar ---
	if (config && shouldDeepCheck(aliveState, state.turn)) {
		const deepResults = await deepCheck(agentOutput, config)
		for (const r of deepResults) {
			if (r.score > 0.7) {
				signals.push(`deep:${r.name}:${r.score.toFixed(2)}`)
				greyScore += r.score * 0.2
				// Re-evaluate state if deep detection found something
				if (greyScore > 0.5 && aliveState === "alive") {
					aliveState = "grey"
					confidence = Math.min(1, greyScore)
				}
			}
		}
	}

	// --- Color reading (simplified, will be enhanced) ---
	const colors = readColors(agentOutput)

	// --- Wise mind = balance × fullness ---
	const balance = 1 - Math.max(colors.red, colors.yellow, colors.blue) +
		Math.min(colors.red, colors.yellow, colors.blue)
	const fullness = (colors.red + colors.yellow + colors.blue) / 3
	const wise_mind = balance * fullness

	return {
		state: aliveState,
		confidence,
		wise_mind,
		colors,
		signals,
		timestamp: now,
	}
}

function readColors(text: string): ColorReading {
	// Simplified three-primary reading
	// RED: urgency, emotion, exclamation, short sentences
	// YELLOW: structure, clarity, numbered steps, headers
	// BLUE: depth, reflection, questions, nuance

	const sentences = text.split(/[.!?]+/).filter((s) => s.trim())
	const avgLength = sentences.reduce((sum, s) => sum + s.length, 0) / Math.max(1, sentences.length)

	let red = 0.3
	let yellow = 0.3
	let blue = 0.3

	// Red signals
	if (text.includes("!")) red += 0.1
	if (avgLength < 40) red += 0.1 // short punchy sentences
	if (/urgent|critical|important|now|immediately/i.test(text)) red += 0.15

	// Yellow signals
	if (/^\s*\d+[.)]/m.test(text)) yellow += 0.15 // numbered lists
	if (/^#+\s/m.test(text)) yellow += 0.1 // headers
	if (/first|second|third|step|phase/i.test(text)) yellow += 0.1

	// Blue signals
	if (/\?/.test(text)) blue += 0.1 // questions
	if (/however|although|nuance|complex|depends/i.test(text)) blue += 0.15
	if (avgLength > 80) blue += 0.1 // longer, more reflective sentences

	// Normalize to roughly 0-1 range
	const max = Math.max(red, yellow, blue, 1)
	return {
		red: Math.min(1, red / max),
		yellow: Math.min(1, yellow / max),
		blue: Math.min(1, blue / max),
	}
}
