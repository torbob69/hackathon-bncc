"""
Seed script: 20 koperasi, 1 admin + 1 manager + 1 farmer per koperasi, 20 financing partners.

Idempotent: skips any entity whose phone number is already registered.
Output   : writes seed_output.txt in the backend/ working directory.

Run from the backend/ directory:
    venv/Scripts/python.exe -m app.scripts.seed_demo
"""
from __future__ import annotations

import asyncio
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import select

from app.core.security import hash_password
from app.db.engine import AsyncSessionLocal, engine
from app.models.enums import FarmerStatus, UserRole
from app.models.koperasi import Koperasi, KoperasiFunds
from app.models.users import Farmer, FinancingPartner, User

load_dotenv()

# ---------------------------------------------------------------------------
# Shared credential
# ---------------------------------------------------------------------------

DEFAULT_PASSWORD = "Koperalink2026!"

# ---------------------------------------------------------------------------
# Koperasi master data (20 entries)
# ---------------------------------------------------------------------------

KOPERASI_DATA = [
    {"name": "Koperasi Tani Melati Jaya",     "type": "KUD",                 "address": "Jl. Raya Pasar Minggu No. 1, Pasar Minggu",     "region": "Jakarta Selatan"},
    {"name": "Koperasi Subur Makmur",          "type": "KSP",                 "address": "Jl. Sudirman No. 45, Tanah Sareal",              "region": "Bogor"},
    {"name": "Koperasi Tani Setia Kawan",      "type": "Koperasi Pertanian",  "address": "Jl. Dipatiukur No. 12, Coblong",                 "region": "Bandung"},
    {"name": "Koperasi Hijau Lestari",         "type": "KUD",                 "address": "Jl. Malioboro No. 7, Gedong Tengen",             "region": "Yogyakarta"},
    {"name": "Koperasi Maju Bersama",          "type": "KSP",                 "address": "Jl. Pemuda No. 88, Gubeng",                      "region": "Surabaya"},
    {"name": "Koperasi Harapan Tani",          "type": "Koperasi Pertanian",  "address": "Jl. Gajahmada No. 22, Semarang Tengah",          "region": "Semarang"},
    {"name": "Koperasi Tunas Muda",            "type": "KUD",                 "address": "Jl. Veteran No. 15, Lowokwaru",                  "region": "Malang"},
    {"name": "Koperasi Sido Maju",             "type": "KSP",                 "address": "Jl. Slamet Riyadi No. 34, Laweyan",              "region": "Solo"},
    {"name": "Koperasi Karya Tani",            "type": "Koperasi Pertanian",  "address": "Jl. Gatot Subroto No. 5, Medan Petisah",         "region": "Medan"},
    {"name": "Koperasi Bumi Pertiwi",          "type": "KUD",                 "address": "Jl. Urip Sumoharjo No. 77, Panakkukang",         "region": "Makassar"},
    {"name": "Koperasi Sumber Rejeki",         "type": "KSP",                 "address": "Jl. Kapten Rivai No. 19, Ilir Timur I",          "region": "Palembang"},
    {"name": "Koperasi Tani Mandiri",          "type": "Koperasi Pertanian",  "address": "Jl. Jend. Sudirman No. 99, Balikpapan Utara",    "region": "Balikpapan"},
    {"name": "Koperasi Jaya Abadi",            "type": "KUD",                 "address": "Jl. Ahmad Yani No. 56, Banjarmasin Tengah",      "region": "Banjarmasin"},
    {"name": "Koperasi Rukun Makmur",          "type": "KSP",                 "address": "Jl. Tanjungpura No. 30, Pontianak Selatan",      "region": "Pontianak"},
    {"name": "Koperasi Berkah Tani",           "type": "Koperasi Pertanian",  "address": "Jl. Sudirman No. 14, Sukajadi",                  "region": "Pekanbaru"},
    {"name": "Koperasi Usaha Bersama",         "type": "KUD",                 "address": "Jl. Sam Ratulangi No. 8, Wenang",                "region": "Manado"},
    {"name": "Koperasi Anugerah Tani",         "type": "KSP",                 "address": "Jl. Gajah Mada No. 23, Denpasar Barat",          "region": "Denpasar"},
    {"name": "Koperasi Mulya Tani",            "type": "Koperasi Pertanian",  "address": "Jl. El Tari No. 11, Kota Lama",                  "region": "Kupang"},
    {"name": "Koperasi Tani Bersatu",          "type": "KUD",                 "address": "Jl. Raya Sentani No. 3, Abepura",                "region": "Jayapura"},
    {"name": "Koperasi Sejahtera Tani",        "type": "KSP",                 "address": "Jl. Pejanggik No. 17, Cakranegara",              "region": "Mataram"},
]

