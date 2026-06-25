function toCsvCell(value: unknown): string {
  if (value === null || value === undefined) return ''
  const str = typeof value === 'object' ? JSON.stringify(value) : String(value)
  if (str.includes(',') || str.includes('"') || str.includes('\n')) {
    return `"${str.replace(/"/g, '""')}"`
  }
  return str
}

function toCsvRow(values: unknown[]): string {
  return values.map(toCsvCell).join(',')
}

function isObjectArray(value: unknown): value is Record<string, unknown>[] {
  return (
    Array.isArray(value) &&
    value.length > 0 &&
    value.every((el) => el !== null && typeof el === 'object' && !Array.isArray(el))
  )
}

export function buildCsvString(structuredData: Record<string, unknown>): string {
  const entries = Object.entries(structuredData)

  const flatFields: [string, unknown][] = []
  const arrayFields: [string, Record<string, unknown>[]][] = []

  for (const [key, value] of entries) {
    if (isObjectArray(value)) {
      arrayFields.push([key, value])
    } else {
      flatFields.push([key, value])
    }
  }

  if (arrayFields.length === 0) {
    if (flatFields.length === 0) {
      return 'data\n' + toCsvCell(JSON.stringify(structuredData))
    }
    const headers = flatFields.map(([k]) => k)
    const values = flatFields.map(([, v]) => v)
    return toCsvRow(headers) + '\n' + toCsvRow(values)
  }

  const [, primaryArray] = arrayFields.reduce((best, curr) =>
    curr[1].length > best[1].length ? curr : best
  )

  const arrayColumns = Array.from(
    new Set(primaryArray.flatMap((row) => Object.keys(row)))
  )
  const flatColumns = flatFields.map(([k]) => k)
  const allColumns = [...arrayColumns, ...flatColumns]

  const rows = primaryArray.map((row) => {
    const arrayValues = arrayColumns.map((col) => row[col] ?? null)
    const flatValues = flatFields.map(([, v]) => v)
    return toCsvRow([...arrayValues, ...flatValues])
  })

  return toCsvRow(allColumns) + '\n' + rows.join('\n')
}

export function exportResultToCsv(
  structuredData: Record<string, unknown>,
  filename: string
): void {
  const csvString = buildCsvString(structuredData)
  const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
