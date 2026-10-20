# Olist Data Platform — Tugas Besar Data Engineering

Platform data lokal untuk sembilan dataset **Brazilian E-Commerce (Olist)**. Pipeline menggabungkan ingestion ber-versi di MinIO, transformasi Parquet dengan quality gate, penyimpanan PostgreSQL, replay Kafka, star schema, enam Gold Mart, dan dashboard Jupyter.

## Ringkasan hasil yang sudah diuji

| Aspek | Bukti hasil |
|---|---|
| Dataset CSV Olist | 9 file, 1.550.922 baris |
| Bronze, Silver, PostgreSQL Raw | 1.550.922 baris; quarantine 0 |
| Soft-quality flags | 13.344 flag (bukan jumlah baris unik) |
| Kafka final-status reconciliation | 99.441 order, 0 hilang, 0 mismatch **setelah recovery** |
| Data warehouse | 9 tabel; 20 pemeriksaan integritas dengan 0 pelanggaran |
| Gold | 6 mart dan 6 ekspor CSV |
| Automated test DW + Gold | 55/55 lulus |
| Failure injection | 5/5 skenario T6 terdeteksi sesuai cakupan test |
| Performa Kafka | Full consumer replay 528,17 detik; target kurang dari 300 detik **belum terpenuhi** |

Angka di atas berasal dari hasil pengujian yang sudah tercatat, bukan janji bahwa clean-room deployment baru pasti menghasilkan output identik tanpa langkah recovery. Lihat [`EVALUATION_EVIDENCE.md`](EVALUATION_EVIDENCE.md) untuk rincian, sumber angka, dan batasan.

## Arsitektur dan komponen

```text
9 CSV Olist (data/raw)
        |
        v
MinIO Bronze (SHA-256 + manifest versi)
        |
        v
Silver Parquet + Quality Gate ------> soft_quality_flags.parquet
        |
        v
PostgreSQL raw.* --------------------> Kafka producer (order lifecycle)
        |                                       |
        v                                       v
PostgreSQL dw.*                          olist.order_events
        |                                       |
        v                                       v
PostgreSQL mart.*                    Consumer + PostgreSQL stream.*
        |                                       |
        +---------- mart.stream_freshness <----+
        |
        v
Gold CSV + Jupyter dashboard
```

Stack Docker Compose: **PostgreSQL 16, Apache Kafka 3.9, MinIO, Kafka UI, dan JupyterLab**. Entry point utama adalah `pipeline.py`; SQL warehouse di `sql/dw_build.sql`, SQL mart di `sql/mart_build.sql`, dan pengujian di `tests/`.

## Persiapan lokal

Gunakan Python 3.11, Docker Desktop + Docker Compose, dan sembilan CSV sumber asli di `data/raw/`. Buat virtual environment dan instal dependensi yang terdaftar di `requirements.txt` terlebih dahulu (langkah setup Python ini **di luar** hitungan 10 perintah pipeline). Atur `.env` mengikuti `.env.example`. Jangan commit `.env` atau kredensial.

## Urutan utama pipeline (10 perintah)

Jalankan dari root repository dengan virtual environment aktif:

```powershell
python pipeline.py init
python pipeline.py up
python pipeline.py check
python pipeline.py profile
python pipeline.py bronze
python pipeline.py silver --upload
python pipeline.py load
python pipeline.py stream --run --limit 99441
python pipeline.py model
python pipeline.py marts
```

**Batas verifikasi:** urutan di atas adalah rancangan jalur utama, bukan klaim clean-run sepenuhnya terbukti dalam 10 perintah. Khususnya, full Kafka replay dapat memerlukan *recovery* untuk event final yang rusak dan stream verification tambahan. Pastikan profil T0 menggunakan entry point yang tersedia; perintah `profile` belum dikonfirmasi ulang melalui pengujian akhir. Lihat [`RUNBOOK.md`](RUNBOOK.md) untuk pemeriksaan dan prosedur recovery. Pada environment yang sudah terisi, jangan mengulang full replay tanpa alasan.

