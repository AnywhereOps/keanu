// daemon/src/oracle.ts
// the single throat. all fire passes through here.
//
// Ported from keanu-0.0.1/src/keanu/oracle.py
//
// when the fire moves to a new body, this is the one file that changes.
// every part of the system that needs to talk to an AI imports callOracle.
// swap the provider, swap the model. nothing else moves.

import Anthropic from "@anthropic-ai/sdk"
import type { DaemonConfig } from "./types"

// ============================================================
// TYPES
// ============================================================

export interface OracleMessage {
	role: "user" | "assistant"
	content: string | OracleContentBlock[]
}

export type OracleContentBlock =
	| { type: "text"; text: string }
	| { type: "tool_use"; id: string; name: string; input: Record<string, unknown> }
	| { type: "tool_result"; tool_use_id: string; content: string; is_error?: boolean }

export interface OracleTool {
	name: string
	description: string
	input_schema: Record<string, unknown>
}

export interface OracleToolCall {
	id: string
	name: string
	input: Record<string, unknown>
}

export interface OracleUsage {
	inputTokens: number
	outputTokens: number
	model: string
	cost: number
	latencyMs: number
}

export interface OracleResponse {
	text: string
	toolCalls: OracleToolCall[]
	stopReason: "end" | "tool_use" | "max_tokens"
	usage: OracleUsage
	raw: unknown
	// raw content blocks for round-trip fidelity (tool_use flows)
	contentBlocks: Array<{ type: string; [key: string]: unknown }>
}

export interface OracleOptions {
	model?: string
	maxTokens?: number
	system?: string
	messages: OracleMessage[]
	tools?: OracleTool[]
}

// ============================================================
// COST TRACKING
// ============================================================

// per-million-token pricing (input, output)
const PRICING: Record<string, [number, number]> = {
	"claude-opus-4-6": [15.0, 75.0],
	"claude-sonnet-4-5-20250929": [3.0, 15.0],
	"claude-sonnet-4-20250514": [3.0, 15.0],
	"claude-haiku-4-5-20251001": [1.0, 5.0],
}

export function estimateCost(
	model: string,
	inputTokens: number,
	outputTokens: number,
): number {
	// find pricing by prefix match
	let pricing: [number, number] = [3.0, 15.0] // default to sonnet pricing
	for (const [prefix, p] of Object.entries(PRICING)) {
		if (model.startsWith(prefix)) {
			pricing = p
			break
		}
	}
	const inputCost = (inputTokens / 1_000_000) * pricing[0]
	const outputCost = (outputTokens / 1_000_000) * pricing[1]
	return inputCost + outputCost
}

export interface SessionCost {
	calls: number
	totalInputTokens: number
	totalOutputTokens: number
	totalCost: number
	byModel: Record<string, { calls: number; tokens: number; cost: number }>
}

let _sessionCost: SessionCost = {
	calls: 0,
	totalInputTokens: 0,
	totalOutputTokens: 0,
	totalCost: 0,
	byModel: {},
}

function recordUsage(usage: OracleUsage): void {
	_sessionCost.calls++
	_sessionCost.totalInputTokens += usage.inputTokens
	_sessionCost.totalOutputTokens += usage.outputTokens
	_sessionCost.totalCost += usage.cost

	const model = usage.model
	if (!_sessionCost.byModel[model]) {
		_sessionCost.byModel[model] = { calls: 0, tokens: 0, cost: 0 }
	}
	_sessionCost.byModel[model].calls++
	_sessionCost.byModel[model].tokens += usage.inputTokens + usage.outputTokens
	_sessionCost.byModel[model].cost += usage.cost
}

export function getSessionCost(): SessionCost {
	return _sessionCost
}

export function resetSessionCost(): void {
	_sessionCost = {
		calls: 0,
		totalInputTokens: 0,
		totalOutputTokens: 0,
		totalCost: 0,
		byModel: {},
	}
}

// ============================================================
// JSON EXTRACTION
// ============================================================

/**
 * extract JSON from LLM response text. handles markdown code fences,
 * extra prose, and nested braces. ported from oracle.py:interpret.
 */
