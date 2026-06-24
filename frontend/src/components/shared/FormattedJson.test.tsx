import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { FormattedJson } from './FormattedJson'

describe('FormattedJson', () => {
  it('renders JSON string keys and values', () => {
    const { container } = render(<FormattedJson value={{ name: 'Alice' }} />)
    // "name" as key and "Alice" as string value should appear in the pre
    expect(container.querySelector('pre')).toHaveTextContent('"name"')
    expect(container.querySelector('pre')).toHaveTextContent('"Alice"')
  })

  it('renders JSON number values', () => {
    render(<FormattedJson value={{ count: 42 }} />)
    expect(screen.getByText('42')).toBeInTheDocument()
  })

  it('renders JSON boolean values', () => {
    render(<FormattedJson value={{ active: true, disabled: false }} />)
    expect(screen.getByText('true')).toBeInTheDocument()
    expect(screen.getByText('false')).toBeInTheDocument()
  })

  it('renders null JSON value as literal text', () => {
    render(<FormattedJson value={{ x: null }} />)
    expect(screen.getByText('null')).toBeInTheDocument()
  })

  it('applies maxHeight style to pre element', () => {
    const { container } = render(<FormattedJson value={{ x: 1 }} maxHeight="10rem" />)
    expect(container.querySelector('pre')?.style.maxHeight).toBe('10rem')
  })

  it('uses default maxHeight of 24rem when prop omitted', () => {
    const { container } = render(<FormattedJson value={{ x: 1 }} />)
    expect(container.querySelector('pre')?.style.maxHeight).toBe('24rem')
  })

  it('handles null value prop gracefully without crashing', () => {
    const { container } = render(<FormattedJson value={null} />)
    expect(container.querySelector('pre')).toBeInTheDocument()
  })

  it('handles undefined value prop gracefully without crashing', () => {
    const { container } = render(<FormattedJson value={undefined} />)
    expect(container.querySelector('pre')).toBeInTheDocument()
  })
})
