# MELATI JAYA — Aplikasi Koperasi Tani (Planning Notes)

> Dokumen ini adalah ringkasan terstruktur dari sketsa Excalidraw `1781253715843_sketsa.excalidraw`, yang berisi rancangan alur (flow) aplikasi koperasi tani "MELATI JAYA". NOTES: Sudah diedit sehingga ada beberapa mismatch dengan file excalidraw

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
- Petani tidak terikat kontrak dengan suatu koperasi, sehingga bisa bebas berinteraksi dengan koperasi manapun.
- Marketplace aplikasi menampilkan semua koperasi yang ada.
- Setiap koperasi memiliki katalog produk sendiri.
- Koperasi bisa meminta modal atau dana dari APBN/pemerintah setempat.

## 3. Fitur-Fitur Utama

1. Masukin barang via QR — data dikeluarkan dan dibuat oleh farmer.
2. Manager hanya bertugas scan dan mengecek ulang beban.
3. Fitur logging dan audit barang masuk & keluar.
4. Dana koperasi dapat dilihat oleh semua anggota.

## 4. Additional Features (Wajib)

1. Pengadaan pupuk bersama → perlu dibuatkan sistemnya. (WE DONT IMPLEMENT THIS)
2. Penerimaan hasil panen di gudang — bisa ditrack dan terintegrasi dengan supply chain. (PARTIALLY Implemented in plan)
3. Mengajukan pinjaman *(DONE — lihat Skenario Loan)*.
4. Anomaly transaction → audit dan deteksi fraud kasir *(DONE)*.
5. Memeriksa perubahan data pinjaman → melihat riwayat perubahan data, approve atau tidak *(DONE)*.

---

## 5. Skenario: Store Item (Panen Masuk)

Alur ketika petani memanen hasil dan memasukkannya ke cold storage:

1. **Petani** melakukan panen sayuran.
2. Sayuran ditimbang ("timbang beban").
3. Sistem **generate QR code** yang berisi data sayur, nama farmer, dan beratnya.
   - QR ini otomatis tersimpan sementara di device farmer dengan estimasi selama beberapa jam dan akan terhapus.
4. **Manager** menimbang ulang beban untuk konfirmasi apakah bebannya sesuai tidak.
5. Jika iya, manager memasukkan barang ke cold storage, lalu melakukan pembayaran ke petani menggunakan dana koperasi yang ada.

## 6. Skenario: Item Out (Kejual)

Alur ketika barang di cold storage keluar karena terjual ke distributor:

1. Sistem mengecek ketersediaan barang ("Sistem mengecek ketersediaan").
2. Cold storage mengeluarkan sayuran sesuai permintaan.
3. Sistem generate QR code dari sayur yang dikeluarkan.
4. Manager melakukan konfirmasi alur data.
5. Barang ditimbang ("timbang beban").
6. Distributor mengambil sayuran; cold storage mengeluarkan sayuran ke distributor.

## 7. Skenario: Pembeli Membeli (Pembelian via Aplikasi)

1. Distributor ingin membeli item melalui aplikasi.
2. Sistem menampilkan semua available koperasi dan barang yang ada di setiap koperasi.
3. Distributor memilih barang, input berat, dan membayar (digital payment).
4. Sistem melakukan validasi hasil pesanan.
5. **Decision — Checkout?**
   - **Yes** → lanjut ke langkah 6.
   - **No** → kembali ke langkah 1 (distributor memilih barang lagi).
6. Pembeli memilih antara **pengiriman** atau **pengambilan**:
   - **Pengiriman**
     - **Yes** → mengisi alamat pengiriman dan membayar langsung, koperasi hanya bertugas untuk mengirim saja → pembeli melakukan transaksi.
     - **No** → aplikasi menyediakan QR setelah pembayaran untuk pengambilan barang → pembeli melakukan transaksi.
7. **Decision — Transaksi berhasil?**
   - **Sukses (Ya)** → sistem menandai barang yang menunggu untuk diambil, dan update database untuk menandai barang yang sudah terjual tetapi stock belum dikurangi, kecuali saat sudah diambil.
   - **Gagal (Tidak)** → transaksi tidak berhasil (proses berhenti).

## 8. Skenario: Pembeli Pick Up

1. Distributor datang ke cold storage.
2. Distributor menyediakan QR pesanan.
3. Manager melakukan scan QR dari distributor, mengecek apakah pesanan asli atau palsu.
4. Cold storage mengeluarkan sayuran sesuai dengan pesanan.
5. Manager dan distributor saling memvalidasi beban dan komoditas yang dibeli sudah benar atau belum.
6. Sayur diberikan kepada distributor.

## 9. Skenario: Signup Farmer

1. Petani mengisi data: nama, NIK, alamat, no. telp, foto KTP/SIM.
2. **Decision — Sistem/admin validasi data secara manual:**
   - **Ya** → set password → tambahkan farmer baru ke database.
   - **Tidak** → signup gagal ("signup failed").

## 10. Skenario: Pinjaman / Loan (Petani)

Alur pengajuan pinjaman oleh petani hingga proses cicilan:

1. Petani membuka menu **Loan**. Dan dia akan mengisi beberapa input seperti jumlah uang yang mau dipinjam, instalment plan (masa cicilannya berapa lama), dan tujuan peminjaman uangnya. Disini petani harus menyetujui ToS dan ketentuan peminjaman, termasuk penyitaan aset.
2. Sistem menghitung **skor kredit**, berdasarkan:
   - Total berat panen 6 bulan terakhir.
   - Frekuensi dan riwayat transaksi, berapa uang masuk dari koperasi ke petani dari hasil penjualan komoditas.
   - Tunggakan aktif.
3. Sistem menerapkan limit maximal untuk setiap petani berdasarkan pengelompokkan tier (tier ditentukan dari skor kredit).
4. Petani mengajukan jumlah pinjaman beserta tujuan (benih / pupuk / alat).
5. **Decision - Jumlah Pinjaman <= Dana koperasi * x%?**
   - Ya --> lanjut ke langkah 6
   - Tidak --> Tolak otomatis
6. **Decision — Jumlah ≤ limit?**
   - **Tidak** → sistem tolak otomatis, notifikasi "melebihi limit".
   - **Ya** → lanjut ke langkah 7 (cek tunggakan lain / status macet).
7. **Decision — Ada tunggakan lain (status macet)?**
   Hitung dulu sisa = limit - current total pinjaman yang masih menunggak
   - **Jika pinjaman > sisa , status macet** → sistem tolak otomatis, notifikasi "melebihi limit".
   - **JIka pinjaman < sisa** →  Kirim request pinjaman untuk di audit (status : PENDING)

### 10.1 Setelah Disetujui (Siklus Cicilan)

1. Sistem akan mengirim request ke admin untuk mengaudit permintaan pinjaman dari petani.
2. Jika disetujui, sistem koperasi akan  mentransfer dana — tercatat otomatis.
3. Status pinjaman menjadi **Aktif**, tampil di dashboard petani. Pinjaman ini bersifat instalment, jadi harus dibayar cicilannya per bulan
4. Jika masa cicilan sudah lewat, DAN belum lunas semua, sistem akan update status : PAST DUE, dan akan difollow up kopdes, untuk ditagih.
5. Sesuai dengan keinginan kopdes, bisa di extend masa cicilannya tergantung kopdes. Kalo kopdes/manager tidak memutuskan untuk extend, maka berlaku prosedur penyitaan aset. 