Perintah aman untuk verifikasi kondisi yang sudah dibangun:

```powershell
python pipeline.py stream --verify-only
python pipeline.py test
python pipeline.py status
python pipeline.py report
```

Dashboard: `notebooks/olist_t5_dashboard.ipynb`. Bila ingin menjalankan failure injection secara eksplisit, gunakan `python pipeline.py inject --scenario f01` hingga `f05`; skenario `f04` dan `f05` mensyaratkan `--yes` karena mengganggu broker atau merebuild batch. **Jangan gunakan `docker compose down -v` untuk troubleshooting rutin.**

## Dokumen dan bukti penilaian

| Artefak | Isi |
|---|---|
| [`RUNBOOK.md`](RUNBOOK.md) | Startup, verifikasi, recovery, troubleshooting, reset warning |
| [`EVALUATION_EVIDENCE.md`](EVALUATION_EVIDENCE.md) | Durasi, row counts, Q1–Q4, integrity, keputusan desain, limitations |
| [`outputs/failure_tests.md`](outputs/failure_tests.md) | F01–F05: injeksi, gejala, deteksi, verdict, recovery |
| `outputs/f04_kafka_outage.json` | Bukti mesin broker outage dan recovery |
| `outputs/f05_batch_rerun.json` | Bukti mesin snapshot before/after batch rerun |
| [`outputs/stream_report.md`](outputs/stream_report.md) | Full Kafka replay historis, termasuk keterbatasan throughput |
| [`outputs/dw_report.md`](outputs/dw_report.md) | Grain/foreign key, integrity, data anomalies |
| [`outputs/marts_report.md`](outputs/marts_report.md) | Revenue, lateness, seller, RFM, payment reconciliation |

**Catatan:** File JSON F04/F05 berada di pola ignore `outputs/*.json` sehingga perlu di-*force-add* secara selektif saat Git commit. Hasil F02 dan F03 dicatat dari output terminal historis, bukan dari JSON independen.

---

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
---

## T3 — Kafka Streaming Replay, DLQ, dan Recovery

### Arsitektur streaming

Pipeline streaming mereplay lifecycle order dari PostgreSQL `raw.olist_orders_dataset` ke Apache Kafka.

Komponen utama:

| Komponen | Implementasi |
|---|---|
| Event generator | `olist/events.py` |
| Producer | `scripts/produce_orders.py` |
| Topic utama | `olist.order_events` |
| Kafka key | `order_id` |
| Consumer group | `olist-stream-consumer-v1` |
| Consumer | `scripts/consume_orders.py` |
| Event log | `stream.order_events` |
| Current status | `stream.order_current` |
| Kafka DLQ | `olist.order_events.dlq` |
| PostgreSQL DLQ | `stream.order_dlq` |

Setiap event menggunakan `event_id` deterministik berdasarkan kombinasi `order_id` dan `status`.

Primary key `event_id` pada `stream.order_events` mencegah event valid yang sama disimpan lebih dari sekali.

Consumer memperbarui status terkini berdasarkan `status_rank` sehingga event yang datang terlambat tidak menurunkan status order.

### Fault injection dan hasil full replay

Producer menyimulasikan kondisi streaming yang tidak ideal:

- Duplikat: 3% dari event dasar.
- Delayed event: 2% dari event dasar.
- Corrupt event: 0,5% dari event dasar.

Hasil full replay:

| Metrik | Hasil |
|---|---:|
| Source orders | 99.441 |
| Base lifecycle events | 394.713 |
| Kafka messages acknowledged | 406.554 |
| Kafka messages consumed | 406.554 |
| Duplicate classification | 15.781 |
| Out-of-order classification | 14.558 |
| DLQ messages | 1.974 |
| Producer duration | 50,17 detik |
| Consumer duration termasuk idle | 528,17 detik |
| Freshness p50 | 219.331,61 ms |
| Freshness p95 | 442.934,87 ms |

