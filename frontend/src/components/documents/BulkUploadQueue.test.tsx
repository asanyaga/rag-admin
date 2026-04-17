import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BulkUploadQueue } from './BulkUploadQueue'

const makeFile = (name: string, sizeBytes: number, type = 'application/pdf') => {
  const file = new File(['x'], name, { type })
  Object.defineProperty(file, 'size', { value: sizeBytes })
  return file
}

const defaultProps = {
  projectId: 'project-1',
  documents: [],
  onBulkUpload: vi.fn().mockResolvedValue({ results: [] }),
  onClose: vi.fn(),
}

describe('BulkUploadQueue', () => {
  it('renders all files up to max 20', () => {
    const files = Array.from({ length: 5 }, (_, i) => makeFile(`doc${i}.pdf`, 100))
    render(<BulkUploadQueue {...defaultProps} initialFiles={files} />)
    expect(screen.getAllByText(/\.pdf/)).toHaveLength(5)
  })

  it('shows truncation warning and limits to 20 files when more than 20 provided', () => {
    const files = Array.from({ length: 25 }, (_, i) => makeFile(`doc${i}.pdf`, 100))
    render(<BulkUploadQueue {...defaultProps} initialFiles={files} />)
    expect(screen.getByText(/maximum 20 files/i)).toBeInTheDocument()
    // Only 20 filenames rendered
    expect(screen.getAllByText(/doc\d+\.pdf/)).toHaveLength(20)
  })

  it('flags files exceeding 25MB as failed with an error message', () => {
    const files = [makeFile('big.pdf', 30 * 1024 * 1024), makeFile('ok.pdf', 100)]
    render(<BulkUploadQueue {...defaultProps} initialFiles={files} />)
    expect(screen.getByText(/exceeds 25mb/i)).toBeInTheDocument()
  })

  it('disables submit button when all files are invalid', () => {
    const files = [makeFile('big.pdf', 30 * 1024 * 1024)]
    render(<BulkUploadQueue {...defaultProps} initialFiles={files} />)
    expect(screen.getByRole('button', { name: /upload/i })).toBeDisabled()
  })

  it('submit button label shows count of valid files', () => {
    const files = [
      makeFile('ok.pdf', 100),
      makeFile('ok2.pdf', 100),
      makeFile('big.pdf', 30 * 1024 * 1024),
    ]
    render(<BulkUploadQueue {...defaultProps} initialFiles={files} />)
    expect(screen.getByRole('button', { name: /upload 2 files/i })).toBeInTheDocument()
  })

  it('calls onBulkUpload with valid files only on submit', async () => {
    const onBulkUpload = vi.fn().mockResolvedValue({ results: [] })
    const files = [makeFile('ok.pdf', 100), makeFile('big.pdf', 30 * 1024 * 1024)]
    render(
      <BulkUploadQueue {...defaultProps} initialFiles={files} onBulkUpload={onBulkUpload} />
    )
    await userEvent.click(screen.getByRole('button', { name: /upload 1 file/i }))
    expect(onBulkUpload).toHaveBeenCalledWith(
      expect.objectContaining({ files: [files[0]] })
    )
  })
})
