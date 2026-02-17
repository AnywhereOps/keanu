// daemon/src/memory/memory.test.ts
// Tests for the memberberry memory system.

import { describe, expect, test, beforeEach, afterEach } from "bun:test"
import { mkdtempSync, rmSync } from "node:fs"
import { join } from "node:path"
import { MemoryStore } from "./store"
import { score } from "./scoring"
import { DisagreementTracker } from "./disagreement"
import type { DaemonConfig, Memory } from "../types"

function tmpConfig(): DaemonConfig {
	const dir = mkdtempSync("/tmp/keanu-test-")
	return {
		socket_path: "/tmp/keanu-test.sock",
		model: "claude-sonnet-4-20250514",
		max_tokens: 8192,
		memory_dir: dir,
		soul_path: "",
		status_path: "",
		langfuse_enabled: false,
		detector_sidecar_url: "",
	}
}

describe("memory store", () => {
	let config: DaemonConfig
	let store: MemoryStore

	beforeEach(() => {
		config = tmpConfig()
		store = new MemoryStore(config)
	})

	afterEach(() => {
		store.close()
		rmSync(config.memory_dir, { recursive: true, force: true })
	})

	test("remember and recall", async () => {
		const id = await store.remember("Bun is the preferred runtime", "preference", {
			importance: 7,
			source: "conversation",
		})
		expect(id).toBeTruthy()
		expect(id.length).toBe(12)

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

	test("supersede tombstones without deleting", async () => {
		const id1 = await store.remember("old info", "fact")
		const id2 = await store.remember("new info", "fact")
		await store.supersede(id1, id2)

		// Recall should only return the new one (superseded filtered out)
		const results = await store.recall("info")
		expect(results.length).toBe(1)
		expect(results[0].content).toBe("new info")
	})

	test("stats tracks counts by type", async () => {
		await store.remember("goal 1", "goal", { importance: 8 })
		await store.remember("fact 1", "fact", { importance: 3 })
		await store.remember("fact 2", "fact", { importance: 4 })

		const stats = store.stats()
		expect(stats.total).toBe(3)
		expect(stats.by_type.goal).toBe(1)
		expect(stats.by_type.fact).toBe(2)
	})

	test("persists across store instances", async () => {
		await store.remember("persistent memory", "lesson", { importance: 9 })
		store.close()

		// New store instance reads from JSONL
		const store2 = new MemoryStore(config)
		const results = await store2.recall("persistent")
		expect(results.length).toBe(1)
		expect(results[0].content).toBe("persistent memory")
		store2.close()
	})
})

describe("relevance scoring", () => {
	test("importance contributes to score", () => {
		const high: Memory = {
			id: "a",
			type: "goal",
			content: "ship keanu",
			source: "",
			context: "",
			importance: 9,
			namespace: "private",
			created_at: new Date().toISOString(),
			hash: "aaa",
		}
		const low: Memory = {
			id: "b",
			type: "fact",
			content: "ship keanu",
			source: "",
			context: "",
			importance: 2,
			namespace: "private",
			created_at: new Date().toISOString(),
			hash: "bbb",
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
			namespace: "private",
			created_at: new Date().toISOString(),
			hash: "ccc",
		}

		const relevant = score(memory, [], "terraform AWS provider")
		const irrelevant = score(memory, [], "cooking recipes")
		expect(relevant).toBeGreaterThan(irrelevant)
	})

	test("type weights favor goals over facts", () => {
		const goal: Memory = {
			id: "d",
			type: "goal",
			content: "test content",
			source: "",
			context: "",
			importance: 5,
			namespace: "private",
			created_at: new Date().toISOString(),
			hash: "ddd",
		}
		const fact: Memory = {
			...goal,
			id: "e",
			type: "fact",
			hash: "eee",
		}

		expect(score(goal, [], "")).toBeGreaterThan(score(fact, [], ""))
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
			namespace: "private",
			created_at: old.toISOString(),
			hash: "fff",
			recall_count: 1, // < 3, will decay
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
