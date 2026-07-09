import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { TableGridEditor } from './TableGridEditor'
import { htmlToModel, modelToHtml, emptyModel, type TableModel } from './tableGrid'

interface PageGroup { page: number; tables: TableModel[] }

function groupByPage(tables: { page: number; html: string }[]): PageGroup[] {
  const byPage = new Map<number, TableModel[]>()
  const order: number[] = []
  for (const t of tables) {
    if (!byPage.has(t.page)) { byPage.set(t.page, []); order.push(t.page) }
    byPage.get(t.page)!.push(htmlToModel(t.html))
  }
  return order.sort((a, b) => a - b).map((page) => ({ page, tables: byPage.get(page)! }))
}

export function TableCaseEditor({ tables, onSave, onCancel }: {
  tables: { page: number; html: string }[]
  onSave: (tables: { page: number; html: string }[], opts: { verify: boolean }) => Promise<void>
  onCancel: () => void
}) {
  const [groups, setGroups] = useState<PageGroup[]>(() => groupByPage(tables))
  const [saving, setSaving] = useState(false)

  const updateGroup = (gi: number, patch: Partial<PageGroup>) =>
    setGroups((gs) => gs.map((g, i) => (i === gi ? { ...g, ...patch } : g)))
  const updateTable = (gi: number, ti: number, model: TableModel) =>
    setGroups((gs) => gs.map((g, i) => i === gi
      ? { ...g, tables: g.tables.map((m, j) => (j === ti ? model : m)) } : g))
  const addTable = (gi: number) =>
    setGroups((gs) => gs.map((g, i) => i === gi
      ? { ...g, tables: [...g.tables, emptyModel(2, 2)] } : g))
  const deleteTable = (gi: number, ti: number) =>
    setGroups((gs) => gs
      .map((g, i) => (i === gi ? { ...g, tables: g.tables.filter((_, j) => j !== ti) } : g))
      .filter((g) => g.tables.length > 0))
  const moveTable = (gi: number, ti: number, dir: -1 | 1) =>
    setGroups((gs) => gs.map((g, i) => {
      if (i !== gi) return g
      const j = ti + dir
      if (j < 0 || j >= g.tables.length) return g
      const t = [...g.tables]
      ;[t[ti], t[j]] = [t[j], t[ti]]
      return { ...g, tables: t }
    }))
  const addPage = () =>
    setGroups((gs) => {
      const nextPage = gs.reduce((m, g) => Math.max(m, g.page), 0) + 1
      return [...gs, { page: nextPage, tables: [emptyModel(2, 2)] }]
    })

  // The scorer matches the i-th expected table to the i-th parsed table, and parsed
  // tables arrive in (page, reading-order). Serialize page-major so ground-truth order
  // mirrors that and positional matching stays correct.
  const serialize = () =>
    [...groups].sort((a, b) => a.page - b.page)
      .flatMap((g) => g.tables.map((m) => ({ page: g.page, html: modelToHtml(m) })))

  const save = async (verify: boolean) => {
    setSaving(true)
    try { await onSave(serialize(), { verify }) } finally { setSaving(false) }
  }

  return (
    <div className="space-y-6">
      {groups.map((g, gi) => (
        <div key={gi} className="space-y-3 rounded-md border p-3">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Page</span>
            <Input type="number" className="w-20" value={g.page}
              onChange={(e) => updateGroup(gi, { page: Number(e.target.value) })} />
          </div>
          {g.tables.map((model, ti) => (
            <div key={ti} className="space-y-2 rounded-md border bg-muted/30 p-3">
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">Table {ti + 1}</span>
                <Button size="sm" variant="ghost" onClick={() => moveTable(gi, ti, -1)}>↑</Button>
                <Button size="sm" variant="ghost" onClick={() => moveTable(gi, ti, 1)}>↓</Button>
                <Button size="sm" variant="ghost"
                  onClick={() => deleteTable(gi, ti)}>Delete table</Button>
              </div>
              <TableGridEditor model={model} onChange={(m) => updateTable(gi, ti, m)} />
            </div>
          ))}
          <Button variant="outline" size="sm"
            onClick={() => addTable(gi)}>Add table on this page</Button>
        </div>
      ))}
      <Button variant="outline" size="sm" onClick={addPage}>Add page</Button>
      <div className="flex gap-2">
        <Button disabled={saving} onClick={() => save(false)}>Save</Button>
        <Button disabled={saving} variant="secondary" onClick={() => save(true)}>Save &amp; Accept</Button>
        <Button variant="ghost" onClick={onCancel}>Cancel</Button>
      </div>
    </div>
  )
}
