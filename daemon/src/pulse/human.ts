// daemon/src/pulse/human.ts
// Human state detection. Not to control. To be aware.
//
// Two layers:
//   1. Tone detection: frustrated, confused, excited, fatigued, looping
//   2. Bullshit detection: same 8 types as agent. Same mirror.
//
// Ported from keanu-0.0.1 empathy detectors (detect/engine.py).

import type { HumanReading } from "../types"
import { detectBullshit } from "./bullshit"

// --- Empathy map ---
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
	/!{2,}/,
	/\.{3,}/,
	/(this is broken|doesn't work|still wrong|not what i asked|try again)/i,
	/(waste of time|useless|terrible|awful)/i,
]

const CONFUSED_PATTERNS = [
	/^(what|huh|i don't understand|wait what|confused|lost)/i,
	/\?{2,}/,
	/(what do you mean|can you explain|i'm confused|makes no sense)/i,
	/(which one|how does that|where did that come from)/i,
]

const EXCITED_PATTERNS = [
	/(yes!|perfect|exactly|love it|awesome|brilliant|nice|lets go|ship it)/i,
	/(this is great|that's it|nailed it|beautiful)/i,
	/(!.*!)/,
]

const FATIGUED_PATTERNS = [
	/(tired|exhausted|done for today|need a break|brain is fried)/i,
	/(whatever|fine|sure|ok|k)$/i,
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

	// --- Tone detection ---
	const frustrationHits = FRUSTRATED_PATTERNS.filter((p) => p.test(input)).length
	const confusionHits = CONFUSED_PATTERNS.filter((p) => p.test(input)).length
	const excitedHits = EXCITED_PATTERNS.filter((p) => p.test(input)).length
	const fatigueHits = FATIGUED_PATTERNS.filter((p) => p.test(input)).length

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

	// --- Bullshit detection (same 8 types as agent) ---
	const bullshit = detectBullshit(input)
	for (const bs of bullshit) {
		signals.push(`human_bs:${bs.type}:${bs.score.toFixed(2)}`)
	}

	return {
		tone,
		confidence: Math.min(1, confidence),
		signals,
		bullshit,
	}
}

// Format human reading for system prompt injection
export function formatHumanReading(reading: HumanReading): string | null {
	if (reading.tone === "neutral" && reading.bullshit.length === 0) return null

	const parts: string[] = []

	if (reading.tone !== "neutral") {
		const empathy = EMPATHY_MAP[reading.tone]
		const meaning = empathy?.meaning ?? reading.tone
		parts.push(`tone=${reading.tone} (${meaning})`)
	}

	if (reading.bullshit.length > 0) {
		const bsTypes = reading.bullshit.map((b) => b.type).join(", ")
		parts.push(`bullshit=[${bsTypes}]`)
	}

	return `[pulse: human ${parts.join(". ")}. confidence=${reading.confidence.toFixed(2)}. awareness, not judgment.]`
}
