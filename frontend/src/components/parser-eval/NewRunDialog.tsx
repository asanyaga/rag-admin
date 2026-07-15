import { useState } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { ParseMethodSelector, PARSER_REGISTRY } from '@/components/documents/ParseMethodSelector'
import { useParserEvalCases } from '@/hooks/useParserEval'
import { useSourceDocuments } from '@/hooks/useSourceDocuments'
import { stableStringify } from '@/lib/stableStringify'
import type { ParseConfig } from '@/types/parsing'
import type { CreateRunRequest } from '@/types/parserEval'

type Variant = { adapter: string; config: ParseConfig }

const DEFAULT_ADAPTER = 'custom_pipeline'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  projectId: string
  onCreate: (data: CreateRunRequest) => Promise<void>
}

export function NewRunDialog({ open, onOpenChange, projectId, onCreate }: Props) {
  const { cases } = useParserEvalCases(projectId)
  const { sourceDocuments } = useSourceDocuments()
  const [name, setName] = useState('')
  const [caseIds, setCaseIds] = useState<string[]>([])
  const [variants, setVariants] = useState<Variant[]>([])
  const [submitting, setSubmitting] = useState(false)

  const filename = (id: string) => sourceDocuments.find((d) => d.id === id)?.filename ?? id
  const toggleCase = (id: string) =>
    setCaseIds((a) => (a.includes(id) ? a.filter((x) => x !== id) : [...a, id]))

  const addVariant = () =>
    setVariants((vs) => [
      ...vs,
      { adapter: DEFAULT_ADAPTER, config: PARSER_REGISTRY[DEFAULT_ADAPTER]?.defaultConfig ?? {} },
    ])
  const removeVariant = (i: number) => setVariants((vs) => vs.filter((_, idx) => idx !== i))
  const setVariant = (i: number, patch: Partial<Variant>) =>
    setVariants((vs) => vs.map((v, idx) => (idx === i ? { ...v, ...patch } : v)))

  const keys = variants.map((v) => `${v.adapter}|${stableStringify(v.config)}`)
  const hasDuplicate = new Set(keys).size !== keys.length
  const canSubmit = caseIds.length > 0 && variants.length > 0 && !hasDuplicate

  const handleSubmit = async () => {
    setSubmitting(true)
    try {
      await onCreate({ name: name || undefined, evalCaseIds: caseIds, variants })
      onOpenChange(false)
      setName('')
      setCaseIds([])
      setVariants([])
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>New Run</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label htmlFor="run-name">Name (optional)</Label>
            <Input id="run-name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>

          <div className="space-y-2">
            <Label>Cases</Label>
            {cases.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No cases yet — create one in the Cases tab first.
              </p>
            ) : (
              cases.map((c) => (
                <div key={c.id} className="flex items-center gap-2 text-sm">
                  <Checkbox
                    aria-label={filename(c.sourceDocumentId)}
                    checked={caseIds.includes(c.id)}
                    onCheckedChange={() => toggleCase(c.id)}
                  />
                  <span>
                    {filename(c.sourceDocumentId)} · {c.dimension}
                  </span>
                </div>
              ))
            )}
          </div>

          <div className="space-y-3">
            <Label>Variants</Label>
            {variants.map((v, i) => (
              <div key={i} className="flex items-start gap-2 rounded-md border p-3">
                <div className="flex-1">
                  <ParseMethodSelector
                    compact
                    parserType={v.adapter}
                    config={v.config}
                    onParserTypeChange={(adapter) => setVariant(i, { adapter })}
                    onConfigChange={(config) => setVariant(i, { config })}
                  />
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label="Remove variant"
                  onClick={() => removeVariant(i)}
                >
                  Remove
                </Button>
              </div>
            ))}
            <Button variant="outline" size="sm" onClick={addVariant}>
              Add variant
            </Button>
          </div>
        </div>

        {hasDuplicate && (
          <p className="text-xs text-destructive">
            Duplicate variant: the same adapter appears more than once with the same config — change or
            remove one.
          </p>
        )}
        {!canSubmit && !hasDuplicate && (
          <p className="text-xs text-muted-foreground">
            Select at least one case and add at least one variant to run. (Name is optional.)
          </p>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button disabled={!canSubmit || submitting} onClick={handleSubmit}>
            {submitting ? 'Starting…' : 'Run'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
