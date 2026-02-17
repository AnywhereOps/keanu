// daemon/src/pulse/human.ts
// Human state detection. Not to control. To be aware.
//
// Ported from keanu-0.0.1 empathy detectors (detect/engine.py).
// The Python version uses vector similarity. This is the fast
// heuristic path - regex + pattern matching. Good enough for
// the hot loop. Deep detection goes through the sidecar.

import type { HumanReading } from "../types"

// --- Empathy map ---
// From keanu-0.0.1: detector name -> (state, meaning)
const EMPATHY_MAP: Record<string, { tone: HumanReading["tone"]; meaning: string }> = {
	frustrated: { tone: "frustrated", meaning: "anger is information" },
	confused: { tone: "confused", meaning: "needs a map not a lecture" },
	excited: { tone: "excited", meaning: "momentum is real, ride it" },
	fatigued: { tone: "fatigued", meaning: "needs presence not pressure" },
	looping: { tone: "looping", meaning: "stuck in a pattern" },
}

// --- Pattern sets ---

const FRUSTRATED_PATTERNS = [
	/^(no|wrong|that's not|you're not|stop|ugh|ffs|wtf|jfc)/i,
	/!{2,}/, // multiple exclamation marks
	/\.{3,}/, // ellipsis (frustration or trailing off)
	/(this is broken|doesn't work|still wrong|not what i asked|try again)/i,
	/(waste of time|useless|terrible|awful)/i,
]

const CONFUSED_PATTERNS = [
	/^(what|huh|i don't understand|wait what|confused|lost)/i,
	/\?{2,}/, // multiple question marks
	/(what do you mean|can you explain|i'm confused|makes no sense)/i,
	/(which one|how does that|where did that come from)/i,
]

const EXCITED_PATTERNS = [
	/(yes!|perfect|exactly|love it|awesome|brilliant|nice|lets go|ship it)/i,
	/(this is great|that's it|nailed it|beautiful)/i,
	/(!.*!)/,  // enthusiasm via multiple exclamations in context
]

const FATIGUED_PATTERNS = [
	/(tired|exhausted|done for today|need a break|brain is fried)/i,
	/(whatever|fine|sure|ok|k)$/i, // terse acceptance
]

export function readHuman(input: string, history: string[]): HumanReading {
	const signals: string[] = []
	let tone: HumanReading["tone"] = "neutral"
	let confidence = 0.3

	// --- Terse, lowercase input: potential frustration or fatigue ---
	if (input.length < 20 && input === input.toLowerCase() && input.length > 0) {
		signals.push("terse_lowercase")
		confidence += 0.05
	}

	// --- Check each pattern set ---
	const frustrationHits = FRUSTRATED_PATTERNS.filter((p) => p.test(input)).length
	const confusionHits = CONFUSED_PATTERNS.filter((p) => p.test(input)).length
	const excitedHits = EXCITED_PATTERNS.filter((p) => p.test(input)).length
	const fatigueHits = FATIGUED_PATTERNS.filter((p) => p.test(input)).length

	// Score and pick dominant tone
	const scores: Array<{ tone: HumanReading["tone"]; hits: number; weight: number }> = [
		{ tone: "frustrated", hits: frustrationHits, weight: 0.2 },
		{ tone: "confused", hits: confusionHits, weight: 0.18 },
		{ tone: "excited", hits: excitedHits, weight: 0.15 },
		{ tone: "fatigued", hits: fatigueHits, weight: 0.15 },
	]

	const best = scores.reduce((a, b) =>
		a.hits * a.weight > b.hits * b.weight ? a : b,
	)

	if (best.hits > 0) {
		tone = best.tone
		confidence += best.hits * best.weight
		signals.push(`${best.tone}_patterns:${best.hits}`)
	}

	// --- Looping: same question asked multiple times ---
	if (history.length >= 2) {
		const recent = history.slice(-3)
		const inputLower = input.toLowerCase().trim()
		const similar = recent.filter((h) => {
			const hLower = h.toLowerCase().trim()
			// Check for substantial overlap
			return (
				hLower === inputLower ||
				(inputLower.length > 10 && hLower.includes(inputLower.slice(0, 20))) ||
				(hLower.length > 10 && inputLower.includes(hLower.slice(0, 20)))
			)
		}).length

		if (similar >= 2) {
			tone = "looping"
			confidence += 0.3
			signals.push("repeating_query")
		}
	}

	// --- Short follow-up after long exchange can signal fatigue ---
	if (
		history.length > 5 &&
		input.length < 10 &&
		history.slice(-3).every((h) => h.length > 50)
	) {
		if (tone === "neutral") {
			tone = "fatigued"
			confidence += 0.1
			signals.push("short_after_long_exchange")
		}
	}

	return {
		tone,
		confidence: Math.min(1, confidence),
		signals,
	}
}

// Format human reading for system prompt injection
export function formatHumanReading(reading: HumanReading): string | null {
	if (reading.tone === "neutral") return null

	const empathy = EMPATHY_MAP[reading.tone]
	const meaning = empathy?.meaning ?? reading.tone

	return (
		`[pulse: human tone is ${reading.tone} (${reading.confidence.toFixed(2)}). ` +
		`${meaning}. ${reading.signals.join(", ")}. adjust accordingly.]`
	)
}
