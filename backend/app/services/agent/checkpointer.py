"""AsyncPostgresSaver factory for LangGraph checkpointing."""
import re

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.config import settings


def get_checkpoint_connection_string() -> str:
    """Convert async DATABASE_URL to psycopg-compatible connection string.

    LangGraph's AsyncPostgresSaver uses psycopg (not asyncpg),
    so we convert from postgresql+asyncpg:// to postgresql://.
    """
    url = settings.DATABASE_URL
    return re.sub(r"^postgresql\+asyncpg://", "postgresql://", url)


def get_checkpointer_context():
    """Return an async context manager for the checkpointer."""
    conn_string = get_checkpoint_connection_string()
    return AsyncPostgresSaver.from_conn_string(conn_string)
