# Starter — Tugas Besar Olist Data Platform

Isi starter ini **sengaja sedikit**: stack yang sama dengan Local Big Data Lab, pemeriksa dataset, kerangka `pipeline.py`,
dan tiga template dokumen. Sisanya kamu bangun mengikuti `TUGAS_BESAR.md`.

```
docker-compose.yml   .env.example   jupyter/Dockerfile      # stack (postgres, kafka, kafka-ui, minio, jupyter) — project name "olist"
pipeline.py                                                 # init/up/down sudah jadi; tahap lain = TODO kamu
scripts/check_dataset.py                                    # cek 9 file CSV Kaggle di data/raw
sql/00_schemas.sql                                          # hanya CREATE SCHEMA; tabel kamu yang rancang
tests/conftest.py                                           # fixture koneksi Postgres untuk test (skip kalau stack mati)
docs/DATA_CONTRACT_TEMPLATE.md  RUNBOOK_TEMPLATE.md  EVALUATION_EVIDENCE_TEMPLATE.md
```

Langkah pertama:

```
pip install -r requirements.txt
python pipeline.py init
python pipeline.py up --build        # pertama kali: build image jupyter (±2–3 menit)
# unduh dataset Kaggle → data/raw/
python scripts/check_dataset.py
```

Lalu buka `TUGAS_BESAR.md` → Tahap 0.

## Pertanyaan README — T0: Data Contract & Profiling

**Pertanyaan:** Dari semua temuan, mana yang jika tidak ditangani akan membuat jawaban Q1–Q4 salah secara diam-diam (bukan error)? Sebutkan minimal tiga dan jelaskan mekanisme salahnya.

Terdapat beberapa temuan kualitas data Olist yang dapat menghasilkan angka analisis keliru meskipun query SQL berhasil dijalankan.

### 1. Dua identitas pelanggan berbeda — berdampak pada Q4

Dataset customers mempunyai 99.441 `customer_id`, tetapi hanya 96.096 `customer_unique_id` yang berbeda. Sebanyak 2.997 orang memiliki lebih dari satu `customer_id`.

Jika jumlah pelanggan dihitung berdasarkan `customer_id`, satu orang yang melakukan beberapa transaksi dapat dianggap sebagai beberapa pelanggan berbeda.

**Mekanisme kesalahan:** jumlah pelanggan menjadi terlalu tinggi, tingkat pembelian ulang menjadi terlalu rendah, dan segmentasi RFM tidak mencerminkan perilaku orang yang sama. Query `COUNT(DISTINCT customer_id)` tetap berhasil dijalankan sehingga kesalahan tidak terlihat sebagai error.

**Penanganan:** gunakan `customer_unique_id` sebagai identitas pelanggan pada `dim_customer` (T4), dengan pemetaan dari `customer_id` transaksi.

### 2. Duplikat review per order — berdampak pada Q2 dan Q3

Profiling menemukan 547 order yang mempunyai lebih dari satu review. `review_id` juga mempunyai 814 duplikat key, sedangkan kombinasi `(review_id, order_id)` terbukti unik.

Jika reviews langsung digabungkan ke orders tanpa mengendalikan grain, sebuah order dapat muncul beberapa kali.

**Mekanisme kesalahan:** rata-rata review, jumlah pengiriman, dan hubungan antara keterlambatan dengan kepuasan pelanggan dapat menjadi bias. Seller dengan order yang memiliki beberapa review juga dapat memperoleh bobot yang tidak proporsional. Query tetap berjalan karena join tersebut sah secara SQL.

**Penanganan:** validasi composite key pada Silver (T2) dan tetapkan kebijakan pemilihan satu review representatif per order pada `fact_review` (T4).

### 3. Order tanpa item atau pembayaran — berdampak pada Q1

Terdapat 775 order tanpa record item dan satu order tanpa record pembayaran. Selain itu, terdapat 1.076 order dengan selisih absolut antara total item + ongkir dan total pembayaran lebih dari BRL 0,01, berdasarkan metode rekonsiliasi T0.

Jika orders digabungkan menggunakan `INNER JOIN` ke items atau payments, order tanpa pasangan dapat hilang dari analisis. Jika item dan pembayaran langsung digabungkan pada level baris, kombinasi banyak-item dan banyak-pembayaran juga dapat menggandakan nilai uang.

**Mekanisme kesalahan:** total pendapatan, jumlah order, dan persentase kecocokan pembayaran bisa salah walaupun agregasi `SUM()` dan query join berhasil tanpa error.

