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
