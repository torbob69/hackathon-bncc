import asyncio
from app.db.engine import AsyncSessionLocal
from app.models.commodities import Commodity
from app.models.koperasi import Koperasi
from sqlalchemy import select

async def seed():
    async with AsyncSessionLocal() as db:
        kops = (await db.execute(select(Koperasi))).scalars().all()
        if not kops:
            print("No koperasi found. Exiting.")
            return

        added_count = 0
        for kop in kops:
            for name, price in [('Bayam', 15000), ('Kangkung', 12000), ('Wortel', 20000), ('Cabai', 50000)]:
                existing = (await db.execute(
                    select(Commodity).where(Commodity.koperasi_id == kop.id, Commodity.name == name)
                )).scalar_one_or_none()
                
                if not existing:
                    c = Commodity(koperasi_id=kop.id, name=name, pihps_price=price, unit='kg')
                    db.add(c)
                    added_count += 1
        
        if added_count > 0:
            await db.commit()
            print(f"Successfully added {added_count} commodities.")
        else:
            print("Commodities already exist.")

if __name__ == "__main__":
    asyncio.run(seed())
