from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.routers import auth, oauth, users
from app.utils.oauth import setup_oauth

app = FastAPI(
    title="RAG Admin API",
    version="0.1.0",
    debug=settings.DEBUG,
)


@app.on_event("startup")
async def startup_event():
    """Initialize OAuth on startup."""
    setup_oauth(settings)

# Add SessionMiddleware for OAuth state management
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET_KEY,
    max_age=600,  # Session expires after 10 minutes (enough time for OAuth flow)
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict[str, str]:
    return {"app": "RAG Admin", "version": "0.1.0"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(oauth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
