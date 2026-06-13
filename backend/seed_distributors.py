import asyncio
import os
from sqlalchemy import select
from app.db.engine import AsyncSessionLocal
from app.models.users import User, Distributor
from app.models.enums import UserRole
from app.core.security import hash_password

async def seed_distributors():
    async with AsyncSessionLocal() as db:
        names = [
            "Agro Indo Nusantara", 
            "Sayur Mayur Jaya", 
            "Pusat Sayur Kota", 
            "Bumi Hijau Distribusi", 
            "Pasar Induk Sejahtera"
        ]
        added = []
        
        for i, name in enumerate(names, 1):
            email = f"distributor{i}@test.com"
            raw_password = "password123"
            phone = f"081300000{i:03d}"
            
            existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if not existing:
                u = User(
                    role=UserRole.distributor,
                    name=name,
                    email=email,
                    phone=phone,
                    password_hash=hash_password(raw_password),
                    status="active"
                )
                db.add(u)
                await db.flush()
                
                d = Distributor(
                    user_id=u.id,
                    company_name=name,
                    address=f"Jl. Distribusi Raya No. {i}, Jakarta"
                )
                db.add(d)
                
                added.append((email, raw_password, name))
                
        if added:
            await db.commit()
            with open("seed_output.txt", "a", encoding="utf-8") as f:
                f.write("\n\n=== ADDITIONAL SEED: 5 DISTRIBUTORS ===\n")
                for email, pw, name in added:
                    f.write(f"Company    : {name}\n")
                    f.write(f"Email      : {email}\n")
                    f.write(f"Password   : {pw}\n")
                    f.write("-" * 35 + "\n")
            print(f"Added {len(added)} distributors and appended to seed_output.txt")
        else:
            print("Distributors already exist.")

if __name__ == "__main__":
    asyncio.run(seed_distributors())
