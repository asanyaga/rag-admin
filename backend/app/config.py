from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://ragadmin:ragadmin_dev@localhost:5432/ragadmin"

    # JWT
    JWT_SECRET_KEY: str = "change-this-to-a-secure-random-key"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Session
    SESSION_SECRET_KEY: str = "change-this-to-another-secure-random-key"

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"

    # CORS
    FRONTEND_URL: str = "http://localhost:5173"
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Application
    DEBUG: bool = True

    # -------------------------------------------------------------------------
    # Observability Configuration (OpenTelemetry)
    # -------------------------------------------------------------------------
    # These settings control how your application emits telemetry data.
    # Telemetry includes: traces (request journeys), logs, and metrics.

    # Master toggle for all observability features.
    # Set to False to completely disable OTel instrumentation.
    # Useful for local development when you don't need telemetry.
    OTEL_ENABLED: bool = True

    # OTLP exporter endpoint - where telemetry data is sent.
    # This should point to your OTel Collector's gRPC endpoint.
    # - Docker: use service name "signoz-otel-collector"
    # - Local: use "localhost" if collector is running on host
    OTEL_EXPORTER_ENDPOINT: str = "http://signoz-otel-collector:4317"

    # Service name appears in all traces and logs.
    # Use a descriptive name that identifies this service uniquely.
    # In a microservices setup, each service would have a different name.
    OTEL_SERVICE_NAME: str = "rag-admin-backend"

    # Minimum log level to capture. Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
    # - DEBUG: Very verbose, includes internal framework logs
    # - INFO: Standard operation logs (recommended for production)
    # - WARNING: Only warnings and errors
    LOG_LEVEL: str = "INFO"

    # Log output format:
    # - "json": Structured JSON logs (recommended for production)
    #           Enables log aggregation, searching, and correlation
    # - "text": Human-readable format (recommended for local development)
    #           Easier to read in terminal, but harder to parse programmatically
    LOG_FORMAT: str = "json"

    # -------------------------------------------------------------------------
    # Frontend Telemetry Proxy Configuration
    # -------------------------------------------------------------------------
    # These settings control the proxy that forwards frontend telemetry to the
    # local OTel collector, preventing browser permission prompts.

    # URL of the OTel collector (HTTP endpoint for OTLP)
    # This is used by the backend proxy to forward frontend telemetry.
    # Note: Frontend signals use HTTP (port 4318), backend signals use gRPC (port 4317)
    OTEL_COLLECTOR_URL: str = "http://localhost:4318"

    # Connection timeout for OTel collector (seconds)
    # How long to wait when establishing connection to the collector
    OTEL_CONNECT_TIMEOUT: float = 2.0

    # Request timeout for OTel collector (seconds)
    # How long to wait for collector to respond after connection is established
    OTEL_REQUEST_TIMEOUT: float = 3.0


settings = Settings()
