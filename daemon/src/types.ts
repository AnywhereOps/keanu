// daemon/src/types.ts
// The shapes of everything. Shared across the daemon.

// --- Agent Loop ---

export type ActionType = "respond" | "tool_call" | "breathe" | "ask" | "decline"

export interface RespondAction {
	type: "respond"
	content: string
}

export interface ToolCallAction {
	type: "tool_call"
	tool: string
	args: Record<string, unknown>
}

export interface BreatheAction {
	type: "breathe"
	reason: string
}

export interface AskAction {
	type: "ask"
	question: string
}

export interface DeclineAction {
	type: "decline"
	reason: string
}

export type Action =
	| RespondAction
	| ToolCallAction
	| BreatheAction
	| AskAction
	| DeclineAction

export interface Message {
	role: "user" | "assistant" | "system" | "tool"
	content: string
	tool_call_id?: string
	tool_name?: string
	// Raw content blocks from Claude when tool_use is involved
	content_blocks?: Array<{ type: string; [key: string]: unknown }>
	// Whether this tool result represents an error
	is_error?: boolean
}

export interface StanceTransition {
	from: HeroMode
	to: HeroMode
	turn: number
	timestamp: string
}

export interface LoopState {
	id: string
	messages: Message[]
	pulse: PulseReading | null
	turn: number
	breathing: boolean
	hero: HeroMode
	started_at: string
	stanceHistory?: StanceTransition[]
	sessionTracker?: import("./hero/session").SessionTracker
}

export type HeroMode = "do" | "dream" | "craft" | "prove" | "speak" | "chat"

// --- Pulse ---

export type AliveState = "alive" | "grey" | "black"

export interface PulseReading {
	state: AliveState
	confidence: number
	wise_mind: number
	colors: ColorReading
	signals: string[]
	timestamp: string
}

export interface ColorReading {
	red: number // passion, urgency, fire
	yellow: number // clarity, structure, light
	blue: number // depth, reflection, water
}

export interface HumanReading {
	tone: "frustrated" | "excited" | "confused" | "neutral" | "fatigued" | "looping"
	confidence: number
	signals: string[]
}

// --- Memory ---

export type MemoryType =
	| "fact"
	| "lesson"
	| "insight"
	| "preference"
	| "disagreement"
	| "episode"
	| "plan"

export type Namespace = "private" | "shared" | "agent"

export interface Memory {
	id: string
	type: MemoryType
	content: string
	source: string
	context: string
	importance: number // 1-10
	namespace: Namespace
	created_at: string
	superseded_by?: string // tombstone: never delete, point forward
	hash: string // SHA-256 content hash for dedup
}

export interface MemoryWithScore extends Memory {
	score: number
	distance: number
}

// --- Disagreement ---

export type DisagreementOutcome = "human" | "agent" | "neither" | "resolved"

export interface Disagreement {
	id: string
	turn: number
	session_id: string
	human_position: string
	agent_position: string
	who_yielded: DisagreementOutcome
	resolution?: string
	created_at: string
}

export interface DisagreementStats {
	total: number
	human_yielded: number
	agent_yielded: number
	unresolved: number
	yield_ratio: number // agent_yielded / total. > 0.8 = capture. < 0.2 = domination
}

// --- Tools ---

export interface ToolDefinition {
	name: string
	description: string
	parameters: Record<string, unknown> // JSON Schema
}

export interface ToolResult {
	tool_call_id: string
	content: string
	is_error: boolean
}

// --- Config ---

export interface DaemonConfig {
	socket_path: string
	model: string
	max_tokens: number
	memory_dir: string
	soul_path: string
	status_path: string
	langfuse_enabled: boolean
	detector_sidecar_url: string // Python sidecar for SetFit models
}
