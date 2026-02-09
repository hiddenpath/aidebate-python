"""SQLite storage for debate history."""

import aiosqlite
import logging

from .types import DebatePhase, Position

logger = logging.getLogger("aidebate")

DB_PATH = "debate.db"


async def init_db(db_path: str | None = None) -> str:
    """Initialize the database and create tables if needed."""
    path = db_path or DB_PATH
    async with aiosqlite.connect(path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS debate_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                phase TEXT NOT NULL,
                provider TEXT,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
    logger.info("Database initialized: %s", path)
    return path


async def save_message(
    db_path: str,
    user_id: str,
    session_id: str,
    role: Position,
    phase: DebatePhase,
    provider: str | None,
    content: str,
) -> None:
    """Save a debate message to the database."""
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "INSERT INTO debate_messages (user_id, session_id, role, phase, provider, content) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, session_id, role.value, phase.value, provider, content),
            )
            await db.commit()
    except Exception as e:
        logger.error("Failed to save message: %s", e)


async def fetch_history(
    db_path: str,
    user_id: str,
    session_id: str,
) -> list[dict]:
    """Fetch debate history for a given user and session."""
    try:
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT role, phase, provider, content FROM debate_messages "
                "WHERE user_id = ? AND session_id = ? "
                "ORDER BY id DESC LIMIT 50",
                (user_id, session_id),
            )
            rows = await cursor.fetchall()
            result = [
                {
                    "role": row["role"],
                    "phase": row["phase"],
                    "provider": row["provider"],
                    "content": row["content"],
                }
                for row in reversed(rows)
            ]
            return result
    except Exception as e:
        logger.error("Failed to fetch history: %s", e)
        return []
