import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ParseRunInputForm } from './ParseRunInputForm'

describe('ParseRunInputForm', () => {
  it('renders a source document picker and parser select', () => {
    render(
      <ParseRunInputForm
        agentDefinitionId="a1"
        sourceDocuments={[
          {
            id: 's1',
            sha256: 'abc',
            filename: 'acme.pdf',
            mimeType: 'application/pdf',
            byteSize: 100,
            createdAt: '2026-01-01',
            projectCount: 1,
          },
        ]}
        isStarting={false}
        onStart={vi.fn()}
      />
    )

    expect(screen.getByText('Source Document')).toBeInTheDocument()
    expect(screen.getByText('Parser')).toBeInTheDocument()
    expect(screen.getByText('acme.pdf')).toBeInTheDocument()
  })
})
