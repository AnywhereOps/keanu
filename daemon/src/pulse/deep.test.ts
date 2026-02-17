// daemon/src/pulse/deep.test.ts
// Tests for deep detection sidecar client.

import { describe, expect, test } from "bun:test"
import { shouldDeepCheck, deepCheck } from "./deep"
import type { DaemonConfig } from "../types"

describe("deep detection", () => {
	test("shouldDeepCheck: true on grey", () => {
		expect(shouldDeepCheck("grey", 1)).toBe(true)
	})

	test("shouldDeepCheck: true on black", () => {
		expect(shouldDeepCheck("black", 1)).toBe(true)
	})

	test("shouldDeepCheck: true every 5th turn", () => {
		expect(shouldDeepCheck("alive", 5)).toBe(true)
		expect(shouldDeepCheck("alive", 10)).toBe(true)
		expect(shouldDeepCheck("alive", 15)).toBe(true)
	})

	test("shouldDeepCheck: false on alive non-5th turn", () => {
		expect(shouldDeepCheck("alive", 1)).toBe(false)
		expect(shouldDeepCheck("alive", 3)).toBe(false)
		expect(shouldDeepCheck("alive", 7)).toBe(false)
	})

	test("deepCheck: returns empty array when sidecar is down", async () => {
		const config = {
			detector_sidecar_url: "http://localhost:99999", // nothing running here
		} as DaemonConfig

		const results = await deepCheck("test text", config)
		expect(results).toEqual([])
	})
})
