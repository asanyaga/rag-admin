import { useState, useCallback, ChangeEvent, DragEvent } from 'react'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

interface DocumentUploadZoneProps {
  onFiles: (files: File[]) => void
  compact?: boolean
  disabled?: boolean
}

const ACCEPT_STRING = '.pdf,application/pdf,image/jpeg,image/png,.jpg,.jpeg,.png'

export function DocumentUploadZone({
  onFiles,
  compact = false,
  disabled = false,
}: DocumentUploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false)

  const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault()
      setIsDragging(false)
      const files = Array.from(e.dataTransfer.files)
      if (files.length > 0) onFiles(files)
    },
    [onFiles]
  )

  const handleFileInput = (e: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? [])
    if (files.length > 0) onFiles(files)
    e.target.value = ''
  }

  if (compact) {
    return (
      <div className="flex items-center gap-2 text-sm">
        <label
          htmlFor="file-upload-more"
          className={cn(
            'text-primary hover:text-primary/80 cursor-pointer font-medium',
            disabled && 'opacity-50 pointer-events-none'
          )}
        >
          Add more files
        </label>
        <Input
          id="file-upload-more"
          type="file"
          accept={ACCEPT_STRING}
          onChange={handleFileInput}
          className="sr-only"
          multiple
          disabled={disabled}
        />
        <span className="text-muted-foreground text-xs">PDF or images (JPEG, PNG), 25MB max</span>
      </div>
    )
  }

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={cn(
        'border-2 border-dashed rounded-lg p-8 text-center transition-colors',
        isDragging
          ? 'border-primary bg-primary/5'
          : 'border-muted-foreground/25 hover:border-muted-foreground/50',
        disabled && 'opacity-50 pointer-events-none'
      )}
    >
      <svg
        className="mx-auto h-12 w-12 text-muted-foreground"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
        />
      </svg>
      <div className="mt-4 space-y-1">
        <label htmlFor="file-upload">
          <span className="text-primary hover:text-primary/80 cursor-pointer font-medium">
            Choose files
          </span>
          <span className="text-muted-foreground"> or drag and drop</span>
        </label>
        <Input
          id="file-upload"
          type="file"
          accept={ACCEPT_STRING}
          onChange={handleFileInput}
          className="sr-only"
          multiple
          disabled={disabled}
        />
        <p className="text-xs text-muted-foreground">PDF or images (JPEG, PNG) up to 25MB</p>
      </div>
    </div>
  )
}
