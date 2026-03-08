import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from contextlib import contextmanager
import logging
from app.config import DATABASE_URL

logger = logging.getLogger(__name__)

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = ThreadedConnectionPool(2, 10, dsn=DATABASE_URL)
    return _pool


def _test_connection(conn):
    """Test if a connection is still valid."""
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
        return True
    except Exception:
        return False


@contextmanager
def get_connection():
    """
    Get a connection from the pool with automatic error handling.
    Tests connection health, rolls back on exception, handles stale connections.
    """
    pool = _get_pool()
    conn = pool.getconn()

    try:
        if not _test_connection(conn):
            logger.warning("Stale connection detected, attempting to reset")
            try:
                conn.close()
            except Exception:
                pass
            pool.putconn(conn, close=True)
            conn = pool.getconn()

        yield conn

    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error(f"Database error: {e}")
        raise

    finally:
        try:
            pool.putconn(conn)
        except Exception as e:
            logger.error(f"Error returning connection to pool: {e}")
