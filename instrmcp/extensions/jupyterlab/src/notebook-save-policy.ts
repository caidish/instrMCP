type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };

type ContentsModel = {
  content?: unknown;
  hash?: string | null;
  hash_algorithm?: string | null;
};

export interface NonInteractiveNotebookContext {
  path: string;
  contentsModel?: { hash?: string | null } | null;
  model: {
    dirty: boolean;
    toJSON: () => unknown;
  };
  // Context.save() is deliberately part of this interface so tests can prove
  // the non-interactive path never reaches JupyterLab's conflict modal.
  save: () => Promise<void>;
  _updateContentsModel: (model: ContentsModel) => void;
}

export interface NotebookContentsService {
  get: (
    path: string,
    options: Record<string, unknown>
  ) => Promise<ContentsModel>;
  save: (
    path: string,
    model: Record<string, unknown>
  ) => Promise<ContentsModel>;
}

function normalizedJson(value: unknown): JsonValue {
  if (Array.isArray(value)) {
    return value.map(normalizedJson);
  }
  if (value && typeof value === 'object') {
    const input = value as Record<string, unknown>;
    const output: Record<string, JsonValue> = {};
    for (const key of Object.keys(input).sort()) {
      output[key] = normalizedJson(input[key]);
    }
    return output;
  }
  if (
    value === null ||
    typeof value === 'boolean' ||
    typeof value === 'number' ||
    typeof value === 'string'
  ) {
    return value as null | boolean | number | string;
  }
  return null;
}

function normalizedCell(value: unknown): JsonValue {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return normalizedJson(value);
  }

  const input = value as Record<string, unknown>;
  const output: Record<string, JsonValue> = {};
  const isCodeCell = input.cell_type === 'code';
  for (const key of Object.keys(input).sort()) {
    if (isCodeCell && (key === 'execution_count' || key === 'outputs')) {
      continue;
    }
    output[key] = normalizedJson(input[key]);
  }
  return output;
}

function normalizedNotebook(value: unknown): JsonValue {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return normalizedJson(value);
  }

  const input = value as Record<string, unknown>;
  const output: Record<string, JsonValue> = {};
  for (const key of Object.keys(input).sort()) {
    if (key === 'cells' && Array.isArray(input.cells)) {
      output.cells = input.cells.map(normalizedCell);
    } else {
      output[key] = normalizedJson(input[key]);
    }
  }
  return output;
}

export function differsOnlyByExecutionState(disk: unknown, live: unknown): boolean {
  return JSON.stringify(normalizedNotebook(disk)) === JSON.stringify(normalizedNotebook(live));
}

export async function saveNotebookNonInteractively(
  context: NonInteractiveNotebookContext,
  contents: NotebookContentsService,
  contentProviderId?: string
): Promise<void> {
  if (typeof context._updateContentsModel !== 'function') {
    throw new Error(
      'JupyterLab context cannot be updated after a non-interactive save'
    );
  }

  const path = context.path;
  const liveContent = context.model.toJSON();
  const clientHash = context.contentsModel?.hash;
  const providerOptions = contentProviderId ? { contentProviderId } : {};
  const disk = await contents.get(path, {
    content: true,
    hash: true,
    ...providerOptions
  });

  if (!clientHash || !disk.hash) {
    throw new Error(
      'Notebook contents manager did not provide hashes; refusing an unattended save'
    );
  }

  if (
    clientHash !== disk.hash &&
    !differsOnlyByExecutionState(disk.content, liveContent)
  ) {
    throw new Error(
      'Notebook source or metadata changed on disk; refusing to overwrite it with the active frontend'
    );
  }

  const currentDisk = await contents.get(path, {
    content: false,
    hash: true,
    ...providerOptions
  });
  if (!currentDisk.hash || currentDisk.hash !== disk.hash) {
    throw new Error(
      'Notebook changed on disk while preparing to save; retry the operation'
    );
  }

  // Never call context.save() here. It can open a modal conflict dialog whose
  // Revert button resolves the promise after discarding the bridge mutation.
  let savedModel = await contents.save(path, {
    type: 'notebook',
    format: 'json',
    content: liveContent,
    ...providerOptions
  });

  try {
    const refreshed = await contents.get(path, {
      content: false,
      hash: true,
      ...providerOptions
    });
    savedModel = {
      ...savedModel,
      hash: refreshed.hash,
      hash_algorithm: refreshed.hash_algorithm
    };
  } catch (error) {
    // The direct save is already durable. Retain its returned metadata; if it
    // has no hash, the next unattended save will fail closed.
    console.warn('Could not refresh notebook hash after save', error);
  }

  try {
    context._updateContentsModel(savedModel);
    context.model.dirty = false;
  } catch (error) {
    // Persistence already succeeded, so bookkeeping failure must not make the
    // caller retry and create duplicate cells. Keep the document dirty and let
    // the next save re-check disk state.
    context.model.dirty = true;
    console.warn('Could not update JupyterLab save bookkeeping', error);
  }
}