**Penanganan:** pertahankan seluruh order, agregasikan item dan pembayaran secara terpisah per `order_id`, lalu lakukan rekonsiliasi pada mart (T5). Klasifikasikan penyebab mismatch, termasuk data item atau pembayaran yang tidak tersedia.

### 4. Tanggal pengiriman tidak konsisten — berdampak pada Q2 dan Q3

Profiling menemukan delapan order berstatus `delivered` tanpa tanggal diterima pelanggan dan 23 order dengan tanggal diterima lebih awal daripada tanggal penyerahan ke kurir.

Jika tanggal kosong otomatis dianggap sebagai pengiriman tepat waktu, atau durasi dari kronologi yang tidak valid tetap dihitung, hasil analisis akan bias.

**Mekanisme kesalahan:** tingkat keterlambatan dapat terlihat lebih rendah, durasi pengiriman menjadi tidak masuk akal, dan seller berpotensi dinilai berdasarkan data kronologi yang keliru.

**Penanganan:** tandai anomali pada Silver (T2), jangan mengubah timestamp secara otomatis, dan gunakan status keterlambatan `NULL` apabila tanggal yang diperlukan tidak tersedia atau tidak layak digunakan (T4–T5).

### 5. ZIP prefix geolocation tidak unik — berdampak pada Q2 dan Q3

Dataset geolocation memiliki 1.000.163 record, tetapi hanya 19.015 ZIP prefix unik. Terdapat 261.831 baris duplikat persis dan 11.687 koordinat di luar batas geografis perkiraan Brasil.

Jika tabel geolocation mentah langsung di-join menggunakan ZIP prefix, satu pelanggan atau seller dapat dipasangkan dengan beberapa observasi geolocation.

**Mekanisme kesalahan:** jumlah order per wilayah dapat berlipat, agregasi performa pengiriman berdasarkan wilayah menjadi bias, dan koordinat tidak wajar dapat mengganggu analisis geografis. Query tetap berjalan karena ZIP prefix yang berulang tidak melanggar sintaks SQL.

**Penanganan:** validasi observasi geolocation pada Silver (T2) dan buat representasi lokasi dengan grain satu baris per ZIP prefix pada `dim_geo` (T4).

### Kesimpulan

Kesalahan yang paling berbahaya dalam analisis bukan selalu error yang menghentikan program, tetapi angka yang terlihat wajar meskipun dihitung menggunakan grain, join, atau definisi bisnis yang salah.

Oleh karena itu, Data Contract T0 menjadi acuan untuk validasi kualitas di T2, penetapan grain dan key di T4, serta rekonsiliasi dan mart analitis di T5.

## Alat bantu

Dalam pengembangan proyek **Olist Data Platform**, saya menggunakan beberapa alat bantu:

| Alat | Penggunaan |
|---|---|
| ChatGPT (OpenAI) | Membantu memahami persyaratan tugas, menjelaskan konsep Data Engineering, menyusun dan merefaktor kode profiling, membantu debugging, serta menyusun dokumentasi dan Data Contract. |
| Visual Studio Code | Editor untuk menulis dan menjalankan kode Python, SQL, serta dokumentasi Markdown. |
| Python dan pandas | Pemeriksaan CSV, profiling, analisis kualitas data, dan pembuatan laporan otomatis. |
| Git | Mengelola versi kode dan menyimpan checkpoint pengembangan. |
| Docker Desktop | Menjalankan infrastruktur lokal PostgreSQL, Kafka, MinIO, dan Jupyter. |

**Batas penggunaan AI:** ChatGPT digunakan sebagai pendamping pembelajaran dan pengembangan. Kode dan perintah yang disarankan dijalankan serta diperiksa menggunakan dataset Olist pada lingkungan lokal. Hasil pengujian yang belum dilaksanakan tidak diklaim sebagai keberhasilan implementasi.

## T1 — Bronze Ingestion

### Mengapa Bronze harus append-only?

Bronze merupakan lapisan penyimpanan data mentah yang berfungsi sebagai sumber historis untuk proses pengolahan berikutnya. Prinsip **append-only** berarti ketika sebuah file sumber berubah, sistem menyimpan file tersebut sebagai versi baru tanpa menimpa atau menghapus versi sebelumnya.

Pendekatan ini penting karena:

1. **Auditabilitas:** perubahan data dapat ditelusuri melalui checksum SHA-256, waktu ingest, dan riwayat versi pada manifest JSON.
2. **Reproduksibilitas:** hasil analisis terdahulu dapat direproduksi menggunakan versi data yang sama.
3. **Pemulihan kesalahan:** apabila file baru ternyata rusak atau mengalami perubahan yang tidak diinginkan, versi sebelumnya masih tersedia.
4. **Idempotensi:** file dengan checksum yang sama tidak perlu diunggah ulang.

