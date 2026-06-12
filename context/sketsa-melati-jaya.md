# MELATI JAYA — Aplikasi Koperasi Tani (MVP Planning Notes)

> Dokumen ini adalah ringkasan terstruktur dari sketsa Excalidraw `1781253715843_sketsa.excalidraw`, dirombak menjadi rencana **MVP** yang fokus pada kelayakan bisnis, profitabilitas, dan kepraktisan implementasi (hackathon scope). NOTES: Sudah diedit sehingga ada beberapa mismatch dengan file excalidraw.

## 0. Prinsip MVP (Baca Dulu)

Tujuan rilis pertama bukan membangun semua revenue stream sekaligus, tetapi **membuktikan loop bisnis yang menghasilkan margin nyata dan bisa dibangun dalam waktu terbatas.**

Tiga aturan scoping:

1. **Marketplace multi-koperasi.** Platform menampung banyak koperasi; distributor bisa membeli dari koperasi manapun yang terdaftar. Inilah inti produk — bukan single-tenant.
2. **Bangun yang punya margin terbukti dulu:** loop dagang komoditas (panen masuk → simpan → jual ke distributor). Menghasilkan uang nyata dan tidak butuh izin khusus.
3. **Fitur berisiko-regulasi (lending) hanya untuk anggota terdaftar**, dengan asumsi konservatif. Lihat Bagian 7 untuk dasar hukumnya.

### Scope Matrix

| Fitur | Status MVP | Alasan |
|---|---|---|
| Pencatatan stok via QR (panen masuk/keluar) | ✅ CORE | Memecahkan masalah utama (Excel), nol friksi adopsi |
| Pembayaran petani dari dana koperasi | ✅ CORE | Otomatisasi operasional |
| Transparansi dana koperasi | ✅ CORE | Trust signal, retention |
| Marketplace multi-koperasi (B2B ke distributor) | ✅ CORE | Sumber margin utama + basis transaction fee |
| Pinjaman anggota + credit scoring | ⚠️ CORE-TERBATAS | Hanya untuk anggota terdaftar, asumsi konservatif |
| Audit & deteksi anomali transaksi | ✅ CORE | Anti-fraud = value proposition di koperasi desa |
| Monetisasi data (anonim) | ⏳ ROADMAP | Revenue masa depan, butuh kemitraan bank |

---

## 1. Tujuan Utama

Aplikasi punya dua aspek:

- **Problem Solving** — menyelesaikan masalah operasional koperasi.
- **Profitting / Business** — menghasilkan pendapatan, baik untuk koperasi maupun untuk platform.

### 1.1 Problem & Solusi

- **Masalah:** data stok hilang/rusak karena pencatatan masih menggunakan Excel; rawan kesalahan dan kecurangan kasir/manajer.
- **Solusi:** pencatatan digital dengan database, harga terkunci ke referensi resmi (PIHPS), dan audit trail yang tidak bisa diubah.

### 1.2 Model Bisnis & Monetisasi (dengan Angka)

Dua lapis pendapatan: **(A) Margin koperasi** (koperasi untung dari dagang) dan **(B) Pendapatan platform** (aplikasi untung dari transaksi). Keduanya harus jelas, karena selama ini hanya (A) yang punya proyeksi.

**A. Margin dagang koperasi (sudah terbukti, ~33-39% gross):**

- Beli dari petani dengan harga acuan PIHPS, jual B2B ke distributor → selisih harga adalah margin koperasi.

**B. Pendapatan platform — Transaction Fee (flat untuk semua):**

- **Setiap koperasi dikenakan transaction fee 1–2% dari nilai transaksi B2B** yang difasilitasi platform. **Tanpa tier** — berlaku sama untuk semua koperasi, besar maupun kecil.
- Model ini menjaga barrier adopsi rendah (gratis dipakai, bayar hanya saat ada transaksi) dan pendapatan platform tumbuh seiring volume.

**C. Pendapatan masa depan (roadmap, bukan MVP):**

- Bunga/biaya layanan pinjaman anggota (lihat Bagian 7).
- *Data licensing* (anonim) — skor kredit berbasis panen sebagai aset data untuk bank UMKM.

> **Catatan modal pemerintah:** Koperasi bisa mengajukan modal/dana dari APBN/pemerintah setempat atau LPDB-KUMKM. Dana ini sebaiknya dipakai untuk **loan pool terpisah**, bukan dicampur dengan modal operasional pembelian komoditas (lihat aturan treasury di Bagian 7).

---

## 2. Entitas Sistem

Entitas pengguna dalam sistem:

