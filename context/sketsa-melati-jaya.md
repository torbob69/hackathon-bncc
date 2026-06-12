# MELATI JAYA — Aplikasi Koperasi Tani (Planning Notes)

> Dokumen ini adalah ringkasan terstruktur dari sketsa Excalidraw `1781253715843_sketsa.excalidraw`, yang berisi rancangan alur (flow) aplikasi koperasi tani "MELATI JAYA".

## 1. Tujuan Utama

Sketsa membagi tujuan aplikasi menjadi dua aspek besar:

- **Problem Solving** — menyelesaikan masalah operasional koperasi.
- **Profitting / Business** — menghasilkan pendapatan dari aplikasi.

### 1.1 Problem & Solusi

- **Masalah:** data stok hilang/rusak — kemungkinan karena pencatatan masih menggunakan Excel.
- **Solusi:** mencatat secara digital menggunakan software custom dengan database (DB).

### 1.2 Model Bisnis (Business)

1. Consistent revenue — license selling / copyright (KopDes), atau model B2B.
2. Transaction / commission fees.
3. Loaning services untuk petani.
4. Commerce functionality.
5. Equipment renting.

## 2. Entitas Sistem

Akan ada beberapa entitas pengguna dalam sistem:

1. Koperasi
2. Buyer / Distributor
3. Farmer (Petani)
4. Manajer
5. Admin
6. (kemungkinan ada entitas tambahan lainnya)

Catatan tambahan:
- Setiap koperasi memiliki beberapa anggota (petani).
- Marketplace aplikasi menampilkan semua koperasi yang ada.
- Setiap koperasi memiliki katalog produk sendiri.

## 3. Fitur-Fitur Utama

1. Masukin barang via QR — data dikeluarkan dan dibuat oleh farmer.
2. Manager hanya bertugas scan dan mengecek ulang beban.
3. Fitur auto-chat via WhatsApp jika suhu cold storage tidak sesuai.
4. Fitur logging dan audit barang masuk & keluar.
5. Dana koperasi dapat dilihat oleh semua anggota.

## 4. Additional Features (Wajib)

1. Pengadaan pupuk bersama → perlu dibuatkan sistemnya.
2. Penerimaan hasil panen di gudang — bisa ditrack dan terintegrasi dengan supply chain.
3. Mengajukan pinjaman *(DONE — lihat Skenario Loan)*.
4. Anomaly transaction → audit dan deteksi fraud kasir *(DONE)*.
5. Memeriksa perubahan data pinjaman → melihat riwayat perubahan data, approve atau tidak *(DONE)*.

---

## 5. Skenario: Store Item (Panen Masuk)

Alur ketika petani memanen hasil dan memasukkannya ke cold storage:

1. **Petani** melakukan panen sayuran.
2. Sayuran ditimbang ("timbang beban").
3. Sistem **generate QR code** yang berisi data sayur, nama farmer, dan beratnya.
   - QR ini otomatis tersimpan sebagai log via backend.
4. **Manager** menimbang ulang beban untuk konfirmasi.
5. Manager memasukkan barang ke cold storage, lalu mengirim bukti foto dan melakukan pembayaran ke petani.

## 6. Skenario: Item Out (Kejual)

Alur ketika barang di cold storage keluar karena terjual ke distributor:

1. Sistem mengecek ketersediaan barang ("Sistem mengecek ketersediaan").
2. Cold storage mengeluarkan sayuran sesuai permintaan.
3. Sistem generate QR code dari sayur yang dikeluarkan.
4. Manager melakukan konfirmasi alur data.
5. Barang ditimbang ("timbang beban").
6. Distributor mengambil sayuran; cold storage mengeluarkan sayuran ke distributor.

> Catatan: terdapat versi/draft awal dari alur yang sama (node-node duplikat) di bagian lain sketsa dengan isi konten yang identik.

## 7. Skenario: Pembeli Membeli (Pembelian via Aplikasi)

1. Distributor ingin membeli item melalui aplikasi.
2. Sistem menampilkan semua barang yang ada di koperasi.
3. Distributor memilih barang, input berat, dan membayar (digital payment).
4. Sistem melakukan validasi hasil pesanan.
5. **Decision — Checkout?**
   - **Yes** → lanjut ke langkah 6.
   - **No** → kembali ke langkah 1 (distributor memilih barang lagi).
