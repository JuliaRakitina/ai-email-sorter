from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import event, text
from .settings import settings

# Configure SQLite with WAL mode for better concurrency
# This allows multiple readers and a single writer without blocking
engine = create_engine(
    "sqlite:///./app.db",
    echo=False,
    connect_args={
        "check_same_thread": False,
        "timeout": 20.0,  # Wait up to 20 seconds for lock to be released
    },
    pool_pre_ping=True,  # Verify connections before using
)

@event.listens_for(engine, "connect")
def set_sqlite_pragmas(dbapi_conn, connection_record):
    """Set SQLite PRAGMAs on each new connection for better concurrency."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=20000")  # 20 second timeout
    cursor.close()

def init_db():
    SQLModel.metadata.create_all(engine)
    # WAL mode will be set automatically via the event listener on first connection

def get_session():
    with Session(engine) as session:
        yield session
