import { useState } from 'react'
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
  const grid = materialize(model)

  const apply = (fn: () => TableModel) => {
    try { setError(null); onChange(fn()) } catch (e) { setError((e as Error).message) }
  }
  const onCellMouseDown = (r: number, c: number, shift: boolean) =>
    setSel((s) => shift ? { ...s, r2: r, c2: c } : { r1: r, c1: c, r2: r, c2: c })

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
      <table className="border-collapse">
        <tbody>
          {grid.map((row, r) => (
            <tr key={r}>
              {row.map((slot, c) => {
                if (slot.kind === 'covered') return null
                const { cell } = slot
                const selected = r === sel.r1 && c === sel.c1
                return (
                  <td key={c} rowSpan={cell.rowspan} colSpan={cell.colspan}
                    onMouseDown={(e) => onCellMouseDown(r, c, e.shiftKey)}
                    className={`border p-0 ${selected ? 'ring-2 ring-primary' : ''} ${cell.isHeader ? 'bg-muted font-semibold' : ''}`}>
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
