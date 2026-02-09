import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Play } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { useProject } from '@/contexts/ProjectContext'
import { useGoldenSets } from '@/hooks/useGoldenSets'
import { useEvalRuns } from '@/hooks/useEvalRuns'
import { useIndexes } from '@/hooks/useIndexes'
import type { EvalRunConfig } from '@/types/eval-run'

export default function NewEvalRunPage() {
  const navigate = useNavigate()
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null

  const { goldenSets } = useGoldenSets(projectId)
  const { indexes } = useIndexes(projectId)
  const { createRun } = useEvalRuns(projectId)

  const [goldenSetId, setGoldenSetId] = useState('')
  const [indexId, setIndexId] = useState('')
  const [name, setName] = useState('')
  const [searchType, setSearchType] = useState<EvalRunConfig['searchType']>('semantic')
  const [topK, setTopK] = useState(5)
  const [similarityThreshold, setSimilarityThreshold] = useState(0)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const readyIndexes = indexes.filter((i) => i.status === 'ready')

  const handleSubmit = async () => {
    if (!goldenSetId || !indexId) return
    setIsSubmitting(true)
    try {
      const run = await createRun({
        goldenSetId,
        indexId,
        name: name.trim() || undefined,
        config: { searchType, topK, similarityThreshold },
      })
      navigate(`/evaluation/runs/${run.id}`)
    } catch {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigate('/evaluation')}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <h1 className="text-2xl font-bold">New Evaluation Run</h1>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Golden Set */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Golden Set</CardTitle>
          </CardHeader>
          <CardContent>
            <Select value={goldenSetId} onValueChange={setGoldenSetId}>
              <SelectTrigger>
                <SelectValue placeholder="Select golden set" />
              </SelectTrigger>
              <SelectContent>
                {goldenSets.map((gs) => (
                  <SelectItem key={gs.id} value={gs.id}>
                    {gs.name} ({gs.queryCount} queries)
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardContent>
        </Card>

        {/* Index */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Index</CardTitle>
          </CardHeader>
          <CardContent>
            <Select value={indexId} onValueChange={setIndexId}>
              <SelectTrigger>
                <SelectValue placeholder="Select index" />
              </SelectTrigger>
              <SelectContent>
                {readyIndexes.map((idx) => (
                  <SelectItem key={idx.id} value={idx.id}>
                    {idx.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardContent>
        </Card>

        {/* Config */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Retrieval Config</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label className="text-xs">Search Mode</Label>
              <ToggleGroup
                type="single"
                value={searchType}
                onValueChange={(v) => {
                  if (v) setSearchType(v as EvalRunConfig['searchType'])
                }}
                className="justify-start"
              >
                <ToggleGroupItem value="semantic" size="sm">Semantic</ToggleGroupItem>
                <ToggleGroupItem value="keyword" size="sm">Keyword</ToggleGroupItem>
                <ToggleGroupItem value="hybrid" size="sm">Hybrid</ToggleGroupItem>
              </ToggleGroup>
            </div>
            <div className="space-y-2">
              <Label className="text-xs">Top K: {topK}</Label>
              <Slider
                value={[topK]}
                onValueChange={([v]) => setTopK(v)}
                min={1}
                max={20}
                step={1}
              />
            </div>
            <div className="space-y-2">
              <Label className="text-xs">
                Similarity Threshold: {similarityThreshold.toFixed(2)}
              </Label>
              <Slider
                value={[similarityThreshold]}
                onValueChange={([v]) => setSimilarityThreshold(v)}
                min={0}
                max={1}
                step={0.05}
              />
            </div>
          </CardContent>
        </Card>

        {/* Run Name */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Run Name</CardTitle>
          </CardHeader>
          <CardContent>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Optional — auto-generated if empty"
            />
          </CardContent>
        </Card>
      </div>

      <div className="flex gap-3">
        <Button
          onClick={handleSubmit}
          disabled={!goldenSetId || !indexId || isSubmitting}
        >
          <Play className="mr-2 h-4 w-4" />
          {isSubmitting ? 'Starting...' : 'Run Evaluation'}
        </Button>
        <Button variant="outline" onClick={() => navigate('/evaluation')}>
          Cancel
        </Button>
      </div>
    </div>
  )
}
