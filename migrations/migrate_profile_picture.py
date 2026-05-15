"""
Migration script to add profile_picture field to User table
"""
import asyncio
from sqlalchemy import text
from app.core.database import engine

async def migrate():
    """Add profile_picture column to user table if it doesn't exist"""
    async with engine.begin() as conn:
        # Check if column exists
        result = await conn.execute(text(
            "SELECT COUNT(*) FROM pragma_table_info('user') WHERE name='profile_picture'"
        ))
        exists = result.scalar()
        
        if not exists:
            print("Adding profile_picture column to user table...")
            await conn.execute(text(
                "ALTER TABLE user ADD COLUMN profile_picture VARCHAR"
            ))
            print("✓ Migration completed successfully")
        else:
            print("✓ profile_picture column already exists")

if __name__ == "__main__":
    asyncio.run(migrate())
