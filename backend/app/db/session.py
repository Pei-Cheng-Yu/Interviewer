from app.db.config import settings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# 1. Create Async Engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # Set True to see SQL logs in console
    pool_pre_ping=True,  # Handles dropped connections automatically
)

# 2. Create Session Factory
# This is what you use to create database sessions in your endpoints
AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)


# 3. Dependency for FastAPI
# Use this in your routes: async def get_db()
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
