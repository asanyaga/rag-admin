import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { ParseMethodSelector } from './ParseMethodSelector'
import type { ParseConfig } from '@/types/parsing'

interface ReParseDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onReparse: (parserType: string, config?: ParseConfig) => Promise<void>
}

export function ReParseDialog({
  open,
  onOpenChange,
  onReparse,
}: ReParseDialogProps) {
  const [parserType, setParserType] = useState('llamaparse')
  const [config, setConfig] = useState<ParseConfig>({ tier: 'agentic', expand: ['markdown', 'text', 'items'] })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      setParserType('llamaparse')
      setConfig({ tier: 'agentic', expand: ['markdown', 'text', 'items'] })
      setError(null)
    }
  }, [open])

  const handleSubmit = async () => {
    setIsSubmitting(true)
    setError(null)
    try {
      await onReparse(
        parserType,
        parserType !== 'simple' ? config : undefined
      )
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Re-parse failed')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Re-parse Document</DialogTitle>
          <DialogDescription>
            Parse this document again with different settings.
          </DialogDescription>
        </DialogHeader>

        <ParseMethodSelector
          parserType={parserType}
          config={config}
          onParserTypeChange={setParserType}
          onConfigChange={setConfig}
          disabled={isSubmitting}
        />

        {error && (
          <p className="text-sm text-destructive">{error}</p>
        )}

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting ? 'Parsing...' : 'Start Parse'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
