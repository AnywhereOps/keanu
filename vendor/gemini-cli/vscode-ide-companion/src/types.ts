/**
 * Inlined types from gemini-cli-core/src/ide/types.
 * Keanu IDE companion types.
 */

import { z } from 'zod';

export const OpenDiffRequestSchema = z.object({
  filePath: z.string(),
  newContent: z.string(),
});

export const CloseDiffRequestSchema = z.object({
  filePath: z.string(),
});

export const IdeDiffAcceptedNotificationSchema = z.object({
  jsonrpc: z.literal('2.0'),
  method: z.literal('ide/diffAccepted'),
  params: z.object({
    filePath: z.string(),
    content: z.string(),
  }),
});

export const IdeDiffRejectedNotificationSchema = z.object({
  jsonrpc: z.literal('2.0'),
  method: z.literal('ide/diffRejected'),
  params: z.object({
    filePath: z.string(),
    content: z.string(),
  }),
});

export const IdeContextNotificationSchema = z.object({
  jsonrpc: z.literal('2.0'),
  method: z.literal('ide/contextUpdate'),
  params: z.object({
    workspaceState: z.object({
      openFiles: z.array(z.object({
        path: z.string(),
        timestamp: z.number(),
        isActive: z.boolean().optional(),
        cursor: z.object({
          line: z.number(),
          character: z.number(),
        }).optional(),
        selectedText: z.string().optional(),
      })),
      isTrusted: z.boolean(),
    }),
  }),
});

export interface File {
  path: string;
  timestamp: number;
  isActive?: boolean;
  cursor?: { line: number; character: number };
  selectedText?: string;
}

export interface IdeContext {
  workspaceState: {
    openFiles: File[];
    isTrusted: boolean;
  };
}
