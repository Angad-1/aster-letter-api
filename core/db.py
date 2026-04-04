import os
import logging
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ---------------- DB FOLDER ----------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_FOLDER = os.path.join(BASE_DIR, "db")
os.makedirs(DB_FOLDER, exist_ok=True)

DB_FILE_NAME = os.getenv("DB_FILE", "alg.db")
DB_FILE = os.path.join(DB_FOLDER, DB_FILE_NAME)

# ✅ ASYNC SQLITE URL
DB_URL = f"sqlite+aiosqlite:///{DB_FILE}"

# ---------------- ENGINE ----------------
engine = create_async_engine(
    DB_URL,
    echo=False,
    future=True
)

SessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ---------------- DEPENDENCY ----------------
async def get_db():
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