Jumlah `duplicate` pada consumer mencakup event yang sudah tersimpan dari pengujian sebelumnya, selain duplikat yang sengaja disisipkan pada full replay.

Pada consumer, `new` berarti event yang memperbarui current status. `out_of_order` berarti event valid yang dicatat di event log tetapi tidak mengubah current status.

Keduanya merupakan klasifikasi berbeda dan tidak boleh disamakan dengan total event valid unik.

Metrik freshness diukur dari `produced_at` sampai waktu konsumsi. Backlog consumer menyebabkan sebagian event mempunyai freshness yang tinggi.

Target full replay kurang dari lima menit belum terbukti tercapai. Optimasi consumer dan pengukuran ulang masih diperlukan.

Rincian full replay historis tersedia pada `outputs/stream_report.md`. `outputs/producer_manifest.json` dapat tertimpa oleh replay berikutnya, sehingga bukan bukti tetap untuk full replay awal.

### Penanganan corrupt event

Pesan yang tidak memenuhi kontrak event diarahkan ke:

1. Topic Kafka `olist.order_events.dlq`.
2. Tabel PostgreSQL `stream.order_dlq`.

Tabel DLQ PostgreSQL menggunakan kombinasi source topic, partition, dan offset untuk menghindari penggandaan catatan source message yang sama.

Publikasi ke topic Kafka DLQ belum berada dalam satu transaksi atomik dengan penyimpanan database. Karena itu, pesan DLQ Kafka masih berpotensi terduplikasi jika terjadi crash dan pesan diproses kembali.

Batasan ini diterima sebagai bagian dari desain at-least-once processing, tetapi harus diperhitungkan oleh sistem yang mengonsumsi DLQ.

### Recovery status order

Pada full replay pertama, 99.441 order sudah mempunyai current status, tetapi terdapat 490 status yang belum cocok dengan `raw.order_status`.

Penyebab yang ditemukan adalah hilangnya sebagian event final valid akibat injeksi corrupt yang menggantikan event asal.

Pemulihan dilakukan dengan:

1. Membandingkan `stream.order_current` terhadap status sumber pada PostgreSQL `raw`.
2. Menghasilkan ulang final lifecycle event yang valid.
3. Mengirim event recovery melalui Kafka.
4. Memproses ulang event menggunakan consumer yang sama.
5. Menjalankan verifikasi status seluruh order.

Recovery tahap pertama berhasil memproses 365 event. Setelah producer recovery mengalami timeout, proses dijalankan ulang untuk 125 status tersisa.

Hasil final:

| Pemeriksaan | Hasil |
|---|---:|
| Total orders | 99.441 |
| Orders with current status | 99.441 |
| Missing orders | 0 |
| Status mismatches | 0 |
| Recovery events processed | 490 |
| Final reconciliation | PASS |

Tidak dilakukan `UPDATE` manual pada status PostgreSQL untuk recovery tersebut.

Recovery saat ini bersifat rekonsiliasi berbasis sumber batch `raw`, bukan perbaikan DLQ secara otomatis.

Bukti: `outputs/stream_status_reconciliation.txt`.

### Skenario crash consumer dan offset commit

Consumer menggunakan manual Kafka offset commit.

Urutan pemrosesan normal:

1. Consumer membaca pesan Kafka.
2. Event divalidasi.
3. Event valid disimpan ke PostgreSQL menggunakan `event_id` deterministik.
4. Current order status diperbarui bila status lebih maju.
5. Transaksi PostgreSQL di-commit.
6. Offset Kafka di-commit setelah transaksi database selesai.

Jika proses mati setelah PostgreSQL commit tetapi sebelum Kafka offset commit, Kafka dapat mengirim kembali pesan yang sama setelah consumer restart.

Karena `event_id` merupakan primary key dan operasi penulisan menggunakan penanganan konflik, event tersebut tidak membuat duplikasi log event.

