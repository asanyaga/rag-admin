/**
 * Deterministic JSON string for equality comparison: object keys are sorted at every
 * nesting level; array order is preserved (order is significant). Not a stable *hash* —
 * used only to detect equal values (e.g. duplicate variant configs).
 */
export function stableStringify(value: unknown): string {
  if (value === null || typeof value !== 'object') {
    return JSON.stringify(value) ?? 'null'
  }
  if (Array.isArray(value)) {
    return `[${value.map(stableStringify).join(',')}]`
  }
  const obj = value as Record<string, unknown>
  const body = Object.keys(obj)
    .sort()
    .map((k) => `${JSON.stringify(k)}:${stableStringify(obj[k])}`)
    .join(',')
  return `{${body}}`
}
