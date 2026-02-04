/**
 * Navigation Tracker Component
 *
 * Tracks route changes and creates spans for page navigation.
 * This component should be placed inside the Router context (e.g., in RootLayout).
 */

import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { getTracer } from '@/lib/tracing'

export function NavigationTracker() {
  const location = useLocation()

  useEffect(() => {
    // Create a span for each navigation
    const tracer = getTracer('navigation')
    const span = tracer.startSpan('navigation', {
      attributes: {
        'navigation.path': location.pathname,
        'navigation.search': location.search,
        'navigation.hash': location.hash,
      },
    })

    // End the span immediately (navigation is instantaneous)
    // The span timestamp marks when the navigation occurred
    span.end()
  }, [location])

  // This component doesn't render anything
  return null
}
