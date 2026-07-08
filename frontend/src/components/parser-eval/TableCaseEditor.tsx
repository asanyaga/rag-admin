import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { TableGridEditor } from './TableGridEditor'
import { htmlToModel, modelToHtml, emptyModel, type TableModel } from './tableGrid'

interface EditableTable { page: number; model: TableModel }

export function TableCaseEditor({ tables, onSave, onCancel }: {
  tables: { page: number; html: string }[]
  onSave: (tables: { page: number; html: string }[], opts: { verify: boolean }) => Promise<void>
  onCancel: () => void
}) {
  const [rows, setRows] = useState<EditableTable[]>(
    () => tables.map((t) => ({ page: t.page, model: htmlToModel(t.html) })))
  const [saving, setSaving] = useState(false)

  const update = (i: number, patch: Partial<EditableTable>) =>
    setRows((r) => r.map((t, idx) => (idx === i ? { ...t, ...patch } : t)))
  const move = (i: number, dir: -1 | 1) => setRows((r) => {
    const j = i + dir
    if (j < 0 || j >= r.length) return r
    const copy = [...r]
    ;[copy[i], copy[j]] = [copy[j], copy[i]]
    return copy
  })
  const serialize = () => rows.map((t) => ({ page: t.page, html: modelToHtml(t.model) }))
  const save = async (verify: boolean) => {
    setSaving(true)
    try { await onSave(serialize(), { verify }) } finally { setSaving(false) }
  }

  return (
    <div className="space-y-6">
      {rows.map((t, i) => (
        <div key={i} className="space-y-2 rounded-md border p-3">
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">Page</span>
            <Input type="number" className="w-20" value={t.page}
              onChange={(e) => update(i, { page: Number(e.target.value) })} />
            <Button size="sm" variant="ghost" onClick={() => move(i, -1)}>↑</Button>
            <Button size="sm" variant="ghost" onClick={() => move(i, 1)}>↓</Button>
            <Button size="sm" variant="ghost"
              onClick={() => setRows((r) => r.filter((_, idx) => idx !== i))}>Delete table</Button>
          </div>
          <TableGridEditor model={t.model} onChange={(m) => update(i, { model: m })} />
        </div>
      ))}
      <Button variant="outline" size="sm"
        onClick={() => setRows((r) => [...r, { page: 1, model: emptyModel(2, 2) }])}>Add table</Button>
      <div className="flex gap-2">
        <Button disabled={saving} onClick={() => save(false)}>Save</Button>
        <Button disabled={saving} variant="secondary" onClick={() => save(true)}>Save &amp; Accept</Button>
        <Button variant="ghost" onClick={onCancel}>Cancel</Button>
      </div>
    </div>
  )
}
