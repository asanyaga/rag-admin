import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  materialize, setText, toggleHeader, addRow, removeRow, addColumn, removeColumn,
  mergeCells, splitCell, type TableModel,
} from './tableGrid'

interface Sel { r1: number; c1: number; r2: number; c2: number }

export function TableGridEditor({ model, onChange }:
  { model: TableModel; onChange: (m: TableModel) => void }) {
  const [sel, setSel] = useState<Sel>({ r1: 0, c1: 0, r2: 0, c2: 0 })
  const [error, setError] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const draggingRef = useRef(false)
  const grid = materialize(model)

  // End the drag on any mouse release, even outside the table.
  useEffect(() => {
    const stop = () => { draggingRef.current = false; setDragging(false) }
    window.addEventListener('mouseup', stop)
    return () => window.removeEventListener('mouseup', stop)
  }, [])

  const apply = (fn: () => TableModel) => {
    try { setError(null); onChange(fn()) } catch (e) { setError((e as Error).message) }
  }
  const startSelect = (r: number, c: number, shift: boolean) => {
    if (shift) { setSel((s) => ({ ...s, r2: r, c2: c })); return }
    setSel({ r1: r, c1: c, r2: r, c2: c })
    draggingRef.current = true
    setDragging(true)
  }
  const extendSelect = (r: number, c: number) => {
    if (draggingRef.current) setSel((s) => ({ ...s, r2: r, c2: c }))
  }

  const top = Math.min(sel.r1, sel.r2)
  const bottom = Math.max(sel.r1, sel.r2)
  const left = Math.min(sel.c1, sel.c2)
  const right = Math.max(sel.c1, sel.c2)
  const inSel = (r: number, c: number) => r >= top && r <= bottom && c >= left && c <= right

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1">
        <Button size="sm" variant="outline" onClick={() => apply(() => addRow(model, sel.r1 + 1))}>Add row</Button>
        <Button size="sm" variant="outline" onClick={() => apply(() => addColumn(model, sel.c1 + 1))}>Add column</Button>
        <Button size="sm" variant="outline" onClick={() => apply(() => removeRow(model, sel.r1))}>Delete row</Button>
        <Button size="sm" variant="outline" onClick={() => apply(() => removeColumn(model, sel.c1))}>Delete column</Button>
        <Button size="sm" variant="outline"
          onClick={() => apply(() => mergeCells(model, sel.r1, sel.c1, sel.r2, sel.c2))}>Merge</Button>
        <Button size="sm" variant="outline" onClick={() => apply(() => splitCell(model, sel.r1, sel.c1))}>Split</Button>
        <Button size="sm" variant="outline" onClick={() => apply(() => toggleHeader(model, sel.r1, sel.c1))}>Header</Button>
      </div>
      {error && <p className="text-xs text-destructive">{error}</p>}
      <table className={`border-collapse ${dragging ? 'select-none' : ''}`}>
        <tbody>
          {grid.map((row, r) => (
            <tr key={r}>
              {row.map((slot, c) => {
                if (slot.kind === 'covered') return null
                const { cell } = slot
                const selected = inSel(r, c)
                return (
                  <td key={c} rowSpan={cell.rowspan} colSpan={cell.colspan}
                    onMouseDown={(e) => startSelect(r, c, e.shiftKey)}
                    onMouseEnter={() => extendSelect(r, c)}
                    className={`border p-0 ${cell.isHeader ? 'font-semibold' : ''} `
                      + (selected ? 'bg-primary/10 ring-2 ring-inset ring-primary'
                        : cell.isHeader ? 'bg-muted' : '')}>
                    <input
                      aria-label={`cell ${r},${c}`}
                      className="w-full min-w-24 bg-transparent px-2 py-1 text-sm outline-none"
                      value={cell.text}
                      onChange={(e) => apply(() => setText(model, r, c, e.target.value))} />
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
