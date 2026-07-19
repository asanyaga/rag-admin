import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { DOCLING_DEFAULT_CONFIG, DoclingConfig } from './DoclingConfig'

function lastCall(onChange: ReturnType<typeof vi.fn>) {
  return onChange.mock.calls[onChange.mock.calls.length - 1][0]
}

describe('DoclingConfig', () => {
  it('an untouched config sends nothing — docling applies its own defaults', () => {
    expect(DOCLING_DEFAULT_CONFIG).toEqual({})
  })

  it('shows the stage toggles up front', () => {
    render(<DoclingConfig config={{}} onChange={vi.fn()} />)
    expect(screen.getByLabelText(/OCR/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/table structure/i)).toBeInTheDocument()
  })

  it('keeps engine options out of the way until asked for', () => {
    render(<DoclingConfig config={{}} onChange={vi.fn()} />)
    expect(screen.queryByRole('combobox', { name: /OCR engine/i })).not.toBeInTheDocument()
  })

  it('reveals engine options behind the advanced toggle', async () => {
    render(<DoclingConfig config={{}} onChange={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /advanced/i }))
    expect(screen.getByRole('combobox', { name: /OCR engine/i })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: /layout model/i })).toBeInTheDocument()
  })

  it('turning a stage off removes its options from the config', async () => {
    const onChange = vi.fn()
    render(
      <DoclingConfig
        config={{ do_ocr: true, ocr_options: { kind: 'tesseract' } }}
        onChange={onChange}
      />,
    )
    await userEvent.click(screen.getByLabelText(/OCR/i))
    const next = lastCall(onChange)
    expect(next.do_ocr).toBe(false)
    // the backend rejects ocr_options alongside do_ocr=false
    expect(next.ocr_options).toBeUndefined()
  })

  it('does not offer options for a disabled stage', async () => {
    render(<DoclingConfig config={{ do_ocr: false }} onChange={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /advanced/i }))
    expect(screen.queryByRole('combobox', { name: /OCR engine/i })).not.toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: /table mode/i })).toBeInTheDocument()
  })

  it('selecting an OCR engine writes it under ocr_options', async () => {
    const onChange = vi.fn()
    render(<DoclingConfig config={{}} onChange={onChange} />)
    await userEvent.click(screen.getByRole('button', { name: /advanced/i }))
    await userEvent.click(screen.getByRole('combobox', { name: /OCR engine/i }))
    await userEvent.click(screen.getByRole('option', { name: /tesseract/i }))
    expect(lastCall(onChange).ocr_options).toMatchObject({ kind: 'tesseract' })
  })

  it('selecting a table mode writes it under table_structure_options', async () => {
    const onChange = vi.fn()
    render(<DoclingConfig config={{}} onChange={onChange} />)
    await userEvent.click(screen.getByRole('button', { name: /advanced/i }))
    await userEvent.click(screen.getByRole('combobox', { name: /table mode/i }))
    await userEvent.click(screen.getByRole('option', { name: /fast/i }))
    expect(lastCall(onChange).table_structure_options).toMatchObject({ mode: 'fast' })
  })

  it('offers only the OCR engines the backend accepts', async () => {
    render(<DoclingConfig config={{}} onChange={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /advanced/i }))
    await userEvent.click(screen.getByRole('combobox', { name: /OCR engine/i }))
    expect(screen.queryByRole('option', { name: /ocrmac/i })).not.toBeInTheDocument()
    expect(screen.getByRole('option', { name: /easyocr/i })).toBeInTheDocument()
  })

  it('switching to the VLM pipeline drops standard-pipeline keys', async () => {
    const onChange = vi.fn()
    render(<DoclingConfig config={{ do_ocr: false }} onChange={onChange} />)
    await userEvent.click(screen.getByRole('combobox', { name: /pipeline/i }))
    await userEvent.click(screen.getByRole('option', { name: /vlm/i }))
    const next = lastCall(onChange)
    // the backend rejects standard-only fields on the vlm pipeline
    expect(next.do_ocr).toBeUndefined()
    expect(next.pipeline).toBe('vlm')
  })

  it('hides the standard-pipeline stages when VLM is selected', () => {
    render(<DoclingConfig config={{ pipeline: 'vlm' }} onChange={vi.fn()} />)
    expect(screen.queryByLabelText(/table structure/i)).not.toBeInTheDocument()
  })

  it('round-trips an existing config without rewriting it', () => {
    const config = {
      backend: 'pypdfium2',
      do_ocr: true,
      ocr_options: { kind: 'tesseract', lang: ['eng'] },
    }
    const onChange = vi.fn()
    render(<DoclingConfig config={config} onChange={onChange} />)
    expect(onChange).not.toHaveBeenCalled()
  })
})

describe('DoclingConfig compact mode', () => {
  it('drops the prose in compact layouts', () => {
    // The selector already hides its own description when compact; a two-line
    // paragraph here would defeat that.
    const { rerender } = render(<DoclingConfig config={{}} onChange={vi.fn()} />)
    expect(screen.getByText(/custom pipeline/i)).toBeInTheDocument()
    rerender(<DoclingConfig config={{}} onChange={vi.fn()} compact />)
    expect(screen.queryByText(/custom pipeline/i)).not.toBeInTheDocument()
  })

  it('keeps every control in compact mode', async () => {
    render(<DoclingConfig config={{}} onChange={vi.fn()} compact />)
    expect(screen.getByRole('combobox', { name: /pipeline/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/OCR/i)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /advanced/i }))
    expect(screen.getByRole('combobox', { name: /OCR engine/i })).toBeInTheDocument()
  })

  it('does not restate the parser description', () => {
    // PARSER_REGISTRY.docling.description already says what docling is; this
    // panel should only add what that line does not cover.
    render(<DoclingConfig config={{}} onChange={vi.fn()} />)
    expect(screen.queryByText(/end-to-end pipeline/i)).not.toBeInTheDocument()
  })
})
