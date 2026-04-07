import { useState } from 'react'
import type { ExtractionGroundTruthSet } from '@/types/extractionGroundTruth'
import type { CreateExtractionEvalRunRequest } from '@/types/extractionEval'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Play } from 'lucide-react'

interface EvalRunConfigProps {
  groundTruthSets: ExtractionGroundTruthSet[]
  onRun: (data: CreateExtractionEvalRunRequest) => Promise<void>
  isRunning: boolean
}

export function EvalRunConfig({ groundTruthSets, onRun, isRunning }: EvalRunConfigProps) {
  const [selectedSetId, setSelectedSetId] = useState('')
  const [name, setName] = useState('')

  const handleRun = async () => {
    if (!selectedSetId) return
    await onRun({
      groundTruthSetId: selectedSetId,
      name: name.trim() || undefined,
    })
    setName('')
  }

  return (
    <div className="rounded-lg border p-4 space-y-4">
      <h3 className="text-sm font-medium">Run Evaluation</h3>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label className="text-xs">Ground Truth Set</Label>
          <Select value={selectedSetId} onValueChange={setSelectedSetId}>
            <SelectTrigger>
              <SelectValue placeholder="Select a set" />
            </SelectTrigger>
            <SelectContent>
              {groundTruthSets.map((set) => (
                <SelectItem key={set.id} value={set.id}>
                  {set.name} ({set.itemCount} items)
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">Run Name (optional)</Label>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Auto-generated if empty"
          />
        </div>
      </div>
      <Button
        onClick={handleRun}
        disabled={!selectedSetId || isRunning}
        size="sm"
      >
        <Play className="h-3.5 w-3.5 mr-1.5" />
        {isRunning ? 'Running...' : 'Run Evaluation'}
      </Button>
    </div>
  )
}
