/**
 * OpenTelemetry Tracing Configuration
 *
 * This module sets up frontend tracing with OpenTelemetry Web SDK to enable
 * end-to-end distributed tracing from browser to backend to database.
 *
 * Features:
 * - Automatic instrumentation of HTTP requests, page loads, and user interactions
 * - W3C Trace Context propagation to backend
 * - Trace ID extraction from backend responses for error correlation
 * - Graceful degradation if tracing fails or collector is unreachable
 */

import { WebTracerProvider } from '@opentelemetry/sdk-trace-web'
import { BatchSpanProcessor } from '@opentelemetry/sdk-trace-base'
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http'
import { resourceFromAttributes, defaultResource } from '@opentelemetry/resources'
import { SEMRESATTRS_SERVICE_NAME } from '@opentelemetry/semantic-conventions'
import { registerInstrumentations } from '@opentelemetry/instrumentation'
import { DocumentLoadInstrumentation } from '@opentelemetry/instrumentation-document-load'
import { UserInteractionInstrumentation } from '@opentelemetry/instrumentation-user-interaction'
import { XMLHttpRequestInstrumentation } from '@opentelemetry/instrumentation-xml-http-request'
import { ZoneContextManager } from '@opentelemetry/context-zone'
import { trace, Tracer } from '@opentelemetry/api'

let tracerProvider: WebTracerProvider | null = null

/**
 * Initialize OpenTelemetry tracing
 *
 * Should be called once at application startup, before React renders.
 * Sets up TracerProvider, OTLP exporter, and automatic instrumentations.
 *
 * Configuration via environment variables:
 * - VITE_OTEL_ENABLED: Enable/disable tracing (default: true)
 * - VITE_OTEL_COLLECTOR_URL: OTLP collector endpoint (default: http://localhost:4318/v1/traces)
 * - VITE_OTEL_SAMPLING_RATE: Sampling ratio 0-1 (default: 1.0 for development)
 */
export function initializeTracing(): void {
  try {
    // Check if tracing is enabled
    const enabled = import.meta.env.VITE_OTEL_ENABLED !== 'false'
    if (!enabled) {
      console.info('[Tracing] OpenTelemetry disabled via VITE_OTEL_ENABLED')
      return
    }

    console.info('[Tracing] Initializing OpenTelemetry...')

    // Create resource with service metadata
    const resource = defaultResource().merge(
      resourceFromAttributes({
        [SEMRESATTRS_SERVICE_NAME]: 'rag-admin-frontend',
        'service.version': '0.1.0',
      })
    )

    // Configure OTLP exporter
    // In production, use backend proxy to avoid browser permission prompts
    // In development, can use direct connection to local collector
    const isDev = import.meta.env.DEV
    const collectorUrl = import.meta.env.VITE_OTEL_COLLECTOR_URL ||
      (isDev ? 'http://localhost:4318/v1/traces' : '/api/v1/traces')

    const exporter = new OTLPTraceExporter({
      url: collectorUrl,
      headers: {
        // Add authentication headers here if needed for production
        // 'Authorization': 'Bearer token'
      },
    })

    // Create batch span processor for efficient export
    const spanProcessor = new BatchSpanProcessor(exporter, {
      // Optimize for development: export quickly for immediate feedback
      scheduledDelayMillis: 2000,  // Export every 2 seconds
      maxExportBatchSize: 50,
      maxQueueSize: 100,
    })

    // Create tracer provider with resource and span processors
    tracerProvider = new WebTracerProvider({
      resource,
      spanProcessors: [spanProcessor],
    })

    // Register provider with ZoneContextManager for proper context propagation
    tracerProvider.register({
      contextManager: new ZoneContextManager(),
    })

    // Register automatic instrumentations
    registerInstrumentations({
      instrumentations: [
        // Track page load performance
        new DocumentLoadInstrumentation(),

        // Track user clicks and form submissions
        new UserInteractionInstrumentation({
          eventNames: ['click', 'submit'],
        }),

        // Track XMLHttpRequest and fetch API calls
        // CRITICAL: This propagates trace context to backend
        new XMLHttpRequestInstrumentation({
          // Propagate trace headers to these origins
          propagateTraceHeaderCorsUrls: [
            /localhost:8000/,     // Local backend
            /localhost:5173/,     // Vite dev server
            /localhost:3000/,     // Alternative frontend port
            // Add production domains here:
            // /api\.example\.com/,
          ],
          // Clear timing resources to prevent memory leaks
          clearTimingResources: true,
        }),
      ],
    })

    console.info('[Tracing] OpenTelemetry initialized successfully')
    console.info(`[Tracing] Collector URL: ${collectorUrl}`)
  } catch (error) {
    // Graceful degradation: log error but don't break the app
    console.error('[Tracing] Failed to initialize OpenTelemetry:', error)
    console.warn('[Tracing] Application will continue without tracing')
  }
}

