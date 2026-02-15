/**
 * Keanu IDE Companion - VSCode extension.
 * Pairs with keanu CLI for IDE-aware agentic work.
 */

import * as vscode from 'vscode';
import { IDEServer } from './ide-server.js';
import { DiffContentProvider, DiffManager } from './diff-manager.js';
import { createLogger } from './utils/logger.js';

const INFO_MESSAGE_SHOWN_KEY = 'keanuInfoMessageShown';
export const DIFF_SCHEME = 'keanu-diff';

let ideServer: IDEServer;
let logger: vscode.OutputChannel;
let log: (message: string) => void = () => {};

export async function activate(context: vscode.ExtensionContext) {
  logger = vscode.window.createOutputChannel('Keanu IDE Companion');
  log = createLogger(context, logger);
  log('Extension activated');

  const diffContentProvider = new DiffContentProvider();
  const diffManager = new DiffManager(log, diffContentProvider);

  context.subscriptions.push(
    vscode.workspace.onDidCloseTextDocument((doc) => {
      if (doc.uri.scheme === DIFF_SCHEME) {
        // eslint-disable-next-line @typescript-eslint/no-floating-promises
        diffManager.cancelDiff(doc.uri);
      }
    }),
    vscode.workspace.registerTextDocumentContentProvider(
      DIFF_SCHEME,
      diffContentProvider,
    ),
    vscode.commands.registerCommand(
      'keanu.diff.accept',
      (uri?: vscode.Uri) => {
        const docUri = uri ?? vscode.window.activeTextEditor?.document.uri;
        if (docUri && docUri.scheme === DIFF_SCHEME) {
          // eslint-disable-next-line @typescript-eslint/no-floating-promises
          diffManager.acceptDiff(docUri);
        }
      },
    ),
    vscode.commands.registerCommand(
      'keanu.diff.cancel',
      (uri?: vscode.Uri) => {
        const docUri = uri ?? vscode.window.activeTextEditor?.document.uri;
        if (docUri && docUri.scheme === DIFF_SCHEME) {
          // eslint-disable-next-line @typescript-eslint/no-floating-promises
          diffManager.cancelDiff(docUri);
        }
      },
    ),
  );

  ideServer = new IDEServer(log, diffManager);
  try {
    await ideServer.start(context);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    log(`Failed to start IDE server: ${message}`);
  }

  if (!context.globalState.get(INFO_MESSAGE_SHOWN_KEY)) {
    void vscode.window.showInformationMessage(
      'Keanu IDE Companion extension successfully installed.',
    );
    context.globalState.update(INFO_MESSAGE_SHOWN_KEY, true);
  }

  context.subscriptions.push(
    vscode.workspace.onDidChangeWorkspaceFolders(() => {
      // eslint-disable-next-line @typescript-eslint/no-floating-promises
      ideServer.syncEnvVars();
    }),
    vscode.workspace.onDidGrantWorkspaceTrust(() => {
      // eslint-disable-next-line @typescript-eslint/no-floating-promises
      ideServer.syncEnvVars();
    }),
    vscode.commands.registerCommand('keanu.run', async () => {
      const workspaceFolders = vscode.workspace.workspaceFolders;
      if (!workspaceFolders || workspaceFolders.length === 0) {
        vscode.window.showInformationMessage(
          'No folder open. Please open a folder to run keanu.',
        );
        return;
      }

      let selectedFolder: vscode.WorkspaceFolder | undefined;
      if (workspaceFolders.length === 1) {
        selectedFolder = workspaceFolders[0];
      } else {
        selectedFolder = await vscode.window.showWorkspaceFolderPick({
          placeHolder: 'Select a folder to run keanu in',
        });
      }

      if (selectedFolder) {
        const terminal = vscode.window.createTerminal({
          name: `keanu (${selectedFolder.name})`,
          cwd: selectedFolder.uri.fsPath,
        });
        terminal.show();
        terminal.sendText('keanu');
      }
    }),
    vscode.commands.registerCommand('keanu.showNotices', async () => {
      const noticePath = vscode.Uri.joinPath(
        context.extensionUri,
        'NOTICES.txt',
      );
      await vscode.window.showTextDocument(noticePath);
    }),
  );
}

export async function deactivate(): Promise<void> {
  log('Extension deactivated');
  try {
    if (ideServer) {
      await ideServer.stop();
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    log(`Failed to stop IDE server during deactivation: ${message}`);
  } finally {
    if (logger) {
      logger.dispose();
    }
  }
}
