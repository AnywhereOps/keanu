// daemon/src/hero/session.ts
// Session awareness. Tracks what the agent has done to prevent loops.
//
// Ported from keanu-0.0.1/src/keanu/hero/do.py — AgentLoop session tracking
//
// 1st repeat: reminds the agent "you already ran this"
// 2nd repeat: warns "content hasn't changed"
// 3rd repeat: returns cached result instead of executing

export interface ActionRecord {
	action: string
	target: string
	turn: number
	result?: string
}

export class SessionTracker {
	private actions: ActionRecord[] = []
	readonly filesRead = new Set<string>()
	readonly filesWritten = new Set<string>()

	/**
	 * Record an action. Returns awareness info if this is a repeat.
	 */
	noteAction(
		action: string,
		target: string,
		turn: number,
		result?: string,
	): { repeat: number; cached?: string } {
		const count = this.consecutiveCount(action, target)

		this.actions.push({ action, target, turn, result })

		// Track file access
		if (action === "read_file") this.filesRead.add(target)
		if (action === "write_file" || action === "edit_file")
			this.filesWritten.add(target)

		if (count === 0) return { repeat: 0 }

		if (count >= 2) {
			// 3rd+ repeat: return cached result
			const lastResult = this.lastResultFor(action, target)
			return { repeat: count + 1, cached: lastResult || undefined }
		}

		// 1st or 2nd repeat
		return { repeat: count + 1 }
	}

	/**
	 * Count consecutive times this exact action+target was called.
	 */
	consecutiveCount(action: string, target: string): number {
		let count = 0
		for (let i = this.actions.length - 1; i >= 0; i--) {
			const a = this.actions[i]
			if (a.action === action && a.target === target) {
				count++
			} else {
				break
			}
		}
		return count
	}

	/**
	 * Get the last result for a given action+target.
	 */
	lastResultFor(action: string, target: string): string | null {
		for (let i = this.actions.length - 1; i >= 0; i--) {
			const a = this.actions[i]
			if (a.action === action && a.target === target && a.result) {
				return a.result
			}
		}
		return null
	}

	/**
	 * Generate awareness context for the system prompt.
	 */
	awareness(): string | null {
		if (this.actions.length === 0) return null

		const parts: string[] = []
		if (this.filesRead.size > 0) {
			parts.push(`files read: ${[...this.filesRead].join(", ")}`)
		}
		if (this.filesWritten.size > 0) {
			parts.push(`files written: ${[...this.filesWritten].join(", ")}`)
		}
		parts.push(`actions taken: ${this.actions.length}`)

		return `[session: ${parts.join(" | ")}]`
	}
}
