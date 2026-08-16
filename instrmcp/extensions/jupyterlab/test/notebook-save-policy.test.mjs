import test from 'node:test';
import assert from 'node:assert/strict';
import { differsOnlyByExecutionState } from '../lib/notebook-save-policy.js';

const disk = {
  cells: [{ cell_type: 'code', execution_count: null, metadata: {}, outputs: [], source: ['print(1)'] }],
  metadata: { kernelspec: { name: 'qdevbot-control' } },
  nbformat: 4,
  nbformat_minor: 5
};

test('allows execution count and output persistence', () => {
  const live = structuredClone(disk);
  live.cells[0].execution_count = 1;
  live.cells[0].outputs = [{ output_type: 'stream', name: 'stdout', text: ['1\n'] }];
  assert.equal(differsOnlyByExecutionState(disk, live), true);
});

test('rejects source changes', () => {
  const live = structuredClone(disk);
  live.cells[0].source = ['print(2)'];
  assert.equal(differsOnlyByExecutionState(disk, live), false);
});

test('rejects notebook and cell metadata changes', () => {
  const changedNotebook = structuredClone(disk);
  changedNotebook.metadata.kernelspec.name = 'foreign-kernel';
  assert.equal(differsOnlyByExecutionState(disk, changedNotebook), false);

  const changedCell = structuredClone(disk);
  changedCell.cells[0].metadata = { externallyEdited: true };
  assert.equal(differsOnlyByExecutionState(disk, changedCell), false);
});