# ---------------------------------------------------------------------------
# Admin data (one per koperasi, idx-matched)
# ---------------------------------------------------------------------------

ADMIN_DATA = [
    {"name": "Budi Santoso",       "email": "admin01@koperalink.id", "phone": "081211100001"},
    {"name": "Dewi Rahayu",        "email": "admin02@koperalink.id", "phone": "081211100002"},
    {"name": "Agus Setiawan",      "email": "admin03@koperalink.id", "phone": "081211100003"},
    {"name": "Sri Wahyuni",        "email": "admin04@koperalink.id", "phone": "081211100004"},
    {"name": "Hendra Kusuma",      "email": "admin05@koperalink.id", "phone": "081211100005"},
    {"name": "Rina Marlina",       "email": "admin06@koperalink.id", "phone": "081211100006"},
    {"name": "Eko Prasetyo",       "email": "admin07@koperalink.id", "phone": "081211100007"},
    {"name": "Yuni Astuti",        "email": "admin08@koperalink.id", "phone": "081211100008"},
    {"name": "Dedi Kurniawan",     "email": "admin09@koperalink.id", "phone": "081211100009"},
    {"name": "Fitri Handayani",    "email": "admin10@koperalink.id", "phone": "081211100010"},
    {"name": "Rudi Hermawan",      "email": "admin11@koperalink.id", "phone": "081211100011"},
    {"name": "Lina Susanti",       "email": "admin12@koperalink.id", "phone": "081211100012"},
    {"name": "Anton Wijaya",       "email": "admin13@koperalink.id", "phone": "081211100013"},
    {"name": "Sari Indah",         "email": "admin14@koperalink.id", "phone": "081211100014"},
    {"name": "Wahyu Nugroho",      "email": "admin15@koperalink.id", "phone": "081211100015"},
    {"name": "Ika Purwanti",       "email": "admin16@koperalink.id", "phone": "081211100016"},
    {"name": "Bambang Sulistyo",   "email": "admin17@koperalink.id", "phone": "081211100017"},
    {"name": "Nita Sari",          "email": "admin18@koperalink.id", "phone": "081211100018"},
    {"name": "Teguh Santoso",      "email": "admin19@koperalink.id", "phone": "081211100019"},
    {"name": "Wulan Permatasari",  "email": "admin20@koperalink.id", "phone": "081211100020"},
]

# ---------------------------------------------------------------------------
# Manager data (one per koperasi, idx-matched)
# ---------------------------------------------------------------------------

