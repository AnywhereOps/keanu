// daemon/src/hero/dream.ts
// The planner. Close your eyes, see the path, open them, walk.
//
// Ported from keanu-0.0.1/src/keanu/hero/dream.py
//
// Single oracle call. Goal in, phased steps out. No loop, no tools.
// Fast and composable. Called directly or via the dream stance.

import type { DaemonConfig } from "../types"
import { callOracle, extractJSON } from "../oracle"

export interface DreamStep {
	action: string
	depends_on: string | null
	why: string
}

export interface DreamPhase {
	name: string
	steps: DreamStep[]
}

export interface DreamResult {
	goal: string
	phases: DreamPhase[]
	total_steps: number
	raw: string
	error?: string
}

// Port from dream.py:DREAM_PROMPT
const DREAM_PROMPT = `You are a planner. Your job is to break a goal into clear,
sequenced phases and steps.

Respond with JSON:
{
    "phases": [
        {
            "name": "short phase name",
            "steps": [
                {
                    "action": "what to do (imperative, specific)",
                    "depends_on": "previous step action or null if none",
                    "why": "one sentence, why this step matters"
                }
            ]
        }
    ]
}

Rules:
- Each step should be small enough to do in one sitting.
- Steps within a phase can run in parallel unless depends_on says otherwise.
- Phases run in order. Phase 2 waits for phase 1 to finish.
- Be specific. "write tests" is bad. "write tests for the parse function in codec.py" is good.
- 2-5 phases. 1-5 steps per phase. No filler phases.
- If context is provided, use it. Don't invent requirements that aren't there.`

/**
 * dream up a plan. single oracle call.
 */
export async function dream(
	goal: string,
	config: DaemonConfig,
	context?: string,
): Promise<DreamResult> {
	let prompt = `GOAL: ${goal}`
	if (context) {
		prompt += `\n\nCONTEXT:\n${context}`
	}

	try {
		const response = await callOracle({
			system: DREAM_PROMPT,
			messages: [{ role: "user", content: prompt }],
		}, config)

		const raw = response.text

		// Extract JSON from response (balanced brace matching, not greedy regex)
		const parsed = extractJSON(raw) as { phases?: DreamPhase[] } | null
		if (!parsed) {
			return { goal, phases: [], total_steps: 0, raw, error: "no JSON in response" }
		}

		const phases: DreamPhase[] = parsed.phases || []
		const total_steps = phases.reduce(
			(sum, p) => sum + (p.steps?.length || 0),
			0,
		)

		return { goal, phases, total_steps, raw }
	} catch (err) {
		return {
			goal,
			phases: [],
			total_steps: 0,
			raw: "",
			error: err instanceof Error ? err.message : String(err),
		}
	}
}
