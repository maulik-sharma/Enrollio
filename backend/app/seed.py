"""Seed data entry point.

Role and permission seeding is implemented in milestone M1.1. Until then this
command is a no-op so that `make seed` is usable from the first milestone.
"""

import asyncio


async def seed() -> None:
    """Insert seed data. Currently nothing to seed."""


def main() -> None:
    asyncio.run(seed())
    print("Nothing to seed yet.")


if __name__ == "__main__":
    main()
