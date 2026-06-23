export interface SourceDocument {
  id: string
  sha256: string
  filename: string | null
  mimeType: string | null
  byteSize: number | null
  createdAt: string
  projectCount: number
}
