import { useState } from 'react'
import {
  Check,
  X,
  Pencil,
  ChevronDown,
  ChevronUp,
  FileText,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import type { GoldenSetQuery, ReviewStatus } from '@/types/golden-set'

interface ReviewableQueryCardProps {
  query: GoldenSetQuery
  onUpdateReviewStatus: (queryId: string, status: ReviewStatus) => void
  onUpdateText: (queryId: string, text: string) => void
  onDelete: (queryId: string) => void
}

const REVIEW_BADGE_VARIANT: Record<ReviewStatus, 'success' | 'warning' | 'destructive' | 'blue'> = {
  accepted: 'success',
  pending: 'warning',
  rejected: 'destructive',
  edited: 'blue',
}

export function ReviewableQueryCard({
  query,
  onUpdateReviewStatus,
  onUpdateText,
  onDelete,
}: ReviewableQueryCardProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editText, setEditText] = useState(query.queryText)
  const [showReasoning, setShowReasoning] = useState(false)

  const handleSaveEdit = () => {
    if (editText.trim() && editText.trim() !== query.queryText) {
      onUpdateText(query.id, editText.trim())
    }
    setIsEditing(false)
  }

  const handleCancelEdit = () => {
    setEditText(query.queryText)
    setIsEditing(false)
  }

  return (
    <div className="rounded-lg border p-4 space-y-3">
      {/* Header row */}
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          {isEditing ? (
            <div className="space-y-2">
              <Input
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSaveEdit()
                  if (e.key === 'Escape') handleCancelEdit()
                }}
              />
              <div className="flex gap-2">
                <Button size="sm" variant="default" onClick={handleSaveEdit}>
                  Save
                </Button>
                <Button size="sm" variant="outline" onClick={handleCancelEdit}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <p className="text-sm">{query.queryText}</p>
          )}
        </div>

        {/* Badges */}
        <div className="flex items-center gap-2 shrink-0">
          {query.questionType && (
            <Badge variant="outline" className="text-xs capitalize">
              {query.questionType}
            </Badge>
          )}
          <Badge variant={REVIEW_BADGE_VARIANT[query.reviewStatus]}>
            {query.reviewStatus}
          </Badge>
        </div>
      </div>

      {/* Source page badges */}
      {query.sources.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          <FileText className="h-3.5 w-3.5 text-muted-foreground" />
          {query.sources.map((s) => (
            <div key={s.id} className="flex items-center gap-1">
              <span className="text-xs text-muted-foreground truncate max-w-[120px]">
                {s.documentName}
              </span>
              {s.locator.type === 'page' && s.locator.pages.map((p) => (
                <Badge key={p} variant="secondary" className="text-xs px-1.5 py-0">
                  p.{p}
                </Badge>
              ))}
            </div>
          ))}
        </div>
      )}

      {/* Reasoning toggle */}
      {query.reasoning && (
        <button
          onClick={() => setShowReasoning(!showReasoning)}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          {showReasoning ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          Reasoning
        </button>
      )}
      {showReasoning && query.reasoning && (
        <p className="text-xs text-muted-foreground bg-muted/50 rounded p-2">
          {query.reasoning}
        </p>
      )}

      {/* Action buttons */}
      <div className="flex items-center gap-2 pt-1">
        {query.reviewStatus !== 'accepted' && (
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs text-emerald-600 border-emerald-200 hover:bg-emerald-50"
            onClick={() => onUpdateReviewStatus(query.id, 'accepted')}
          >
            <Check className="mr-1 h-3 w-3" />
            Accept
          </Button>
        )}
        {!isEditing && (
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs"
            onClick={() => {
              setEditText(query.queryText)
              setIsEditing(true)
            }}
          >
            <Pencil className="mr-1 h-3 w-3" />
            Edit
          </Button>
        )}
        {query.reviewStatus !== 'rejected' && (
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs text-red-600 border-red-200 hover:bg-red-50"
            onClick={() => onUpdateReviewStatus(query.id, 'rejected')}
          >
            <X className="mr-1 h-3 w-3" />
            Reject
          </Button>
        )}
        <div className="flex-1" />
        <Button
          size="sm"
          variant="ghost"
          className="h-7 text-xs text-muted-foreground"
          onClick={() => onDelete(query.id)}
        >
          Delete
        </Button>
      </div>
    </div>
  )
}
