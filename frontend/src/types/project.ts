export interface Project {
  id: string
  userId: string
  name: string
  description: string | null
  tags: string[]
  isArchived: boolean
  createdAt: string
  updatedAt: string
}

export interface ProjectCreate {
  name: string
  description?: string
  tags?: string[]
}

export interface ProjectUpdate {
  name?: string
  description?: string
  tags?: string[]
}
