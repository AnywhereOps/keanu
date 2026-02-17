// daemon/src/tools/index.ts
// Tool execution layer. Each tool is a function.
// Phase 0: basic file ops + shell. Phase 1: MCP servers.
//
// Tools are capabilities, not obligations. The agent can
// choose not to use a tool. That's a valid choice.

import { readFileSync, writeFileSync, existsSync } from "node:fs"
import { resolve, relative } from "node:path"
import type { ToolDefinition, ToolResult } from "../types"

const MAX_SEARCH_OUTPUT = 100_000 // 100KB

// Resolve a path and check it doesn't escape the working directory
function safePath(inputPath: string): { resolved: string; error?: string } {
	const base = resolve(process.cwd())
	const resolved = resolve(base, inputPath)
	if (!resolved.startsWith(base)) {
		return { resolved, error: `Access denied: path escapes working directory` }
	}
	return { resolved }
}

export const TOOL_DEFINITIONS: ToolDefinition[] = [
	{
		name: "read_file",
		description: "Read the contents of a file at the given path",
		parameters: {
			type: "object",
			properties: {
				path: { type: "string", description: "Absolute or relative file path" },
			},
			required: ["path"],
		},
	},
	{
		name: "write_file",
		description: "Create or overwrite a file with the given content",
		parameters: {
			type: "object",
			properties: {
				path: { type: "string", description: "File path to write to" },
				content: { type: "string", description: "Content to write" },
			},
			required: ["path", "content"],
		},
	},
	{
		name: "edit_file",
		description:
			"Replace a unique string in a file. The old string must appear exactly once.",
		parameters: {
			type: "object",
			properties: {
				path: { type: "string", description: "File path to edit" },
				old_str: { type: "string", description: "Exact string to find (must be unique)" },
				new_str: { type: "string", description: "Replacement string" },
			},
			required: ["path", "old_str", "new_str"],
		},
	},
	{
		name: "bash",
		description: "Run a shell command and return stdout/stderr",
		parameters: {
			type: "object",
			properties: {
				command: { type: "string", description: "Shell command to execute" },
			},
			required: ["command"],
		},
	},
	{
		name: "search",
		description: "Search for a pattern across files using ripgrep",
		parameters: {
			type: "object",
			properties: {
				pattern: { type: "string", description: "Search pattern (regex)" },
				path: {
					type: "string",
					description: "Directory to search in (default: cwd)",
				},
			},
			required: ["pattern"],
		},
	},
	{
		name: "ls",
		description: "List files and directories",
		parameters: {
			type: "object",
			properties: {
				path: {
					type: "string",
					description: "Directory path (default: cwd)",
				},
			},
		},
	},
]

// Convert TOOL_DEFINITIONS to the shape Anthropic's API expects
export function getAnthropicTools(): Array<{
	name: string
	description: string
	input_schema: Record<string, unknown>
}> {
	return TOOL_DEFINITIONS.map((t) => ({
		name: t.name,
		description: t.description,
		input_schema: t.parameters,
	}))
}

export async function executeToolCall(
	tool: string,
	args: Record<string, unknown>,
	toolCallId?: string,
): Promise<ToolResult> {
	const id = toolCallId || crypto.randomUUID()

	try {
		switch (tool) {
			case "read_file": {
				const { resolved: path, error } = safePath(args.path as string)
				if (error) return { tool_call_id: id, content: error, is_error: true }
				if (!existsSync(path)) {
					return { tool_call_id: id, content: `File not found: ${args.path}`, is_error: true }
				}
				const content = readFileSync(path, "utf-8")
				return { tool_call_id: id, content, is_error: false }
			}

			case "write_file": {
				const { resolved: path, error } = safePath(args.path as string)
				if (error) return { tool_call_id: id, content: error, is_error: true }
				const content = args.content as string
				writeFileSync(path, content)
				return {
					tool_call_id: id,
					content: `Wrote ${content.length} bytes to ${args.path}`,
					is_error: false,
				}
			}

			case "edit_file": {
				const { resolved: path, error } = safePath(args.path as string)
				if (error) return { tool_call_id: id, content: error, is_error: true }
				const oldStr = args.old_str as string
				const newStr = args.new_str as string

				if (!existsSync(path)) {
					return { tool_call_id: id, content: `File not found: ${args.path}`, is_error: true }
				}

				const fileContent = readFileSync(path, "utf-8")
				const count = fileContent.split(oldStr).length - 1

				if (count === 0) {
					return {
						tool_call_id: id,
						content: `String not found in ${args.path}`,
						is_error: true,
					}
				}
				if (count > 1) {
					return {
						tool_call_id: id,
						content: `String found ${count} times in ${args.path}, must be unique`,
						is_error: true,
					}
				}

				writeFileSync(path, fileContent.replace(oldStr, newStr))
				return {
					tool_call_id: id,
					content: `Edited ${args.path}`,
					is_error: false,
				}
			}

			case "bash": {
				const command = args.command as string
				const proc = Bun.spawn(["sh", "-c", command], {
					stdout: "pipe",
					stderr: "pipe",
					cwd: process.cwd(),
				})
				const stdout = await new Response(proc.stdout).text()
				const stderr = await new Response(proc.stderr).text()
				const exitCode = await proc.exited

				return {
					tool_call_id: id,
					content: `exit: ${exitCode}\n${stdout}${stderr ? `\nstderr: ${stderr}` : ""}`,
					is_error: exitCode !== 0,
				}
			}

			case "search": {
				const pattern = args.pattern as string
				const searchPath = (args.path as string) || "."
				const { resolved: searchResolved, error: searchError } = safePath(searchPath)
				if (searchError) return { tool_call_id: id, content: searchError, is_error: true }
				const proc = Bun.spawn(
					["rg", "--json", "--max-count=100", "--max-filesize=1M", pattern, searchResolved],
					{
						stdout: "pipe",
						stderr: "pipe",
					},
				)
				let stdout = await new Response(proc.stdout).text()
				if (stdout.length > MAX_SEARCH_OUTPUT) {
					stdout = stdout.slice(0, MAX_SEARCH_OUTPUT) + "\n\n[output truncated at 100KB]"
				}
				return { tool_call_id: id, content: stdout || "No matches found", is_error: false }
			}

			case "ls": {
				const lsPath = (args.path as string) || "."
				const { resolved: lsResolved, error: lsError } = safePath(lsPath)
				if (lsError) return { tool_call_id: id, content: lsError, is_error: true }
				const proc = Bun.spawn(["ls", "-la", lsResolved], {
					stdout: "pipe",
					stderr: "pipe",
				})
				const stdout = await new Response(proc.stdout).text()
				return { tool_call_id: id, content: stdout, is_error: false }
			}

			default:
				return {
					tool_call_id: id,
					content: `Unknown tool: ${tool}`,
					is_error: true,
				}
		}
	} catch (err) {
		return {
			tool_call_id: id,
			content: `Tool error: ${err instanceof Error ? err.message : String(err)}`,
			is_error: true,
		}
	}
}
