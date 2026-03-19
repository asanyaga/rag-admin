import { useState, useCallback, ChangeEvent, DragEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import { ParseMethodSelector } from './ParseMethodSelector'
import type { ParseConfig } from '@/types/parsing'

interface DocumentUploadZoneProps {
  projectId: string
  onUpload: (
    file: File,
    title: string,
    description?: string,
    parserType?: string,
    parseConfig?: ParseConfig
  ) => Promise<void>
  disabled?: boolean
}

const ALLOWED_PDF_TYPES = ['application/pdf']
const ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png']

export function DocumentUploadZone({
  onUpload,
  disabled = false,
}: DocumentUploadZoneProps) {
  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [parserType, setParserType] = useState('simple')
  const [parseConfig, setParseConfig] = useState<ParseConfig>({
    tier: 'agentic',
    expand: ['markdown', 'text'],
  })

  const allowedTypes = [...ALLOWED_PDF_TYPES, ...ALLOWED_IMAGE_TYPES]

  const acceptString = '.pdf,application/pdf,image/jpeg,image/png,.jpg,.jpeg,.png'

  const validateFile = (f: File): string | null => {
    if (!allowedTypes.includes(f.type)) {
      return 'Only PDF and image files (JPEG, PNG) are supported'
    }

    const maxSize = 25 * 1024 * 1024
    if (f.size > maxSize) {
      return 'File size must be less than 25MB'
    }

    return null
  }

  const handleFile = useCallback((f: File) => {
    const validationError = validateFile(f)
    if (validationError) {
      setError(validationError)
      return
    }

    setFile(f)
    setError(null)

    if (!title) {
      const filename = f.name.replace(/\.\w+$/i, '')
      setTitle(filename)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [title, parserType])

  const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(false)

    const droppedFile = e.dataTransfer.files[0]
    if (droppedFile) {
      handleFile(droppedFile)
    }
  }, [handleFile])

  const handleFileInput = (e: ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    if (selectedFile) {
      handleFile(selectedFile)
    }
  }

  const handleParserTypeChange = (type: string) => {
    setParserType(type)
  }

  const handleSubmit = async () => {
    if (!file || !title.trim()) {
      setError('Please select a file and enter a title')
      return
    }

    setIsUploading(true)
    setError(null)

    try {
      await onUpload(
        file,
        title.trim(),
        description.trim() || undefined,
        parserType,
        parserType === 'llamaparse' ? parseConfig : undefined,
      )

      // Reset form
      setFile(null)
      setTitle('')
      setDescription('')
      setParserType('simple')
      setParseConfig({ tier: 'agentic', expand: ['markdown', 'text'] })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div className="space-y-4">
      {/* Drag and Drop Zone */}
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
          {file ? (
            <div className="space-y-2">
              <svg
                className="mx-auto h-12 w-12 text-primary"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
              <div>
                <p className="font-medium">{file.name}</p>
                <p className="text-sm text-muted-foreground">
                  {(file.size / 1024 / 1024).toFixed(2)} MB
                </p>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setFile(null)}
                disabled={isUploading}
              >
                Remove
              </Button>
            </div>
          ) : (
            <div className="space-y-2">
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
              <div>
                <label htmlFor="file-upload">
                  <span className="text-primary hover:text-primary/80 cursor-pointer font-medium">
                    Choose a file
                  </span>
                  <span className="text-muted-foreground"> or drag and drop</span>
                </label>
                <Input
                  id="file-upload"
                  type="file"
                  accept={acceptString}
                  onChange={handleFileInput}
                  className="sr-only"
                  disabled={disabled}
                />
              </div>
              <p className="text-xs text-muted-foreground">
                PDF or images (JPEG, PNG) up to 25MB
              </p>
            </div>
          )}
        </div>

        {/* Title and Description */}
        {file && (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="title">Title *</Label>
              <Input
                id="title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Enter document title"
                disabled={isUploading}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional description"
                disabled={isUploading}
                rows={3}
              />
            </div>
          </div>
        )}

        {/* Parse Method Selector */}
        <ParseMethodSelector
          parserType={parserType}
          config={parseConfig}
          onParserTypeChange={handleParserTypeChange}
          onConfigChange={setParseConfig}
          disabled={isUploading}
        />

        {/* Error Message */}
        {error && (
          <div className="text-sm text-red-600 dark:text-red-400">{error}</div>
        )}

        {/* Upload Button */}
        {file && (
          <Button
            onClick={handleSubmit}
            disabled={!file || !title.trim() || isUploading || disabled}
            className="w-full"
          >
            {isUploading ? 'Uploading...' : 'Upload Document'}
          </Button>
        )}
    </div>
  )
}