### Skenario pada dataset Olist

Misalnya, file `olist_order_payments_dataset.csv` menerima pembaruan, tetapi terjadi kesalahan saat ekspor sehingga beberapa nilai `payment_value` berubah atau hilang.

Jika Bronze menimpa file lama, kita akan kehilangan data pembayaran asli dan sulit mengetahui apakah perbedaan total pembayaran berasal dari transaksi yang sebenarnya atau dari kesalahan proses ekspor.

Dengan penyimpanan append-only, kedua versi tetap tersedia. Kita dapat membandingkan checksum, jumlah baris, dan nilai pembayaran, kemudian menggunakan versi lama untuk memulihkan proses pengolahan Silver serta mereproduksi hasil analisis sebelumnya.

### Bukti implementasi

Bronze ingestion menggunakan MinIO pada bucket `bronze`. Setiap CSV disimpan menggunakan object key berbasis SHA-256, sedangkan `manifest.json` menyimpan metadata dan riwayat versi.

Hasil pengujian:

- Sembilan dataset berhasil diingest.
- Ingestion berulang menghasilkan sembilan status `unchanged`.
- Perubahan satu byte pada salinan `product_category_name_translation.csv` menghasilkan status `new_version`.
- Kedua versi tetap tersedia di MinIO.
- Penunjuk `latest` berhasil dikembalikan ke CSV asli.
- Seluruh sembilan manifest lolos validasi.

Rincian implementasi dan hasil pengujian tersedia dalam `outputs/bronze_report.md`.

## T2 — Silver, Data Quality & PostgreSQL Raw

### Ringkasan implementasi

Pipeline T2 memproses sembilan dataset Olist dari CSV menjadi Silver Parquet, menjalankan validasi kualitas data, lalu memuat hasil yang lolos ke PostgreSQL schema `raw`.

Komponen utama:

- `olist/schema.py` — definisi bersama 9 tabel dan 52 kolom.
- `olist/silver.py` — parsing tipe data dan mekanisme karantina.
- `olist/quality.py` — Hard Rules H01–H10 serta validasi schema.
- `olist/soft_quality.py` — Soft Rules S01–S08.
- `olist/quality_gate.py` — keputusan `PASS`, `PASS+KARANTINA`, atau `FAIL`.
- `olist/silver_pipeline.py` — pipeline Silver, Parquet, dan publikasi lokal.
- `olist/dq_report.py` — generator laporan Data Quality.
- `olist/postgres.py` — DDL dan verifikasi schema PostgreSQL.
- `olist/raw_loader.py` — pemuatan transaksional menggunakan `TRUNCATE + COPY`.

Artefak hasil:

- `outputs/silver/dq_report.md`
- `outputs/load_report.md`
- Bucket MinIO `silver`, prefix `olist/`
- PostgreSQL schema `raw`, berisi sembilan tabel

### Hasil Data Quality pada dataset asli

| Metrik | Hasil |
|---|---:|
| Jumlah dataset | 9 |
| Total source rows | 1.550.922 |
| Total Silver rows | 1.550.922 |
| Total quarantine rows | 0 |
| Overall verdict | PASS |
| Total soft-rule flags | 13.344 |
| Durasi pipeline Silver | 43,25 detik |

Rekonsiliasi:

`1.550.922 source = 1.550.922 Silver + 0 quarantine`

Seluruh sepuluh Hard Rules telah diuji menggunakan data sintetis. Pada dataset asli, tidak ditemukan pelanggaran hard rules maupun schema yang memerlukan karantina.

Soft-rule flags yang dihasilkan:

| Rule | Jumlah |
|---|---:|
| S01 | 8 |
| S02 | 23 |
| S03 | 0 |
| S04 | 11.687 |
| S05 | 547 |
| S06 | 775 |
| S07 | 1 |
| S08 | 303 |

Soft rules hanya menghasilkan flag; record tetap dipertahankan di Silver selama lolos hard rules.

**Catatan S08:** Audit independen menggunakan `Decimal` mengonfirmasi 303 order dengan selisih absolut antara total item beserta ongkir dan total pembayaran yang melebihi BRL 0,01. Profiling awal mencatat 1.076 kasus; perbedaan definisi atau implementasi perhitungan tersebut belum direkonsiliasi dan perlu ditinjau sebelum dianggap sebagai metrik yang identik.

### Ambang karantina: berapa dan mengapa?

