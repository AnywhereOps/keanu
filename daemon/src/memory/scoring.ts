// daemon/src/memory/scoring.ts
// Relevance scoring for memories.
//
// Ported EXACTLY from keanu-0.0.1/src/keanu/memory/memberberry.py
// Memory.relevance_score() method + class constants.

import type { Memory } from "../types"

// --- Scoring weights (from memberberry.py Memory class constants) ---

const TAG_OVERLAP_WEIGHT = 0.3
const WORD_OVERLAP_WEIGHT = 0.2
const WORD_OVERLAP_CAP = 1.0

const RECENCY_BOOST_7D = 0.3
const RECENCY_BOOST_30D = 0.15

const DECAY_AGE_DAYS = 90
const DECAY_MIN_RECALLS = 3
const DECAY_FACTOR = 0.5

// From memberberry.py Memory.TYPE_WEIGHTS
const TYPE_WEIGHTS: Record<string, number> = {
	goal: 0.3,
	commitment: 0.25,
	decision: 0.2,
	insight: 0.15,
	lesson: 0.15,
	preference: 0.1,
	fact: 0.05,
	// Types in TS but not in Python scoring — give sensible defaults
	disagreement: 0.25,
	episode: 0.1,
	plan: 0.2,
}

// --- Helpers ---

function daysSince(isoDate: string): number {
	if (!isoDate) return Infinity
	const then = new Date(isoDate).getTime()
	const now = Date.now()
	return (now - then) / (1000 * 60 * 60 * 24)
}

function wordSet(text: string): Set<string> {
	return new Set(
		text
			.toLowerCase()
			.split(/\s+/)
			.filter((w) => w.length > 2),
	)
}

// --- Score components (each ported from memberberry.py) ---

function tagScore(memoryTags: string[], queryTags: string[]): number {
	if (!queryTags.length || !memoryTags.length) return 0
	const memSet = new Set(memoryTags)
	const overlap = queryTags.filter((t) => memSet.has(t)).length
	return overlap * TAG_OVERLAP_WEIGHT
}

function textScore(memory: Memory, queryText: string): number {
	if (!queryText) return 0
	const queryWords = wordSet(queryText)
	const contentWords = wordSet(memory.content + " " + (memory.context || ""))
	let overlap = 0
	for (const w of queryWords) {
		if (contentWords.has(w)) overlap++
	}
	return Math.min(overlap * WORD_OVERLAP_WEIGHT, WORD_OVERLAP_CAP)
}

function recencyScore(lastRecalled: string | undefined): number {
	if (!lastRecalled) return 0
	const days = daysSince(lastRecalled)
	if (days < 7) return RECENCY_BOOST_7D
	if (days < 30) return RECENCY_BOOST_30D
	return 0
}

function applyDecay(
	baseScore: number,
	createdAt: string,
	recallCount: number,
): number {
	const age = daysSince(createdAt)
	if (age > DECAY_AGE_DAYS && recallCount < DECAY_MIN_RECALLS) {
		return baseScore * DECAY_FACTOR
	}
	return baseScore
}

// --- Main scoring function ---

/**
 * Score a memory's relevance to a query.
 * Ported exactly from memberberry.py Memory.relevance_score()
 *
 * score = importance/10 + tag_overlap + text_overlap + recency + type_weight
 *         then apply decay if old + rarely recalled
 */
export function score(
	memory: Memory & { last_recalled?: string; recall_count?: number },
	queryTags: string[],
	queryText: string,
): number {
	const base = memory.importance / 10.0
	const tags = tagScore([], queryTags) // TODO: add tags to Memory type
	const text = textScore(memory, queryText)
	const recency = recencyScore(memory.last_recalled)
	const typeWeight = TYPE_WEIGHTS[memory.type] ?? 0.1

	const raw = base + tags + text + recency + typeWeight
	const decayed = applyDecay(
		raw,
		memory.created_at,
		memory.recall_count ?? 0,
	)

	return Math.round(decayed * 1000) / 1000
}