1. **Koperasi** — penyimpan dan penjual komoditas; tampil di marketplace.
2. **Buyer / Distributor** — pembeli B2B; bisa membeli dari koperasi manapun.
3. **Farmer (Petani)** — penyetor hasil panen, anggota koperasi.
4. **Manajer** — verifikator pasif (timbang ulang, scan, konfirmasi).
5. **Admin** — validasi pendaftaran, audit pinjaman.

Catatan penting:

- **Petani terikat sebagai anggota terdaftar pada satu koperasi.** Semua kegiatan (jual komoditas, pinjam uang) dilakukan pada koperasi tempat ia terdaftar. Ini adalah dasar hukum yang membuat layanan pinjaman sah sebagai **Koperasi Simpan Pinjam (KSP)** tanpa harus berizin OJK P2P lending.
- **Marketplace menampilkan semua koperasi yang terdaftar.** Distributor melihat katalog lintas-koperasi.
- Setiap koperasi memiliki katalog produk sendiri.

---

## 3. Fitur Inti MVP

1. **Input barang via QR** — data dibuat oleh farmer saat menyetor panen.
2. **Manajer pasif** — hanya scan & timbang ulang untuk konfirmasi, tidak bisa mengubah harga (harga terkunci PIHPS).
3. **Logging & audit barang masuk/keluar** — immutable, untuk anti-fraud.
4. **Transparansi dana koperasi** — saldo & arus kas dapat dilihat semua anggota.
5. **Marketplace multi-koperasi** — distributor membeli dari koperasi manapun; platform memungut transaction fee 1–2%.

### Pertimbangan Adopsi (Realita Petani Desa)

Karena target pengguna adalah petani dengan literasi digital & koneksi terbatas, MVP harus mempertimbangkan:

- **Offline-friendly:** aksi penting (scan QR, catat panen) bisa jalan saat sinyal lemah, sync menyusul.
- **Digital assistant / operator koperasi:** satu orang di koperasi membantu input data petani yang belum terbiasa. Ini kunci adopsi, bukan UX semata.
- **Opsi pembayaran tunai** tetap didukung sebagai sinyal kepercayaan.

---

## 4. Fitur Lanjutan & Status

1. **Penerimaan hasil panen di gudang** — track & terintegrasi supply chain *(PARTIAL di MVP)*.
2. **Mengajukan pinjaman** *(CORE-TERBATAS — lihat Bagian 7)*.
3. **Anomaly transaction → audit & deteksi fraud kasir** *(CORE)*.
4. **Audit perubahan data pinjaman** — riwayat perubahan, approve/tolak *(CORE)*.
5. **Monetisasi data (anonim)** *(ROADMAP)*.

---

## 5. Skenario: Store Item (Panen Masuk)

Alur ketika petani memanen hasil dan memasukkannya ke cold storage:

1. **Petani** melakukan panen sayuran.
2. Sayuran ditimbang ("timbang beban").
3. Sistem **generate QR code** berisi data sayur, nama farmer, dan beratnya.
   - QR tersimpan sementara di device farmer (beberapa jam) lalu terhapus.
4. **Manajer** menimbang ulang untuk konfirmasi kesesuaian beban.
5. Jika sesuai, manajer memasukkan barang ke cold storage, lalu membayar petani menggunakan dana koperasi. Harga ikut acuan PIHPS (terkunci, tidak bisa dinegosiasi manual).

## 6. Skenario: Item Out (Terjual ke Distributor)

Alur ketika barang di cold storage keluar karena terjual:

1. Sistem mengecek ketersediaan barang.
2. Cold storage mengeluarkan sayuran sesuai permintaan.
3. Sistem generate QR code dari sayur yang dikeluarkan.
4. Manajer melakukan konfirmasi alur data.
5. Barang ditimbang ulang.
6. Distributor mengambil sayuran.

> **Pricing B2B:** harga dasar = PIHPS. Untuk menarik distributor besar, sistem boleh menerapkan **diskon volume terstruktur yang terkunci sistem** (mis. 100–500 kg → −3%, > 500 kg → −5%) — tetap transparan & anti-manipulasi, tidak dinego manual. Platform memungut transaction fee 1–2% dari nilai transaksi.

## 7. Skenario: Pembelian via Aplikasi (Marketplace)

1. Distributor ingin membeli item via aplikasi.
2. Sistem menampilkan semua koperasi terdaftar & barang di tiap koperasi.
3. Distributor memilih barang, input berat, bayar digital.
4. Sistem validasi pesanan → checkout.
5. Pilih **pengiriman** (isi alamat, koperasi mengirim) atau **pengambilan** (QR untuk pickup).
6. Jika transaksi sukses → sistem menandai barang terjual & update DB (stok dikurangi saat barang diambil). **Platform memungut transaction fee 1–2% dari nilai transaksi.**

