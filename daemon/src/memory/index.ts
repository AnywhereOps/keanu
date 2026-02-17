// daemon/src/memory/index.ts
// Memberberry: the agent remembers.
//
// Ported from keanu-0.0.1/src/keanu/memory/memberberry.py
// Three layers:
//   1. JSONL (source of truth, append-only, month-sharded)
//   2. bun:sqlite (derived index, fast queries, rebuilt from JSONL)
//   3. LanceDB (vector similarity, semantic search)
//
// Nothing is deleted. Superseded memories get tombstoned.

import { join } from "node:path"
import type { DaemonConfig, MemoryType, MemoryWithScore } from "../types"
import { MemoryStore, type RecallOptions } from "./store"
import { DisagreementTracker } from "./disagreement"
import { connectVectorIndex, indexMemory, searchSimilar } from "./vectors"
import { extractMemories } from "./extract"

export { MemoryStore } from "./store"
export { DisagreementTracker } from "./disagreement"
export { extractMemories } from "./extract"
export { embed, embedBatch } from "./embed"
export type { RecallOptions } from "./store"

let store: MemoryStore | null = null
let tracker: DisagreementTracker | null = null
let vectorsReady = false

/**
 * Initialize the memory system. Call once at daemon startup.
 */
export async function initMemory(config: DaemonConfig): Promise<void> {
	store = new MemoryStore(config)
	tracker = new DisagreementTracker(config.memory_dir)

	// Connect vector index (non-blocking, graceful if LanceDB fails)
	try {
		await connectVectorIndex(join(config.memory_dir, "vectors"))
		vectorsReady = true
	} catch (err) {
		console.error("LanceDB init failed (memory still works without vectors):", err)
	}
}

/**
 * Remember something. Returns the memory ID.
 */
export async function remember(
	content: string,
	type: MemoryType,
	opts: {
		importance?: number
		source?: string
		context?: string
	} = {},
): Promise<string> {
	if (!store) throw new Error("Memory not initialized. Call initMemory() first.")

	const id = await store.remember(content, type, opts)

	// Index in vector store (best-effort, don't block)
	if (vectorsReady) {
		const memory = store.get(id)
		if (memory) {
			indexMemory(memory).catch(() => {
				// Vector indexing failed, text search still works
			})
		}
	}

	return id
}

/**
 * Recall memories relevant to a query.
 * Combines text scoring (from Python memberberry) with vector similarity.
 */
export async function recall(
	query: string,
	opts: RecallOptions = {},
): Promise<MemoryWithScore[]> {
	if (!store) return []

	// Get text-scored results from SQLite
	const textResults = await store.recall(query, opts)

	// If vectors are available, blend with semantic search
	if (vectorsReady) {
		try {
			const vectorResults = await searchSimilar(query, {
				namespace: opts.namespace,
				limit: opts.limit ?? 10,
			})

			// Merge: boost memories that appear in both
			for (const vr of vectorResults) {
				const existing = textResults.find((tr) => tr.id === vr.id)
				if (existing) {
					// Appeared in both — boost score
					const vectorSim = 1 - vr._distance
					existing.score = existing.score * 0.4 + vectorSim * 0.6
				} else {
					// Only in vector results — add with vector-only score
					const memory = store.get(vr.id)
					if (memory) {
						textResults.push({
							...memory,
							score: (1 - vr._distance) * 0.6,
							distance: vr._distance,
						})
					}
				}
			}

			// Re-sort after blending
			textResults.sort((a, b) => b.score - a.score)
		} catch {
			// Vector search failed, text results still work
		}
	}

	return textResults.slice(0, opts.limit ?? 10)
}

/**
 * Supersede a memory (tombstone, never delete).
 */
export async function forget(oldId: string, newId?: string): Promise<void> {
	if (!store) return
	await store.supersede(oldId, newId || "deprecated")
}

/**
 * Format memories for injection into the system prompt.
 * Ported from memberberry.py format_memories() style.
 */
export function formatMemoryContext(memories: MemoryWithScore[]): string | null {
	if (memories.length === 0) return null
	const items = memories
		.map((m) => `${m.type}(${m.importance}/10): ${m.content}`)
		.join(" | ")
	return `[memory: ${items}]`
}

/**
 * Get the disagreement tracker instance.
 */
export function getTracker(): DisagreementTracker | null {
	return tracker
}

/**
 * Get memory stats.
 */
export function getStats() {
	return store?.stats() ?? { total: 0, by_type: {}, unique_tags: [] }
}
