import test from 'node:test';
import assert from 'node:assert/strict';
import {
  differsOnlyByExecutionState,
  saveNotebookNonInteractively
} from '../lib/notebook-save-policy.js';

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

test('preserves nested metadata keys named outputs', () => {
  const diskWithPluginMetadata = structuredClone(disk);
  diskWithPluginMetadata.cells[0].metadata.plugin = { outputs: ['disk'] };
  const live = structuredClone(diskWithPluginMetadata);
  live.cells[0].metadata.plugin.outputs = ['frontend'];
  assert.equal(differsOnlyByExecutionState(diskWithPluginMetadata, live), false);
});

test('preserves nested metadata keys named execution_count', () => {
  const diskWithPluginMetadata = structuredClone(disk);
  diskWithPluginMetadata.cells[0].metadata.plugin = { execution_count: 1 };
  const live = structuredClone(diskWithPluginMetadata);
  live.cells[0].metadata.plugin.execution_count = 2;
  assert.equal(differsOnlyByExecutionState(diskWithPluginMetadata, live), false);
});

test('only ignores execution fields on code cells', () => {
  const markdownDisk = structuredClone(disk);
  markdownDisk.cells[0] = {
    cell_type: 'markdown',
    metadata: {},
    outputs: ['plugin-owned'],
    source: ['hello']
  };
  const live = structuredClone(markdownDisk);
  live.cells[0].outputs = ['changed'];
  assert.equal(differsOnlyByExecutionState(markdownDisk, live), false);
});

test('non-interactive save never reaches the Revert conflict path', async () => {
  const live = structuredClone(disk);
  live.cells.push({
    cell_type: 'code',
    execution_count: null,
    metadata: {},
    outputs: [],
    source: ['new_cell = True']
  });
  let interactiveSaveCalls = 0;
  let persisted = null;
  const context = {
    path: '/test.ipynb',
    contentsModel: { hash: 'base-hash' },
    model: {
      dirty: true,
      toJSON: () => structuredClone(live)
    },
    save: async () => {
      interactiveSaveCalls += 1;
      live.cells.pop(); // Simulate JupyterLab's Revert button.
    },
    _updateContentsModel: model => {
      context.contentsModel = model;
    }
  };
  let getCalls = 0;
  const contents = {
    get: async (_path, options) => {
      getCalls += 1;
      if (getCalls === 1) {
        return {
          hash: 'base-hash',
          content: structuredClone(disk)
        };
      }
      return { hash: getCalls === 2 ? 'base-hash' : 'saved-hash' };
    },
    save: async (_path, model) => {
      persisted = structuredClone(model.content);
      return { hash: 'saved-hash' };
    }
  };

  await saveNotebookNonInteractively(context, contents);

  assert.equal(interactiveSaveCalls, 0);
  assert.equal(persisted.cells.length, 2);
  assert.equal(context.model.dirty, false);
  assert.equal(context.contentsModel.hash, 'saved-hash');
});

test('non-interactive save fails closed before writing without hashes', async () => {
  let saveCalls = 0;
  const context = {
    path: '/test.ipynb',
    contentsModel: { hash: null },
    model: { dirty: true, toJSON: () => structuredClone(disk) },
    save: async () => {},
    _updateContentsModel: () => {}
  };
  const contents = {
    get: async () => ({ hash: null, content: structuredClone(disk) }),
    save: async () => {
      saveCalls += 1;
      return {};
    }
  };

  await assert.rejects(
    saveNotebookNonInteractively(context, contents),
    /did not provide hashes/
  );
  assert.equal(saveCalls, 0);
  assert.equal(context.model.dirty, true);
});
