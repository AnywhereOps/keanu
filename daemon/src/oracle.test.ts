// daemon/src/oracle.test.ts
// tests for the oracle. response normalization, cost tracking, JSON extraction.

import { describe, expect, test, beforeEach } from "bun:test"
import {
	estimateCost,
	extractJSON,
	getSessionCost,
	resetSessionCost,
} from "./oracle"

describe("estimateCost", () => {
	test("opus pricing", () => {
		const cost = estimateCost("claude-opus-4-6", 1_000_000, 1_000_000)
		expect(cost).toBe(15.0 + 75.0)
	})

	test("sonnet pricing", () => {
		const cost = estimateCost("claude-sonnet-4-20250514", 1_000_000, 1_000_000)
		expect(cost).toBe(3.0 + 15.0)
	})

	test("haiku pricing", () => {
		const cost = estimateCost("claude-haiku-4-5-20251001", 1_000_000, 1_000_000)
		expect(cost).toBe(1.0 + 5.0)
	})

	test("unknown model defaults to sonnet pricing", () => {
		const cost = estimateCost("some-unknown-model", 1_000_000, 1_000_000)
		expect(cost).toBe(3.0 + 15.0)
	})

	test("zero tokens costs zero", () => {
		const cost = estimateCost("claude-opus-4-6", 0, 0)
		expect(cost).toBe(0)
	})

	test("small token counts", () => {
		// 1000 input tokens on opus = $0.015
		const cost = estimateCost("claude-opus-4-6", 1000, 500)
		expect(cost).toBeCloseTo(0.015 + 0.0375, 5)
	})
})

describe("extractJSON", () => {
	test("extracts from ```json fence", () => {
		const text = 'Here is the plan:\n```json\n{"phases": [{"name": "setup"}]}\n```\nDone.'
		const result = extractJSON(text) as Record<string, unknown>
		expect(result).toBeTruthy()
		expect((result.phases as Array<{name: string}>)[0].name).toBe("setup")
	})

	test("extracts from ``` fence without language", () => {
		const text = '```\n{"key": "value"}\n```'
		const result = extractJSON(text) as Record<string, unknown>
		expect(result).toBeTruthy()
		expect(result.key).toBe("value")
	})

	test("extracts bare JSON", () => {
		const text = '{"simple": true}'
		const result = extractJSON(text) as Record<string, unknown>
		expect(result).toBeTruthy()
		expect(result.simple).toBe(true)
	})

	test("extracts JSON with surrounding prose", () => {
		const text = 'Here is my response:\n{"translation": "hello", "key_shifts": []}\nHope that helps!'
		const result = extractJSON(text) as Record<string, unknown>
		expect(result).toBeTruthy()
		expect(result.translation).toBe("hello")
	})

	test("handles nested braces correctly", () => {
		const text = '{"outer": {"inner": {"deep": true}}, "sibling": "yes"}'
		const result = extractJSON(text) as Record<string, unknown>
		expect(result).toBeTruthy()
		expect(result.sibling).toBe("yes")
		expect((result.outer as Record<string, unknown>).inner).toBeTruthy()
	})

	test("handles braces in strings", () => {
		const text = '{"message": "use {braces} in text", "ok": true}'
		const result = extractJSON(text) as Record<string, unknown>
		expect(result).toBeTruthy()
		expect(result.ok).toBe(true)
		expect(result.message).toBe("use {braces} in text")
	})

	test("returns null for no JSON", () => {
		expect(extractJSON("just plain text")).toBeNull()
	})

	test("returns null for malformed JSON", () => {
		expect(extractJSON("{not: valid json}")).toBeNull()
	})

	test("greedy regex bug: two JSON objects in response", () => {
		// the old greedy regex /\{[\s\S]*\}/ would match from first { to last }
		// capturing both objects as one invalid blob
		const text = '{"first": true} some text {"second": true}'
		const result = extractJSON(text) as Record<string, unknown>
		expect(result).toBeTruthy()
		expect(result.first).toBe(true)
		// should NOT have "second" - that's a separate object
		expect(result).not.toHaveProperty("second")
	})
})

describe("session cost tracking", () => {
	beforeEach(() => {
		resetSessionCost()
	})

	test("starts at zero", () => {
		const cost = getSessionCost()
		expect(cost.calls).toBe(0)
		expect(cost.totalCost).toBe(0)
		expect(cost.totalInputTokens).toBe(0)
		expect(cost.totalOutputTokens).toBe(0)
	})

	test("reset clears everything", () => {
		// we can't easily trigger recordUsage without calling callOracle,
		// but we can verify reset works on the structure
		resetSessionCost()
		const cost = getSessionCost()
		expect(cost.calls).toBe(0)
		expect(Object.keys(cost.byModel)).toHaveLength(0)
	})
})
