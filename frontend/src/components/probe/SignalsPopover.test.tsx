import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { SignalsPopover, DEFAULT_PROBE_CONFIG } from './SignalsPopover'

describe('SignalsPopover', () => {
  it('toggling a signal emits an updated config', () => {
    const onChange = vi.fn()
    render(<SignalsPopover config={DEFAULT_PROBE_CONFIG} onChange={onChange} onRerun={() => {}} />)
    fireEvent.click(screen.getByText('Signals'))            // open popover
    fireEvent.click(screen.getByLabelText('edge_density'))  // toggle off
    expect(onChange).toHaveBeenCalled()
    const cfg = onChange.mock.calls.at(-1)![0]
    expect(cfg.enabled_signals).not.toContain('edge_density')
  })
})