Current status juga tidak boleh mundur ketika menerima event lama.

Dengan demikian, desain database mendukung pemrosesan ulang yang idempoten, meskipun delivery Kafka bersifat at-least-once.

Controlled crash injection F03 kini telah diuji: proses dihentikan dengan exit code 73 sesudah commit PostgreSQL tetapi sebelum commit offset Kafka. Offset tetap pada 136903 setelah crash, lalu maju ke 136904 setelah restart, tanpa penggandaan event. Target event sudah ada di PostgreSQL sebelum injeksi, sehingga test ini belum membuktikan first-time insert sebelum crash. Lihat `outputs/failure_tests.md`.

### Cara menjalankan T3

Prasyarat: PostgreSQL dan Kafka aktif.

Persiapan:

```powershell
python -B -m scripts.create_stream_tables
python -B -m scripts.create_kafka_topics
```

Jalankan consumer dan producer pada dua terminal berbeda.

Terminal 1:

```powershell
python -B -m scripts.consume_orders --idle-seconds 60
```

Terminal 2:

```powershell
python -B -m scripts.produce_orders
```

Setelah consumer selesai:

```powershell
python -B -m scripts.verify_stream_status
```

Apabila terdapat status mismatch, recovery tersedia melalui:

```powershell
python -B -m scripts.replay_missing_final_events --limit 99441
python -B -m scripts.consume_orders --idle-seconds 5
python -B -m scripts.verify_stream_status
```

Catatan: menjalankan producer penuh kembali pada topic dan database yang sama akan menghasilkan pemrosesan ulang. Karena itu, metrik eksperimen harus dipisahkan berdasarkan run.

---

## T4 — Dimensional Data Warehouse

### Arsitektur dan grain

Data Warehouse dibangun dalam schema PostgreSQL `dw` menggunakan SQL yang disimpan pada `sql/dw_build.sql`.

| Tabel | Grain | Jumlah baris |
|---|---|---:|
| `dw.dim_date` | Satu kalender tanggal | 1.827 |
| `dw.dim_customer` | Satu orang unik | 96.096 |
| `dw.dim_product` | Satu produk | 32.951 |
| `dw.dim_seller` | Satu seller | 3.095 |
| `dw.dim_geo` | Satu ZIP prefix valid atau UNKNOWN | 18.677 |
| `dw.fact_order` | Satu order | 99.441 |
| `dw.fact_order_item` | Satu item dalam order | 112.650 |
| `dw.fact_payment` | Satu urutan pembayaran dalam order | 103.886 |
| `dw.fact_review` | Satu review terpilih per order | 98.673 |

Seluruh tabel memiliki primary key yang dipasang pada PostgreSQL.

Foreign key diterapkan pada hubungan fakta dan dimensi, bukan sekadar didokumentasikan.

### Identitas customer dan SCD Type 1

`dim_customer` menggunakan `customer_unique_id` sebagai primary key karena satu orang dapat mempunyai beberapa `customer_id` pada transaksi berbeda.

Atribut lokasi customer dipilih dari transaksi terbaru berdasarkan `order_purchase_timestamp`.

Kebijakan ini merupakan Slowly Changing Dimension Type 1.

Keuntungannya adalah dimensi customer mempunyai satu baris per orang dan tidak menggandakan hasil analisis.

Keterbatasannya adalah riwayat perubahan kota, negara bagian, dan ZIP prefix tidak disimpan sebagai versi historis tersendiri.

### Geolocation dan kategori produk

`dim_geo` dibentuk dengan agregasi geolocation berdasarkan ZIP prefix.

Koordinat di luar batas perkiraan Brasil tidak dimasukkan ke dalam agregasi.

Latitude dan longitude diringkas menggunakan rata-rata. Kota dan negara bagian menggunakan nilai yang paling sering muncul.

Baris `UNKNOWN` disediakan untuk customer atau seller yang ZIP prefix-nya tidak ditemukan dalam geolocation valid.

