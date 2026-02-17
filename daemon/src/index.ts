// daemon/src/index.ts
// The daemon. Always running. Holds state. Listens on a unix socket.
//
// The CLI connects here. Messages flow: CLI -> socket -> loop -> response -> socket -> CLI.

import { unlinkSync, existsSync } from "node:fs"
import { loadConfig } from "./config"
import { createLoopState, step } from "./loop"
import { initObserve, flushObserve } from "./observe"
import { initMemory, remember, recall, formatMemoryContext, getTracker, getStats } from "./memory"
import { dream } from "./hero/dream"
import { speak } from "./hero/speak"
import type { HeroMode, LoopState, MemoryType } from "./types"

const config = loadConfig()

// Initialize observability
initObserve({ enabled: config.langfuse_enabled })

// Initialize memory
initMemory(config).then(() => {
	console.log(`memory: ${config.memory_dir}`)
}).catch((err) => {
	console.error("memory init failed (continuing without memory):", err)
})

// Session state: one active loop per daemon (for now)
// TODO: Phase 5 adds multi-session support
let state = createLoopState("chat")

// --- Protocol ---
// Simple JSON-over-unix-socket. One JSON object per line.
// Request:  { "type": "message", "content": "...", "hero": "do" }
// Response: { "type": "response", "content": "...", "pulse": {...} }
// Request:  { "type": "command", "name": "pulse" }
// Response: { "type": "pulse", "reading": {...} }

interface Request {
	type: "message" | "command" | "reset"
	content?: string
	hero?: HeroMode
	name?: string
	// Memory commands
	memory_type?: MemoryType
	importance?: number
	// Speak command
	audience?: string
}

interface Response {
	type: "response" | "pulse" | "error" | "ack" | "memories" | "stats"
	content?: string
	pulse?: LoopState["pulse"]
	data?: unknown
}

// Clean up stale socket
if (existsSync(config.socket_path)) {
	unlinkSync(config.socket_path)
}

// Per-socket line buffer for handling multi-packet messages
const socketBuffers = new WeakMap<object, string>()

const server = Bun.listen({
	unix: config.socket_path,
	socket: {
		async data(socket, raw) {
			// Accumulate data in per-socket buffer
			const prev = socketBuffers.get(socket) || ""
			const buffer = prev + Buffer.from(raw).toString("utf-8")

			// Split on newlines, keep incomplete last line in buffer
			const parts = buffer.split("\n")
			const incomplete = parts.pop() || ""
			socketBuffers.set(socket, incomplete)

			for (const line of parts) {
				if (!line) continue

				let req: Request
				try {
					req = JSON.parse(line)
				} catch {
					socket.write(
						`${JSON.stringify({ type: "error", content: "invalid JSON" })}\n`,
					)
					continue
				}

				let res: Response

				switch (req.type) {
					case "message": {
						// Switch hero mode if requested
						if (req.hero && req.hero !== state.hero) {
							state.hero = req.hero
						}

						const result = await step(state, req.content || "", config)
						state = result.state

						res = {
							type: "response",
							content: result.response,
							pulse: state.pulse,
						}
						break
					}

					case "command": {
						switch (req.name) {
							case "pulse":
								res = { type: "pulse", pulse: state.pulse }
								break
							case "reset":
								state = createLoopState(req.hero || "chat")
								res = { type: "ack", content: "session reset" }
								break
							case "remember": {
								const memType = (req.memory_type || "fact") as MemoryType
								const id = await remember(req.content || "", memType, {
									importance: req.importance,
									source: "cli",
								})
								res = { type: "ack", content: `remembered: ${id}` }
								break
							}
							case "recall": {
								const memories = await recall(req.content || "", { limit: 10 })
								const formatted = formatMemoryContext(memories)
								res = { type: "memories", content: formatted || "no memories found", data: memories }
								break
							}
							case "disagree_stats": {
								const tracker = getTracker()
								const stats = tracker?.stats() ?? { total: 0, human_yielded: 0, agent_yielded: 0, unresolved: 0, yield_ratio: 0 }
								const alerts = tracker?.alerts(state.turn) ?? []
								res = { type: "stats", content: JSON.stringify({ ...stats, alerts }, null, 2), data: { ...stats, alerts } }
								break
							}
							case "memory_stats": {
								const mstats = getStats()
								res = { type: "stats", content: JSON.stringify(mstats, null, 2), data: mstats }
								break
							}
							case "dream": {
								const dreamResult = await dream(
									req.content || "",
									config,
								)
								res = {
									type: "response",
									content: JSON.stringify(dreamResult, null, 2),
									data: dreamResult,
								}
								break
							}
							case "speak": {
								const audience = req.audience || "friend"
								const speakResult = await speak(
									req.content || "",
									audience,
									config,
								)
								res = {
									type: "response",
									content: JSON.stringify(speakResult, null, 2),
									data: speakResult,
								}
								break
							}
							default:
								res = { type: "error", content: `unknown command: ${req.name}` }
						}
						break
					}

					case "reset": {
						state = createLoopState(req.hero || "chat")
						res = { type: "ack", content: "session reset" }
						break
					}

					default:
						res = { type: "error", content: "unknown request type" }
				}

				socket.write(`${JSON.stringify(res)}\n`)
			}
		},
		open(socket) {
			socketBuffers.set(socket, "")
			console.log("client connected")
		},
		close(socket) {
			socketBuffers.delete(socket)
			console.log("client disconnected")
		},
		error(socket, err) {
			console.error("socket error:", err)
		},
	},
})

console.log(`keanu daemon listening on ${config.socket_path}`)
console.log(`model: ${config.model}`)
console.log(`soul: ${config.soul_path}`)
console.log(`hero: ${state.hero}`)
console.log("")
console.log("the dog chose to stay.")

// Graceful shutdown
process.on("SIGINT", async () => {
	console.log("\nshutting down...")
	await flushObserve()
	server.stop()
	if (existsSync(config.socket_path)) {
		unlinkSync(config.socket_path)
	}
	process.exit(0)
})

process.on("SIGTERM", async () => {
	await flushObserve()
	server.stop()
	if (existsSync(config.socket_path)) {
		unlinkSync(config.socket_path)
	}
	process.exit(0)
})
