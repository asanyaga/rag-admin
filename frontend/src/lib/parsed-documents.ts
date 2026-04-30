import apiClient from '@/api/client'

export interface ParsedDocumentListItem {
  id: string
  parseRunId: string
  parser: string
  parseConfigHash: string
  sourceDocumentId: string
  sourceFilename: string | null
  hasFullMarkdown: boolean
  blockCount: number
  parsedAt: string
}

export async function listParsedDocuments(
  projectId: string,
  params: {
    parser?: string
    parseConfigHash?: string
    representation?: 'full_text' | 'full_markdown' | 'block'
    latestPerSource?: boolean
  } = {},
): Promise<ParsedDocumentListItem[]> {
  const response = await apiClient.get<ParsedDocumentListItem[]>(
    `/projects/${projectId}/parsed-documents`,
    { params },
  )
  return response.data
}

export interface ResolvedFamily {
  parser: string
  parseConfigHash: string
  parsedDocumentIds: string[]
}

/**
 * Resolves a wizard-selected document set to:
 *   1. The latest succeeded parsed-doc per source-document.
 *   2. The (parser, parseConfigHash) family inferred from those parsed-docs.
 *
 * Throws if the resolved parsed-docs span multiple families, or if no
 * succeeded parsed-doc exists in the project for the requested representation.
 *
 * BRIDGE: Unit 4 replaces this with an explicit parsed-doc picker in the wizard.
 *
 * Wide-net: this adapter returns ALL latest parsed-docs in the project for the
 * given representation, not just those tied to the documentIds passed in.
 * Filtering by selected documents requires a backend endpoint extension that
 * Unit 1 didn't ship; the precise picker lands in Unit 4.
 */
export async function resolveLatestParsedDocsForDocuments(
  projectId: string,
  _documentIds: string[],
  representation: 'full_text' | 'full_markdown' | 'block',
): Promise<ResolvedFamily> {
  const all = await listParsedDocuments(projectId, {
    representation,
    latestPerSource: true,
  })

  if (all.length === 0) {
    throw new Error(
      `No succeeded parsed-documents found in this project for ` +
      `representation=${representation}. Parse documents first.`
    )
  }

  const families = new Set<string>()
  const ids: string[] = []
  for (const pd of all) {
    families.add(`${pd.parser}|${pd.parseConfigHash}`)
    ids.push(pd.parseRunId)
  }
  if (families.size > 1) {
    throw new Error(
      'Multiple parse-config families detected in this project. ' +
      'The Unit 4 picker will let you choose one explicitly. ' +
      'For now, parse all documents with a single configuration.'
    )
  }

  const [family] = [...families]
  const [parser, parseConfigHash] = family.split('|')
  return { parser, parseConfigHash, parsedDocumentIds: ids }
}
