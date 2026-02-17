// daemon/src/hero/hero.test.ts
// Tests for the stance system.

import { describe, expect, test } from "bun:test"
import { STANCES, getStance, filterTools } from "./stance"
import { detectShift, applyShift } from "./shift"
import { SessionTracker } from "./session"
import type { LoopState } from "../types"

function makeState(hero: string = "chat"): LoopState {
	return {
		id: "test-session",
		messages: [],
		pulse: null,
		turn: 5,
		breathing: false,
		hero: hero as LoopState["hero"],
		started_at: new Date().toISOString(),
	}
}

describe("stance configs", () => {
	test("all hero modes have configs", () => {
		const modes = ["chat", "do", "craft", "prove", "dream", "speak"]
		for (const mode of modes) {
			const stance = getStance(mode as LoopState["hero"])
			expect(stance.name).toBe(mode)
		}
	})

	test("chat allows all tools", () => {
		expect(STANCES.chat.allowedTools).toBeNull()
	})

	test("do allows all tools", () => {
		expect(STANCES.do.allowedTools).toBeNull()
	})

	test("craft restricts to code tools", () => {
		const tools = STANCES.craft.allowedTools!
		expect(tools).toContain("read_file")
		expect(tools).toContain("write_file")
		expect(tools).toContain("edit_file")
		expect(tools).toContain("bash")
		expect(tools.length).toBe(6)
	})

	test("prove restricts to read-only tools", () => {
		const tools = STANCES.prove.allowedTools!
		expect(tools).toContain("read_file")
		expect(tools).toContain("search")
		expect(tools).not.toContain("write_file")
		expect(tools).not.toContain("edit_file")
	})

	test("dream has no tools", () => {
		expect(STANCES.dream.allowedTools).toEqual([])
	})

	test("speak has no tools", () => {
		expect(STANCES.speak.allowedTools).toEqual([])
	})

	test("prove has lower max turns than craft", () => {
		expect(STANCES.prove.maxTurns).toBeLessThan(STANCES.craft.maxTurns)
	})
})

describe("tool filtering", () => {
	const mockTools = [
		{ name: "read_file", description: "read" },
		{ name: "write_file", description: "write" },
		{ name: "edit_file", description: "edit" },
		{ name: "bash", description: "bash" },
		{ name: "search", description: "search" },
		{ name: "ls", description: "ls" },
	]

	test("null allowedTools returns null (all tools)", () => {
		const result = filterTools(mockTools, STANCES.do)
		expect(result).toBeNull()
	})

	test("empty allowedTools returns empty array", () => {
		const result = filterTools(mockTools, STANCES.dream)
		expect(result).toEqual([])
	})

	test("craft filters to allowed tools only", () => {
		const result = filterTools(mockTools, STANCES.craft)!
		expect(result.length).toBe(6) // all 6 mock tools are in craft's allowed list
		expect(result.map((t) => t.name)).toContain("read_file")
	})

	test("prove excludes write tools", () => {
		const result = filterTools(mockTools, STANCES.prove)!
		expect(result.map((t) => t.name)).not.toContain("write_file")
		expect(result.map((t) => t.name)).not.toContain("edit_file")
	})
})

describe("stance shifting", () => {
	test("detects [stance: craft] signal", () => {
		const result = detectShift(
			"I need to write some code. [stance: craft]",
			"do",
		)
		expect(result).toBe("craft")
	})

	test("detects [stance: dream] signal", () => {
		const result = detectShift(
			"Let me plan this out first. [stance: dream]",
			"do",
		)
		expect(result).toBe("dream")
	})

	test("returns null when no signal", () => {
		const result = detectShift("Just a normal response", "do")
		expect(result).toBeNull()
	})

	test("returns null for same stance", () => {
		const result = detectShift("[stance: do]", "do")
		expect(result).toBeNull()
	})

	test("returns null for invalid stance", () => {
		const result = detectShift("[stance: invalid_mode]", "do")
		expect(result).toBeNull()
	})

	test("case insensitive", () => {
		const result = detectShift("[Stance: CRAFT]", "do")
		expect(result).toBe("craft")
	})

	test("applyShift updates state and logs transition", () => {
		const state = makeState("do")
		const { state: newState, signals } = applyShift(state, "craft")

		expect(newState.hero).toBe("craft")
		expect(newState.stanceHistory).toHaveLength(1)
		expect(newState.stanceHistory![0].from).toBe("do")
		expect(newState.stanceHistory![0].to).toBe("craft")
		expect(signals).toEqual([])
	})

	test("detects stance thrashing", () => {
		const state = makeState("do")
		state.turn = 5

		// Simulate 4 rapid shifts
		applyShift(state, "craft")
		state.turn = 5
		applyShift(state, "prove")
		state.turn = 5
		applyShift(state, "dream")
		state.turn = 6
		const { signals } = applyShift(state, "do")

		expect(signals).toContain("stance_thrashing")
	})
})

describe("session tracker", () => {
	test("tracks actions", () => {
		const tracker = new SessionTracker()
		const result = tracker.noteAction("read_file", "foo.ts", 1)
		expect(result.repeat).toBe(0)
		expect(tracker.filesRead.has("foo.ts")).toBe(true)
	})

	test("detects first repeat", () => {
		const tracker = new SessionTracker()
		tracker.noteAction("read_file", "foo.ts", 1)
		const result = tracker.noteAction("read_file", "foo.ts", 2)
		expect(result.repeat).toBe(2)
	})

	test("detects second repeat with warning", () => {
		const tracker = new SessionTracker()
		tracker.noteAction("read_file", "foo.ts", 1)
		tracker.noteAction("read_file", "foo.ts", 2)
		const result = tracker.noteAction("read_file", "foo.ts", 3)
		expect(result.repeat).toBeGreaterThanOrEqual(2)
	})

	test("returns cached result on third+ repeat", () => {
		const tracker = new SessionTracker()
		tracker.noteAction("read_file", "foo.ts", 1, "file contents")
		tracker.noteAction("read_file", "foo.ts", 2)
		tracker.noteAction("read_file", "foo.ts", 3)
		const result = tracker.noteAction("read_file", "foo.ts", 4)
		expect(result.repeat).toBeGreaterThanOrEqual(3)
		expect(result.cached).toBe("file contents")
	})

	test("resets count when different action intervenes", () => {
		const tracker = new SessionTracker()
		tracker.noteAction("read_file", "foo.ts", 1)
		tracker.noteAction("write_file", "bar.ts", 2)
		const result = tracker.noteAction("read_file", "foo.ts", 3)
		expect(result.repeat).toBe(0) // reset because different action in between
	})

	test("tracks files read and written", () => {
		const tracker = new SessionTracker()
		tracker.noteAction("read_file", "a.ts", 1)
		tracker.noteAction("write_file", "b.ts", 2)
		tracker.noteAction("edit_file", "c.ts", 3)

		expect(tracker.filesRead.has("a.ts")).toBe(true)
		expect(tracker.filesWritten.has("b.ts")).toBe(true)
		expect(tracker.filesWritten.has("c.ts")).toBe(true)
	})

	test("generates awareness context", () => {
		const tracker = new SessionTracker()
		tracker.noteAction("read_file", "foo.ts", 1)
		tracker.noteAction("write_file", "bar.ts", 2)

		const ctx = tracker.awareness()
		expect(ctx).toContain("files read: foo.ts")
		expect(ctx).toContain("files written: bar.ts")
		expect(ctx).toContain("actions taken: 2")
	})

	test("returns null awareness when no actions", () => {
		const tracker = new SessionTracker()
		expect(tracker.awareness()).toBeNull()
	})
})
