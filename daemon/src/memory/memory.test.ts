// daemon/src/memory/memory.test.ts
// Tests for the memberberry memory system.

import { describe, expect, test, beforeEach, afterEach } from "bun:test"
import { mkdtempSync, rmSync, existsSync, readFileSync } from "node:fs"
import { join } from "node:path"
import { MemoryStore } from "./store"
import { score } from "./scoring"
import { DisagreementTracker } from "./disagreement"
import {
	loadMemoryMd,
	ensureMemoryMd,
	appendDailyLog,
	parseDailyLog,
	findDailyLogs,
} from "./markdown"
import { ensureRepo, commit } from "./git"
import type { DaemonConfig, Memory } from "../types"

function tmpConfig(): DaemonConfig {
	const dir = mkdtempSync("/tmp/keanu-test-")
	const memberberryDir = mkdtempSync("/tmp/keanu-berry-")
	return {
		socket_path: "/tmp/keanu-test.sock",
		model: "claude-sonnet-4-20250514",
		max_tokens: 8192,
		memory_dir: dir,
		memberberry_dir: memberberryDir,
		hero_name: "keanu",
		soul_path: "",
		status_path: "",
		langfuse_enabled: false,
		detector_sidecar_url: "",
	}
}

// --- Memory Store (markdown + keyword search, no LanceDB in tests) ---

describe("memory store", () => {
	let config: DaemonConfig
	let store: MemoryStore

	beforeEach(async () => {
		config = tmpConfig()
		store = new MemoryStore(config)
		// Don't call store.init() — skips LanceDB in tests, keyword search still works
	})

	afterEach(() => {
		store.close()
		rmSync(config.memory_dir, { recursive: true, force: true })
		rmSync(config.memberberry_dir, { recursive: true, force: true })
	})

	test("remember writes to daily markdown and recall finds it", async () => {
		const id = await store.remember("Bun is the preferred runtime", "preference", {
			importance: 7,
			source: "conversation",
		})
		expect(id).toBeTruthy()
		expect(id.length).toBe(12)

		// Check markdown file was created
		const logs = findDailyLogs(config.memberberry_dir, "keanu")
		expect(logs.length).toBe(1)

		// Recall via keyword search
		const results = await store.recall("runtime")
		expect(results.length).toBe(1)
		expect(results[0].content).toBe("Bun is the preferred runtime")
		expect(results[0].importance).toBe(7)
	})

	test("deduplicates identical content", async () => {
		const id1 = await store.remember("same content", "fact")
		const id2 = await store.remember("same content", "fact")
		expect(id1).toBe(id2)

		const stats = store.stats()
		expect(stats.total).toBe(1)
	})

	test("stats tracks counts by type", async () => {
		await store.remember("goal 1", "plan", { importance: 8 })
		await store.remember("fact 1", "fact", { importance: 3 })
		await store.remember("fact 2", "fact", { importance: 4 })

		const stats = store.stats()
		expect(stats.total).toBe(3)
		expect(stats.by_type.plan).toBe(1)
		expect(stats.by_type.fact).toBe(2)
	})

	test("persists across store instances via markdown", async () => {
		await store.remember("persistent memory", "lesson", { importance: 9 })
		store.close()

		// New store instance reads from markdown
		const store2 = new MemoryStore(config)
		// Manually trigger cache rebuild (normally done in init())
		await (store2 as any).rebuildCache()
		const results = await store2.recall("persistent")
		expect(results.length).toBe(1)
		expect(results[0].content).toBe("persistent memory")
		store2.close()
	})

	test("filters by hero", async () => {
		await store.remember("keanu memory", "fact")

		// Recall all heroes
		const all = await store.recall("memory")
		expect(all.length).toBe(1)

		// Recall specific hero
		const keanuOnly = await store.recall("memory", { hero: "keanu" })
		expect(keanuOnly.length).toBe(1)

		// Recall wrong hero
		const neo = await store.recall("memory", { hero: "neo" })
		expect(neo.length).toBe(0)
	})

	test("filters by type", async () => {
		await store.remember("a fact", "fact")
		await store.remember("a lesson", "lesson")

		const facts = await store.recall("", { type: "fact" })
		expect(facts.length).toBe(1)
		expect(facts[0].type).toBe("fact")
	})

	test("tags are stored and scored", async () => {
		await store.remember("use bun for everything", "preference", {
			tags: ["tooling", "runtime"],
		})

		const stats = store.stats()
		expect(stats.unique_tags).toContain("tooling")
		expect(stats.unique_tags).toContain("runtime")

		// Tag match boosts score
		const withTag = await store.recall("tools", { tags: ["tooling"] })
		const withoutTag = await store.recall("tools")
		expect(withTag[0]?.score).toBeGreaterThanOrEqual(withoutTag[0]?.score || 0)
	})
})

