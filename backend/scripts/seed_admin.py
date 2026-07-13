"""
One-off script to create the first admin user.

Usage (from backend/ with the venv or container active):
    python -m scripts.seed_admin admin@company.com yourpassword
"""

import asyncio
import sys

from app.core.security import hash_password
from app.db.database import AsyncSessionLocal, init_models
from app.db.models import Role, User


async def seed(email: str, password: str) -> None:
    await init_models()
    async with AsyncSessionLocal() as session:
        user = User(email=email, hashed_password=hash_password(password), role=Role.ADMIN.value, full_name="Admin")
        session.add(user)
        await session.commit()
        print(f"Created admin user: {email}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python -m scripts.seed_admin <email> <password>")
        sys.exit(1)
    asyncio.run(seed(sys.argv[1], sys.argv[2]))
