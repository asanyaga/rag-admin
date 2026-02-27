/**
 * Test utilities — wraps components with required providers for testing.
 */
import { type ReactElement } from 'react'
import { render, type RenderOptions } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

interface WrapperProps {
  children: React.ReactNode
}

function AllProviders({ children }: WrapperProps) {
  return <MemoryRouter>{children}</MemoryRouter>
}

function customRender(
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) {
  return render(ui, { wrapper: AllProviders, ...options })
}

export * from '@testing-library/react'
export { customRender as render }
