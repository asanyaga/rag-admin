#!/usr/bin/env python3
"""
Test script to manually create and export a span to SigNoz.
This verifies the full OTLP export pipeline works.
"""

import time
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

print("=" * 60)
print("OTLP Export Test")
print("=" * 60)

# Configuration
service_name = "test-service"
endpoint = "http://signoz-otel-collector:4317"

print(f"Service Name: {service_name}")
print(f"Endpoint: {endpoint}")
print()

# Step 1: Create resource
print("Step 1: Creating resource...")
resource = Resource.create({
    SERVICE_NAME: service_name,
})
print(f"✓ Resource created: {resource.attributes}")

# Step 2: Create TracerProvider
print("\nStep 2: Creating TracerProvider...")
provider = TracerProvider(resource=resource)
print("✓ TracerProvider created")

# Step 3: Create OTLP exporter
print("\nStep 3: Creating OTLP exporter...")
try:
    exporter = OTLPSpanExporter(
        endpoint=endpoint,
        insecure=True,
    )
    print(f"✓ OTLP exporter created (endpoint: {endpoint})")
except Exception as e:
    print(f"✗ Failed to create exporter: {e}")
    exit(1)

# Step 4: Add BatchSpanProcessor
print("\nStep 4: Adding BatchSpanProcessor...")
processor = BatchSpanProcessor(exporter)
provider.add_span_processor(processor)
print("✓ BatchSpanProcessor added")

# Step 5: Set as global provider
print("\nStep 5: Setting as global tracer provider...")
trace.set_tracer_provider(provider)
print("✓ Global tracer provider set")

# Step 6: Create test span
print("\nStep 6: Creating test span...")
tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("test-span") as span:
    span.set_attribute("test.type", "manual-export-test")
    span.set_attribute("test.timestamp", int(time.time()))
    span.add_event("Test event", {"event.type": "test"})
    print("✓ Test span created with attributes")
    time.sleep(0.1)  # Simulate some work

print("✓ Test span completed")

# Step 7: Force flush to export immediately
print("\nStep 7: Forcing export (flushing)...")
try:
    provider.force_flush(timeout_millis=10000)
    print("✓ Flush completed successfully")
except Exception as e:
    print(f"✗ Flush failed: {e}")
    exit(1)

print("\n" + "=" * 60)
print("SUCCESS: Test span created and exported!")
print("=" * 60)
print()
print("Now check SigNoz UI:")
print("  1. Open: http://localhost:8080")
print("  2. Go to: Traces")
print("  3. Filter: service = test-service")
print("  4. Look for: test-span")
print()
print("If you see the span, the OTLP export pipeline works!")
print("If not, there may be a collector configuration issue.")
