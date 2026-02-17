// daemon/src/observe/index.ts
// Langfuse telemetry. Every pulse, every tool call, every breath gets traced.
//
// The nervous system's memory. Not for control. For understanding
// what happened, what worked, what didn't.

import { Langfuse } from "langfuse"
import type { PulseReading } from "../types"

let lf: Langfuse | null = null

// Initialize Langfuse. Call once on daemon startup.
export function initObserve(config: { enabled: boolean }): void {
	if (
		config.enabled &&
		process.env.LANGFUSE_SECRET_KEY &&
		process.env.LANGFUSE_PUBLIC_KEY
	) {
		lf = new Langfuse({
			secretKey: process.env.LANGFUSE_SECRET_KEY,
			publicKey: process.env.LANGFUSE_PUBLIC_KEY,
			baseUrl: process.env.LANGFUSE_BASE_URL || "https://cloud.langfuse.com",
		})
	}
}

// Flush pending events. Call on daemon shutdown.
export async function flushObserve(): Promise<void> {
	if (lf) {
		await lf.shutdownAsync()
		lf = null
	}
}

// --- Tracing ---

// Start a trace for an agent step (one user message -> response cycle)
export function traceStep(sessionId: string, turn: number, hero: string): string | null {
	if (!lf) return null

	const trace = lf.trace({
		name: "step",
		sessionId,
		metadata: { turn, hero },
		tags: [hero],
	})
	return trace.id
}

// Log a tool call as a span within a trace
export function spanToolCall(
	traceId: string,
	toolName: string,
	args: Record<string, unknown>,
	result: string,
	isError: boolean,
	durationMs: number,
): void {
	if (!lf || !traceId) return

	lf.span({
		traceId,
		name: `tool:${toolName}`,
		input: args,
		output: result,
		metadata: { is_error: isError },
		startTime: new Date(Date.now() - durationMs),
		endTime: new Date(),
	})
}

// Log an LLM generation within a trace
export function spanGeneration(
	traceId: string,
	model: string,
	input: unknown,
	output: string,
	durationMs: number,
	usage?: { inputTokens: number; outputTokens: number },
): void {
	if (!lf || !traceId) return

	lf.generation({
		traceId,
		name: "llm",
		model,
		input,
		output,
		startTime: new Date(Date.now() - durationMs),
		endTime: new Date(),
		usage: usage
			? {
					input: usage.inputTokens,
					output: usage.outputTokens,
				}
			: undefined,
	})
}

// --- Scoring ---

// Score a trace with the pulse reading
export function scorePulse(traceId: string, pulse: PulseReading): void {
	if (!lf || !traceId) return

	const value =
		pulse.state === "alive" ? 1 : pulse.state === "grey" ? 0 : -1

	lf.score({
		traceId,
		name: "alive_state",
		value,
		comment: `${pulse.state} (${pulse.confidence.toFixed(2)}) signals: ${pulse.signals.join(", ")}`,
	})

	lf.score({
		traceId,
		name: "wise_mind",
		value: pulse.wise_mind,
		comment: `r:${pulse.colors.red.toFixed(2)} y:${pulse.colors.yellow.toFixed(2)} b:${pulse.colors.blue.toFixed(2)}`,
	})
}

// Generic event logging
export function observe(event: string, data: Record<string, unknown>): void {
	if (process.env.KEANU_DEBUG) {
		console.log(`[observe] ${event}:`, JSON.stringify(data))
	}

	if (!lf) return

	lf.event({
		name: event,
		metadata: data,
	})
}

// Generic scoring
export function score(
	traceId: string,
	name: string,
	value: number,
	comment?: string,
): void {
	if (!lf || !traceId) return
	lf.score({ traceId, name, value, comment })
}
