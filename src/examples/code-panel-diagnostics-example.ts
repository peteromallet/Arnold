/**
 * code-panel-diagnostics-example — M2 code panel diagnostics example.
 *
 * Demonstrates structured diagnostic reporting with 1-based source
 * ranges, representing what a code panel extension would emit when
 * analyzing script content.  Exercises the full ExtensionDiagnostic
 * shape including severity, code, message, extensionId, contributionId,
 * milestone, and detail fields.
 *
 * @publicContract
 */

import { defineExtension } from '@reigh/editor-sdk';
import type {
  ReighExtension,
  ExtensionContext,
  DisposeHandle,
  ExtensionDiagnostic,
  DiagnosticSeverity,
  ExportDiagnostic,
} from '@reigh/editor-sdk';

export const codePanelDiagnosticsExample: ReighExtension = defineExtension({
  manifest: {
    id: 'com.reigh.examples.code-panel-m2' as any,
    version: '1.0.0',
    label: 'Code Panel Diagnostics M2 Example',
    description:
      'Demonstrates code panel diagnostics with 1-based source ranges.',
    apiVersion: 1,
    contributions: [
      {
        id: 'm2-code-panel' as any,
        kind: 'slot',
        slot: 'codePanel',
        label: 'M2 Code Panel',
      },
    ],
    messages: {
      'activated': 'M2 Code Panel Diagnostics example activated.',
      'disposed': 'M2 Code Panel Diagnostics example disposed.',
      'syntax-error':
        'Syntax error at line {{line}}, col {{col}}: {{message}}',
    },
  },

  activate(ctx: ExtensionContext): DisposeHandle {
    // Simulate code analysis diagnostics with 1-based source ranges.
    // The `detail` field carries structured position information that
    // the DiagnosticPanel renders as human-readable positions.

    const diagnostics: Omit<ExtensionDiagnostic, 'extensionId'>[] = [
      {
        severity: 'error' as DiagnosticSeverity,
        code: 'code/syntax-error',
        message: "Unexpected token '}' at line 7, column 5",
        contributionId: 'm2-code-panel',
        milestone: 'M2',
        detail: {
          line: 7,
          column: 5,
          endLine: 7,
          endColumn: 9,
          source: '  if (x >  } y) {',
        },
      },
      {
        severity: 'warning' as DiagnosticSeverity,
        code: 'code/unused-variable',
        message: "Variable 'unusedVar' is never used",
        contributionId: 'm2-code-panel',
        milestone: 'M2',
        detail: {
          line: 12,
          column: 7,
          endLine: 12,
          endColumn: 16,
          variableName: 'unusedVar',
        },
      },
      {
        severity: 'info' as DiagnosticSeverity,
        code: 'code/analysis-complete',
        message: 'Code analysis complete. 2 issues found.',
        contributionId: 'm2-code-panel',
        milestone: 'M2',
        detail: {
          totalLines: 45,
          issuesFound: 2,
        },
      },
    ];

    for (const diag of diagnostics) {
      ctx.services.diagnostics.report(diag);
    }

    // Demonstrate export diagnostic shape (export-prefixed code)
    ctx.services.diagnostics.report({
      severity: 'warning' as DiagnosticSeverity,
      code: 'export/unknown-clip-type' as 'export/unknown-clip-type',
      message: 'Clip type "customEffect" is not recognized during export.',
      contributionId: 'm2-code-panel',
      detail: {
        clipId: 'clip-0042',
        clipType: 'customEffect',
      },
    } as Omit<ExtensionDiagnostic, 'extensionId'>);

    // Demonstrate chrome.focus() scoping (no shell root = diagnostic)
    ctx.chrome.focus('#code-panel-editor');

    ctx.chrome.toast(ctx.services.i18n.t('activated'), 'info');

    return {
      dispose(): void {
        ctx.chrome.toast(ctx.services.i18n.t('disposed'), 'info');
      },
    };
  },
});