/**
 * Get the global tracer instance for manual instrumentation
 *
 * @param name - Tracer name (typically module/component name)
 * @returns Tracer instance for creating manual spans
 *
 * @example
 * ```typescript
 * const tracer = getTracer('my-component')
 * const span = tracer.startSpan('operation-name')
 * try {
 *   // Do work
 *   span.end()
 * } catch (error) {
 *   span.recordException(error)
 *   span.end()
 * }
 * ```
 */
export function getTracer(name = 'rag-admin-frontend'): Tracer {
  return trace.getTracer(name)
}

/**
 * Extract trace context from HTTP response headers
 *
 * Parses W3C Trace Context headers (traceparent, tracestate) and Server-Timing
 * header from backend responses. This enables correlating frontend errors with
 * backend traces in SigNoz.
 *
 * @param headers - Axios response headers or Headers object
 * @returns Object containing traceId, spanId, and traceFlags
 *
 * @example
 * ```typescript
 * // In Axios interceptor
 * apiClient.interceptors.response.use(
 *   (response) => {
 *     const trace = extractTraceFromHeaders(response.headers)
 *     if (trace.traceId) {
 *       console.log('Trace ID:', trace.traceId)
 *     }
 *     return response
 *   }
 * )
 * ```
 */
export function extractTraceFromHeaders(headers: unknown): {
  traceId: string | undefined
  spanId: string | undefined
  traceFlags: string | undefined
} {
  try {
    // Handle both Axios headers (object-like) and fetch Headers (class with get method)
    let traceparent: string | null | undefined
    let serverTiming: string | null | undefined

    if (headers && typeof headers === 'object') {
      // Check if it's a Headers object with a get method
      if ('get' in headers && typeof headers.get === 'function') {
        traceparent = headers.get('traceparent')
        serverTiming = headers.get('server-timing')
      } else {
        // Treat as plain object (Axios headers)
        const headersObj = headers as Record<string, unknown>
        traceparent = headersObj.traceparent as string | undefined
        serverTiming = headersObj['server-timing'] as string | undefined
      }
    }

    // Try to get traceparent header (W3C Trace Context format)
    // Format: version-traceId-spanId-flags
    // Example: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
    if (traceparent && typeof traceparent === 'string') {
      const parts = traceparent.split('-')
      if (parts.length === 4) {
        return {
          traceId: parts[1],
          spanId: parts[2],
          traceFlags: parts[3],
        }
      }
    }

    // Fallback: try Server-Timing header
    // Format: traceparent;desc="00-traceId-spanId-flags"
    if (serverTiming && typeof serverTiming === 'string') {
      const match = serverTiming.match(/traceparent;desc="(.+?)"/)
      if (match && match[1]) {
        const parts = match[1].split('-')
        if (parts.length === 4) {
          return {
            traceId: parts[1],
            spanId: parts[2],
            traceFlags: parts[3],
          }
        }
      }
    }
  } catch (error) {
    console.warn('[Tracing] Failed to extract trace from headers:', error)
  }

  // Return undefined values if extraction failed
  return {
    traceId: undefined,
    spanId: undefined,
    traceFlags: undefined,
  }
}

/**
 * Shutdown tracing and flush pending spans
 *
 * Should be called on application unmount or before page unload.
 * Ensures all pending spans are exported to the collector.
 *
 * @returns Promise that resolves when shutdown is complete
 */
export async function shutdownTracing(): Promise<void> {
  if (tracerProvider) {
    try {
      console.info('[Tracing] Shutting down OpenTelemetry...')
      await tracerProvider.shutdown()
      console.info('[Tracing] OpenTelemetry shutdown complete')
    } catch (error) {
      console.error('[Tracing] Error during OpenTelemetry shutdown:', error)
    }
  }
}

// Optional: Add beforeunload handler to flush spans on page close
if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', () => {
    // Force flush spans before page unload
    tracerProvider?.forceFlush()
  })
}