6. Pembeli memilih antara **pengiriman** atau **pengambilan**:
   - **Pengiriman**
     - **Yes** → mengisi alamat pengiriman → pembeli melakukan transaksi.
     - **No** → aplikasi menyediakan QR untuk pengambilan → pembeli melakukan transaksi.
7. **Decision — Transaksi berhasil?**
   - **Sukses (Ya)** → penyimpanan menandai barang yang menunggu untuk diambil.
   - **Gagal (Tidak)** → transaksi tidak berhasil (proses berhenti).

## 8. Skenario: Pembeli Pick Up

1. Distributor datang ke cold storage.
2. Distributor menyediakan QR pesanan.
3. Manager melakukan scan QR dari distributor, mengecek apakah pesanan asli atau palsu.
4. Manager dan distributor saling memvalidasi beban dan komoditas yang dibeli sudah benar atau belum.
5. Cold storage mengeluarkan sayuran sesuai dengan pesanan.
6. Sayur diberikan kepada distributor.

## 9. Skenario: Signup Farmer

1. Petani mengisi data: nama, NIK, alamat, no. telp, foto KTP/SIM.
2. **Decision — Sistem/admin validasi data secara manual:**
   - **Ya** → set password → tambahkan farmer baru ke database.
   - **Tidak** → signup gagal ("signup failed").

## 10. Skenario: Pinjaman / Loan (Petani)

Alur pengajuan pinjaman oleh petani hingga proses cicilan:

1. Petani membuka menu **Loan**.
2. Sistem menghitung **limit kredit**, berdasarkan:
   - Total kg panen 6 bulan terakhir.
   - Frekuensi transaksi.
   - Tunggakan aktif.
3. Sistem menampilkan limit maksimal pinjaman ke petani.
4. Petani mengajukan jumlah pinjaman beserta tujuan (benih / pupuk / alat).
5. **Decision — Jumlah ≤ limit?**
   - **Tidak** → sistem tolak otomatis, notifikasi "melebihi limit".
   - **Ya** → lanjut ke langkah 6 (cek tunggakan lain / status macet).
6. **Decision — Ada tunggakan lain (status macet)?**
   - **Ya, status macet** → sistem tolak otomatis, notifikasi "melebihi limit".
   - **Tidak / status lancar** → sistem **APPROVE otomatis** dan generate jadwal cicilan.

### 10.1 Setelah Disetujui (Siklus Cicilan)

1. Sistem mengirim notifikasi ke **Manajer**: "cairkan dana ke Petani X".
2. Manajer transfer dana via sistem — tercatat otomatis.
3. Status pinjaman menjadi **Aktif**, tampil di dashboard petani & log publik.
4. Masuk ke **Siklus Cicilan**, yang dievaluasi setiap kali ada transaksi panen petani:
   - **Decision — Petani tidak panen 30 hari berturut-turut?**
     - **Ya** → status berubah menjadi **MENUNGGAK**, notifikasi dikirim ke petani + admin → kembali ke siklus cicilan.
     - Siklus cicilan kemudian dicek lagi:
       - **Decision — Tunggak 60 hari?**
         - Jika berlanjut (termasuk pengecekan ulang "tidak panen 30 hari berturut-turut") → status berubah menjadi **MACET**.
           - Sistem memberi flag, akses pinjaman baru dikunci.
           - **Admin/Pengawas** melakukan review manual, dengan opsi: restrukturisasi cicilan, atau write-off dari Cadangan Operasional.

> Catatan: pada sketsa terdapat kolom paralel (di sisi kanan) dengan elemen-elemen serupa ("Setiap transaksi panen petani", "Petani tidak panen 30 hari berturut-turut?", "Sistem tolak otomatis – notifikasi melebihi limit", "Siklus cicilan") yang merepresentasikan eksplorasi/alternatif alur evaluasi tunggakan, namun belum memiliki garis penghubung (arrow) yang eksplisit ke alur utama di atas.

---

## 11. Catatan Tambahan dari Sketsa

- Terdapat kotak "Business" yang terhubung dari kotak "Profitting" pada bagian atas sketsa, menjelaskan dua kelompok model bisnis (lihat bagian 1.2).
- Beberapa elemen merupakan gambar/ilustrasi (foto petani, sayuran, timbangan, cold storage, dsb.) yang menggambarkan aktor dan objek pada tiap skenario, namun tidak membawa informasi tekstual tambahan di luar yang sudah dirangkum di atas.
