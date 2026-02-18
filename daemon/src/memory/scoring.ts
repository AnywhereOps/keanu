// daemon/src/memory/scoring.ts
// Relevance scoring for memories.
//
// Ported from keanu-0.0.1/src/keanu/memory/memberberry.py
// Simplified: removed recency/decay (not tracked in markdown store).

import type { Memory } from "../types"

// --- Scoring weights (from memberberry.py Memory class constants) ---

const TAG_OVERLAP_WEIGHT = 0.3
const WORD_OVERLAP_WEIGHT = 0.2
const WORD_OVERLAP_CAP = 1.0

// From memberberry.py Memory.TYPE_WEIGHTS
const TYPE_WEIGHTS: Record<string, number> = {
	goal: 0.3,
	commitment: 0.25,
	decision: 0.2,
	insight: 0.15,
	lesson: 0.15,
	preference: 0.1,
	fact: 0.05,
	disagreement: 0.25,
	episode: 0.1,
	plan: 0.2,
}

// --- Helpers ---

function wordSet(text: string): Set<string> {
	return new Set(
		text
			.toLowerCase()
			.split(/\s+/)
			.filter((w) => w.length > 2),
	)
}

// --- Score components ---

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

// --- Main scoring function ---

/**
 * Score a memory's relevance to a query.
 *
 * score = importance/10 + tag_overlap + text_overlap + type_weight
 */
export function score(
	memory: Memory,
	queryTags: string[],
	queryText: string,
): number {
	const base = memory.importance / 10.0
	const tags = tagScore(memory.tags || [], queryTags)
	const text = textScore(memory, queryText)
	const typeWeight = TYPE_WEIGHTS[memory.type] ?? 0.1

	const raw = base + tags + text + typeWeight
	return Math.round(raw * 1000) / 1000
}
