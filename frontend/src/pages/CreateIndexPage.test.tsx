import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import CreateIndexPage from './CreateIndexPage'

vi.mock('@/contexts/ProjectContext', () => ({
  useProject: () => ({
    currentProject: { id: 'proj-1', name: 'Test Project' },
  }),
}))

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => vi.fn() }
})

vi.mock('@/hooks/useIndexes', () => ({
  useIndexes: () => ({
    createIndex: vi.fn().mockResolvedValue({ id: 'new-idx' }),
    previewChunks: vi.fn().mockResolvedValue({
      totalChunksEstimate: 2,
      avgChunkSizeChars: 100,
      avgChunkSizeTokens: 25,
      minChunkSizeChars: 80,
      maxChunkSizeChars: 120,
      previewChunks: [],
    }),
  }),
}))

vi.mock('@/lib/parsed-documents', () => ({
  listParseConfigs: vi.fn().mockResolvedValue([
    {
      parser: 'llamaparse',
      parseConfigHash: 'abc123',
      config: { result_type: 'markdown' },
      parsedDocumentCount: 2,
      hasFullMarkdown: true,
      latestParsedAt: '2026-04-30T09:00:00Z',
    },
  ]),
  listParsedDocuments: vi.fn().mockResolvedValue([
    {
      id: 'pd-1',
      parseRunId: 'pr-1',
      parser: 'llamaparse',
      parseConfigHash: 'abc123',
      sourceDocumentId: 'sd-1',
      sourceFilename: 'acme-msa.pdf',
      hasFullMarkdown: true,
      blockCount: 12,
      parsedAt: '2026-04-30T09:11:00Z',
    },
  ]),
}))

function renderPage() {
  return render(
    <MemoryRouter>
      <CreateIndexPage />
    </MemoryRouter>,
  )
}

describe('CreateIndexPage wizard', () => {
  it('starts at step 1 and disables Continue when name is empty', () => {
    renderPage()
    expect(screen.getByRole('heading', { name: 'Details' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /continue/i })).toBeDisabled()
  })

  it('advances to step 2 (Parse Config) after entering a name', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.type(screen.getByLabelText(/name/i), 'My Index')
    await user.click(screen.getByRole('button', { name: /continue/i }))
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Parse Config' })).toBeInTheDocument(),
    )
  })

  it('disables Continue at step 2 until a family is selected', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.type(screen.getByLabelText(/name/i), 'My Index')
    await user.click(screen.getByRole('button', { name: /continue/i }))
    await waitFor(() => screen.getByText('LlamaParse'))

    expect(screen.getByRole('button', { name: /continue/i })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: /llamaparse/i }))
    expect(screen.getByRole('button', { name: /continue/i })).not.toBeDisabled()
  })

  it('disables Continue at step 4 until a parsed-doc is selected', async () => {
    const user = userEvent.setup()
    renderPage()
    // Step 1 → 2
    await user.type(screen.getByLabelText(/name/i), 'My Index')
    await user.click(screen.getByRole('button', { name: /continue/i }))
    await waitFor(() => screen.getByText('LlamaParse'))
    await user.click(screen.getByRole('button', { name: /llamaparse/i }))
    await user.click(screen.getByRole('button', { name: /continue/i }))
    // Step 3 → 4
    await user.click(screen.getByRole('button', { name: /continue/i }))
    // Step 4
    await waitFor(() => screen.getByText('acme-msa.pdf'))
    expect(screen.getByRole('button', { name: /continue/i })).toBeDisabled()
    await user.click(screen.getByRole('checkbox', { name: 'acme-msa.pdf' }))
    expect(screen.getByRole('button', { name: /continue/i })).not.toBeDisabled()
  })
})
