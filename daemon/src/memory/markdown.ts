// daemon/src/memory/markdown.ts
// Pure markdown storage for memberberries.
//
// Two layers:
//   1. MEMORY.md — curated long-term memory, loaded every session
//   2. memory-{hero}-{date}.md — daily logs, append-only
//
// Human-readable, git-diffable, grep-friendly.
// LanceDB is the derived index (built from these files).

import {
	existsSync,
	mkdirSync,
	readFileSync,
	appendFileSync,
	writeFileSync,
	readdirSync,
} from "node:fs"
import { join, basename } from "node:path"

/**
 * Load MEMORY.md for system prompt injection.
 * Returns null if file doesn't exist.
 */
export function loadMemoryMd(memberberryDir: string): string | null {
	const path = join(memberberryDir, "MEMORY.md")
	if (!existsSync(path)) return null
	return readFileSync(path, "utf-8")
}

/**
 * Ensure MEMORY.md exists with a minimal header.
 */
export function ensureMemoryMd(memberberryDir: string, heroName: string): void {
	if (!existsSync(memberberryDir)) mkdirSync(memberberryDir, { recursive: true })
	const path = join(memberberryDir, "MEMORY.md")
	if (!existsSync(path)) {
		writeFileSync(
			path,
			`# Memberberries\n\nCurated memories for ${heroName}. Loaded every session.\n`,
		)
	}
}

// --- Daily logs ---

export interface DailyEntry {
	type: string
	content: string
	importance?: number
	tags?: string[]
}

function dailyLogPath(memberberryDir: string, heroName: string, date?: Date): string {
	const d = date || new Date()
	const dateStr = d.toISOString().slice(0, 10) // 2026-02-17
	return join(memberberryDir, `memory-${heroName}-${dateStr}.md`)
}

/**
 * Append a memory entry to today's daily log.
 */
export function appendDailyLog(
	memberberryDir: string,
	heroName: string,
	entry: DailyEntry,
	sessionId?: string,
): void {
	if (!existsSync(memberberryDir)) mkdirSync(memberberryDir, { recursive: true })

	const path = dailyLogPath(memberberryDir, heroName)
	const time = new Date().toTimeString().slice(0, 5) // HH:MM
	const tags = entry.tags?.length ? ` ${entry.tags.map((t) => `#${t}`).join(" ")}` : ""
	const importance = entry.importance ? ` (${entry.importance}/10)` : ""

	// If file doesn't exist, write header
	if (!existsSync(path)) {
		const dateStr = new Date().toISOString().slice(0, 10)
		writeFileSync(path, `# ${heroName} — ${dateStr}\n\n`)
	}

	// Check if we need a session header
	if (sessionId) {
		const existing = readFileSync(path, "utf-8")
		const sessionHeader = `## ${time} — session ${sessionId.slice(0, 8)}`
		if (!existing.includes(`session ${sessionId.slice(0, 8)}`)) {
			appendFileSync(path, `\n${sessionHeader}\n`)
		}
	}

	const line = `- [${entry.type}]${importance} ${entry.content}${tags}\n`
	appendFileSync(path, line)
}

/**
 * Flush multiple memories to today's daily log.
 */
export function flushToDaily(
	memberberryDir: string,
	heroName: string,
	memories: DailyEntry[],
	sessionId: string,
): void {
	for (const m of memories) {
		appendDailyLog(memberberryDir, heroName, m, sessionId)
	}
}

// --- Parsing ---

export interface ParsedMemoryEntry {
	type: string
	content: string
	importance: number
	tags: string[]
	hero: string
	date: string
	sessionId?: string
}

/**
 * Parse a daily log markdown file into structured entries.
 * Used by LanceDB indexer to build vectors.
 */
export function parseDailyLog(filePath: string): ParsedMemoryEntry[] {
	if (!existsSync(filePath)) return []

	const filename = basename(filePath)
	// memory-keanu-2026-02-17.md -> hero=keanu, date=2026-02-17
	// Non-greedy .+? so hyphenated hero names (hero-name) parse correctly
	const match = filename.match(/^memory-(.+?)-(\d{4}-\d{2}-\d{2})\.md$/)
	if (!match) return []

	const hero = match[1]
	const date = match[2]
	const text = readFileSync(filePath, "utf-8")
	const lines = text.split("\n")

	const entries: ParsedMemoryEntry[] = []
	let currentSession: string | undefined

	for (const line of lines) {
		// Session header: ## 14:30 — session abc12345
		const sessionMatch = line.match(/^## .+ — session (\w+)/)
		if (sessionMatch) {
			currentSession = sessionMatch[1]
			continue
		}

		// Entry: - [type] (7/10) content #tag1 #tag2
		const entryMatch = line.match(
			/^- \[(\w+)\](?:\s*\((\d+)\/10\))?\s+(.+)$/,
		)
		if (entryMatch) {
			const type = entryMatch[1]
			const importance = entryMatch[2] ? Number.parseInt(entryMatch[2]) : 5
			let content = entryMatch[3]

			// Extract inline #tags
			const tags: string[] = []
			content = content.replace(/#(\w+)/g, (_, tag) => {
				tags.push(tag)
				return ""
			}).trim()

			entries.push({
				type,
				content,
				importance,
				tags,
				hero,
				date,
				sessionId: currentSession,
			})
		}
	}

	return entries
}

/**
 * Find all daily log files, optionally filtered by hero.
 */
export function findDailyLogs(
	memberberryDir: string,
	hero?: string,
): string[] {
	if (!existsSync(memberberryDir)) return []
	const pattern = hero ? `memory-${hero}-` : "memory-"
	return readdirSync(memberberryDir)
		.filter((f) => f.startsWith(pattern) && f.endsWith(".md"))
		.sort()
		.map((f) => join(memberberryDir, f))
}