### 7.1 Pembeli Pick Up

1. Distributor datang ke cold storage, menyediakan QR pesanan.
2. Manajer scan QR, cek asli/palsu.
3. Cold storage mengeluarkan sayuran sesuai pesanan.
4. Manajer & distributor saling memvalidasi beban & komoditas.
5. Sayur diberikan ke distributor.

## 8. Skenario: Pinjaman / Loan Anggota (Core-Terbatas)

> **Dasar hukum (PENTING):** Pinjaman HANYA diberikan kepada **anggota terdaftar** koperasi tempat petani bergabung. Dengan demikian operasi ini berjalan sebagai **Koperasi Simpan Pinjam (KSP)** di bawah Kementerian Koperasi, bukan P2P lending OJK. Untuk MVP/demo, ini cukup; untuk skala produksi, daftarkan izin simpan-pinjam KSP secara resmi, atau bermitra dengan BPR/fintech berlisensi sebagai penyalur.

### 8.1 Aturan Treasury (Mitigasi Risiko Modal)

- **Pisahkan loan pool dari modal operasional** pembelian komoditas. Sumber loan pool: alokasi profit koperasi dan/atau dana bergulir (LPDB-KUMKM, APBN).
- **Reserve ratio:** minimal sebagian dana wajib disisihkan sebagai likuiditas operasional, tidak boleh dipinjamkan.
- **Asumsi konservatif:** modelkan *default rate* realistis (mis. 15–20%) dan sediakan provisi kerugian. Lending agrikultur tidak pernah 0% gagal bayar.

### 8.2 Alur Pengajuan

1. Petani membuka menu **Loan**, mengisi: jumlah pinjaman, *installment plan* (lama cicilan), tujuan (benih/pupuk/alat). Menyetujui ToS termasuk ketentuan jaminan.
   - **Jaminan harus legally enforceable** (mis. BPKB via fidusia / agunan yang sah), bukan sekadar checkbox "penyitaan aset" yang tidak punya kekuatan eksekutorial.
2. Sistem menghitung **skor kredit** berdasarkan:
   - Total berat panen 6 bulan terakhir.
   - Frekuensi & riwayat transaksi (uang masuk dari koperasi ke petani).
   - Tunggakan aktif.
3. Sistem menetapkan **limit** per petani berdasarkan tier kredit (dari skor kredit).
4. Petani mengajukan jumlah & tujuan pinjaman.
5. **Decision — Jumlah ≤ (loan pool tersedia × x%)?** Tidak → tolak otomatis.
6. **Decision — Jumlah ≤ limit kredit?** Tidak → tolak otomatis ("melebihi limit").
7. **Decision — Ada tunggakan macet?**
   - Hitung sisa = limit − total pinjaman menunggak.
   - Jika pinjaman > sisa (status macet) → tolak otomatis.
   - Jika pinjaman ≤ sisa → kirim ke audit (status **PENDING**).

### 8.3 Setelah Disetujui (Siklus Cicilan)

1. Sistem mengirim request ke admin untuk audit pinjaman.
2. Jika disetujui, koperasi mentransfer dana (tercatat otomatis dari loan pool).
3. Status **Aktif**, tampil di dashboard petani. Cicilan dibayar per bulan.
4. Jika jatuh tempo lewat & belum lunas → status **PAST DUE**, di-follow up koperasi untuk ditagih.
5. Koperasi dapat meng-*extend* masa cicilan. Jika tidak di-extend & tetap gagal bayar → berlaku prosedur eksekusi jaminan sesuai ketentuan hukum yang sah.

## 9. Skenario: Signup Farmer (Menjadi Anggota)

1. Petani mengisi data: nama, NIK, alamat, no. telp, foto KTP/SIM.
2. **Decision — Admin validasi data secara manual + status keanggotaan koperasi:**
   - **Ya** → set password → tambahkan sebagai anggota terdaftar di database.
   - **Tidak** → signup gagal.

---

## 10. Ringkasan Prioritas Implementasi

| # | Aksi | Dampak | Effort |
|---|---|---|---|
| 1 | Loop dagang komoditas (panen masuk → jual B2B) | Margin utama, problem-solution fit | Inti MVP |
| 2 | Marketplace multi-koperasi + transaction fee 1–2% | Pendapatan platform, basis monetisasi | Sedang |
| 3 | Transparansi dana + audit anti-fraud | Trust & retention | Rendah-Sedang |
| 4 | Pinjaman anggota (KSP, asumsi konservatif) | Revenue masa depan, harus legally sound | Sedang |
