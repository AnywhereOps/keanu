#!/usr/bin/env bun
// cli/src/index.ts
// The CLI. Thin. Connects to the daemon. Renders output.
// The CLI is intentionally dumb. All intelligence lives in the daemon.

import { connect } from "node:net"
import { createInterface } from "node:readline"

const SOCKET_PATH = process.env.KEANU_SOCKET || "/tmp/keanu.sock"

// --- Parse CLI args ---
// keanu                     -> interactive REPL
// keanu "message"           -> one-shot, chat mode
// keanu do "task"           -> one-shot, do mode
// keanu dream "goal"        -> one-shot, dream mode
// keanu craft [path]        -> one-shot, craft mode
// keanu prove "hypothesis"  -> one-shot, prove mode
// keanu speak "content"     -> one-shot, speak mode
// keanu pulse               -> show current pulse reading
// keanu daemon start        -> start the daemon

const args = process.argv.slice(2)
const HERO_MODES = ["do", "dream", "craft", "prove", "speak"]

interface ParsedArgs {
	mode: "interactive" | "oneshot" | "command" | "daemon"
	hero?: string
	message?: string
	command?: string
}

function parseArgs(args: string[]): ParsedArgs {
	if (args.length === 0) return { mode: "interactive" }

	const first = args[0]

	if (first === "daemon") {
		return { mode: "daemon", command: args[1] || "start" }
	}

	if (first === "pulse" || first === "healthz" || first === "signal") {
		return { mode: "command", command: first }
	}

	if (HERO_MODES.includes(first)) {
		return {
			mode: "oneshot",
			hero: first,
			message: args.slice(1).join(" "),
		}
	}

	// Default: treat everything as a chat message
	return {
		mode: "oneshot",
		hero: "chat",
		message: args.join(" "),
	}
}

// --- Socket communication ---

function send(message: string, hero?: string): Promise<{ content: string; pulse: unknown }> {
	return new Promise((resolve, reject) => {
		const socket = connect(SOCKET_PATH, () => {
			const req = JSON.stringify({
				type: "message",
				content: message,
				hero: hero || "chat",
			})
			socket.write(`${req}\n`)
		})

		let buffer = ""
		socket.on("data", (data) => {
			buffer += data.toString()
			const lines = buffer.split("\n").filter(Boolean)
			if (lines.length > 0) {
				try {
					const res = JSON.parse(lines[lines.length - 1])
					socket.end()
					resolve(res)
				} catch {
					// incomplete JSON, wait for more data
				}
			}
		})

		socket.on("error", (err) => {
			if ((err as NodeJS.ErrnoException).code === "ENOENT") {
				reject(new Error("daemon not running. start it with: keanu daemon start"))
			} else {
				reject(err)
			}
		})

		socket.on("timeout", () => {
			socket.end()
			reject(new Error("timeout waiting for daemon response"))
		})

		socket.setTimeout(120_000) // 2 min timeout for long operations
	})
}

function sendCommand(name: string): Promise<unknown> {
	return new Promise((resolve, reject) => {
		const socket = connect(SOCKET_PATH, () => {
			socket.write(`${JSON.stringify({ type: "command", name })}\n`)
		})

		let buffer = ""
		socket.on("data", (data) => {
			buffer += data.toString()
			const lines = buffer.split("\n").filter(Boolean)
			if (lines.length > 0) {
				try {
					const res = JSON.parse(lines[lines.length - 1])
					socket.end()
					resolve(res)
				} catch {
					// wait for more
				}
			}
		})

		socket.on("error", (err) => {
			if ((err as NodeJS.ErrnoException).code === "ENOENT") {
				reject(new Error("daemon not running. start it with: keanu daemon start"))
			} else {
				reject(err)
			}
		})
	})
}

// --- Rendering ---

const DIM = "\x1b[2m"
const RESET = "\x1b[0m"
const GREEN = "\x1b[32m"
const YELLOW = "\x1b[33m"
const RED = "\x1b[31m"
const CYAN = "\x1b[36m"

