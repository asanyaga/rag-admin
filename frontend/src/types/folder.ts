export interface Folder {
  id: string
  projectId: string
  name: string
  description: string | null
  tags: string[]
  documentCount: number
  createdBy: string
  createdAt: string
  updatedAt: string
}

export interface FolderCreate {
  name: string
  description?: string
  tags?: string[]
}

export interface FolderUpdate {
  name?: string
  description?: string
  tags?: string[]
}
