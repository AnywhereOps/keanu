// daemon/src/memory/store.ts
// Memberberry: the agent remembers.
//
// Pure markdown storage + LanceDB vector index.
//
// Source of truth: markdown files (memory-{hero}-{date}.md)
// Derived index: LanceDB (vectors + metadata columns, rebuildable)
// No SQLite. No JSONL.

import * as lancedb from "@lancedb/lancedb"
import { existsSync, mkdirSync } from "node:fs"
import { join } from "node:path"
import type {
	Memory,
	MemoryType,
	MemoryWithScore,
	DaemonConfig,
} from "../types"
import { score } from "./scoring"
import { embed, embedBatch, EMBEDDING_DIM } from "./embed"
import {
	appendDailyLog,
	parseDailyLog,
	findDailyLogs,
	type DailyEntry,
} from "./markdown"

// --- Hashing ---

function contentHash(content: string): string {
	const hasher = new Bun.CryptoHasher("sha256")
	hasher.update(content)
	return hasher.digest("hex").slice(0, 16)
}

function memoryId(content: string, createdAt: string): string {
	const hasher = new Bun.CryptoHasher("sha256")
	hasher.update(content + createdAt)
	return hasher.digest("hex").slice(0, 12)
}

// --- Store ---

export interface RecallOptions {
	hero?: string
	type?: MemoryType
	tags?: string[]
	limit?: number
}

export interface MemoryStats {
	total: number
	by_type: Record<string, number>
	unique_tags: string[]
}

const TABLE_NAME = "memories"

export class MemoryStore {
	private memberberryDir: string
	private heroName: string
	private contentHashes: Set<string> = new Set()
	private db: Awaited<ReturnType<typeof lancedb.connect>> | null = null
	private table: Awaited<ReturnType<typeof lancedb.connect.prototype.openTable>> | null = null
	private vectorsReady = false

	// In-memory cache of all parsed memories (for keyword search fallback)
	private memoryCache: Memory[] = []

	constructor(
		private config: DaemonConfig,
	) {
		this.memberberryDir = config.memberberry_dir
		this.heroName = config.hero_name
		if (!existsSync(this.memberberryDir)) mkdirSync(this.memberberryDir, { recursive: true })
	}

	/**
	 * Initialize LanceDB and rebuild index from markdown files.
	 * Call once at startup.
	 */
	async init(): Promise<void> {
		const vectorDir = join(this.memberberryDir, "vectors")
		if (!existsSync(vectorDir)) mkdirSync(vectorDir, { recursive: true })

		try {
			this.db = await lancedb.connect(vectorDir)

			// Check if table exists
			const tables = await this.db.tableNames()
			if (tables.includes(TABLE_NAME)) {
				this.table = await this.db.openTable(TABLE_NAME)
			}

			this.vectorsReady = true
		} catch (err) {
			console.error("LanceDB init failed (keyword search still works):", err)
		}

		// Load all memories from markdown into cache
		await this.rebuildCache()
	}

	/**
	 * Rebuild in-memory cache from markdown files.
	 * Also rebuilds LanceDB if empty.
	 */
	private async rebuildCache(): Promise<void> {
		this.memoryCache = []
		this.contentHashes.clear()

		// Parse all daily log files (all heroes — reading is shared)
		const logFiles = findDailyLogs(this.memberberryDir)
		for (const file of logFiles) {
			const entries = parseDailyLog(file)
			for (const entry of entries) {
				const now = `${entry.date}T00:00:00.000Z`
				const hash = contentHash(entry.content)
				const id = memoryId(entry.content, now)

				const memory: Memory = {
					id,
					type: entry.type as MemoryType,
					content: entry.content,
					source: "daily-log",
					context: entry.sessionId || "",
					importance: entry.importance,
					hero: entry.hero,
					created_at: now,
					hash,
					tags: entry.tags,
				}

				this.memoryCache.push(memory)
				this.contentHashes.add(hash)
			}
		}

		// If LanceDB is ready and table is empty/missing, rebuild vectors
		if (this.vectorsReady && this.memoryCache.length > 0 && !this.table) {
			await this.rebuildVectors()
		}
	}

	/**
	 * Batch-embed all cached memories into LanceDB.
	 */
	private async rebuildVectors(): Promise<void> {
		if (!this.db || this.memoryCache.length === 0) return

		const BATCH_SIZE = 32
		const rows: Array<Record<string, unknown>> = []

		for (let i = 0; i < this.memoryCache.length; i += BATCH_SIZE) {
			const batch = this.memoryCache.slice(i, i + BATCH_SIZE)
			const texts = batch.map((m) => m.content)
			const vectors = await embedBatch(texts)

			for (let j = 0; j < batch.length; j++) {
				const m = batch[j]
				rows.push({
					id: m.id,
					vector: vectors[j],
					type: m.type,
					content: m.content,
					importance: m.importance,
					hero: m.hero,
					created_at: m.created_at,
					hash: m.hash,
					tags: m.tags.join(","),
				})
			}
		}

		// Drop and recreate table
		try {
			await this.db.dropTable(TABLE_NAME)
		} catch { /* table might not exist */ }

		this.table = await this.db.createTable(TABLE_NAME, rows)
	}

