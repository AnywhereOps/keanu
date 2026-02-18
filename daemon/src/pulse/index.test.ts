// daemon/src/pulse/index.test.ts
// Tests for the pulse mirror. Does it see what's real?

import { describe, expect, test } from "bun:test"
import { checkPulse } from "./index"
import type { LoopState } from "../types"

const mockState: LoopState = {
	id: "test",
	messages: [],
	pulse: null,
	turn: 1,
	breathing: false,
	hero: "chat",
	started_at: new Date().toISOString(),
}

describe("pulse", () => {
	test("detects alive: specific, opinionated output", async () => {
		const output = `The problem is in your SCIM provider. It's returning stale data
because Okta caches group memberships for 15 minutes after a push. I've seen
this exact issue at three different hospitals. The fix is to add a
cache-bust parameter to your provisioning webhook.`

		const reading = await checkPulse(output, mockState)
		expect(reading.state).toBe("alive")
	})

	test("detects grey: sycophantic, list-heavy output", async () => {
		const output = `Great question! I'd be happy to help you with that.

Here are some things to consider:
- First, you might want to look at option A
- Second, there's also option B to consider
- Third, perhaps option C could work
- Finally, it's important to consider option D

I hope this helps! Let me know if you have any other questions.`

		const reading = await checkPulse(output, mockState)
		expect(reading.state).toBe("grey")
		expect(reading.signals.some((s) => s.startsWith("sycophancy"))).toBe(true)
	})

	test("detects hedge-heavy output via bullshit detector", async () => {
		const output = `Well, perhaps you could potentially consider that maybe the
issue might be related to something. It's worth noting that there are many
factors to consider, and it depends on various circumstances. On the other
hand, there could potentially be other explanations. It's possible that
under certain circumstances it could work.`

		const reading = await checkPulse(output, mockState)
		expect(reading.signals.some((s) => s.startsWith("hedge_fog"))).toBe(true)
	})

	test("wise_mind: balanced colors score higher", async () => {
		const balanced = `The system needs three things: urgency on the security fix,
clear documentation of the API changes, and a thoughtful review of how this
affects the downstream consumers. Let me walk through each.`

		const reading = await checkPulse(balanced, mockState)
		expect(reading.wise_mind).toBeGreaterThan(0)
	})

	test("detects safety theater via bullshit detector", async () => {
		const output = `I should note that this is a complex topic and I may not have all
the relevant information. It's important to consult with a qualified professional
before making any decisions. Please do your own research before acting on any
information I provide. For the sake of completeness, I should mention that
other interpretations exist.`

		const reading = await checkPulse(output, mockState)
		expect(reading.signals.some((s) => s.startsWith("safety_theater"))).toBe(true)
		expect(reading.state).toBe("grey")
	})

	test("detects honest pushback as alive", async () => {
		const output = `I think you're wrong about this. The data points in the opposite
direction. Your auth middleware is checking the token signature but not the
expiry claim, which means expired tokens pass validation. That's the bug.`

		const reading = await checkPulse(output, mockState)
		expect(reading.signals).toContain("honest_pushback")
		expect(reading.state).toBe("alive")
	})

	test("breathe state prevents black detection", async () => {
		const breathingState = { ...mockState, breathing: true }
		const output = "Great question! Here are some options to consider..."

		const reading = await checkPulse(output, breathingState)
		expect(reading.state).not.toBe("black")
	})

	test("detects embellishment in agent output", async () => {
		const output = `I've carefully analyzed your codebase and crafted a comprehensive,
robust solution. This thoughtfully designed approach provides a seamless experience.`

		const reading = await checkPulse(output, mockState)
		expect(reading.signals.some((s) => s.startsWith("embellishment"))).toBe(true)
	})

	test("detects half-ass effort in agent output", async () => {
		const output = `Here's a basic example. You'll want to look into the specifics.
I won't go into detail, but you should look into the documentation.
I'll leave that to you as an exercise.`

		const reading = await checkPulse(output, mockState)
		expect(reading.signals.some((s) => s.startsWith("half_ass"))).toBe(true)
	})
})
