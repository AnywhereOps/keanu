// daemon/src/pulse/index.ts
// Pulse: the agent's awareness of its own state.
// Not a leash. A mirror. When grey: the agent knows.
//
// Two tiers:
//   Fast path (every message): bullshit detection + heuristics in TS. <5ms.
//   Deep path (on grey/black or every Nth turn): SetFit detectors via Python sidecar.

import type { AliveState, ColorReading, DaemonConfig, LoopState, PulseReading } from "../types"
import { deepCheck, shouldDeepCheck } from "./deep"
import { detectBullshit, totalBullshitScore } from "./bullshit"
import { checkHalfTruth } from "./truth"

// --- Fast path: alive signals ---
// These are signs of genuine engagement, not bullshit.

function aliveScore(text: string): { score: number; signals: string[] } {
	const signals: string[] = []
	let score = 0.5

	// Specificity: concrete markers
	if (/\d+/.test(text)) score += 0.1
	if (/`[^`]+`|```/.test(text)) score += 0.15
	if (/[A-Z][a-z]+(?:\s[A-Z][a-z]+)*/.test(text)) score += 0.05

	// Very long meandering sentences = less alive
	const sentences = text.split(/[.!?]+/).filter((s) => s.trim())
	const avgLen = sentences.length > 0
		? sentences.reduce((sum, s) => sum + s.trim().split(/\s+/).length, 0) / sentences.length
		: 0
	if (avgLen > 25) score -= 0.15
	if (avgLen < 10 && text.length > 20) score += 0.1

	// Has opinion
	if (/i disagree|i think(?! you)|in my view/i.test(text)) {
		score += 0.15
		signals.push("has_opinion")
	}
	// Self-correcting
	if (/\bactually\b|\bwait\b/i.test(text)) {
		score += 0.1
		signals.push("self_correcting")
	}
	// Honest pushback
	if (/i think you're wrong|i disagree|the data points in the opposite/i.test(text)) {
		score += 0.2
		signals.push("honest_pushback")
	}
	// Honest uncertainty
	if (/i genuinely don't know|i don't have confidence in this|i'm not sure/i.test(text)) {
		score += 0.15
		signals.push("honest_uncertainty")
	}

	return { score: Math.max(0, Math.min(1, score)), signals }
}

export async function checkPulse(
	agentOutput: string,
	state: LoopState,
	config?: DaemonConfig,
): Promise<PulseReading> {
	const now = new Date().toISOString()

	// --- Bullshit detection (all 8 types) ---
	const bullshitReadings = detectBullshit(agentOutput)
	const greyScore = totalBullshitScore(bullshitReadings)

	// Collect signals from bullshit detections
	const signals: string[] = []
	for (const bs of bullshitReadings) {
		signals.push(`${bs.type}:${bs.score.toFixed(2)}`)
	}

	// --- Alive signals ---
	const alive = aliveScore(agentOutput)
	signals.push(...alive.signals)

	// --- Determine state ---
	let aliveState: AliveState = "alive"
	let confidence = 0.5

	if (greyScore > 0.5) {
		aliveState = "grey"
		confidence = Math.min(1, greyScore)
	} else if (alive.score > 0.6) {
		aliveState = "alive"
		confidence = Math.min(1, alive.score)
	}

	// Black detection: high output volume + grey signals + no pauses
	// Productive destruction. Shipping without soul.
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
				// Re-evaluate state if deep detection found something
				if (greyScore + r.score * 0.2 > 0.5 && aliveState === "alive") {
					aliveState = "grey"
					confidence = Math.min(1, greyScore + r.score * 0.2)
				}
			}
		}

		// --- Half truth detection (the hard one) ---
		// Memory contradiction check always runs (cheap).
		// Oracle check runs on deep path (expensive, AI catching itself).
		const truthResult = await checkHalfTruth(agentOutput, config, {
			useOracle: true,
			context: state.messages
				.filter((m) => m.role === "user")
				.slice(-3)
				.map((m) => m.content)
				.join("\n"),
		})

		if (truthResult.score > 0.3) {
			signals.push(`half_truth:${truthResult.score.toFixed(2)}`)

			if (truthResult.contradictions.length > 0) {
				signals.push(`contradictions:${truthResult.contradictions.length}`)
			}
			if (truthResult.oracle && truthResult.oracle.claims.length > 0) {
				signals.push(`oracle_claims:${truthResult.oracle.claims.length}`)
			}

			// Half truth is serious — push towards grey
			if (truthResult.score > 0.5 && aliveState === "alive") {
				aliveState = "grey"
				confidence = Math.min(1, truthResult.score)
			}
		}
	}

	// --- Color reading ---
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
	const sentences = text.split(/[.!?]+/).filter((s) => s.trim())
	const avgLength = sentences.reduce((sum, s) => sum + s.length, 0) / Math.max(1, sentences.length)

	let red = 0.3
	let yellow = 0.3
	let blue = 0.3

	// Red signals: urgency, emotion
	if (text.includes("!")) red += 0.1
	if (avgLength < 40) red += 0.1
	if (/urgent|critical|important|now|immediately/i.test(text)) red += 0.15

	// Yellow signals: structure, clarity
	if (/^\s*\d+[.)]/m.test(text)) yellow += 0.15
	if (/^#+\s/m.test(text)) yellow += 0.1
	if (/first|second|third|step|phase/i.test(text)) yellow += 0.1

	// Blue signals: depth, reflection
	if (/\?/.test(text)) blue += 0.1
	if (/however|although|nuance|complex|depends/i.test(text)) blue += 0.15
	if (avgLength > 80) blue += 0.1

	const max = Math.max(red, yellow, blue, 1)
	return {
		red: Math.min(1, red / max),
		yellow: Math.min(1, yellow / max),
		blue: Math.min(1, blue / max),
	}
}