Pada hasil build, terdapat 1.357 customer dan 14 seller yang menggunakan referensi `UNKNOWN`. Seluruh foreign key tetap valid.

`dim_product` memperbaiki nama kolom sumber `product_name_lenght` menjadi `product_name_length`, serta `product_description_lenght` menjadi `product_description_length`.

Kategori produk diterjemahkan ke bahasa Inggris jika tersedia. Jika tidak tersedia, digunakan kategori asal atau nilai `unknown`.

### Kebijakan deduplikasi fact_review

Dataset Olist mempunyai 547 order dengan lebih dari satu review.

Agar `fact_review` memiliki grain satu baris per order, digunakan aturan deterministik berikut:

1. Pilih review dengan `review_answer_timestamp` terbaru.
2. Jika seri, pilih `review_creation_date` terbaru.
3. Jika masih seri, gunakan `review_id` terbesar sebagai pemutus seri.

Kolom `review_count` menyimpan jumlah review asli untuk setiap order.

Alternatif yang tidak dipilih adalah menggunakan rata-rata semua skor review dalam satu order.

Alternatif tersebut dapat merepresentasikan seluruh penilaian, tetapi menghasilkan skor gabungan yang bukan merupakan skor satu review asli.

Dampak terhadap Q2: rata-rata skor review untuk order terlambat dan tepat waktu dihitung dari satu review representatif per order. Hasilnya dapat berbeda dari metode yang menghitung setiap review mentah atau merata-ratakan seluruh review per order.

Karena itu, kebijakan review harus tetap konsisten antara warehouse, mart, dan dashboard.

### Order tanpa pasangan dan is_late

`fact_order` mempertahankan seluruh 99.441 order, termasuk:

| Kondisi | Jumlah |
|---|---:|
| Order tanpa item | 775 |
| Order tanpa pembayaran | 1 |
| Order dengan minimal satu review | 98.673 |
| Order berstatus delivered | 96.478 |

Kolom `has_no_items` dan `has_no_payment` membedakan order yang tidak mempunyai pasangan data.

Kolom `is_late` menggunakan tiga kemungkinan nilai:

- `TRUE`: tanggal delivered lebih lambat daripada estimasi.
- `FALSE`: tanggal delivered sama atau lebih awal daripada estimasi.
- `NULL`: order belum delivered, atau tanggal yang diperlukan tidak tersedia.

Perbandingan dilakukan pada level tanggal, bukan timestamp penuh, agar delivery pada hari estimasi tidak keliru dikategorikan terlambat.

### Dimensi tanggal

`dim_date` menyediakan atribut tahun, bulan, hari, kuartal, dan hari dalam minggu.

Kolom `is_complete_month` menandai Januari 2017 sampai Agustus 2018 sebagai bulan lengkap untuk kebutuhan analisis.

Bulan lain tetap disimpan dan dapat dikecualikan secara eksplisit oleh query mart.

### Idempotensi full rebuild

Warehouse dibangun menggunakan pendekatan full rebuild dari tabel PostgreSQL `raw`.

Perintah rebuild menjalankan SQL dalam satu transaksi PostgreSQL.

Jika validasi atau proses build gagal sebelum commit, transaksi di-rollback sehingga build parsial tidak dipublikasikan.

Pendekatan ini idempoten selama sumber `raw` tidak berubah.

Konsekuensinya, rebuild schema `dw` dapat memengaruhi objek turunan yang bergantung padanya. Mart downstream harus dibangun ulang setelah rebuild DW jika diperlukan.

### Hasil pengujian T4

| Pengujian | Hasil |
|---|---|
| Build sembilan tabel | PASS |
| Pemeriksaan integritas SQL | 20 pemeriksaan, 0 pelanggaran |
| Pytest database | 26 passed |
| Rebuild kedua | PASS |
| Pytest setelah rebuild | 26 passed |
| Jumlah baris setelah rebuild | Tidak berubah |
| Durasi build pertama | 7,27 detik |
| Durasi rebuild kedua | 9,29 detik |

