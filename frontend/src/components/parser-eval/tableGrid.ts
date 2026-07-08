export interface EditorCell {
  text: string
  isHeader: boolean
}

export interface AnchorCell extends EditorCell {
  row: number
  col: number
  rowspan: number
  colspan: number
}

export interface TableModel {
  rows: number
  cols: number
  cells: AnchorCell[]
}

export type Slot =
  | { kind: 'anchor'; cell: AnchorCell }
  | { kind: 'covered'; cell: AnchorCell }

function newCell(row: number, col: number): AnchorCell {
  return { row, col, rowspan: 1, colspan: 1, text: '', isHeader: false }
}

export function emptyModel(rows: number, cols: number): TableModel {
  const cells: AnchorCell[] = []
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) cells.push(newCell(r, c))
  return { rows, cols, cells }
}

/** Fill any unoccupied (r,c) inside rows×cols with empty 1×1 anchors. */
function fillHoles(model: TableModel): TableModel {
  const occupied = new Set<string>()
  for (const cell of model.cells) {
    for (let dr = 0; dr < cell.rowspan; dr++) {
      for (let dc = 0; dc < cell.colspan; dc++) occupied.add(`${cell.row + dr},${cell.col + dc}`)
    }
  }
  for (let r = 0; r < model.rows; r++) {
    for (let c = 0; c < model.cols; c++) {
      if (!occupied.has(`${r},${c}`)) model.cells.push(newCell(r, c))
    }
  }
  model.cells.sort((a, b) => (a.row - b.row) || (a.col - b.col))
  return model
}

export function htmlToModel(html: string): TableModel {
  const doc = new DOMParser().parseFromString(html, 'text/html')
  const table = doc.querySelector('table')
  if (!table) return emptyModel(1, 1)

  const occupied = new Set<string>()
  const cells: AnchorCell[] = []
  let maxRow = 0
  let maxCol = 0

  Array.from(table.querySelectorAll('tr')).forEach((tr, r) => {
    let c = 0
    for (const el of Array.from(tr.children)) {
      if (el.tagName !== 'TD' && el.tagName !== 'TH') continue
      while (occupied.has(`${r},${c}`)) c++
      const td = el as HTMLTableCellElement
      const rowspan = Math.max(1, td.rowSpan || 1)
      const colspan = Math.max(1, td.colSpan || 1)
      cells.push({ row: r, col: c, rowspan, colspan,
        text: (el.textContent ?? '').trim(), isHeader: el.tagName === 'TH' })
      for (let dr = 0; dr < rowspan; dr++) {
        for (let dc = 0; dc < colspan; dc++) occupied.add(`${r + dr},${c + dc}`)
      }
      maxRow = Math.max(maxRow, r + rowspan)
      maxCol = Math.max(maxCol, c + colspan)
      c += colspan
    }
  })

  if (cells.length === 0) return emptyModel(1, 1)
  return fillHoles({ rows: maxRow, cols: maxCol, cells })
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;')
}

export function modelToHtml(model: TableModel): string {
  const byRow = new Map<number, AnchorCell[]>()
  for (const cell of model.cells) {
    if (!byRow.has(cell.row)) byRow.set(cell.row, [])
    byRow.get(cell.row)!.push(cell)
  }
  const parts = ['<table>']
  for (let r = 0; r < model.rows; r++) {
    parts.push('<tr>')
    const row = (byRow.get(r) ?? []).slice().sort((a, b) => a.col - b.col)
    for (const cell of row) {
      const tag = cell.isHeader ? 'th' : 'td'
      let attrs = ''
      if (cell.colspan > 1) attrs += ` colspan="${cell.colspan}"`
      if (cell.rowspan > 1) attrs += ` rowspan="${cell.rowspan}"`
      parts.push(`<${tag}${attrs}>${escapeHtml(cell.text)}</${tag}>`)
    }
    parts.push('</tr>')
  }
  parts.push('</table>')
  return parts.join('')
}

export function materialize(model: TableModel): Slot[][] {
  const grid: Slot[][] = Array.from({ length: model.rows }, () =>
    new Array<Slot>(model.cols))
  for (const cell of model.cells) {
    for (let dr = 0; dr < cell.rowspan; dr++) {
      for (let dc = 0; dc < cell.colspan; dc++) {
        grid[cell.row + dr][cell.col + dc] =
          dr === 0 && dc === 0 ? { kind: 'anchor', cell } : { kind: 'covered', cell }
      }
    }
  }
  return grid
}

