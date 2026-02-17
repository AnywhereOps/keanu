// daemon/src/memory/vectors.ts
// LanceDB vector index for semantic memory search.
//
// The JSONL store is source of truth. This is a derived index
// for fast similarity search. Can be rebuilt from JSONL at any time.

import * as lancedb from "@lancedb/lancedb"
import { embed, EMBEDDING_DIM } from "./embed"
import type { Memory } from "../types"

let db: Awaited<ReturnType<typeof lancedb.connect>> | null = null
let table: Awaited<ReturnType<typeof db.openTable>> | null = null

const TABLE_NAME = "memories"

/**
 * Connect to (or create) the LanceDB index.
 */
export async function connectVectorIndex(indexDir: string): Promise<void> {
	db = await lancedb.connect(indexDir)

	// Check if table exists
	const tables = await db.tableNames()
	if (tables.includes(TABLE_NAME)) {
		table = await db.openTable(TABLE_NAME)
	}
	// If no table yet, it'll be created on first insert
}

/**
 * Index a memory's content as a vector.
 */
export async function indexMemory(memory: Memory): Promise<void> {
	if (!db) return

	const vector = await embed(memory.content)

	const row = {
		id: memory.id,
		vector,
		type: memory.type,
		content: memory.content,
		importance: memory.importance,
		namespace: memory.namespace,
		created_at: memory.created_at,
	}

	if (!table) {
		// Create table with first row
		table = await db.createTable(TABLE_NAME, [row])
	} else {
		await table.add([row])
	}
}

/**
 * Search for similar memories by text query.
 * Returns IDs and distances (lower = more similar).
 */
export async function searchSimilar(
	query: string,
	opts: { namespace?: string; limit?: number } = {},
): Promise<Array<{ id: string; _distance: number }>> {
	if (!table) return []

	const queryVector = await embed(query)
	let search = table.vectorSearch(queryVector).limit(opts.limit ?? 10)

	// Note: LanceDB where() filter uses SQL syntax
	if (opts.namespace) {
		search = search.where(`namespace = '${opts.namespace}'`)
	}

	const results = await search.toArray()
	return results.map((r) => ({
		id: r.id as string,
		_distance: r._distance as number,
	}))
}

/**
 * Check if the vector index is connected and ready.
 */
export function isReady(): boolean {
	return db !== null
}