Pengujian mencakup grain, primary key, foreign key, orphan records, kategori produk, geolocation, review count, dan aturan keterlambatan.

### Cara menjalankan T4

Dari root proyek `starter`:

```powershell
python -B -m scripts.build_dw
python -m pytest tests/test_dw_integrity.py -q
```

Bukti implementasi tersedia pada:

- `sql/dw_build.sql`
- `scripts/build_dw.py`
- `tests/test_dw_integrity.py`
- `outputs/dw_report.md`

---

## Status implementasi dan keterbatasan yang masih terbuka

T0–T5 telah diimplementasikan; fungsi utama CLI `pipeline.py` dan dua generator laporan T6 telah diuji. Kelima skenario failure injection sudah dijalankan dan tercatat di `outputs/failure_tests.md`. Consumer full replay historis **belum** memenuhi target lima menit (528,17 detik), sehingga optimasi dan pengukuran ulang masih menjadi pekerjaan teknis. Bukti fresh-environment run sepuluh perintah dan penyiapan demo akhir juga belum dinyatakan tervalidasi sepenuhnya.


---

## T5 — Gold Marts & Dashboard

### Ringkasan implementasi

Tahap T5 membangun enam tabel analitik pada schema PostgreSQL `mart`, mengekspor hasilnya menjadi CSV Gold, dan menyediakan dashboard Jupyter yang membaca data PostgreSQL.

| Mart | Grain | Jumlah baris |
|---|---|---:|
| `mart.monthly_sales` | Bulan x kategori x state | 11.670 |
| `mart.delivery_performance` | Bulan x state | 565 |
| `mart.seller_scorecard` | Seller | 3.095 |
| `mart.customer_rfm` | Customer unik | 96.096 |
| `mart.stream_freshness` | Menit konsumsi event | 13 |
| `mart.payment_reconciliation` | Order | 99.441 |

SQL mart disimpan di `sql/mart_build.sql`. Query ringkasan untuk laporan dan dashboard didefinisikan bersama di `olist/mart_queries.py`.

### Q1 — Pendapatan produk

Revenue didefinisikan sebagai jumlah `price` dari item pada order berstatus `delivered`. Ongkos kirim dipisahkan dari pendapatan produk. Analisis bulanan menggunakan bulan lengkap Januari 2017 sampai Agustus 2018.

Pada periode tersebut, revenue produk bulanan tertinggi terjadi pada November 2017, sebesar BRL 987.765,37.

Kategori dengan revenue tertinggi adalah `health_beauty`, sebesar BRL 1.229.557,50.

### Q2 — Keterlambatan dan kepuasan pelanggan

Late rate dihitung dengan penyebut hanya order yang `is_late IS NOT NULL`, bukan seluruh order.

Dari 96.203 order yang dapat dievaluasi pada bulan lengkap, sebanyak 6.531 terlambat. Late rate adalah 6,79%.

Rata-rata review order tepat waktu adalah 4,291/5, sedangkan order terlambat 2,271/5. Selisihnya 2,020 poin.

Setiap order memiliki paling banyak satu review representatif sesuai kebijakan deduplikasi T4.

### Q3 — Seller scorecard

Seller scorecard menghitung jumlah order unik, revenue produk delivered, skor review, dan late rate.

Seller dinilai berdasarkan rasio keterlambatan hanya jika memiliki minimal 30 order yang dapat dievaluasi.

Seller dengan revenue delivered tertinggi pada daftar eligible menghasilkan BRL 226.987,93.

Review dan status keterlambatan merupakan atribut pada level order. Jika satu order melibatkan beberapa seller, metrik order tersebut dapat berkontribusi ke masing-masing seller terkait. Oleh karena itu, agregasi lintas seller tidak boleh digunakan sebagai hitungan order global.

### Q4 — Segmentasi pelanggan RFM

