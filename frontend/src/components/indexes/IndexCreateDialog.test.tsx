import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { IndexCreateDialog } from './IndexCreateDialog'

const defaultProps = {
  open: true,
  onOpenChange: vi.fn(),
  onSubmit: vi.fn().mockResolvedValue(undefined),
  onPreviewChunks: vi.fn().mockResolvedValue({
    totalChunksEstimate: 0,
    avgChunkSizeChars: 0,
    avgChunkSizeTokens: 0,
    minChunkSizeChars: 0,
    maxChunkSizeChars: 0,
    previewChunks: [],
  }),
  documents: [],
}

describe('IndexCreateDialog — chunking config', () => {
  it('shows text chunking fields by default (raw_text source)', () => {
    render(<IndexCreateDialog {...defaultProps} />)
    expect(screen.getByLabelText('Chunk Size')).toBeInTheDocument()
    expect(screen.getByLabelText('Overlap')).toBeInTheDocument()
    expect(screen.queryByText('Heading split level')).not.toBeInTheDocument()
    expect(screen.queryByText('Max section size')).not.toBeInTheDocument()
  })

  it('shows markdown controls and hides text controls when full_markdown selected', async () => {
    const user = userEvent.setup()
    render(<IndexCreateDialog {...defaultProps} />)

    // Click the "full_markdown" option in the source representation control
    const fullMarkdownButton = screen.getByRole('radio', { name: /full markdown/i })
    await user.click(fullMarkdownButton)

    expect(screen.getByText('Heading split level')).toBeInTheDocument()
    expect(screen.getByText('Max section size')).toBeInTheDocument()
    expect(screen.queryByLabelText('Chunk Size')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Overlap')).not.toBeInTheDocument()
  })
})
