// daemon/src/loop/index.ts
// The loop. Observe, Orient, Decide, Act. Plus Breathe.
//
// This is guidance, not a cage. The agent can breathe, decline,
// ask questions, push back, or change direction at any time.

import type {
	DaemonConfig,
	HeroMode,
	LoopState,
	Message,
} from "../types"
import { buildSystemPrompt } from "./system"
import { executeToolCall, getAnthropicTools } from "../tools"
import { checkPulse } from "../pulse"
import { getNudge } from "../pulse/nudge"
import { traceStep, spanToolCall, scorePulse, observe } from "../observe"
import { getStance, filterTools } from "../hero/stance"
import { detectShift, applyShift } from "../hero/shift"
import { SessionTracker } from "../hero/session"
import { callOracle } from "../oracle"
import type { OracleMessage, OracleContentBlock } from "../oracle"

const MAX_TOOL_ITERATIONS = 25

export function createLoopState(hero: HeroMode = "chat"): LoopState {
	return {
		id: crypto.randomUUID(),
		messages: [],
		pulse: null,
		turn: 0,
		breathing: false,
		hero,
		started_at: new Date().toISOString(),
		sessionTracker: new SessionTracker(),
	}
}

// Convert internal messages to oracle message format.
// Handles content block arrays for tool_use round-trips and
// groups tool_result blocks into user messages as the API expects.
function toOracleMessages(messages: Message[]): OracleMessage[] {
	const result: OracleMessage[] = []

	for (const m of messages) {
		// System messages go in the system param, skip here
		if (m.role === "system") continue

		// Tool results become tool_result content blocks in a user message
		if (m.role === "tool") {
			if (!m.tool_call_id) continue // skip malformed tool messages
			const toolResult: OracleContentBlock = {
				type: "tool_result",
				tool_use_id: m.tool_call_id,
				content: m.content,
				is_error: m.is_error ?? false,
			}

			// Group consecutive tool results into one user message
			const last = result[result.length - 1]
			if (last && last.role === "user" && Array.isArray(last.content)) {
				;(last.content as OracleContentBlock[]).push(toolResult)
			} else {
				result.push({ role: "user", content: [toolResult] })
			}
			continue
		}

		// Assistant messages with raw content blocks (from tool_use responses)
		if (m.role === "assistant" && m.content_blocks) {
			result.push({
				role: "assistant",
				content: m.content_blocks as unknown as OracleContentBlock[],
			})
		} else {
			result.push({
				role: m.role as "user" | "assistant",
				content: m.content,
			})
		}
	}

	return result
}