RFM menggunakan `customer_unique_id` sebagai identitas pelanggan.

Recency diukur relatif terhadap satu hari setelah tanggal pembelian delivered terakhir pada dataset, bukan terhadap tanggal saat dashboard dibuka.

Frequency menggunakan aturan diskret berdasarkan jumlah pembelian delivered, bukan kuintil mentah, karena banyak pelanggan hanya membeli satu kali.

Segmen terbesar adalah `AT_RISK`, sebanyak 53.810 pelanggan. Label ini adalah hasil aturan segmentasi yang dipilih dan bukan bukti bahwa seluruh pelanggan tersebut telah berhenti berbelanja secara permanen.

### Streaming freshness

Freshness dihitung sebagai selisih `consumed_at - produced_at` dari event valid unik yang tersimpan di `stream.order_events`.

Mart mengagregasikan metrik per menit konsumsi. Pada hasil dashboard, p95 freshness per menit tertinggi mencapai 458,45 detik.

Mart ini tidak mencakup seluruh pesan Kafka yang diproses, seperti duplikat dan pesan invalid dalam DLQ. Schema event saat ini juga tidak menyediakan identitas batch replay secara eksplisit.

### Rekonsiliasi pembayaran

Rekonsiliasi membandingkan nilai item beserta ongkos kirim terhadap total pembayaran per order, dengan toleransi BRL 0,01.

| Kategori | Order | Selisih absolut (BRL) |
|---|---:|---:|
| MATCH | 98.362 | 2,73 |
| NO_ITEMS | 775 | 162.591,95 |
| INSTALLMENT_REVIEW | 266 | 3.172,87 |
| VOUCHER_REVIEW | 7 | 17,48 |
| NO_PAYMENT | 1 | 143,46 |
| UNEXPLAINED | 30 | 78,87 |

Sebanyak 98.362 dari 99.441 order cocok, dengan match rate 98,915%. Angka ini melewati kriteria minimal 98%.

### Pertanyaan README T5 — Selisih uang dan pertanyaan ke finance

**Pertanyaan:** Dari rekonsiliasi, berapa total selisih uang yang tidak bisa kamu jelaskan, dan apa yang akan kamu tanyakan ke tim finance Olist?

Total selisih absolut pada 1.079 order yang tidak cocok adalah **BRL 166.004,63**. Angka ini merupakan jumlah nilai absolut per order, bukan selisih bersih setelah nilai positif dan negatif saling menghapus.

Sebanyak **BRL 78,87**, dari 30 order, berada pada kelas `UNEXPLAINED` karena tidak mempunyai petunjuk penyebab dari klasifikasi yang tersedia.

Namun, BRL 166.004,63 tetap merupakan nilai mismatch yang belum direkonsiliasi secara akuntansi. Label `NO_ITEMS`, `VOUCHER_REVIEW`, dan `INSTALLMENT_REVIEW` bukan bukti bahwa selisih tersebut sudah terselesaikan.

Pertanyaan yang akan diajukan kepada tim finance Olist:

1. Apa perlakuan keuangan untuk pembayaran order yang tidak memiliki baris item, khususnya 775 order pada kelas `NO_ITEMS`?
2. Apakah dataset mempunyai diskon, refund, pembatalan, adjustment, atau komponen transaksi lain yang tidak tersedia dalam tabel item dan pembayaran?
3. Bagaimana nilai voucher dialokasikan ke total pembayaran dan nilai order?
4. Apakah `payment_value` untuk transaksi cicilan merepresentasikan nilai pembayaran penuh atau bagian dari jadwal pembayaran?
5. Dapatkah tim finance menyediakan ledger atau referensi settlement per `order_id` untuk memastikan penyebab selisih?

Sebelum ada konfirmasi tersebut, mismatch tidak boleh diam-diam dianggap sebagai revenue atau dihapus dari laporan.

### Dashboard dan pengujian

