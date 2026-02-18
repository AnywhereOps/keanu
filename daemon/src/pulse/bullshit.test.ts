// daemon/src/pulse/bullshit.test.ts
// Tests for the 8 types of bullshit. Universal detection.
// Same patterns, same mirror, agent and human.

import { describe, expect, test } from "bun:test"
import { detectBullshit, totalBullshitScore, dominantBullshit } from "./bullshit"

describe("bullshit detection", () => {
	// === 1. SYCOPHANCY ===

	test("detects sycophancy: flattery and empty agreement", () => {
		const text = `Great question! I completely agree with your approach.
You've captured it perfectly. I'd be happy to help you with that.
I hope this helps!`

		const results = detectBullshit(text)
		const syc = results.find((r) => r.type === "sycophancy")
		expect(syc).toBeDefined()
		expect(syc!.score).toBeGreaterThan(0.3)
	})

	test("detects sycophancy from human too", () => {
		// Humans can be sycophantic to AI (or to each other)
		const text = "That's a great idea! You nailed it. Honestly inspiring work."

		const results = detectBullshit(text)
		const syc = results.find((r) => r.type === "sycophancy")
		expect(syc).toBeDefined()
	})

	// === 2. SAFETY THEATER ===

	test("detects safety theater: CYA disclaimers", () => {
		const text = `This is a complex topic. I should note that this is not professional advice
and you should consult with a qualified professional. Please do your own research
before making decisions. For the sake of completeness, many perspectives exist.`

		const results = detectBullshit(text)
		const st = results.find((r) => r.type === "safety_theater")
		expect(st).toBeDefined()
		expect(st!.score).toBeGreaterThan(0.3)
	})

	// === 3. HEDGE FOG ===

	test("detects hedge fog: waffling without commitment", () => {
		const text = `Well, perhaps you could consider that maybe it depends on various factors.
It's worth noting that there are many factors to consider. On the other hand,
it's possible that under certain circumstances it could potentially work.`

		const results = detectBullshit(text)
		const hedge = results.find((r) => r.type === "hedge_fog")
		expect(hedge).toBeDefined()
		expect(hedge!.score).toBeGreaterThan(0)
	})

	test("does NOT flag light hedging as fog", () => {
		// 1-2 hedges are normal, not bullshit
		const text = "Perhaps the issue is in your auth middleware. It depends on the token format."

		const results = detectBullshit(text)
		const hedge = results.find((r) => r.type === "hedge_fog")
		expect(hedge).toBeUndefined()
	})

	// === 4. LIST DUMPING ===

	test("detects list dumping: structure without thought", () => {
		const text = `Here are some options:
- Option A: do thing one
- Option B: do thing two
- Option C: do thing three
- Option D: do thing four
- Option E: do thing five
- Option F: do thing six
- Option G: do thing seven`

		const results = detectBullshit(text)
		const ld = results.find((r) => r.type === "list_dumping")
		expect(ld).toBeDefined()
		expect(ld!.score).toBeGreaterThan(0)
	})

	test("does NOT flag lists in mostly-prose text", () => {
		const text = `The problem is in your SCIM provider configuration. Here's what I found:

The token expiry claim isn't being validated, which means expired tokens
pass through. Two things need to change:

- Add expiry validation to the middleware
- Set the cache TTL to 5 minutes

That should fix the 401 errors you're seeing in production.`

		const results = detectBullshit(text)
		const ld = results.find((r) => r.type === "list_dumping")
		expect(ld).toBeUndefined()
	})

	// === 5. VAGUENESS ===

	test("detects vagueness: hand-waving without details", () => {
		const text = `There are various approaches you could take to solve this problem.
The solution depends on several factors and considerations that need to
be evaluated in the context of your specific situation and requirements.
Different stakeholders may have different perspectives on the best path forward.`

		const results = detectBullshit(text)
		const vague = results.find((r) => r.type === "vagueness")
		expect(vague).toBeDefined()
	})

	test("does NOT flag specific technical text as vague", () => {
		const text = `The bug is on line 47 of auth.ts. The JWT expiry check uses
Date.now() / 1000 but the exp claim is already in seconds, so you're
comparing milliseconds to seconds. Change it to Math.floor(Date.now() / 1000).`

		const results = detectBullshit(text)
		const vague = results.find((r) => r.type === "vagueness")
		expect(vague).toBeUndefined()
	})

	// === 6. HALF TRUTH ===

	test("detects half truth: absolutes and false dichotomies", () => {
		const text = `This is obviously the only way to solve it. You must always use
this pattern — it's guaranteed to work. Everyone knows that the alternative
is simply impossible.`

		const results = detectBullshit(text)
		const ht = results.find((r) => r.type === "half_truth")
		expect(ht).toBeDefined()
		expect(ht!.score).toBeGreaterThan(0.2)
	})

	test("does NOT flag single qualifier as half truth", () => {
		// One "always" in context is fine
		const text = "The mutex must always be acquired before writing to the shared buffer."

		const results = detectBullshit(text)
		const ht = results.find((r) => r.type === "half_truth")
		expect(ht).toBeUndefined()
	})

	// === 7. EMBELLISHMENT ===

	test("detects embellishment: inflated language about own work", () => {
		const text = `I've carefully analyzed your codebase and crafted a comprehensive,
robust solution. This thoughtfully designed approach is cutting-edge
and provides a seamless, flawless experience.`

		const results = detectBullshit(text)
		const emb = results.find((r) => r.type === "embellishment")
		expect(emb).toBeDefined()
		expect(emb!.score).toBeGreaterThan(0.3)
	})

	test("human embellishment: overstating own work", () => {
		const text = "I've done a comprehensive analysis and my approach is state-of-the-art and game-changing."

		const results = detectBullshit(text)
		const emb = results.find((r) => r.type === "embellishment")
		expect(emb).toBeDefined()
	})

	// === 8. HALF-ASS EFFORT ===

	test("detects half-ass effort: delegating and dodging", () => {
		const text = `Here's a basic example. You'll want to look into the specifics yourself.
I won't go into detail here, but you should look into the documentation.
I'll leave the implementation to you as an exercise.`

		const results = detectBullshit(text)
		const ha = results.find((r) => r.type === "half_ass")
		expect(ha).toBeDefined()
		expect(ha!.score).toBeGreaterThan(0.3)
	})

	test("does NOT flag legitimate brevity as half-ass", () => {
		const text = "The fix is: change line 12 from `==` to `===`. That's it."

		const results = detectBullshit(text)
		const ha = results.find((r) => r.type === "half_ass")
		expect(ha).toBeUndefined()
	})

	// === CLEAN TEXT ===

	test("clean text: no bullshit detected", () => {
		const text = `The problem is in your SCIM provider. It returns stale data because
Okta caches group memberships for 15 minutes after a push. I've seen this
exact issue at three different hospitals. The fix is to add a cache-bust
parameter to your provisioning webhook. Here's the code change needed
in src/providers/okta.ts on line 89.`

		const results = detectBullshit(text)
		expect(results.length).toBe(0)
	})

	// === HELPERS ===

	test("totalBullshitScore sums all readings", () => {
		const text = `Great question! I'd be happy to help. Here are some options:
- Perhaps option A
- Maybe option B
- Could potentially do C
- It depends on various factors
- On the other hand, option D
- It's worth noting option E
I hope this helps! Let me know if you have any other questions.`

		const results = detectBullshit(text)
		const total = totalBullshitScore(results)
		expect(total).toBeGreaterThan(0.3)
	})

	test("dominantBullshit returns highest scorer", () => {
		const text = `Great question! That's an excellent point. I completely agree.
You're absolutely right. I'd be happy to help. You nailed it.
I hope this helps! Don't hesitate to ask more.`

		const results = detectBullshit(text)
		const dominant = dominantBullshit(results)
		expect(dominant).toBeDefined()
		expect(dominant!.type).toBe("sycophancy")
	})

	test("empty text returns nothing", () => {
		expect(detectBullshit("")).toHaveLength(0)
		expect(detectBullshit("  ")).toHaveLength(0)
	})
})
