# Manual Span Instrumentation Guide

This guide shows how to add custom spans to trace business logic alongside auto-instrumentation.

## Quick Reference

```python
from app.observability import get_tracer
from opentelemetry.trace import Status, StatusCode

# Get tracer for your module
tracer = get_tracer(__name__)

# Create a span
with tracer.start_as_current_span("operation_name") as span:
    # Add attributes for context
    span.set_attribute("key", "value")

    # Your code here
    result = do_something()

    # Record success/failure
    if success:
        span.set_status(Status(StatusCode.OK))
    else:
        span.set_status(Status(StatusCode.ERROR, "Reason"))
```

## When to Use Manual Spans

Add manual spans for:

✅ **Business logic operations** (authenticate_user, process_payment)
✅ **CPU-intensive work** (password hashing, image processing)
✅ **External service calls not auto-instrumented**
✅ **Critical paths you want to measure separately**

Don't add spans for:

❌ **Trivial operations** (<10ms, simple getters/setters)
❌ **Operations already traced** (DB queries, HTTP requests)
❌ **High-frequency loops** (creates too many spans)

## Example: Auth Flow

See `backend/app/routers/auth.py` for a complete example:

```python
from app.observability import get_tracer
from opentelemetry.trace import Status, StatusCode

tracer = get_tracer(__name__)

@router.post("/signin")
async def sign_in(request_data: SignInRequest, ...):
    # Create span for authentication flow
    with tracer.start_as_current_span("authenticate_user") as span:
        # Add context
        span.set_attribute("auth.email", request_data.email)
        span.set_attribute("auth.method", "email_password")

        try:
            user, tokens = await auth_service.sign_in(...)

            # Record success
            span.set_attribute("auth.success", True)
            span.set_attribute("user.id", user.id)
            span.set_status(Status(StatusCode.OK))

            return response

        except AuthenticationError:
            # Record failure
            span.set_attribute("auth.success", False)
            span.set_status(Status(StatusCode.ERROR, "Invalid credentials"))
            raise
```

## Span Hierarchy

The example above creates this hierarchy:

```
POST /api/v1/auth/signin (auto-instrumented by FastAPI)
└── authenticate_user (manual span)
    ├── SELECT FROM users (auto-instrumented by SQLAlchemy)
    └── verify_password (future: manual span in service layer)
```

## Best Practices

### 1. Use Semantic Attributes

Follow OpenTelemetry conventions: https://opentelemetry.io/docs/specs/semconv/

```python
# ✅ Good: Semantic conventions
span.set_attribute("http.method", "POST")
span.set_attribute("db.system", "postgresql")
span.set_attribute("auth.success", True)

# ❌ Bad: Non-standard naming
span.set_attribute("method", "POST")
span.set_attribute("database", "postgres")
span.set_attribute("success", True)
```

### 2. Avoid High Cardinality

```python
# ✅ Good: Bounded values
span.set_attribute("auth.method", "email_password")  # Only 2-3 values

# ❌ Bad: Unbounded values
span.set_attribute("auth.email", email)  # Millions of possible values
span.set_attribute("request.body", json.dumps(body))  # Huge strings
```

### 3. Always Set Status on Errors

```python
# ✅ Good: Clear error indication
try:
    result = risky_operation()
    span.set_status(Status(StatusCode.OK))
except ValueError as e:
    span.record_exception(e)  # Captures exception details
    span.set_status(Status(StatusCode.ERROR, str(e)))
    raise

# ❌ Bad: No error indication
try:
    result = risky_operation()
except ValueError:
    raise  # Span status remains UNSET
```

### 4. Use Nested Spans for Complex Operations

```python
with tracer.start_as_current_span("process_order") as order_span:
    order_span.set_attribute("order.id", order_id)

    # Validate
    with tracer.start_as_current_span("validate_order") as val_span:
        validate_items(order)
        validate_payment(order)

    # Process payment
    with tracer.start_as_current_span("charge_payment") as pay_span:
        pay_span.set_attribute("payment.amount", order.total)
        charge_result = payment_gateway.charge(order)

    # Update inventory
    with tracer.start_as_current_span("update_inventory") as inv_span:
        update_stock(order.items)
```

## Troubleshooting

### Spans not appearing?

1. **Check TracerProvider is initialized**:
   ```python
   from opentelemetry import trace
   provider = trace.get_tracer_provider()
   print(type(provider))  # Should be TracerProvider, not ProxyTracerProvider
   ```

2. **Run diagnostic script**:
   ```bash
   docker exec rag-admin-backend python diagnose_instrumentation.py
   ```

3. **Check SigNoz UI** (wait 5-10 seconds for batch export)

### Spans in wrong hierarchy?

Make sure you're in an active context:

```python
# ❌ Wrong: No parent context
async def background_job():
    with tracer.start_as_current_span("job"):
        ...  # This is a root span, disconnected

# ✅ Right: Propagate context
from opentelemetry import context

async def api_handler():
    ctx = context.get_current()
    asyncio.create_task(background_job(ctx))

async def background_job(ctx):
    with tracer.start_as_current_span("job", context=ctx):
        ...  # This is a child of api_handler span
```

## Additional Resources

- [OpenTelemetry Python Tracing API](https://opentelemetry.io/docs/instrumentation/python/manual/)
- [Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/)
- [Deep Dive: How Tracing Works](./deep-dive.md#distributed-tracing-explained)