// --- Markdown layer ---

describe("markdown", () => {
	let dir: string

	beforeEach(() => {
		dir = mkdtempSync("/tmp/keanu-md-")
	})

	afterEach(() => {
		rmSync(dir, { recursive: true, force: true })
	})

	test("ensureMemoryMd creates MEMORY.md", () => {
		ensureMemoryMd(dir, "keanu")
		const content = loadMemoryMd(dir)
		expect(content).toContain("keanu")
		expect(content).toContain("Memberberries")
	})

	test("loadMemoryMd returns null if missing", () => {
		expect(loadMemoryMd(dir)).toBeNull()
	})

	test("appendDailyLog creates and appends", () => {
		appendDailyLog(dir, "keanu", {
			type: "decision",
			content: "Using LanceDB as single index",
			importance: 8,
		})
		appendDailyLog(dir, "keanu", {
			type: "lesson",
			content: "String.replace only replaces first match",
			tags: ["javascript"],
		})

		const logs = findDailyLogs(dir, "keanu")
		expect(logs.length).toBe(1)

		const content = readFileSync(logs[0], "utf-8")
		expect(content).toContain("[decision]")
		expect(content).toContain("LanceDB")
		expect(content).toContain("[lesson]")
		expect(content).toContain("#javascript")
	})

	test("parseDailyLog round-trips entries", () => {
		appendDailyLog(dir, "keanu", {
			type: "fact",
			content: "Earth orbits the sun",
			importance: 3,
			tags: ["science"],
		}, "abc12345")

		const logs = findDailyLogs(dir, "keanu")
		const entries = parseDailyLog(logs[0])
		expect(entries.length).toBe(1)
		expect(entries[0].type).toBe("fact")
		expect(entries[0].content).toBe("Earth orbits the sun")
		expect(entries[0].importance).toBe(3)
		expect(entries[0].tags).toContain("science")
		expect(entries[0].hero).toBe("keanu")
	})

	test("findDailyLogs filters by hero", () => {
		appendDailyLog(dir, "keanu", { type: "fact", content: "a" })
		appendDailyLog(dir, "neo", { type: "fact", content: "b" })

		expect(findDailyLogs(dir, "keanu").length).toBe(1)
		expect(findDailyLogs(dir, "neo").length).toBe(1)
		expect(findDailyLogs(dir).length).toBe(2)
	})
})

// --- Git layer ---

describe("git", () => {
	let dir: string

	beforeEach(() => {
		dir = mkdtempSync("/tmp/keanu-git-")
	})

	afterEach(() => {
		rmSync(dir, { recursive: true, force: true })
	})

	test("ensureRepo creates git repo with .gitignore", () => {
		ensureRepo(dir)
		expect(existsSync(join(dir, ".git"))).toBe(true)
		expect(existsSync(join(dir, ".gitignore"))).toBe(true)

		const gitignore = readFileSync(join(dir, ".gitignore"), "utf-8")
		expect(gitignore).toContain("vectors/")
	})

	test("ensureRepo is idempotent", () => {
		ensureRepo(dir)
		ensureRepo(dir) // should not throw
		expect(existsSync(join(dir, ".git"))).toBe(true)
	})

	test("commit adds and commits changes", async () => {
		ensureRepo(dir)

		// Write a file
		const { writeFileSync } = await import("node:fs")
		writeFileSync(join(dir, "test.md"), "hello")

		await commit(dir, "test commit")

		// Verify git log
		const { execSync } = await import("node:child_process")
		const log = execSync("git log --oneline", { cwd: dir }).toString()
		expect(log).toContain("test commit")
	})

	test("commit is no-op when nothing changed", async () => {
		ensureRepo(dir)
		await commit(dir, "empty") // should not throw
	})
})