Ambang karantina ditetapkan sebesar **1% per tabel**, bukan 1% dari keseluruhan dataset.

Alasannya, setiap tabel memiliki ukuran yang berbeda. Dengan batas per tabel, kerusakan signifikan pada tabel kecil tidak tersembunyi oleh volume data dari tabel besar seperti Geolocation.

Keputusan quality gate:

| Kondisi | Verdict |
|---|---|
| Tidak ada baris dikarantina | PASS |
| Karantina lebih dari 0% sampai 1% | PASS+KARANTINA |
| Karantina lebih dari 1% | FAIL |

**Contoh kasus yang lolos:** Pada data sintetis Payments, terdapat 200 record dan satu record dengan `payment_value` negatif. Sebanyak satu record (0,5%) dikarantina dan 199 record masuk Silver. Pipeline menghasilkan `PASS+KARANTINA` dan boleh memublikasikan batch baru.

**Contoh kasus yang gagal:** Pada data sintetis Payments, terdapat 100 record dan dua record dengan `payment_value` negatif. Sebanyak dua record (2%) dikarantina. Pipeline menghasilkan `FAIL` dan menolak publikasi batch Silver baru.

Kedua kasus sudah diuji melalui `scripts/test_silver_pipeline_gate.py`.

### Publikasi dan pengujian ulang

Pipeline Silver mempersiapkan seluruh Parquet dan laporan dalam staging sebelum publikasi lokal. Publikasi menggunakan pergantian direktori dengan cadangan generasi sebelumnya, sehingga file karantina yang tidak lagi relevan tidak tertinggal ketika pipeline dijalankan ulang.

Perilaku tersebut telah diuji menggunakan `scripts/test_silver_republish.py`.

Sebanyak 11 artefak produksi berhasil diunggah ke bucket MinIO `silver`:

- Sembilan file dataset Parquet.
- Satu file `soft_quality_flags.parquet`.
- Satu file `dq_report.md`.

Upload menggunakan object key tetap dan verifikasi ukuran objek. Proses upload MinIO belum menerapkan publikasi seluruh batch secara atomik.

### PostgreSQL Raw: load dan idempotensi

Kesembilan tabel PostgreSQL dibuat dari definisi bersama `olist/schema.py`. Pemeriksaan struktur mencakup nama dan urutan kolom, tipe data, panjang `VARCHAR`, presisi `NUMERIC`, serta aturan `NOT NULL`.

Loader menggunakan `TRUNCATE + COPY FROM STDIN` dalam satu transaksi PostgreSQL. Jika terjadi kegagalan sebelum commit, seluruh perubahan transaksi dibatalkan.

| Metrik | Load pertama | Load kedua |
|---|---:|---:|
| Tabel dimuat | 9 | 9 |
| Total baris | 1.550.922 | 1.550.922 |
| Durasi | 6,21 detik | 6,59 detik |
| Transaksi | COMMITTED | COMMITTED |

Pengujian menjalankan load kedua membuktikan tidak terjadi penambahan jumlah baris. Pemeriksaan `COUNT(*)` pada kesembilan tabel juga memastikan total aktual PostgreSQL tetap 1.550.922 baris.

Uji kegagalan `COPY` menggunakan nilai yang melebihi kapasitas `NUMERIC(12,2)` berhasil memicu exception PostgreSQL. Perbandingan data sebelum dan sesudah pengujian membuktikan rollback mempertahankan kondisi database.

### Cara menjalankan ulang T2

Jalankan dari root proyek `starter` dengan Python virtual environment aktif dan layanan Docker yang diperlukan berjalan.

```powershell
python -B -m scripts.run_silver
python -B -m scripts.verify_silver_outputs
python -B -m scripts.upload_silver
python -B -m scripts.create_raw_tables
python -B -m scripts.verify_raw_schema
python -B -m scripts.load_raw
python -B -m scripts.verify_raw_counts
```

Pengujian utama:

```powershell
python -B -m scripts.test_quality_gate
python -B -m scripts.test_silver_pipeline
python -B -m scripts.test_silver_pipeline_gate
python -B -m scripts.test_silver_republish
python -B -m scripts.test_dq_report
python -B -m scripts.test_raw_loader
python -B -m scripts.test_raw_loader_transaction
python -B -m scripts.test_raw_loader_failure
```

File CSV di `data/raw/` tidak dimodifikasi oleh pipeline. Data Silver Parquet produksi disimpan secara lokal tetapi diabaikan Git; kode, laporan Markdown, dan pengujian disimpan untuk reproduksibilitas.