function clone(model: TableModel): TableModel {
  return { rows: model.rows, cols: model.cols, cells: model.cells.map((c) => ({ ...c })) }
}

function anchorAt(model: TableModel, row: number, col: number): AnchorCell {
  const cell = model.cells.find((c) => c.row === row && c.col === col)
  if (!cell) throw new Error(`No anchor cell at (${row}, ${col}); select a top-left cell`)
  return cell
}

export function setText(model: TableModel, row: number, col: number, text: string): TableModel {
  const next = clone(model)
  anchorAt(next, row, col).text = text
  return next
}

export function toggleHeader(model: TableModel, row: number, col: number): TableModel {
  const next = clone(model)
  const cell = anchorAt(next, row, col)
  cell.isHeader = !cell.isHeader
  return next
}

export function addRow(model: TableModel, at: number): TableModel {
  const next = clone(model)
  for (const cell of next.cells) {
    if (at <= cell.row) cell.row++
    else if (at <= cell.row + cell.rowspan - 1) cell.rowspan++
  }
  next.rows++
  for (let c = 0; c < next.cols; c++) next.cells.push(newCell(at, c))
  return fillHoles(next)
}

export function removeRow(model: TableModel, at: number): TableModel {
  if (model.rows <= 1) throw new Error('A table needs at least one row')
  for (const cell of model.cells) {
    if (cell.rowspan > 1 && cell.row <= at && at <= cell.row + cell.rowspan - 1) {
      throw new Error('Split the merged cell crossing this row before removing it')
    }
  }
  const next = clone(model)
  next.cells = next.cells.filter((cell) => cell.row !== at)
  for (const cell of next.cells) if (cell.row > at) cell.row--
  next.rows--
  return next
}

export function addColumn(model: TableModel, at: number): TableModel {
  const next = clone(model)
  for (const cell of next.cells) {
    if (at <= cell.col) cell.col++
    else if (at <= cell.col + cell.colspan - 1) cell.colspan++
  }
  next.cols++
  for (let r = 0; r < next.rows; r++) next.cells.push(newCell(r, at))
  return fillHoles(next)
}

export function removeColumn(model: TableModel, at: number): TableModel {
  if (model.cols <= 1) throw new Error('A table needs at least one column')
  for (const cell of model.cells) {
    if (cell.colspan > 1 && cell.col <= at && at <= cell.col + cell.colspan - 1) {
      throw new Error('Split the merged cell crossing this column before removing it')
    }
  }
  const next = clone(model)
  next.cells = next.cells.filter((cell) => cell.col !== at)
  for (const cell of next.cells) if (cell.col > at) cell.col--
  next.cols--
  return next
}

export function mergeCells(model: TableModel, r1: number, c1: number,
                           r2: number, c2: number): TableModel {
  const top = Math.min(r1, r2)
  const bottom = Math.max(r1, r2)
  const left = Math.min(c1, c2)
  const right = Math.max(c1, c2)
  const grid = materialize(model)
  const members: AnchorCell[] = []
  for (let r = top; r <= bottom; r++) {
    for (let c = left; c <= right; c++) {
      const slot = grid[r][c]
      if (slot.kind !== 'anchor' || slot.cell.rowspan !== 1 || slot.cell.colspan !== 1) {
        throw new Error('Merge only supports a clean rectangle of single cells')
      }
      members.push(slot.cell)
    }
  }
  const next = clone(model)
  const keep = anchorAt(next, top, left)
  keep.rowspan = bottom - top + 1
  keep.colspan = right - left + 1
  keep.text = members.map((m) => m.text).filter((t) => t).join(' ')
  const removed = new Set(members.filter((m) => !(m.row === top && m.col === left))
    .map((m) => `${m.row},${m.col}`))
  next.cells = next.cells.filter((c) => !removed.has(`${c.row},${c.col}`))
  return next
}

export function splitCell(model: TableModel, row: number, col: number): TableModel {
  const next = clone(model)
  const cell = anchorAt(next, row, col)
  const { rowspan, colspan } = cell
  cell.rowspan = 1
  cell.colspan = 1
  for (let dr = 0; dr < rowspan; dr++) {
    for (let dc = 0; dc < colspan; dc++) {
      if (dr === 0 && dc === 0) continue
      next.cells.push(newCell(row + dr, col + dc))
    }
  }
  next.cells.sort((a, b) => (a.row - b.row) || (a.col - b.col))
  return next
}