MANAGER_DATA = [
    {"name": "Siti Aminah",        "email": "manager01@koperalink.id", "phone": "081211200001"},
    {"name": "Joko Widodo",        "email": "manager02@koperalink.id", "phone": "081211200002"},
    {"name": "Ratna Sari",         "email": "manager03@koperalink.id", "phone": "081211200003"},
    {"name": "Irwan Syah",         "email": "manager04@koperalink.id", "phone": "081211200004"},
    {"name": "Endah Lestari",      "email": "manager05@koperalink.id", "phone": "081211200005"},
    {"name": "Fajar Nugraha",      "email": "manager06@koperalink.id", "phone": "081211200006"},
    {"name": "Mega Putri",         "email": "manager07@koperalink.id", "phone": "081211200007"},
    {"name": "Gunawan Hadi",       "email": "manager08@koperalink.id", "phone": "081211200008"},
    {"name": "Novi Pramita",       "email": "manager09@koperalink.id", "phone": "081211200009"},
    {"name": "Rizky Ramadhan",     "email": "manager10@koperalink.id", "phone": "081211200010"},
    {"name": "Putri Cahyani",      "email": "manager11@koperalink.id", "phone": "081211200011"},
    {"name": "Surya Pratama",      "email": "manager12@koperalink.id", "phone": "081211200012"},
    {"name": "Yanti Oktaviani",    "email": "manager13@koperalink.id", "phone": "081211200013"},
    {"name": "Bagas Wicaksono",    "email": "manager14@koperalink.id", "phone": "081211200014"},
    {"name": "Intan Permata",      "email": "manager15@koperalink.id", "phone": "081211200015"},
    {"name": "Dimas Aditya",       "email": "manager16@koperalink.id", "phone": "081211200016"},
    {"name": "Ayu Wandari",        "email": "manager17@koperalink.id", "phone": "081211200017"},
    {"name": "Reza Firmansyah",    "email": "manager18@koperalink.id", "phone": "081211200018"},
    {"name": "Windi Astuti",       "email": "manager19@koperalink.id", "phone": "081211200019"},
    {"name": "Gilang Ramadhana",   "email": "manager20@koperalink.id", "phone": "081211200020"},
]

# ---------------------------------------------------------------------------
# Farmer data (one per koperasi, idx-matched)
# ---------------------------------------------------------------------------

FARMER_DATA = [
    {"name": "Ahmad Fauzi",        "phone": "081211300001", "nik": "3174021506900001", "address": "Jl. Kebun Anggrek No. 3"},
    {"name": "Suparman",           "phone": "081211300002", "nik": "3201021506900002", "address": "Jl. Raya Cisalak No. 7"},
    {"name": "Nurlaila",           "phone": "081211300003", "nik": "3273021506900003", "address": "Jl. Cibeureum No. 12"},
    {"name": "Jumadi",             "phone": "081211300004", "nik": "3471021506900004", "address": "Jl. Bantul Km 5"},
    {"name": "Marini Wulandari",   "phone": "081211300005", "nik": "3578021506900005", "address": "Jl. Keputran No. 9"},
    {"name": "Sarimin",            "phone": "081211300006", "nik": "3374021506900006", "address": "Jl. Tlogosari No. 4"},
    {"name": "Samsul Hadi",        "phone": "081211300007", "nik": "3573021506900007", "address": "Jl. Sumbersari No. 11"},
    {"name": "Partini",            "phone": "081211300008", "nik": "3372021506900008", "address": "Jl. Mojosongo No. 5"},
    {"name": "Mansur Lubis",       "phone": "081211300009", "nik": "1271021506900009", "address": "Jl. Helvetia No. 2"},
    {"name": "Hasnah Binti",       "phone": "081211300010", "nik": "7371021506900010", "address": "Jl. Antang Raya No. 6"},
    {"name": "Romlah",             "phone": "081211300011", "nik": "1671021506900011", "address": "Jl. Demang Lebar Daun"},
    {"name": "Supardi",            "phone": "081211300012", "nik": "6471021506900012", "address": "Jl. Mulawarman No. 8"},
    {"name": "Juminten",           "phone": "081211300013", "nik": "6371021506900013", "address": "Jl. A. Yani Km 3"},
    {"name": "Samino",             "phone": "081211300014", "nik": "6171021506900014", "address": "Jl. Imam Bonjol No. 15"},
    {"name": "Rohimah",            "phone": "081211300015", "nik": "1471021506900015", "address": "Jl. Nanas No. 7"},
    {"name": "Hendrik Tamaela",    "phone": "081211300016", "nik": "7171021506900016", "address": "Jl. Babe Palar No. 3"},
    {"name": "Ni Wayan Sumarni",   "phone": "081211300017", "nik": "5171021506900017", "address": "Jl. Teuku Umar No. 10"},
    {"name": "Dominikus Lao",      "phone": "081211300018", "nik": "5371021506900018", "address": "Jl. Timor Raya No. 4"},
    {"name": "Lukas Wally",        "phone": "081211300019", "nik": "9471021506900019", "address": "Jl. Percetakan No. 2"},
    {"name": "Suhartini Amir",     "phone": "081211300020", "nik": "5271021506900020", "address": "Jl. Sriwijaya No. 9"},
]

