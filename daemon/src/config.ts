// daemon/src/config.ts
// Configuration. Sensible defaults. Override with env vars or config file.

import { existsSync, readFileSync } from "node:fs"
import { join } from "node:path"
import type { DaemonConfig } from "./types"

const HOME = process.env.HOME || "~"
const KEANU_HOME = process.env.KEANU_HOME || join(HOME, ".keanu")

export function loadConfig(): DaemonConfig {
	const configPath = join(KEANU_HOME, "config.json")
	let fileConfig: Partial<DaemonConfig> = {}

	if (existsSync(configPath)) {
		try {
			fileConfig = JSON.parse(readFileSync(configPath, "utf-8"))
		} catch {
			// bad config file, use defaults
		}
	}

	return {
		socket_path: process.env.KEANU_SOCKET || fileConfig.socket_path || "/tmp/keanu.sock",
		model:
			process.env.KEANU_MODEL || fileConfig.model || "claude-sonnet-4-20250514",
		max_tokens: Number(process.env.KEANU_MAX_TOKENS) || fileConfig.max_tokens || 8192,
		memory_dir: fileConfig.memory_dir || join(KEANU_HOME, "memory"),
		soul_path: fileConfig.soul_path || findSoulPath(),
		status_path: fileConfig.status_path || findStatusPath(),
		langfuse_enabled: process.env.LANGFUSE_SECRET_KEY !== undefined,
		detector_sidecar_url:
			process.env.KEANU_DETECTOR_URL ||
			fileConfig.detector_sidecar_url ||
			"http://localhost:8787",
	}
}

function findSoulPath(): string {
	// Look for soul.md in: cwd, then ~/.keanu/
	const candidates = [join(process.cwd(), "soul.md"), join(KEANU_HOME, "soul.md")]
	return candidates.find((p) => existsSync(p)) || candidates[0]
}

function findStatusPath(): string {
	const candidates = [join(process.cwd(), "status.md"), join(KEANU_HOME, "status.md")]
	return candidates.find((p) => existsSync(p)) || candidates[0]
}
