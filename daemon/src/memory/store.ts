// daemon/src/memory/store.ts
// Memberberry: the agent remembers.
//
// Ported from keanu-0.0.1/src/keanu/memory/memberberry.py
// JSONL append-only (source of truth) + bun:sqlite (derived index).
// Nothing is deleted. Superseded memories get tombstoned.

import { Database } from "bun:sqlite"
import {
	existsSync,
	mkdirSync,
	readFileSync,
	writeFileSync,
	appendFileSync,
} from "node:fs"
import { join } from "node:path"
import type {
	Memory,
	MemoryType,
	MemoryWithScore,
	Namespace,
	DaemonConfig,
} from "../types"
import { score } from "./scoring"

// --- Hashing (ported from compress/dns.py:short_hash) ---

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

// --- JSONL month-sharding (ported from memberberry.py:_shard_path) ---

function shardPath(baseDir: string, namespace: string): string {
	const now = new Date()
	const month = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`
	const dir = join(baseDir, namespace)
	if (!existsSync(dir)) mkdirSync(dir, { recursive: true })
	return join(dir, `${month}.jsonl`)
}

// --- Store ---

export interface RecallOptions {
	namespace?: Namespace
	type?: MemoryType
	tags?: string[]
	limit?: number
}

export interface MemoryStats {
	total: number
	by_type: Record<string, number>
	unique_tags: string[]
}

export class MemoryStore {
	private db: ReturnType<typeof Database.prototype>
	private baseDir: string
	private contentHashes: Set<string> = new Set()

	constructor(config: DaemonConfig) {
		this.baseDir = config.memory_dir
		if (!existsSync(this.baseDir)) mkdirSync(this.baseDir, { recursive: true })

		// SQLite is the derived index. JSONL is source of truth.
		const dbPath = join(this.baseDir, "index.db")
		this.db = new Database(dbPath)
		this.db.run("PRAGMA journal_mode = WAL")
		this.initSchema()
		this.rebuildFromJSONL()
	}

	private initSchema(): void {
		this.db.run(`
			CREATE TABLE IF NOT EXISTS memories (
				id TEXT PRIMARY KEY,
				type TEXT NOT NULL,
				content TEXT NOT NULL,
				source TEXT DEFAULT '',
				context TEXT DEFAULT '',
				importance INTEGER DEFAULT 5,
				namespace TEXT DEFAULT 'private',
				created_at TEXT NOT NULL,
				last_recalled TEXT DEFAULT '',
				recall_count INTEGER DEFAULT 0,
				superseded_by TEXT DEFAULT NULL,
				hash TEXT NOT NULL,
				tags TEXT DEFAULT '[]'
			)
		`)
		this.db.run(`
			CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(type)
		`)
		this.db.run(`
			CREATE INDEX IF NOT EXISTS idx_memories_namespace ON memories(namespace)
		`)
		this.db.run(`
			CREATE INDEX IF NOT EXISTS idx_memories_hash ON memories(hash)
		`)
	}

	// Rebuild SQLite from JSONL files (JSONL is source of truth)
	private rebuildFromJSONL(): void {
		this.contentHashes.clear()
		const namespaces = ["private", "shared", "agent"]

		for (const ns of namespaces) {
			const dir = join(this.baseDir, ns)
			if (!existsSync(dir)) continue

			// Find all JSONL files in this namespace
			const files = Bun.file(dir)
			try {
				const entries = Array.from(
					new Bun.Glob("*.jsonl").scanSync({ cwd: dir }),
				)
				for (const file of entries) {
					const lines = readFileSync(join(dir, file), "utf-8")
						.split("\n")
						.filter((l) => l.trim())
					for (const line of lines) {
						try {
							const memory = JSON.parse(line) as Memory
							this.contentHashes.add(contentHash(memory.content))
							this.upsertToSQLite(memory)
						} catch {
							// skip malformed lines
						}
					}
				}
			} catch {
				// directory might not have any files yet
			}
		}
	}

	private upsertToSQLite(memory: Memory): void {
		const stmt = this.db.prepare(`
			INSERT OR REPLACE INTO memories
			(id, type, content, source, context, importance, namespace,
			 created_at, last_recalled, recall_count, superseded_by, hash, tags)
			VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		`)
		stmt.run(
			memory.id,
			memory.type,
			memory.content,
			memory.source || "",
			memory.context || "",
			memory.importance,
			memory.namespace || "private",
			memory.created_at,
			"",
			0,
			memory.superseded_by || null,
			memory.hash,
			JSON.stringify([]), // tags stored as JSON string
		)
	}

	// --- Public API ---

	/** Remember something. Returns the memory ID. */
	async remember(
		content: string,
		type: MemoryType,
		opts: {
			importance?: number
			source?: string
			context?: string
			namespace?: Namespace
		} = {},
	): Promise<string> {
		const hash = contentHash(content)

		// Dedup: if we already have this content, return existing
		if (this.contentHashes.has(hash)) {
			const existing = this.db
				.prepare("SELECT id FROM memories WHERE hash = ?")
				.get(hash) as { id: string } | undefined
			if (existing) return existing.id
		}

		const now = new Date().toISOString()
		const id = memoryId(content, now)
		const namespace = opts.namespace || "private"

		const memory: Memory = {
			id,
			type,
			content,
			source: opts.source || "conversation",
			context: opts.context || "",
			importance: opts.importance ?? 5,
			namespace,
			created_at: now,
			hash,
		}

		// 1. Append to JSONL (source of truth)
		const path = shardPath(this.baseDir, namespace)
		appendFileSync(path, JSON.stringify(memory) + "\n")

		// 2. Insert into SQLite (derived index)
		this.upsertToSQLite(memory)

		// 3. Track content hash
		this.contentHashes.add(hash)

		return id
	}

	/** Recall memories relevant to a query. */
	async recall(
		query: string,
		opts: RecallOptions = {},
	): Promise<MemoryWithScore[]> {
		const limit = opts.limit ?? 10
		const namespace = opts.namespace || "private"

		// Build SQL query
		let sql = "SELECT * FROM memories WHERE namespace = ? AND superseded_by IS NULL"
		const params: unknown[] = [namespace]

		if (opts.type) {
			sql += " AND type = ?"
			params.push(opts.type)
		}

		const rows = this.db.prepare(sql).all(...params) as Array<
			Memory & { tags: string }
		>

		// Score each memory using the ported relevance algorithm
		const queryTags = opts.tags || []
		const scored: MemoryWithScore[] = rows
			.map((row) => {
				const tags = JSON.parse(row.tags || "[]") as string[]
				const relevance = score(
					{
						...row,
						tags: undefined, // not in Memory type
					} as Memory,
					queryTags,
					query,
				)
				return {
					...row,
					tags: undefined,
					score: relevance,
					distance: 1 - relevance, // for compatibility
				} as MemoryWithScore
			})
			.filter((m) => m.score > 0)
			.sort((a, b) => b.score - a.score)
			.slice(0, limit)

		// Update recall stats for returned memories
		const updateStmt = this.db.prepare(
			"UPDATE memories SET last_recalled = ?, recall_count = recall_count + 1 WHERE id = ?",
		)
		const now = new Date().toISOString()
		for (const m of scored) {
			updateStmt.run(now, m.id)
		}

		return scored
	}

	/** Tombstone a memory (never delete, point forward). */
	async supersede(oldId: string, newId: string): Promise<void> {
		this.db
			.prepare("UPDATE memories SET superseded_by = ? WHERE id = ?")
			.run(newId, oldId)
	}

	/** Get a single memory by ID. */
	get(id: string): Memory | null {
		return (
			(this.db.prepare("SELECT * FROM memories WHERE id = ?").get(id) as Memory) ||
			null
		)
	}

	/** Stats about the memory store. */
	stats(): MemoryStats {
		const total = (
			this.db
				.prepare(
					"SELECT COUNT(*) as count FROM memories WHERE superseded_by IS NULL",
				)
				.get() as { count: number }
		).count

		const byType = this.db
			.prepare(
				"SELECT type, COUNT(*) as count FROM memories WHERE superseded_by IS NULL GROUP BY type",
			)
			.all() as Array<{ type: string; count: number }>

		const by_type: Record<string, number> = {}
		for (const row of byType) {
			by_type[row.type] = row.count
		}

		// Get unique tags from JSONL (tags not stored in SQLite yet)
		const unique_tags: string[] = []

		return { total, by_type, unique_tags }
	}

	/** Close the database connection. */
	close(): void {
		this.db.close()
	}
}
