// daemon/src/memory/git.ts
// Git layer for memberberries.
//
// Each agent writes its own hero-scoped files (no conflicts).
// Lockfile guards concurrent git operations.
// Pull-rebase before push (different files = auto-resolve).

import { existsSync, writeFileSync, unlinkSync, openSync, closeSync } from "node:fs"
import { join } from "node:path"
import { execSync } from "node:child_process"

const LOCK_TIMEOUT_MS = 5000
const LOCK_RETRY_MS = 200

function exec(cmd: string, cwd: string): string {
	try {
		return execSync(cmd, { cwd, stdio: "pipe", timeout: 10000 }).toString().trim()
	} catch (err) {
		const msg = err instanceof Error ? err.message : String(err)
		throw new Error(`git: ${cmd} failed: ${msg}`)
	}
}

/**
 * File-based lock for serializing git operations across agents.
 */
async function withLock<T>(repoDir: string, fn: () => Promise<T>): Promise<T> {
	const lockPath = join(repoDir, ".git-lock")
	const start = Date.now()

	while (true) {
		try {
			// O_CREAT | O_EXCL — atomic create-or-fail
			const fd = openSync(lockPath, "wx")
			closeSync(fd)
			break
		} catch {
			if (Date.now() - start > LOCK_TIMEOUT_MS) {
				// Stale lock? Force remove and retry once.
				try { unlinkSync(lockPath) } catch { /* ignore */ }
				const fd = openSync(lockPath, "wx")
				closeSync(fd)
				break
			}
			await new Promise((r) => setTimeout(r, LOCK_RETRY_MS))
		}
	}

	try {
		return await fn()
	} finally {
		try { unlinkSync(lockPath) } catch { /* ignore */ }
	}
}

/**
 * Ensure the memberberry dir is a git repo.
 * Creates and initializes if needed.
 */
export function ensureRepo(repoDir: string): void {
	if (!existsSync(repoDir)) {
		execSync(`mkdir -p "${repoDir}"`)
	}
	if (!existsSync(join(repoDir, ".git"))) {
		exec("git init", repoDir)
		// Write .gitignore
		const gitignore = `vectors/\n*.db\n*.sqlite\n.git-lock\n`
		writeFileSync(join(repoDir, ".gitignore"), gitignore)
		exec("git add .gitignore", repoDir)
		exec('git commit -m "init memberberries"', repoDir)
	}
}

/**
 * Check if the repo has a remote configured.
 */
export function hasRemote(repoDir: string): boolean {
	try {
		const remotes = exec("git remote", repoDir)
		return remotes.length > 0
	} catch {
		return false
	}
}

/**
 * Commit all changes with a message.
 * Lockfile-guarded for multi-agent safety.
 */
export async function commit(repoDir: string, msg: string): Promise<void> {
	await withLock(repoDir, async () => {
		// Check if there's anything to commit
		const status = exec("git status --porcelain", repoDir)
		if (!status) return // nothing to commit

		exec("git add -A", repoDir)
		exec(`git commit -m "${msg.replace(/"/g, '\\"')}"`, repoDir)
	})
}

/**
 * Sync with remote: pull --rebase then push.
 * Lockfile-guarded. Safe because agents write different files.
 */
export async function sync(repoDir: string): Promise<void> {
	if (!hasRemote(repoDir)) return

	await withLock(repoDir, async () => {
		try {
			exec("git pull --rebase", repoDir)
		} catch {
			// Only abort if a rebase is actually in progress
			if (
				existsSync(join(repoDir, ".git", "rebase-merge")) ||
				existsSync(join(repoDir, ".git", "rebase-apply"))
			) {
				exec("git rebase --abort", repoDir)
			}
			// Otherwise it was a network/auth error — nothing to abort
		}

		const status = exec("git status --porcelain", repoDir)
		if (status) {
			exec("git add -A", repoDir)
			exec('git commit -m "auto-sync"', repoDir)
		}

		try {
			exec("git push", repoDir)
		} catch {
			// Push failed — remote might not be set up yet. That's fine.
		}
	})
}

/**
 * Commit and sync in one call. The typical end-of-session operation.
 */
export async function commitAndSync(repoDir: string, msg: string): Promise<void> {
	await commit(repoDir, msg)
	await sync(repoDir)
}
