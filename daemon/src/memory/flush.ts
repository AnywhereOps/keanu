// daemon/src/memory/flush.ts
// Memory flush: git commit what's already written.
//
// No LLM extraction here. The agent decides what to remember
// during conversation via remember(). Flush just persists to git.
//
// Called at:
// - Session end (SIGINT/SIGTERM)
// - Session reset command

import type { DaemonConfig } from "../types"
import { commitAndSync, ensureRepo } from "./git"

/**
 * Commit and sync memberberry repo.
 * Just git — no extraction, no memory-of-memory loops.
 */
export async function flushMemories(config: DaemonConfig): Promise<void> {
	const { memberberry_dir, hero_name } = config

	ensureRepo(memberberry_dir)

	try {
		await commitAndSync(memberberry_dir, `${hero_name}: session sync`)
	} catch (err) {
		console.error("git sync failed (memories still saved locally):", err)
	}
}