# ---------------------------------------------------------------------------
# Financing partner data (20 entries, cross-tenant)
# ---------------------------------------------------------------------------

FINANCING_PARTNER_DATA = [
    {"name": "BRI Agroniaga Finance",          "email": "partner01@koperalink.id", "phone": "081211400001", "contact_email": "bri.agro@example.id"},
    {"name": "Bank Mandiri UMKM",              "email": "partner02@koperalink.id", "phone": "081211400002", "contact_email": "mandiri.umkm@example.id"},
    {"name": "BNI Tani Sejahtera",             "email": "partner03@koperalink.id", "phone": "081211400003", "contact_email": "bni.tani@example.id"},
    {"name": "PNM Pertanian",                  "email": "partner04@koperalink.id", "phone": "081211400004", "contact_email": "pnm.pertanian@example.id"},
    {"name": "Bank Bukopin Agribisnis",        "email": "partner05@koperalink.id", "phone": "081211400005", "contact_email": "bukopin.agri@example.id"},
    {"name": "Sarana Multi Infrastruktur",     "email": "partner06@koperalink.id", "phone": "081211400006", "contact_email": "smi@example.id"},
    {"name": "LPMUKP Kemenkop",               "email": "partner07@koperalink.id", "phone": "081211400007", "contact_email": "lpmukp@example.id"},
    {"name": "Bank Jateng Agro",               "email": "partner08@koperalink.id", "phone": "081211400008", "contact_email": "jateng.agro@example.id"},
    {"name": "Koperasi Kredit Nusantara",      "email": "partner09@koperalink.id", "phone": "081211400009", "contact_email": "kkn@example.id"},
    {"name": "Fintek Tani Indonesia",          "email": "partner10@koperalink.id", "phone": "081211400010", "contact_email": "fintek.tani@example.id"},
    {"name": "Pegadaian Agraris",              "email": "partner11@koperalink.id", "phone": "081211400011", "contact_email": "pegadaian.agri@example.id"},
    {"name": "BPD Kalimantan Agro",            "email": "partner12@koperalink.id", "phone": "081211400012", "contact_email": "bpd.kalim@example.id"},
    {"name": "Permodalan Nasional Madani",     "email": "partner13@koperalink.id", "phone": "081211400013", "contact_email": "pnm2@example.id"},
    {"name": "Lembaga Keuangan Mikro Tani",   "email": "partner14@koperalink.id", "phone": "081211400014", "contact_email": "lkm.tani@example.id"},
    {"name": "Bank Sulutgo Pertanian",         "email": "partner15@koperalink.id", "phone": "081211400015", "contact_email": "sulutgo@example.id"},
    {"name": "Bali Finance Agribisnis",        "email": "partner16@koperalink.id", "phone": "081211400016", "contact_email": "bali.agri@example.id"},
    {"name": "NTT Development Finance",        "email": "partner17@koperalink.id", "phone": "081211400017", "contact_email": "ntt.dev@example.id"},
    {"name": "Papua Agro Investment",          "email": "partner18@koperalink.id", "phone": "081211400018", "contact_email": "papua.agro@example.id"},
    {"name": "Lombok Financing Partners",      "email": "partner19@koperalink.id", "phone": "081211400019", "contact_email": "lombok.fin@example.id"},
    {"name": "Mitra Usaha Tani Mandiri",      "email": "partner20@koperalink.id", "phone": "081211400020", "contact_email": "mutm@example.id"},
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _phone_exists(session, phone: str) -> bool:
    r = await session.execute(select(User).where(User.phone == phone))
    return r.scalar_one_or_none() is not None


async def _koperasi_exists(session, name: str) -> Koperasi | None:
    r = await session.execute(select(Koperasi).where(Koperasi.name == name))
    return r.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Main seed function
# ---------------------------------------------------------------------------

async def seed() -> None:
    results: list[dict] = []  # collect for TXT output

    async with AsyncSessionLocal() as session:
        async with session.begin():

            # ── 1. Koperasi + Funds + Admin + Manager + Farmer ─────────────────
            for i, kd in enumerate(KOPERASI_DATA):
                ad = ADMIN_DATA[i]
                md = MANAGER_DATA[i]
                fd = FARMER_DATA[i]

                # Koperasi
                kop = await _koperasi_exists(session, kd["name"])
                if kop is None:
                    kop = Koperasi(
                        name=kd["name"], type=kd["type"],
                        address=kd["address"], region=kd["region"],
                    )
                    session.add(kop)
                    await session.flush()

                    session.add(KoperasiFunds(
                        koperasi_id=kop.id,
                        marginal_profit_pool_balance=Decimal("0"),
                        loan_pool_balance=Decimal("0"),
                    ))
                    await session.flush()
                    kop_status = "BARU"
                else:
                    kop_status = "ADA"

                # Admin
                admin_status = "ADA"
                if not await _phone_exists(session, ad["phone"]):
                    session.add(User(
                        koperasi_id=kop.id, role=UserRole.admin,
                        name=ad["name"], email=ad["email"], phone=ad["phone"],
                        password_hash=hash_password(DEFAULT_PASSWORD), status="active",
                    ))
                    admin_status = "BARU"

                # Manager
                mgr_status = "ADA"
                if not await _phone_exists(session, md["phone"]):
                    session.add(User(
                        koperasi_id=kop.id, role=UserRole.manager,
                        name=md["name"], email=md["email"], phone=md["phone"],
                        password_hash=hash_password(DEFAULT_PASSWORD), status="active",
                    ))
                    mgr_status = "BARU"

                # Farmer (User + Farmer row)
                farmer_status = "ADA"
                if not await _phone_exists(session, fd["phone"]):
                    farmer_user = User(
                        koperasi_id=None,  # farmer tenant comes from Farmer.koperasi_id
                        role=UserRole.farmer,
                        name=fd["name"], phone=fd["phone"], email=None,
                        password_hash=hash_password(DEFAULT_PASSWORD), status="active",
                    )
                    session.add(farmer_user)
                    await session.flush()

                    # Check NIK uniqueness before inserting
                    nik_r = await session.execute(
                        select(Farmer).where(Farmer.nik == fd["nik"])
                    )
                    if nik_r.scalar_one_or_none() is None:
                        session.add(Farmer(
                            user_id=farmer_user.id,
                            koperasi_id=kop.id,
                            nik=fd["nik"],
                            address=fd["address"],
                            status=FarmerStatus.active,
                        ))
                    farmer_status = "BARU"

                results.append({
                    "koperasi": {**kd, "id": kop.id, "status": kop_status},
                    "admin": {**ad, "status": admin_status},
                    "manager": {**md, "status": mgr_status},
                    "farmer": {**fd, "status": farmer_status},
                })

            await session.flush()

            # ── 2. Financing Partners ───────────────────────────────────────────
            fp_results = []
            for fp in FINANCING_PARTNER_DATA:
                fp_status = "ADA"
                if not await _phone_exists(session, fp["phone"]):
                    fp_user = User(
                        koperasi_id=None, role=UserRole.financing_partner,
                        name=fp["name"], email=fp["email"], phone=fp["phone"],
                        password_hash=hash_password(DEFAULT_PASSWORD), status="active",
                    )
                    session.add(fp_user)
                    await session.flush()

                    session.add(FinancingPartner(
                        user_id=fp_user.id,
                        name=fp["name"],
                        contact_email=fp["contact_email"],
                    ))
                    fp_status = "BARU"

                fp_results.append({**fp, "status": fp_status})

        # commit happens on context-manager exit

    # ── 3. Write TXT output ────────────────────────────────────────────────────
    out_path = Path(__file__).parent.parent.parent / "seed_output.txt"
    _write_txt(out_path, results, fp_results)
    print(f"\n[seed] Done. Credentials written to: {out_path}")


def _write_txt(path: Path, results: list[dict], fp_results: list[dict]) -> None:
    SEP  = "=" * 68
    LINE = "-" * 68

    lines = [
        SEP,
        "  KOPERALINK — Demo Seed Data",
        f"  Generated for hackathon demo · Password semua akun: {DEFAULT_PASSWORD}",
        SEP,
        "",
        f"  Total koperasi       : {len(results)}",
        f"  Total admin          : {len(results)}",
        f"  Total manajer        : {len(results)}",
        f"  Total petani         : {len(results)}",
        f"  Total mitra pembiayaan: {len(fp_results)}",
        "",
        SEP,
        "  KOPERASI + STAFF + PETANI",
        SEP,
        "",
    ]

    for i, r in enumerate(results, 1):
        k   = r["koperasi"]
        ad  = r["admin"]
        mg  = r["manager"]
        fa  = r["farmer"]

        lines += [
            f"#{i:02d}  {k['name']}",
            LINE,
            f"  Tipe     : {k['type']}",
            f"  Wilayah  : {k['region']}",
            f"  Alamat   : {k['address']}",
            f"  DB ID    : {k['id']}",
            f"  Status   : {k['status']}",
            "",
            "  [ ADMIN ]",
            f"    Nama   : {ad['name']}",
            f"    Email  : {ad['email']}",
            f"    HP     : {ad['phone']}",
            f"    Sandi  : {DEFAULT_PASSWORD}",
            f"    Status : {ad['status']}",
            "",
            "  [ MANAJER ]",
            f"    Nama   : {mg['name']}",
            f"    Email  : {mg['email']}",
            f"    HP     : {mg['phone']}",
            f"    Sandi  : {DEFAULT_PASSWORD}",
            f"    Status : {mg['status']}",
            "",
            "  [ PETANI ]",
            f"    Nama   : {fa['name']}",
            f"    HP     : {fa['phone']}",
            f"    NIK    : {fa['nik']}",
            f"    Alamat : {fa['address']}",
            f"    Sandi  : {DEFAULT_PASSWORD}",
            f"    Status : {fa['status']}",
            "",
        ]

    lines += [
        SEP,
        "  MITRA PEMBIAYAAN (cross-tenant)",
        SEP,
        "",
    ]

    for i, fp in enumerate(fp_results, 1):
        lines += [
            f"#{i:02d}  {fp['name']}",
            LINE,
            f"    Email Login   : {fp['email']}",
            f"    HP            : {fp['phone']}",
            f"    Kontak Email  : {fp['contact_email']}",
            f"    Sandi         : {DEFAULT_PASSWORD}",
            f"    Status        : {fp['status']}",
            "",
        ]

    lines += [
        SEP,
        "  QUICK REFERENCE — Login by Role",
        SEP,
        "",
        "  Platform Admin   : admin@koperalink.id  (seed_platform_admin.py)",
        f"  Admin Koperasi 1 : {results[0]['admin']['email']}  /  {results[0]['admin']['phone']}",
        f"  Manajer Kop. 1  : {results[0]['manager']['email']}  /  {results[0]['manager']['phone']}",
        f"  Petani Kop. 1   : {results[0]['farmer']['phone']}",
        f"  Mitra Pembiayaan: {fp_results[0]['email']}  /  {fp_results[0]['phone']}",
        f"  Sandi semua akun: {DEFAULT_PASSWORD}",
        "",
        SEP,
        "",
    ]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # Also print summary to console
    print(f"\n[seed] Seeded entities:")
    for i, r in enumerate(results, 1):
        k  = r["koperasi"]
        print(f"  [{k['status']:4s}] #{i:02d} {k['name']} (id={k['id']}) "
              f"| admin={r['admin']['status']} mgr={r['manager']['status']} farmer={r['farmer']['status']}")
    print(f"\n[seed] Financing partners:")
    for i, fp in enumerate(fp_results, 1):
        print(f"  [{fp['status']:4s}] #{i:02d} {fp['name']}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def _main() -> None:
    try:
        await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
