# Keanu IDE Companion

The Keanu IDE Companion extension pairs with the keanu CLI. This extension is
compatible with both VS Code and VS Code forks.

## Features

- **Open Editor File Context**: keanu gains awareness of the files you have
  open in your editor, providing it with a richer understanding of your
  project's structure and content.

- **Selection Context**: keanu can access your cursor's position and
  selected text within the editor, giving it valuable context directly from your
  current work.

- **Native Diffing**: Seamlessly view, modify, and accept code changes suggested by
  keanu directly within the editor.

- **Launch keanu**: Quickly start a new keanu session from the Command
  Palette (Cmd+Shift+P or Ctrl+Shift+P) by running the "Keanu: Run" command.

## Requirements

- VS Code version 1.99.0 or newer
- keanu CLI (installed separately) running within the integrated terminal

## How it Works

The extension starts a local MCP server on localhost that exposes two tools:

- `openDiff`: Opens a diff view to create or modify a file
- `closeDiff`: Closes an open diff view and returns the final content

It also sends IDE context (open files, cursor position, selected text) to
connected keanu sessions via JSON-RPC 2.0 notifications.

The keanu CLI auto-discovers the extension via the `KEANU_IDE_SERVER_PORT`
environment variable or by scanning `$TMPDIR/keanu/ide/` for port files.
