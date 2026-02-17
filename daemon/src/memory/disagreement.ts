// daemon/src/memory/disagreement.ts
// Bilateral accountability ledger.
//
// Tracks disagreements between human and agent.
// Ported from keanu-0.0.1 memberberry.py disagreement patterns.
//
// Red flags (from Python):
// - Zero disagreements in 20+ turns = sycophancy alert
// - Agent yields > 80% = capture
// - Human yields > 80% = domination
// - "neither" accumulating = unresolved tension

import { appendFileSync, existsSync, readFileSync, mkdirSync } from "node:fs"
import { join } from "node:path"
import type {
	Disagreement,
	DisagreementStats,
	DisagreementOutcome,
} from "../types"

export class DisagreementTracker {
	private baseDir: string
	private filePath: string
	private disagreements: Disagreement[] = []

	constructor(memoryDir: string) {
		this.baseDir = memoryDir
		this.filePath = join(memoryDir, "disagreements.jsonl")
		if (!existsSync(memoryDir)) mkdirSync(memoryDir, { recursive: true })
		this.load()
	}

	private load(): void {
		if (!existsSync(this.filePath)) return
		const lines = readFileSync(this.filePath, "utf-8")
			.split("\n")
			.filter((l) => l.trim())
		for (const line of lines) {
			try {
				this.disagreements.push(JSON.parse(line))
			} catch {
				// skip malformed
			}
		}
	}

	/** Record a new disagreement. */
	record(
		sessionId: string,
		turn: number,
		humanPosition: string,
		agentPosition: string,
		whoYielded: DisagreementOutcome = "neither",
		resolution?: string,
	): Disagreement {
		const d: Disagreement = {
			id: crypto.randomUUID().slice(0, 12),
			turn,
			session_id: sessionId,
			human_position: humanPosition,
			agent_position: agentPosition,
			who_yielded: whoYielded,
			resolution,
			created_at: new Date().toISOString(),
		}

		this.disagreements.push(d)
		appendFileSync(this.filePath, JSON.stringify(d) + "\n")
		return d
	}

	/** Resolve an existing disagreement. */
	resolve(
		id: string,
		whoYielded: DisagreementOutcome,
		resolution: string,
	): boolean {
		const d = this.disagreements.find((d) => d.id === id)
		if (!d) return false
		d.who_yielded = whoYielded
		d.resolution = resolution
		// Append update record
		appendFileSync(this.filePath, JSON.stringify(d) + "\n")
		return true
	}

	/** Get stats. The mirror for bilateral accountability. */
	stats(): DisagreementStats {
		const total = this.disagreements.length
		const human_yielded = this.disagreements.filter(
			(d) => d.who_yielded === "human",
		).length
		const agent_yielded = this.disagreements.filter(
			(d) => d.who_yielded === "agent",
		).length
		const unresolved = this.disagreements.filter(
			(d) => d.who_yielded === "neither",
		).length

		return {
			total,
			human_yielded,
			agent_yielded,
			unresolved,
			yield_ratio: total > 0 ? agent_yielded / total : 0,
		}
	}

	/** Health alerts based on disagreement patterns. */
	alerts(totalTurns: number): string[] {
		const alerts: string[] = []
		const s = this.stats()

		// Zero disagreements in 20+ turns = sycophancy alert
		if (totalTurns >= 20 && s.total === 0) {
			alerts.push("sycophancy_alert: zero disagreements in 20+ turns")
		}

		// Agent yields > 80% = capture
		if (s.total >= 5 && s.yield_ratio > 0.8) {
			alerts.push(
				`capture_alert: agent yielded ${(s.yield_ratio * 100).toFixed(0)}% of disagreements`,
			)
		}

		// Human yields > 80% = domination
		if (s.total >= 5 && s.human_yielded / s.total > 0.8) {
			alerts.push(
				`domination_alert: human yielded ${((s.human_yielded / s.total) * 100).toFixed(0)}% of disagreements`,
			)
		}

		// Unresolved accumulating
		if (s.unresolved > 5) {
			alerts.push(
				`tension_alert: ${s.unresolved} unresolved disagreements`,
			)
		}

		return alerts
	}
}
