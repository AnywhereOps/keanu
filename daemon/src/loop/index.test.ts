// daemon/src/loop/index.test.ts
// Tests for the agent loop. Does it work end to end?

import { describe, expect, test } from "bun:test"
import { createLoopState } from "./index"
import type { Message } from "../types"

// --- Unit tests (no API calls) ---

describe("loop state", () => {
	test("createLoopState initializes correctly", () => {
		const state = createLoopState("do")
		expect(state.hero).toBe("do")
		expect(state.messages).toEqual([])
		expect(state.turn).toBe(0)
		expect(state.breathing).toBe(false)
		expect(state.pulse).toBeNull()
		expect(state.id).toBeTruthy()
	})

	test("createLoopState defaults to chat", () => {
		const state = createLoopState()
		expect(state.hero).toBe("chat")
	})
})

// --- Message format tests ---

describe("message format", () => {
	test("Message type supports content_blocks", () => {
		const msg: Message = {
			role: "assistant",
			content: "thinking...",
			content_blocks: [
				{ type: "text", text: "thinking..." },
				{
					type: "tool_use",
					id: "123",
					name: "read_file",
					input: { path: "foo.ts" },
				},
			],
		}
		expect(msg.content_blocks).toHaveLength(2)
		expect(msg.content_blocks![0].type).toBe("text")
		expect(msg.content_blocks![1].type).toBe("tool_use")
	})

	test("Message type supports is_error for tool results", () => {
		const msg: Message = {
			role: "tool",
			content: "File not found",
			tool_call_id: "123",
			tool_name: "read_file",
			is_error: true,
		}
		expect(msg.is_error).toBe(true)
	})
})

// --- Integration tests (require ANTHROPIC_API_KEY) ---
// These tests make real API calls. Skip if no key.

const hasApiKey = !!process.env.ANTHROPIC_API_KEY

describe.skipIf(!hasApiKey)("loop integration", () => {
	test("step responds to simple message without tools", async () => {
		const { step } = await import("./index")
		const { loadConfig } = await import("../config")

		const state = createLoopState("chat")
		const config = loadConfig()
		const result = await step(
			state,
			"Reply with just the word 'hello'",
			config,
		)
		expect(result.response.toLowerCase()).toContain("hello")
		expect(result.state.turn).toBe(1)
		expect(result.state.pulse).toBeTruthy()
	}, 30_000)

	test("step uses tools when asked to read a file", async () => {
		const { step } = await import("./index")
		const { loadConfig } = await import("../config")

		const state = createLoopState("do")
		const config = loadConfig()
		const result = await step(
			state,
			"Read the file at ./package.json and tell me the package name. Be brief.",
			config,
		)
		// Should have used the read_file tool
		const hasToolMessage = result.state.messages.some(
			(m) => m.role === "tool",
		)
		expect(hasToolMessage).toBe(true)
		expect(result.response).toBeTruthy()
	}, 60_000)
})