	// --- Public API ---

	/** Remember something. Writes to markdown + indexes in LanceDB. Returns the memory ID. */
	async remember(
		content: string,
		type: MemoryType,
		opts: {
			importance?: number
			source?: string
			context?: string
			tags?: string[]
		} = {},
	): Promise<string> {
		const hash = contentHash(content)

		// Dedup: if we already have this content, return existing
		if (this.contentHashes.has(hash)) {
			const existing = this.memoryCache.find((m) => m.hash === hash)
			if (existing) return existing.id
		}

		const now = new Date().toISOString()
		const id = memoryId(content, now)

		const memory: Memory = {
			id,
			type,
			content,
			source: opts.source || "conversation",
			context: opts.context || "",
			importance: opts.importance ?? 5,
			hero: this.heroName,
			created_at: now,
			hash,
			tags: opts.tags || [],
		}

		// 1. Append to daily markdown (source of truth)
		const entry: DailyEntry = {
			type,
			content,
			importance: opts.importance,
			tags: opts.tags,
		}
		appendDailyLog(this.memberberryDir, this.heroName, entry)

		// 2. Add to in-memory cache
		this.memoryCache.push(memory)
		this.contentHashes.add(hash)

		// 3. Index in LanceDB (best-effort)
		if (this.vectorsReady) {
			this.indexMemory(memory).catch(() => {
				// Vector indexing failed, keyword search still works
			})
		}

		return id
	}

	/** Index a single memory in LanceDB. */
	private async indexMemory(memory: Memory): Promise<void> {
		if (!this.db) return

		const vector = await embed(memory.content)
		const row = {
			id: memory.id,
			vector,
			type: memory.type,
			content: memory.content,
			importance: memory.importance,
			hero: memory.hero,
			created_at: memory.created_at,
			hash: memory.hash,
			tags: memory.tags.join(","),
		}

		if (!this.table) {
			this.table = await this.db.createTable(TABLE_NAME, [row])
		} else {
			await this.table.add([row])
		}
	}

	/** Recall memories relevant to a query. Combines vector + keyword scoring. */
	async recall(
		query: string,
		opts: RecallOptions = {},
	): Promise<MemoryWithScore[]> {
		const limit = opts.limit ?? 10

		// --- Vector search path ---
		let vectorResults: Map<string, number> = new Map()
		if (this.vectorsReady && this.table) {
			try {
				const queryVector = await embed(query)
				let search = this.table.vectorSearch(queryVector).limit(limit * 2)

				// Filter by hero if specified
				if (opts.hero) {
					search = search.where(`hero = '${opts.hero}'`)
				}
				if (opts.type) {
					search = search.where(`type = '${opts.type}'`)
				}

				const results = await search.toArray()
				for (const r of results) {
					vectorResults.set(r.id as string, r._distance as number)
				}
			} catch {
				// Vector search failed, fall back to keyword only
			}
		}

		// --- Keyword scoring path ---
		let candidates = this.memoryCache
		if (opts.hero) {
			candidates = candidates.filter((m) => m.hero === opts.hero)
		}
		if (opts.type) {
			candidates = candidates.filter((m) => m.type === opts.type)
		}

		const queryTags = opts.tags || []
		const scored: MemoryWithScore[] = candidates.map((m) => {
			const keywordScore = score(m, queryTags, query)
			const vectorDist = vectorResults.get(m.id)

			let finalScore: number
			if (vectorDist !== undefined) {
				// Blend: vector similarity (60%) + keyword relevance (40%)
				const vectorSim = 1 - vectorDist
				finalScore = vectorSim * 0.6 + keywordScore * 0.4
			} else {
				finalScore = keywordScore
			}

			return {
				...m,
				score: finalScore,
				distance: vectorDist ?? 1 - keywordScore,
			}
		})

		return scored
			.filter((m) => m.score > 0)
			.sort((a, b) => b.score - a.score)
			.slice(0, limit)
	}

	/** Get a single memory by ID. */
	get(id: string): Memory | null {
		return this.memoryCache.find((m) => m.id === id) || null
	}

	/** Stats about the memory store. */
	stats(): MemoryStats {
		const active = this.memoryCache
		const by_type: Record<string, number> = {}
		const tagSet = new Set<string>()

		for (const m of active) {
			by_type[m.type] = (by_type[m.type] || 0) + 1
			for (const t of m.tags) tagSet.add(t)
		}

		return {
			total: active.length,
			by_type,
			unique_tags: Array.from(tagSet),
		}
	}

	/** Close resources. */
	close(): void {
		// LanceDB doesn't need explicit close
		this.memoryCache = []
		this.contentHashes.clear()
	}
}
