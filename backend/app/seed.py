"""Seed data entry point (`make seed`).

Seeds roles, permissions, the role-permission matrix, and (outside production)
three demo accounts. Running it twice must not create duplicates.
"""

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import Environment, Settings, get_settings
from app.core.database import create_engine
from app.services.seed import SeedResult, seed_all


async def seed(settings: Settings | None = None) -> SeedResult:
    """Apply seed data using the configured database."""
    app_settings = settings or get_settings()
    if app_settings.ENV is Environment.production and app_settings.SEED_DEMO_USERS:
        raise RuntimeError("Refusing to seed demo users in production")

    engine = create_engine(app_settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            result = await seed_all(session, app_settings)
            await session.commit()
    finally:
        await engine.dispose()

    return result


def main() -> None:
    result = asyncio.run(seed())
    print(
        "Seeded "
        f"{result.roles} roles, {result.permissions} permissions, "
        f"{result.role_permission_links} role-permission links, "
        f"{result.demo_users} demo users."
    )


if __name__ == "__main__":
    main()
