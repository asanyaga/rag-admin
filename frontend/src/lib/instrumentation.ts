/**
 * Manual Instrumentation Utilities
 *
 * Helper functions for adding custom tracing to application code.
 * These utilities wrap the OpenTelemetry API with convenient TypeScript interfaces.
 *
 * Use these for:
 * - Tracing business logic functions
 * - Adding context to critical user flows
 * - Instrumenting custom operations not covered by auto-instrumentation
 */

import { Span, SpanStatusCode, trace, context } from '@opentelemetry/api'
import { getTracer } from './tracing'

/**
 * Wrap an async function with tracing
 *
 * Creates a span for the duration of the function execution. The span is
 * automatically ended when the function completes or throws an error.
 *
 * @param spanName - Name for the span (e.g., 'projects.create')
 * @param fn - Async function to trace. Receives the span as first argument.
 * @param attributes - Optional span attributes to set
 * @returns The result of the wrapped function
 *
 * @example
 * ```typescript
 * const result = await traceAsync(
 *   'user.signup',
 *   async (span) => {
 *     span.setAttribute('user.email', email)
 *     const user = await createUser(email)
 *     span.setAttribute('user.id', user.id)
 *     return user
 *   },
 *   { 'component': 'auth' }
 * )
 * ```
 */
export async function traceAsync<T>(
  spanName: string,
  fn: (span: Span) => Promise<T>,
  attributes?: Record<string, string | number | boolean>
): Promise<T> {
  const tracer = getTracer()
  const span = tracer.startSpan(spanName)

  // Set initial attributes if provided
  if (attributes) {
    Object.entries(attributes).forEach(([key, value]) => {
      span.setAttribute(key, value)
    })
  }

  try {
    // Execute function in span context
    const result = await context.with(trace.setSpan(context.active(), span), async () => {
      return await fn(span)
    })

    // Mark span as successful
    span.setStatus({ code: SpanStatusCode.OK })
    return result
  } catch (error) {
    // Record exception and mark span as error
    span.recordException(error as Error)
    span.setStatus({
      code: SpanStatusCode.ERROR,
      message: error instanceof Error ? error.message : 'Unknown error',
    })
    throw error
  } finally {
    // Always end the span
    span.end()
  }
}

/**
 * Wrap a synchronous function with tracing
 *
 * Similar to traceAsync but for synchronous operations.
 *
 * @param spanName - Name for the span
 * @param fn - Sync function to trace. Receives the span as first argument.
 * @param attributes - Optional span attributes to set
 * @returns The result of the wrapped function
 *
 * @example
 * ```typescript
 * const processed = traceSync(
 *   'data.transform',
 *   (span) => {
 *     span.setAttribute('data.size', rawData.length)
 *     return processData(rawData)
 *   }
 * )
 * ```
 */
export function traceSync<T>(
  spanName: string,
  fn: (span: Span) => T,
  attributes?: Record<string, string | number | boolean>
): T {
  const tracer = getTracer()
  const span = tracer.startSpan(spanName)

  // Set initial attributes if provided
  if (attributes) {
    Object.entries(attributes).forEach(([key, value]) => {
      span.setAttribute(key, value)
    })
  }

  try {
    // Execute function in span context
    const result = context.with(trace.setSpan(context.active(), span), () => {
      return fn(span)
    })

    // Mark span as successful
    span.setStatus({ code: SpanStatusCode.OK })
    return result
  } catch (error) {
    // Record exception and mark span as error
    span.recordException(error as Error)
    span.setStatus({
      code: SpanStatusCode.ERROR,
      message: error instanceof Error ? error.message : 'Unknown error',
    })
    throw error
  } finally {
    // Always end the span
    span.end()
  }
}

/**
 * Add an event to the current active span
 *
 * Events are timestamped messages that can be attached to spans to mark
 * significant moments during execution.
 *
 * @param name - Event name (e.g., 'validation.failed', 'cache.hit')
 * @param attributes - Optional event attributes
 *
 * @example
 * ```typescript
 * addSpanEvent('cache.miss', { 'cache.key': 'user:123' })
 * ```
 */
export function addSpanEvent(
  name: string,
  attributes?: Record<string, string | number | boolean>
): void {
  const span = trace.getActiveSpan()
  if (span && span.isRecording()) {
    span.addEvent(name, attributes)
  }
}

/**
 * Set an attribute on the current active span
 *
 * Attributes are key-value pairs that add context to spans.
 * They're indexed in SigNoz and can be used for filtering and querying.
 *
 * @param key - Attribute key (use dot notation: 'user.role', 'http.status_code')
 * @param value - Attribute value
 *
 * @example
 * ```typescript
 * setSpanAttribute('user.id', userId)
 * setSpanAttribute('query.duration_ms', durationMs)
 * setSpanAttribute('feature.enabled', true)
 * ```
 */
export function setSpanAttribute(
  key: string,
  value: string | number | boolean
): void {
  const span = trace.getActiveSpan()
  if (span && span.isRecording()) {
    span.setAttribute(key, value)
  }
}

/**
 * Record an exception on the current active span
 *
 * Marks the span as errored and attaches exception details.
 *
 * @param error - Error object to record
 * @param attributes - Optional additional context
 *
 * @example
 * ```typescript
 * try {
 *   await riskyOperation()
 * } catch (error) {
 *   recordSpanException(error, { 'retry.count': retryCount })
 *   throw error
 * }
 * ```
 */
export function recordSpanException(
  error: Error,
  attributes?: Record<string, string | number | boolean>
): void {
  const span = trace.getActiveSpan()
  if (span && span.isRecording()) {
    span.recordException(error)
    span.setStatus({
      code: SpanStatusCode.ERROR,
      message: error.message,
    })
    if (attributes) {
      Object.entries(attributes).forEach(([key, value]) => {
        span.setAttribute(key, value)
      })
    }
  }
}

/**
 * Get the current trace ID
 *
 * Useful for logging the trace ID for correlation with backend traces.
 *
 * @returns Current trace ID as hex string, or null if no active span
 *
 * @example
 * ```typescript
 * const traceId = getCurrentTraceId()
 * console.log('Processing request with trace ID:', traceId)
 * ```
 */
export function getCurrentTraceId(): string | null {
  const span = trace.getActiveSpan()
  if (span) {
    const spanContext = span.spanContext()
    return spanContext.traceId
  }
  return null
}

/**
 * Get the current span ID
 *
 * @returns Current span ID as hex string, or null if no active span
 */
export function getCurrentSpanId(): string | null {
  const span = trace.getActiveSpan()
  if (span) {
    const spanContext = span.spanContext()
    return spanContext.spanId
  }
  return null
}
