// daemon/src/pulse/deep.ts
// Deep detection via Python sidecar. The full blood work.
//
// Fast path (pulse/index.ts) catches 80%. This catches the rest.
// Calls the FastAPI sidecar running SetFit models.
// Graceful degradation: if sidecar is down, we just skip it.

import type { DaemonConfig } from "../types"

export interface DetectorResult {
	name: string
	score: number
	label: "detected" | "clean"
	confidence: number
}

export async function deepCheck(
	text: string,
	config: DaemonConfig,
	detectors?: string[],
): Promise<DetectorResult[]> {
	try {
		const res = await fetch(`${config.detector_sidecar_url}/detect`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ text, detectors: detectors ?? null }),
			signal: AbortSignal.timeout(5000), // 5s timeout, don't block the loop
		})
		if (!res.ok) return []
		const data = (await res.json()) as { results: DetectorResult[] }
		return data.results ?? []
	} catch {
		// Sidecar not running or timed out. That's fine. Degrade gracefully.
		return []
	}
}

// Should we run deep detection on this turn?
export function shouldDeepCheck(
	aliveState: string,
	turn: number,
): boolean {
	// Always on grey or black
	if (aliveState === "grey" || aliveState === "black") return true
	// Every 5th turn as a health check
	if (turn > 0 && turn % 5 === 0) return true
	return false
}
