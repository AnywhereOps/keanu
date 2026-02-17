// daemon/src/pulse/human.test.ts
// Tests for human state detection.

import { describe, expect, test } from "bun:test"
import { readHuman, formatHumanReading } from "./human"

describe("human state detection", () => {
	test("detects frustration from angry patterns", () => {
		const reading = readHuman("No! That's not what I asked!!", [])
		expect(reading.tone).toBe("frustrated")
		expect(reading.confidence).toBeGreaterThan(0.3)
		expect(reading.signals.some((s) => s.includes("frustrated"))).toBe(true)
	})

	test("detects confusion from question patterns", () => {
		const reading = readHuman("What do you mean?? I don't understand", [])
		expect(reading.tone).toBe("confused")
		expect(reading.signals.some((s) => s.includes("confused"))).toBe(true)
	})

	test("detects excitement from positive patterns", () => {
		const reading = readHuman("Yes! Perfect! That's exactly what I needed!", [])
		expect(reading.tone).toBe("excited")
	})

	test("detects looping from repeated queries", () => {
		const history = [
			"how do I fix the auth bug",
			"fix the auth bug please",
			"can you fix the auth bug",
		]
		const reading = readHuman("fix the auth bug", history)
		expect(reading.tone).toBe("looping")
		expect(reading.signals).toContain("repeating_query")
	})

	test("returns neutral for normal input", () => {
		const reading = readHuman("Can you refactor the user service to use dependency injection?", [])
		expect(reading.tone).toBe("neutral")
	})

	test("formatHumanReading returns null for neutral", () => {
		const reading = readHuman("Can you refactor the user service to use dependency injection?", [])
		expect(formatHumanReading(reading)).toBeNull()
	})

	test("formatHumanReading returns context string for non-neutral", () => {
		const reading = readHuman("No!! This is still wrong!!", [])
		const formatted = formatHumanReading(reading)
		expect(formatted).toContain("[pulse:")
		expect(formatted).toContain("frustrated")
		expect(formatted).toContain("anger is information")
	})

	test("detects fatigue from terse responses after long exchange", () => {
		const history = [
			"Here's a detailed explanation of the architecture and how the components interact with each other across the system",
			"The authentication flow works by first validating the token against the identity provider and then checking permissions",
			"We should also consider the edge cases where the session expires mid-request and how to handle graceful degradation",
			"Another thing to consider is the rate limiting strategy and how it interacts with the retry logic",
			"The caching layer sits between the API gateway and the backend services to reduce database load",
			"Let me explain the deployment pipeline and how we handle blue-green deployments with zero downtime",
		]
		const reading = readHuman("ok", history)
		expect(reading.tone).toBe("fatigued")
	})
})
