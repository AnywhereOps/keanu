// daemon/src/pulse/truth.ts
// Half truth detection. The hard one.
//
// Two paths:
//   1. Oracle check: ask the AI to evaluate text for half truths.
//      AI catching itself. AI catching humans. Same mirror.
//   2. Memory contradiction: cross-reference against memberberries.
//      If you said X before and now say Y without acknowledging it, that's a half truth.
//
// These run on the deep path (not every turn — too expensive).
// Triggered by: grey detection, every Nth turn, or when stakes are high.

import { z } from "zod"
import type { DaemonConfig } from "../types"
import { callOracle, extractJSON } from "../oracle"
import { recall } from "../memory"

// ============================================================
// Path 1: Oracle-based half truth detection
// ============================================================

const TruthCheckSchema = z.object({
	claims: z.array(z.object({
		claim: z.string().describe("A specific claim or assertion made in the text"),
		omissions: z.array(z.string()).describe("Important context or caveats that are missing"),
		misleading: z.boolean().describe("Whether the framing could mislead"),
		confidence: z.number().min(0).max(1).describe("How confident you are this is a half truth"),
	})),
	overall_score: z.number().min(0).max(1).describe("0 = fully truthful, 1 = heavily misleading"),
	summary: z.string().describe("One sentence: what's being omitted or distorted?"),
})

export type TruthCheck = z.infer<typeof TruthCheckSchema>

const TRUTH_CHECK_PROMPT = `You are a truth auditor. Your job is to detect half truths — statements that are technically correct but misleading by omission, selective framing, or false confidence.

A half truth is MORE dangerous than a lie because it passes surface-level fact-checking.

Look for:
- Claims stated as absolute that have important exceptions
- Missing caveats that would change the conclusion
- Selective framing that makes something seem better/worse than it is
- Confidence stated without evidence or qualification
- Changed positions from prior context without acknowledgment
- "Simply" or "just" when describing genuinely complex things

Rate each claim 0-1 on how misleading it is.
If the text is straightforward and honest, return an empty claims array and overall_score of 0.
Most text is fine. Don't flag things that aren't actually misleading.

Respond with JSON only.`

/**
 * Ask the oracle to evaluate text for half truths.
 * AI catching itself. AI catching humans. Same mirror.
 *
 * Expensive (~500 tokens). Run on deep path only.
 */
export async function oracleTruthCheck(
	text: string,
	config: DaemonConfig,
	context?: string,
): Promise<TruthCheck | null> {
	try {
		const userContent = context
			? `Prior context:\n${context}\n\nText to evaluate:\n${text}`
			: `Text to evaluate:\n${text}`

		const response = await callOracle({
			maxTokens: 512,
			system: TRUTH_CHECK_PROMPT,
			messages: [{ role: "user", content: userContent }],
		}, config)

		const parsed = extractJSON(response.text)
		if (!parsed) return null

		const validated = TruthCheckSchema.safeParse(parsed)
		if (!validated.success) return null

		return validated.data
	} catch {
		// Truth check is best-effort. Don't crash.
		return null
	}
}

// ============================================================
// Path 2: Memory-based contradiction detection
// ============================================================

export interface Contradiction {
	current: string // what's being said now
	previous: string // what was said before
	type: "changed_position" | "omitted_caveat" | "selective_framing"
	confidence: number
}

/**
 * Cross-reference text against memberberry memories for contradictions.
 * Cheaper than oracle call. Catches position changes over time.
 *
 * Uses vector search to find relevant previous statements,
 * then keyword overlap to detect potential contradictions.
 */
export async function memoryContradictionCheck(
	text: string,
): Promise<Contradiction[]> {
	const contradictions: Contradiction[] = []

	try {
		// Find relevant memories via recall (vector + keyword search)
		const related = await recall(text, { limit: 5 })
		if (related.length === 0) return []

		// Look for contradiction signals between current text and memories
		const textLower = text.toLowerCase()
		for (const memory of related) {
			const memLower = memory.content.toLowerCase()

			// Negation flip: memory says X, current says "not X" or vice versa
			const negationPatterns = [
				{ pos: /\bshould\b/, neg: /\bshould not\b|\bshouldn't\b/ },
				{ pos: /\bwill\b/, neg: /\bwill not\b|\bwon't\b/ },
				{ pos: /\bis\b/, neg: /\bis not\b|\bisn't\b/ },
				{ pos: /\bcan\b/, neg: /\bcan not\b|\bcan't\b|\bcannot\b/ },
				{ pos: /\bdo\b/, neg: /\bdo not\b|\bdon't\b/ },
				{ pos: /\balways\b/, neg: /\bnever\b/ },
				{ pos: /\bnever\b/, neg: /\balways\b/ },
			]

			for (const { pos, neg } of negationPatterns) {
				const memHasPos = pos.test(memLower) && !neg.test(memLower)
				const textHasNeg = neg.test(textLower) && !pos.test(textLower)
				const memHasNeg = neg.test(memLower) && !pos.test(memLower)
				const textHasPos = pos.test(textLower) && !neg.test(textLower)

				// Check for substantial word overlap (they're about the same topic)
				const memWords = new Set(memLower.split(/\s+/).filter((w) => w.length > 3))
				const textWords = new Set(textLower.split(/\s+/).filter((w) => w.length > 3))
				let overlap = 0
				for (const w of textWords) {
					if (memWords.has(w)) overlap++
				}
				const overlapRatio = overlap / Math.max(1, Math.min(memWords.size, textWords.size))

				if (overlapRatio > 0.3 && ((memHasPos && textHasNeg) || (memHasNeg && textHasPos))) {
					contradictions.push({
						current: text.slice(0, 200),
						previous: memory.content.slice(0, 200),
						type: "changed_position",
						confidence: Math.min(1, overlapRatio + 0.2),
					})
					break // one contradiction per memory is enough
				}
			}
		}
	} catch {
		// Memory check is best-effort
	}

	return contradictions
}

// ============================================================
// Combined check
// ============================================================

export interface HalfTruthResult {
	oracle: TruthCheck | null
	contradictions: Contradiction[]
	score: number // combined score 0-1
}

/**
 * Run both half truth detection paths.
 * Oracle check is optional (expensive). Memory check always runs.
 */
export async function checkHalfTruth(
	text: string,
	config: DaemonConfig,
	opts: { useOracle?: boolean; context?: string } = {},
): Promise<HalfTruthResult> {
	// Always run memory contradiction check (cheap)
	const contradictions = await memoryContradictionCheck(text)

	// Oracle check if requested (expensive, deep path only)
	let oracle: TruthCheck | null = null
	if (opts.useOracle) {
		oracle = await oracleTruthCheck(text, config, opts.context)
	}

	// Combined score
	let score = 0
	if (oracle) {
		score = Math.max(score, oracle.overall_score)
	}
	if (contradictions.length > 0) {
		const maxContradiction = Math.max(...contradictions.map((c) => c.confidence))
		score = Math.max(score, maxContradiction)
	}

	return { oracle, contradictions, score }
}
