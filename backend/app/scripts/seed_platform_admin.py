"""Seed a platform_admin user.

platform_admin is the cross-tenant operator role (CLAUDE.md §2.2 #7): it has NO
koperasi_id (operates across all tenants), unlike the koperasi-level `admin` role
which carries a koperasi_id and validates farmer signups / audits loans.

Idempotent: if a user with the target email already exists, the script reports it
and makes no change (it never overwrites an existing password).

Run from the backend/ directory:
    venv/Scripts/python.exe -m app.scripts.seed_platform_admin

Credentials are read from env vars (with dev-friendly defaults):
    PLATFORM_ADMIN_EMAIL     (default: admin@koperalink.id)
    PLATFORM_ADMIN_PASSWORD  (default: a generated value, printed once)
    PLATFORM_ADMIN_NAME      (default: Platform Admin)
"""
import asyncio
import os
import secrets

from sqlalchemy import select

from app.core.security import hash_password
from app.db.engine import AsyncSessionLocal, engine
from app.models.enums import UserRole
from app.models.users import User


async def seed_platform_admin() -> None:
    email = os.getenv("PLATFORM_ADMIN_EMAIL", "admin@koperalink.id").strip().lower()
    name = os.getenv("PLATFORM_ADMIN_NAME", "Platform Admin").strip()
    # If no password is supplied, generate a strong one and print it once.
    password = os.getenv("PLATFORM_ADMIN_PASSWORD")
    generated = False
    if not password:
        password = secrets.token_urlsafe(16)
        generated = True

    async with AsyncSessionLocal() as session:
        existing = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()

        if existing is not None:
            note = ""
            if existing.role != UserRole.platform_admin:
                note = f"  WARNING: existing user role is '{existing.role.value}', not platform_admin"
            print(f"[seed] platform_admin already exists: {email} (id={existing.id}){note}")
            print("[seed] no change made (existing passwords are never overwritten).")
            return

        user = User(
            koperasi_id=None,  # cross-tenant: platform_admin has no tenant
            role=UserRole.platform_admin,
            name=name,
            email=email,
            phone=None,
            password_hash=hash_password(password),
            status="active",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        print(f"[seed] created platform_admin id={user.id}")
        print(f"[seed]   email:    {email}")
        if generated:
            print(f"[seed]   password: {password}   <-- generated; save it now, it is not stored in plaintext")
        else:
            print("[seed]   password: (from PLATFORM_ADMIN_PASSWORD env var)")


async def _main() -> None:
    try:
        await seed_platform_admin()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
