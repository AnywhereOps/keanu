// daemon/src/pulse/truth.test.ts
// Tests for half truth detection. The hard one.
//
// Path 1 (oracle) can't be unit tested without mocking the API.
// Path 2 (memory contradiction) can be tested with seeded memories.

import { describe, expect, test } from "bun:test"
import { memoryContradictionCheck, checkHalfTruth } from "./truth"
import type { DaemonConfig } from "../types"

// Note: memoryContradictionCheck uses recall() which requires initMemory().
// Without init, it gracefully returns empty (the catch block handles it).
// Full integration test would seed memories first.

const mockConfig: DaemonConfig = {
	socket_path: "/tmp/test.sock",
	model: "claude-sonnet-4-20250514",
	max_tokens: 8192,
	memory_dir: "/tmp/test-memory",
	memberberry_dir: "/tmp/test-berry",
	hero_name: "keanu",
	soul_path: "",
	status_path: "",
	langfuse_enabled: false,
	detector_sidecar_url: "",
}

describe("half truth detection", () => {
	test("memory contradiction check returns empty when memory not initialized", async () => {
		// Without initMemory(), recall() returns []. Graceful degradation.
		const contradictions = await memoryContradictionCheck(
			"React is always the best choice for web development.",
		)
		expect(contradictions).toHaveLength(0)
	})

	test("checkHalfTruth without oracle returns memory-only result", async () => {
		const result = await checkHalfTruth(
			"This approach will always work.",
			mockConfig,
			{ useOracle: false },
		)
		expect(result.oracle).toBeNull()
		expect(result.contradictions).toBeDefined()
		expect(result.score).toBeGreaterThanOrEqual(0)
	})

	test("checkHalfTruth score is 0 with no memories and no oracle", async () => {
		const result = await checkHalfTruth(
			"The bug is on line 47. The JWT expiry check uses milliseconds instead of seconds.",
			mockConfig,
			{ useOracle: false },
		)
		expect(result.score).toBe(0)
	})
})

// Integration test sketch (requires seeded memories):
//
// test("detects contradiction with previous memory", async () => {
//   // Seed: remember("React should be used for this project", "decision")
//   // Check: "We should definitely use Vue for this project"
//   // Expect: contradiction detected (changed_position)
// })
//
// test("oracle catches omission in confident claim", async () => {
//   // Text: "MongoDB is the best database for this use case"
//   // Oracle should flag: missing context about query patterns, scale, consistency needs
//   // Requires live API call
// })