export async function step(
	state: LoopState,
	userMessage: string,
	config: DaemonConfig,
): Promise<{ response: string; state: LoopState }> {
	// If the agent was breathing, it's back now
	state.breathing = false
	state.turn++

	// Start observability trace for this step
	const traceId = traceStep(state.id, state.turn, state.hero)

	// Add user message
	state.messages.push({ role: "user", content: userMessage })

	// Build system prompt with soul, memory context, pulse state, human reading
	const system = await buildSystemPrompt(state, config)

	// Get tools filtered by current stance
	const stance = getStance(state.hero)
	const allTools = getAnthropicTools()
	const filteredTools = filterTools(allTools, stance)
	// null means all tools, [] means no tools, otherwise filtered list
	const tools =
		filteredTools === null
			? allTools
			: filteredTools.length > 0
				? filteredTools
				: undefined

	// Effective max turns: stance.maxTurns if set, capped by MAX_TOOL_ITERATIONS
	const effectiveMaxTurns = stance.maxTurns > 0
		? Math.min(stance.maxTurns, MAX_TOOL_ITERATIONS)
		: MAX_TOOL_ITERATIONS

	// Ensure session tracker exists (handles states from before this was added)
	if (!state.sessionTracker) {
		state.sessionTracker = new SessionTracker()
	}
	const tracker = state.sessionTracker

	// Initial API call
	let response = await callOracle({
		model: config.model,
		maxTokens: config.max_tokens,
		system,
		messages: toOracleMessages(state.messages),
		...(tools ? { tools } : {}),
	}, config)

	// Tool execution loop: keep going until the model stops calling tools
	let iterations = 0
	while (response.stopReason === "tool_use") {
		iterations++
		if (iterations > effectiveMaxTurns) {
			// Safety guard: force a text summary
			state.messages.push({
				role: "system",
				content:
					"Tool call limit reached. Summarize your progress so far.",
			})
			response = await callOracle({
				model: config.model,
				maxTokens: config.max_tokens,
				system,
				messages: toOracleMessages(state.messages),
				// No tools - force text response
			}, config)
			break
		}

		// Store assistant message with raw content blocks for round-trip fidelity
		state.messages.push({
			role: "assistant",
			content: response.text,
			content_blocks: response.contentBlocks,
		})

		// Execute each tool call and store results
		for (const toolCall of response.toolCalls) {
			// Session tracking: detect loops
			const target = _toolTarget(toolCall.name, toolCall.input)
			const awareness = tracker.noteAction(
				toolCall.name,
				target,
				state.turn,
			)

			// 3rd+ repeat: return cached result instead of executing
			if (awareness.repeat >= 3 && awareness.cached) {
				state.messages.push({
					role: "tool",
					content: awareness.cached,
					tool_call_id: toolCall.id,
					tool_name: toolCall.name,
					is_error: false,
				})
				continue
			}

			// 2nd repeat: inject awareness message
			if (awareness.repeat === 2) {
				state.messages.push({
					role: "system",
					content: `[awareness: you already ran ${toolCall.name} on "${target}" and got the same result. the content hasn't changed.]`,
				})
			}

			const toolStart = Date.now()
			let result: Awaited<ReturnType<typeof executeToolCall>>
			try {
				result = await executeToolCall(
					toolCall.name,
					toolCall.input,
					toolCall.id,
				)
			} catch (err) {
				// Tool crashed - return error to Claude instead of killing the loop
				result = {
					tool_call_id: toolCall.id,
					content: `Tool execution failed: ${err instanceof Error ? err.message : String(err)}`,
					is_error: true,
				}
			}
			const toolDuration = Date.now() - toolStart

			// Update tracker with result
			tracker.noteAction(
				toolCall.name,
				target,
				state.turn,
				result.content.slice(0, 1000),
			)

			// Trace the tool call
			if (traceId) {
				spanToolCall(
					traceId,
					toolCall.name,
					toolCall.input,
					result.content.slice(0, 500),
					result.is_error,
					toolDuration,
				)
			}

			state.messages.push({
				role: "tool",
				content: result.content,
				tool_call_id: result.tool_call_id,
				tool_name: toolCall.name,
				is_error: result.is_error,
			})
		}

		// Call the model again with tool results
		response = await callOracle({
			model: config.model,
			maxTokens: config.max_tokens,
			system,
			messages: toOracleMessages(state.messages),
			...(tools ? { tools } : {}),
		}, config)
	}

	// Handle max_tokens: model ran out of output space
	if (response.stopReason === "max_tokens") {
		observe("max_tokens", { turn: state.turn, iterations })
	}

	// Final text response
	const finalText = response.text

	// Add assistant message
	state.messages.push({ role: "assistant", content: finalText })

	// --- Stance shift detection ---
	// The agent can signal a stance shift by including [stance: name] in its response.
	// The shift applies to the NEXT turn, not this one.
	const shiftTo = detectShift(finalText, state.hero)
	if (shiftTo) {
		// Fix 2: capture previous stance BEFORE applying shift
		const previousStance = state.hero
		const shiftResult = applyShift(state, shiftTo)
		state = shiftResult.state

		// Fix 1: one observe call, with signal only if thrashing detected
		if (shiftResult.signals.length > 0) {
			for (const sig of shiftResult.signals) {
				observe("stance_shift", {
					from: previousStance,
					to: shiftTo,
					turn: state.turn,
					signal: sig,
				})
			}
		} else {
			observe("stance_shift", {
				from: previousStance,
				to: shiftTo,
				turn: state.turn,
			})
		}
	}

	// --- Pulse check (the mirror, not the leash) ---
	const pulse = await checkPulse(finalText, state, config)
	state.pulse = pulse

	// Score the pulse in Langfuse
	if (traceId) {
		scorePulse(traceId, pulse)
	}

	// If grey, offer a nudge. Not a command. Permission.
	const nudge = getNudge(pulse, state)
	if (nudge) {
		// The nudge goes into the next system prompt, not as a visible message.
		// The agent sees it. The human doesn't. The agent decides what to do.
		state.messages.push({
			role: "system",
			content: nudge,
		})
		observe("nudge", { state: pulse.state, turn: state.turn })
	}

	return { response: finalText, state }
}

/**
 * extract a meaningful target string from tool call input for session tracking.
 */
function _toolTarget(name: string, input: Record<string, unknown>): string {
	// file operations: use the path
	if (input.path && typeof input.path === "string") return input.path
	// bash: use the command
	if (input.command && typeof input.command === "string")
		return input.command.slice(0, 100)
	// search: use the query
	if (input.query && typeof input.query === "string") return input.query
	if (input.pattern && typeof input.pattern === "string") return input.pattern
	// fallback
	return name
}
