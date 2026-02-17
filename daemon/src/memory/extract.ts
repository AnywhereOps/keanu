// daemon/src/memory/extract.ts
// Memory extraction from conversations.
//
// The agent decides WHAT to remember and WHY.
// Uses the oracle for LLM calls. Parses structured JSON from response.

import { z } from "zod"
import type { Message, DaemonConfig } from "../types"
import { callOracle, extractJSON } from "../oracle"

// --- Schema (ported from memberberry.py PlanGenerator pattern) ---

const MemoryItemSchema = z.object({
	type: z.enum([
		"fact",
		"lesson",
		"insight",
		"preference",
		"commitment",
		"decision",
	]),
	content: z.string().describe("What to remember. Concise, specific."),
	importance: z
		.number()
		.min(1)
		.max(10)
		.describe(
			"1-3: ambient. 4-6: useful. 7-9: critical. 10: identity-level.",
		),
	reason: z.string().describe("Why this is worth remembering."),
})

const ExtractionSchema = z.object({
	memories: z
		.array(MemoryItemSchema)
		.describe("Memories worth keeping from this exchange. Can be empty."),
})

export type ExtractedMemory = z.infer<typeof MemoryItemSchema>

const EXTRACTION_PROMPT = `You are reviewing a conversation to decide what's worth remembering long-term.

Extract memories that would be useful in future conversations. Be selective — not everything is worth keeping.

Guidelines:
- FACT: concrete information (names, dates, technical details)
- LESSON: something learned from a mistake or success
- INSIGHT: a realization or connection that wasn't obvious
- PREFERENCE: how the human likes things done
- COMMITMENT: something promised or agreed to
- DECISION: a choice made and why

Importance scale:
- 1-3: ambient context (nice to know)
- 4-6: useful working knowledge
- 7-9: critical for future interactions
- 10: identity-level (core values, non-negotiables)

If nothing is worth remembering, return an empty memories array. Most exchanges don't produce memories. That's fine.`

/**
 * Extract memories from recent conversation messages.
 * Returns structured memories the agent thinks are worth keeping.
 */
export async function extractMemories(
	messages: Message[],
	config: DaemonConfig,
): Promise<ExtractedMemory[]> {
	// Only look at recent exchange (last 10 messages)
	const recent = messages.slice(-10)
	if (recent.length < 2) return [] // need at least a back-and-forth

	// Build conversation text
	const conversationText = recent
		.filter((m) => m.role === "user" || m.role === "assistant")
		.map((m) => `${m.role}: ${m.content}`)
		.join("\n\n")

	try {
		const response = await callOracle({
			maxTokens: 1024,
			system: EXTRACTION_PROMPT,
			messages: [
				{
					role: "user",
					content: `Review this conversation and extract any memories worth keeping:\n\n${conversationText}`,
				},
			],
		}, config)

		// Extract JSON from the response (balanced brace matching)
		const parsed = extractJSON(response.text)
		if (!parsed) return []

		const validated = ExtractionSchema.safeParse(parsed)
		if (!validated.success) return []

		return validated.data.memories
	} catch {
		// Extraction is best-effort. Don't crash the loop.
		return []
	}
}