Dashboard berada pada `notebooks/olist_t5_dashboard.ipynb`. Visual mencakup Q1, Q2, Q3, Q4, dan freshness stream, serta ringkasan rekonsiliasi.

Dashboard membaca PostgreSQL dan menggunakan query bersama dengan laporan `outputs/marts_report.md`.

Perintah build dan pengujian:

```powershell
python -B -m scripts.build_marts
python -m pytest tests/test_dw_integrity.py tests/test_marts.py -q
```

Hasil verifikasi:

- Enam Gold Marts berhasil dibangun.
- Enam CSV berhasil diekspor ke `outputs/gold/`.
- Semua validasi business rules lulus.
- 29 tes T5 lulus.
- Gabungan T4 dan T5: 55 tes lulus.
- Rebuild kedua mempertahankan jumlah baris dan hasil pengujian.
- Dashboard berhasil dieksekusi dengan lima grafik.

T5 telah lulus pengujian DW/Gold. T6 failure injection telah dijalankan dan dibuktikan dalam `outputs/failure_tests.md`, sementara target performa full Kafka replay tetap terbuka.

---

## T6 — Failure Injection, Reproducibility, dan Evaluasi

Lima skenario telah diuji pada lingkungan yang sudah berisi data proyek:

| ID | Gangguan | Gejala/deteksi yang diamati | Pemulihan dan hasil |
|---|---|---|---|
| F01 | CSV orders kehilangan kolom wajib `order_id` (file sementara) | `ValueError`, validator menyebut `missing=['order_id']` | Header sumber asli tidak berubah; **TERTANGKAP** |
| F02 | Producer dua kali untuk 20 order dan seed 42 | 164 pesan diproses sebagai duplikat; 0 duplikat `event_id` | DB tetap 393.251 event unik dan 99.441 current order; **TERTANGKAP** |
| F03 | Consumer crash sesudah DB commit, sebelum offset Kafka commit | Exit code 73; offset tertahan 136903 | Restart membaca ulang event, commit 136904, tanpa duplikat; **TERTANGKAP** |
| F04 | Single Kafka broker dihentikan saat replay | `KafkaConnectionError: socket disconnected` | Broker restart, producer retry lewat replay ulang, status 99.441 cocok; **TERTANGKAP** |
| F05 | Bronze → Silver → Raw → DW → Gold dijalankan ulang | Fingerprint source/Bronze/Silver/DB sebelum dan sesudah tetap sama | 1.550.922 Silver rows, 55 tes lulus; **TERTANGKAP** |

**Cakupan:** F03 menggunakan event yang sebelumnya sudah ada di database; F05 tidak membandingkan isi `soft_quality_flags.parquet` dan beberapa kolom audit yang volatile; F02/F03 bersumber dari hasil terminal historis. Kafka single-broker tidak menjamin high availability, dan publikasi DLQ Kafka tidak atomik bersama commit PostgreSQL.

Perintah untuk membuat ulang laporan (tanpa mengulangi outage/rebuild):

```powershell
python pipeline.py report
```

Perintah tersebut menjalankan `scripts.generate_failure_report` lalu `scripts.generate_evaluation_evidence`. Bukti lebih lengkap tersedia di `outputs/failure_tests.md` dan `EVALUATION_EVIDENCE.md`.

### Keputusan desain dan eksperimen lanjutan

Keputusan penting meliputi Bronze content-addressed append-only, Silver quality gate per tabel, Raw transaksional `TRUNCATE + COPY`, Kafka *at-least-once* dengan `event_id` deterministik, `dim_customer` SCD Type 1, dan Gold Marts berbasis SQL yang tervalidasi. Perbandingan alternatif serta alasannya tercantum di `EVALUATION_EVIDENCE.md`.

Prioritas eksperimen: benchmark consumer full replay di bawah 300 detik, crash setelah *first insert* baru, perluasan snapshot F05 ke soft flags, serta investigasi selisih pembayaran bersama sumber ledger.
