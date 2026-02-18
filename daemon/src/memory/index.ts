// daemon/src/memory/index.ts
// Memberberry: the agent remembers.
//
// Pure markdown + LanceDB. No SQLite, no JSONL.
//
// Source of truth: markdown files in ~/memberberries/
// Derived index: LanceDB vectors (rebuildable)
// Git-backed: lockfile-guarded commit/sync

import type { DaemonConfig, MemoryType, MemoryWithScore } from "../types"
import { MemoryStore, type RecallOptions } from "./store"
import { DisagreementTracker } from "./disagreement"
import { loadMemoryMd, ensureMemoryMd } from "./markdown"
import { ensureRepo } from "./git"
import { extractMemories } from "./extract"

export { MemoryStore } from "./store"
export { DisagreementTracker } from "./disagreement"
export { extractMemories } from "./extract"
export { embed, embedBatch } from "./embed"
export { flushMemories } from "./flush"
export { loadMemoryMd } from "./markdown"
export type { RecallOptions } from "./store"

let store: MemoryStore | null = null
let tracker: DisagreementTracker | null = null

/**
 * Initialize the memory system. Call once at daemon startup.
 */
export async function initMemory(config: DaemonConfig): Promise<void> {
	// Ensure memberberry repo exists
	ensureRepo(config.memberberry_dir)
	ensureMemoryMd(config.memberberry_dir, config.hero_name)

	// Init store (markdown + LanceDB)
	store = new MemoryStore(config)
	await store.init()

	// Disagreement tracker (still JSONL — it's a ledger, not memories)
	tracker = new DisagreementTracker(config.memory_dir)
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
		tags?: string[]
	} = {},
): Promise<string> {
	if (!store) throw new Error("Memory not initialized. Call initMemory() first.")
	return store.remember(content, type, opts)
}

/**
 * Recall memories relevant to a query.
 * Combines vector similarity with keyword scoring.
 */
export async function recall(
	query: string,
	opts: RecallOptions = {},
): Promise<MemoryWithScore[]> {
	if (!store) return []
	return store.recall(query, opts)
}

/**
 * Format memories for injection into the system prompt.
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