// --- Relevance scoring ---

describe("relevance scoring", () => {
	test("importance contributes to score", () => {
		const high: Memory = {
			id: "a",
			type: "plan",
			content: "ship keanu",
			source: "",
			context: "",
			importance: 9,
			hero: "keanu",
			created_at: new Date().toISOString(),
			hash: "aaa",
			tags: [],
		}
		const low: Memory = {
			id: "b",
			type: "fact",
			content: "ship keanu",
			source: "",
			context: "",
			importance: 2,
			hero: "keanu",
			created_at: new Date().toISOString(),
			hash: "bbb",
			tags: [],
		}

		const highScore = score(high, [], "keanu")
		const lowScore = score(low, [], "keanu")
		expect(highScore).toBeGreaterThan(lowScore)
	})

	test("text overlap boosts score", () => {
		const memory: Memory = {
			id: "c",
			type: "fact",
			content: "the terraform module uses AWS provider version 5.0",
			source: "",
			context: "",
			importance: 5,
			hero: "keanu",
			created_at: new Date().toISOString(),
			hash: "ccc",
			tags: [],
		}

		const relevant = score(memory, [], "terraform AWS provider")
		const irrelevant = score(memory, [], "cooking recipes")
		expect(relevant).toBeGreaterThan(irrelevant)
	})

	test("tag overlap boosts score", () => {
		const memory: Memory = {
			id: "d",
			type: "fact",
			content: "some content",
			source: "",
			context: "",
			importance: 5,
			hero: "keanu",
			created_at: new Date().toISOString(),
			hash: "ddd",
			tags: ["terraform", "aws"],
		}

		const withTags = score(memory, ["terraform"], "")
		const withoutTags = score(memory, [], "")
		expect(withTags).toBeGreaterThan(withoutTags)
	})

	test("old rarely-recalled memories decay", () => {
		const old = new Date()
		old.setDate(old.getDate() - 100) // 100 days ago

		const memory: Memory & { recall_count: number } = {
			id: "f",
			type: "fact",
			content: "old info",
			source: "",
			context: "",
			importance: 5,
			hero: "keanu",
			created_at: old.toISOString(),
			hash: "fff",
			tags: [],
			recall_count: 1,
		}

		const fresh: Memory & { recall_count: number } = {
			...memory,
			id: "g",
			created_at: new Date().toISOString(),
			hash: "ggg",
			recall_count: 0,
		}

		expect(score(memory, [], "")).toBeLessThan(score(fresh, [], ""))
	})
})

// --- Disagreement tracker ---

describe("disagreement tracker", () => {
	let dir: string
	let tracker: DisagreementTracker

	beforeEach(() => {
		dir = mkdtempSync("/tmp/keanu-disagree-")
		tracker = new DisagreementTracker(dir)
	})

	afterEach(() => {
		rmSync(dir, { recursive: true, force: true })
	})

	test("records and retrieves stats", () => {
		tracker.record("s1", 5, "use React", "use Svelte", "neither")
		tracker.record("s1", 8, "skip tests", "write tests", "human")

		const stats = tracker.stats()
		expect(stats.total).toBe(2)
		expect(stats.human_yielded).toBe(1)
		expect(stats.unresolved).toBe(1)
	})

	test("alerts on zero disagreements", () => {
		const alerts = tracker.alerts(25)
		expect(alerts.some((a) => a.includes("sycophancy"))).toBe(true)
	})

	test("alerts on agent capture", () => {
		for (let i = 0; i < 6; i++) {
			tracker.record("s1", i, "human says X", "agent says Y", "agent")
		}

		const alerts = tracker.alerts(10)
		expect(alerts.some((a) => a.includes("capture"))).toBe(true)
	})

	test("persists across instances", () => {
		tracker.record("s1", 1, "A", "B", "neither")

		const tracker2 = new DisagreementTracker(dir)
		expect(tracker2.stats().total).toBe(1)
	})
})