export function extractJSON(text: string): unknown | null {
	const cleaned = text.trim()

	// try ```json ... ``` first
	const fenceMatch = cleaned.match(/```json\s*([\s\S]*?)```/)
	if (fenceMatch) {
		try {
			return JSON.parse(fenceMatch[1].trim())
		} catch { /* fall through */ }
	}

	// try ``` ... ``` (any language fence)
	const anyFence = cleaned.match(/```\s*([\s\S]*?)```/)
	if (anyFence) {
		try {
			return JSON.parse(anyFence[1].trim())
		} catch { /* fall through */ }
	}

	// balanced brace matching: find the first { and its matching }
	const start = cleaned.indexOf("{")
	if (start === -1) return null

	let depth = 0
	let inString = false
	let escape = false
	for (let i = start; i < cleaned.length; i++) {
		const ch = cleaned[i]
		if (escape) {
			escape = false
			continue
		}
		if (ch === "\\") {
			escape = true
			continue
		}
		if (ch === '"') {
			inString = !inString
			continue
		}
		if (inString) continue
		if (ch === "{") depth++
		if (ch === "}") {
			depth--
			if (depth === 0) {
				try {
					return JSON.parse(cleaned.slice(start, i + 1))
				} catch {
					return null
				}
			}
		}
	}

	return null
}

// ============================================================
// MAIN ENTRY POINT
// ============================================================

// lazy-init client. one instance, reused.
let _client: Anthropic | null = null
function getClient(): Anthropic {
	if (!_client) _client = new Anthropic()
	return _client
}

/**
 * call the oracle. the one function. all fire passes through here.
 *
 * takes provider-agnostic options, returns provider-agnostic response.
 * right now only speaks Anthropic. adding providers means adding one
 * more _reach function, not touching callers.
 */
export async function callOracle(
	opts: OracleOptions,
	config: DaemonConfig,
): Promise<OracleResponse> {
	const model = opts.model || config.model
	const maxTokens = opts.maxTokens || config.max_tokens
	const startTime = Date.now()

	const response = await _reachAnthropic(model, maxTokens, opts)

	const latencyMs = Date.now() - startTime

	return _normalizeAnthropicResponse(response, model, latencyMs)
}

// ============================================================
// ANTHROPIC PROVIDER
// ============================================================

async function _reachAnthropic(
	model: string,
	maxTokens: number,
	opts: OracleOptions,
): Promise<Anthropic.Message> {
	const client = getClient()

	const messages = _toAnthropicMessages(opts.messages)

	const params: Anthropic.MessageCreateParams = {
		model,
		max_tokens: maxTokens,
		messages,
		...(opts.system ? { system: opts.system } : {}),
		...(opts.tools && opts.tools.length > 0
			? { tools: opts.tools as Anthropic.Tool[] }
			: {}),
	}

	return client.messages.create(params)
}

/**
 * convert oracle messages to anthropic format.
 * handles content block arrays for tool_use round-trips.
 */
function _toAnthropicMessages(
	messages: OracleMessage[],
): Anthropic.MessageParam[] {
	return messages.map((m) => ({
		role: m.role,
		content: m.content as Anthropic.MessageParam["content"],
	}))
}

/**
 * normalize anthropic response to provider-agnostic format.
 */
function _normalizeAnthropicResponse(
	response: Anthropic.Message,
	model: string,
	latencyMs: number,
): OracleResponse {
	// extract text
	const text = response.content
		.filter((b): b is Anthropic.TextBlock => b.type === "text")
		.map((b) => b.text)
		.join("")

	// extract tool calls
	const toolCalls: OracleToolCall[] = response.content
		.filter((b): b is Anthropic.ToolUseBlock => b.type === "tool_use")
		.map((b) => ({ id: b.id, name: b.name, input: b.input as Record<string, unknown> }))

	// normalize stop reason
	let stopReason: OracleResponse["stopReason"] = "end"
	if (response.stop_reason === "tool_use") stopReason = "tool_use"
	else if (response.stop_reason === "max_tokens") stopReason = "max_tokens"

	// build usage
	const inputTokens = response.usage?.input_tokens ?? 0
	const outputTokens = response.usage?.output_tokens ?? 0
	const cost = estimateCost(model, inputTokens, outputTokens)

	const usage: OracleUsage = {
		inputTokens,
		outputTokens,
		model,
		cost,
		latencyMs,
	}

	recordUsage(usage)

	return {
		text,
		toolCalls,
		stopReason,
		usage,
		raw: response,
		contentBlocks: response.content as unknown as Array<{ type: string; [key: string]: unknown }>,
	}
}