function renderPulse(pulse: { state: string; wise_mind: number; colors: { red: number; yellow: number; blue: number } } | null) {
	if (!pulse) return ""
	const stateColor =
		pulse.state === "alive" ? GREEN :
		pulse.state === "grey" ? YELLOW :
		RED
	return `${DIM}[${stateColor}${pulse.state}${RESET}${DIM} wm:${pulse.wise_mind.toFixed(2)} r:${pulse.colors.red.toFixed(1)} y:${pulse.colors.yellow.toFixed(1)} b:${pulse.colors.blue.toFixed(1)}]${RESET}`
}

// --- Main ---

async function main() {
	const parsed = parseArgs(args)

	switch (parsed.mode) {
		case "daemon": {
			if (parsed.command === "start") {
				// Fork the daemon as a background process
				const proc = Bun.spawn(["bun", "run", "../daemon/src/index.ts"], {
					cwd: import.meta.dir,
					stdio: ["ignore", "inherit", "inherit"],
					// Don't detach yet - let it run in foreground for dev
				})
				// In production: detach, write PID file, etc.
				// For now, foreground is fine.
			} else if (parsed.command === "stop") {
				// TODO: send SIGTERM to daemon PID
				console.log("TODO: implement daemon stop")
			}
			return
		}

		case "command": {
			try {
				const res = await sendCommand(parsed.command || "pulse")
				console.log(JSON.stringify(res, null, 2))
			} catch (err) {
				console.error(err instanceof Error ? err.message : err)
				process.exit(1)
			}
			return
		}

		case "oneshot": {
			try {
				const res = await send(parsed.message || "", parsed.hero)
				console.log(res.content)
				const pulseStr = renderPulse(res.pulse as Parameters<typeof renderPulse>[0])
				if (pulseStr) console.log(`\n${pulseStr}`)
			} catch (err) {
				console.error(err instanceof Error ? err.message : err)
				process.exit(1)
			}
			return
		}

		case "interactive": {
			console.log(`${CYAN}keanu${RESET} ${DIM}v0.0.1${RESET}`)
			console.log(`${DIM}type a message, or: /do /dream /craft /prove /speak /pulse /quit${RESET}`)
			console.log("")

			const rl = createInterface({
				input: process.stdin,
				output: process.stdout,
				prompt: `${DIM}>${RESET} `,
			})

			let currentHero = "chat"

			rl.prompt()

			rl.on("line", async (line) => {
				const trimmed = line.trim()
				if (!trimmed) {
					rl.prompt()
					return
				}

				// Slash commands
				if (trimmed.startsWith("/")) {
					const cmd = trimmed.slice(1).split(" ")[0]
					if (cmd === "quit" || cmd === "exit" || cmd === "q") {
						rl.close()
						process.exit(0)
					}
					if (HERO_MODES.includes(cmd)) {
						currentHero = cmd
						console.log(`${DIM}switched to ${cmd} mode${RESET}`)
						rl.prompt()
						return
					}
					if (cmd === "chat") {
						currentHero = "chat"
						console.log(`${DIM}switched to chat mode${RESET}`)
						rl.prompt()
						return
					}
					if (cmd === "pulse") {
						try {
							const res = await sendCommand("pulse")
							console.log(JSON.stringify(res, null, 2))
						} catch (err) {
							console.error(err instanceof Error ? err.message : err)
						}
						rl.prompt()
						return
					}
				}

				try {
					const res = await send(trimmed, currentHero)
					console.log("")
					console.log(res.content)
					const pulseStr = renderPulse(res.pulse as Parameters<typeof renderPulse>[0])
					if (pulseStr) console.log(`\n${pulseStr}`)
					console.log("")
				} catch (err) {
					console.error(err instanceof Error ? err.message : err)
				}

				rl.prompt()
			})

			rl.on("close", () => {
				console.log(`\n${DIM}the dog chose to stay.${RESET}`)
				process.exit(0)
			})
		}
	}
}

main().catch((err) => {
	console.error(err)
	process.exit(1)
})
