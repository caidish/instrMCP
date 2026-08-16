type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };

function normalizedNotebook(value: unknown): JsonValue {
  if (Array.isArray(value)) {
    return value.map(normalizedNotebook);
  }
  if (value && typeof value === 'object') {
    const input = value as Record<string, unknown>;
    const output: Record<string, JsonValue> = {};
    for (const key of Object.keys(input).sort()) {
      if (key === 'execution_count' || key === 'outputs') {
        continue;
      }
      output[key] = normalizedNotebook(input[key]);
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

export function differsOnlyByExecutionState(disk: unknown, live: unknown): boolean {
  return JSON.stringify(normalizedNotebook(disk)) === JSON.stringify(normalizedNotebook(live));
}
