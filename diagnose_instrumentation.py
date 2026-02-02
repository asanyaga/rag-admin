#!/usr/bin/env python3
"""
Diagnostic script to understand why FastAPI instrumentation isn't working.
"""

import sys
sys.path.insert(0, '/app')

from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor, OpenTelemetryMiddleware
from app.main import app

print("=" * 70)
print("FastAPI Instrumentation Diagnostic")
print("=" * 70)

# 1. Check tracer provider
print("\n1. Tracer Provider:")
provider = trace.get_tracer_provider()
print(f"   Type: {type(provider)}")
print(f"   Instance: {provider}")

# 2. Check if FastAPI app has OpenTelemetry middleware
print("\n2. Middleware Stack:")
for i, middleware in enumerate(app.user_middleware):
    mw_class = middleware.cls if hasattr(middleware, 'cls') else middleware
    print(f"   {i}. {mw_class}")
    if 'OpenTelemetry' in str(mw_class):
        print(f"      ✓ OpenTelemetry middleware found!")

has_otel = any('OpenTelemetry' in str(m) for m in app.user_middleware)
print(f"\n   OpenTelemetry middleware present: {has_otel}")

# 3. Check instrumentor state
print("\n3. FastAPI Instrumentor State:")
instrumentor = FastAPIInstrumentor()
print(f"   is_instrumented_by_opentelemetry: {instrumentor.is_instrumented_by_opentelemetry}")

# 4. Try to create a manual span
print("\n4. Manual Span Test:")
try:
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("diagnostic-test-span") as span:
        span.set_attribute("test", "value")
        print("   ✓ Manual span created successfully")
except Exception as e:
    print(f"   ✗ Failed to create span: {e}")

# 5. Check SpanProcessor
print("\n5. Span Processors:")
if hasattr(provider, '_active_span_processor'):
    processor = provider._active_span_processor
    print(f"   Processor: {type(processor)}")
    if hasattr(processor, '_span_processors'):
        print(f"   Sub-processors: {processor._span_processors}")
else:
    print("   No _active_span_processor attribute")

print("\n" + "=" * 70)
print("Diagnosis Complete")
print("=" * 70)
