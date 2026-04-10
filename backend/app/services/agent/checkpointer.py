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


async def create_checkpointer() -> AsyncPostgresSaver:
    """Create and set up the AsyncPostgresSaver checkpointer."""
    conn_string = get_checkpoint_connection_string()
    checkpointer = AsyncPostgresSaver.from_conn_string(conn_string)
    await checkpointer.setup()
    return checkpointer
