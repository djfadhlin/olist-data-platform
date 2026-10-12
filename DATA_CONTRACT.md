# Olist Data Platform — Data Contract

## 1. Tujuan

Dokumen ini menetapkan struktur sumber data, grain, kandidat natural key, tipe data target, aturan kualitas, dan kebijakan penanganan anomali untuk Olist Data Platform.

Data Contract digunakan sebagai acuan implementasi Bronze, Silver, dan Data Warehouse.

## 2. Sumber Data

Sumber data terdiri dari sembilan file CSV Olist yang disimpan pada `data/raw/`.

Data asli dipertahankan pada Bronze untuk kebutuhan audit, reproduksibilitas, dan pemrosesan ulang.

### 2.1 Jumlah Baris yang Diharapkan

Jumlah baris berikut berasal dari pemeriksaan sembilan CSV menggunakan `python pipeline.py check` pada tahap T0.

| Dataset | Expected rows |
|---|---:|
| `olist_customers_dataset.csv` | 99.441 |
| `olist_geolocation_dataset.csv` | 1.000.163 |
| `olist_order_items_dataset.csv` | 112.650 |
| `olist_order_payments_dataset.csv` | 103.886 |
| `olist_order_reviews_dataset.csv` | 99.224 |
| `olist_orders_dataset.csv` | 99.441 |
| `olist_products_dataset.csv` | 32.951 |
| `olist_sellers_dataset.csv` | 3.095 |
| `product_category_name_translation.csv` | 71 |

Jumlah baris merupakan baseline dataset sumber yang digunakan dalam proyek ini. Perubahan jumlah baris harus diperiksa dan didokumentasikan sebelum data diproses pada tahap berikutnya.

Validasi jumlah baris dan checksum dilakukan menggunakan `python pipeline.py check`, dengan evidence pada `outputs/dataset_check.md`.


## 3. Grain dan Natural Key

| Dataset | Grain sumber | Natural key / kebijakan identifikasi |
|---|---|---|
| `olist_orders_dataset` | Satu order | `order_id` |
| `olist_order_items_dataset` | Satu item pada order | `(order_id, order_item_id)` |
| `olist_order_payments_dataset` | Satu urutan pembayaran pada order | `(order_id, payment_sequential)` |
| `olist_order_reviews_dataset` | Satu pasangan review dan order | `(review_id, order_id)` |
| `olist_customers_dataset` | Satu customer ID | `customer_id` |
| `olist_sellers_dataset` | Satu seller | `seller_id` |
| `olist_products_dataset` | Satu produk | `product_id` |
| `olist_geolocation_dataset` | Satu observasi geolokasi | ZIP prefix bukan key unik; gunakan kebijakan deduplikasi dan agregasi pada lapisan berikutnya |
| `product_category_name_translation` | Satu kategori produk | `product_category_name` |

**Catatan:**

- `customer_unique_id` mengidentifikasi orang yang sama di berbagai `customer_id`.
- `review_id` saja tidak unik. Kombinasi `(review_id, order_id)` terbukti unik pada dataset yang diperiksa.
- `geolocation_zip_code_prefix` tidak unik dan tidak boleh langsung dijadikan primary key pada data mentah.
- Natural key sumber tidak selalu sama dengan grain tabel Data Warehouse.

## 4. Target Data Types

Definisi tipe berikut merupakan target parsing pada Silver dan acuan untuk tabel PostgreSQL. Bronze tetap menyimpan isi CSV asli tanpa mengubah tipe data.

Keterangan nullable:
- **Tidak**: tidak ditemukan nilai null pada profiling sumber; diusulkan wajib terisi pada Silver.
- **Ya**: ditemukan nilai null atau kolom bersifat opsional menurut interpretasi bisnis.

### 4.1 Customers — `olist_customers_dataset`

**Grain:** satu baris per `customer_id`.

| Kolom | Target PostgreSQL | Nullable |
|---|---|---|
| `customer_id` | `VARCHAR(32)` | Tidak |
| `customer_unique_id` | `VARCHAR(32)` | Tidak |
| `customer_zip_code_prefix` | `VARCHAR(5)` | Tidak |
| `customer_city` | `TEXT` | Tidak |
| `customer_state` | `VARCHAR(2)` | Tidak |

`customer_id` merupakan natural key sumber. `customer_unique_id` digunakan untuk mengidentifikasi pelanggan yang sama di beberapa order.

### 4.2 Geolocation — `olist_geolocation_dataset`

**Grain:** satu observasi lokasi geografis.

| Kolom | Target PostgreSQL | Nullable |
|---|---|---|
| `geolocation_zip_code_prefix` | `VARCHAR(5)` | Tidak |
| `geolocation_lat` | `DOUBLE PRECISION` | Tidak |
| `geolocation_lng` | `DOUBLE PRECISION` | Tidak |
| `geolocation_city` | `TEXT` | Tidak |
| `geolocation_state` | `VARCHAR(2)` | Tidak |

`geolocation_zip_code_prefix` tidak unik sehingga tidak dijadikan primary key pada data observasi. Untuk `dim_geo`, diperlukan pemilihan atau agregasi observasi valid per ZIP prefix.

### 4.3 Order Items — `olist_order_items_dataset`

**Grain:** satu item dalam satu order.

| Kolom | Target PostgreSQL | Nullable |
|---|---|---|
| `order_id` | `VARCHAR(32)` | Tidak |
| `order_item_id` | `INTEGER` | Tidak |
| `product_id` | `VARCHAR(32)` | Tidak |
| `seller_id` | `VARCHAR(32)` | Tidak |
| `shipping_limit_date` | `TIMESTAMP` | Tidak |
| `price` | `NUMERIC(12,2)` | Tidak |
| `freight_value` | `NUMERIC(12,2)` | Tidak |

Natural key: `(order_id, order_item_id)`.

### 4.4 Payments — `olist_order_payments_dataset`

**Grain:** satu pembayaran berurutan untuk suatu order.

| Kolom | Target PostgreSQL | Nullable |
|---|---|---|
| `order_id` | `VARCHAR(32)` | Tidak |
| `payment_sequential` | `INTEGER` | Tidak |
| `payment_type` | `TEXT` | Tidak |
| `payment_installments` | `INTEGER` | Tidak |
| `payment_value` | `NUMERIC(12,2)` | Tidak |

Natural key: `(order_id, payment_sequential)`. Satu order dapat mempunyai beberapa pembayaran.

### 4.5 Reviews — `olist_order_reviews_dataset`

**Grain:** satu pasangan review dan order.

| Kolom | Target PostgreSQL | Nullable |
|---|---|---|
| `review_id` | `VARCHAR(32)` | Tidak |
| `order_id` | `VARCHAR(32)` | Tidak |
| `review_score` | `INTEGER` | Tidak |
| `review_comment_title` | `TEXT` | Ya |
| `review_comment_message` | `TEXT` | Ya |
| `review_creation_date` | `TIMESTAMP` | Tidak |
| `review_answer_timestamp` | `TIMESTAMP` | Tidak |

Natural key sumber: `(review_id, order_id)`.

Pada profiling, `review_id` memiliki 814 duplikat key, sedangkan kombinasi `(review_id, order_id)` memiliki 0 duplikat.

Kolom komentar bersifat opsional. Nilai null pada judul atau isi komentar tidak otomatis menyebabkan review dikarantina.

### 4.6 Orders — `olist_orders_dataset`

**Grain:** satu baris per order.

| Kolom | Target PostgreSQL | Nullable |
|---|---|---|
| `order_id` | `VARCHAR(32)` | Tidak |
| `customer_id` | `VARCHAR(32)` | Tidak |
| `order_status` | `TEXT` | Tidak |
| `order_purchase_timestamp` | `TIMESTAMP` | Tidak |
| `order_approved_at` | `TIMESTAMP` | Ya |
| `order_delivered_carrier_date` | `TIMESTAMP` | Ya |
| `order_delivered_customer_date` | `TIMESTAMP` | Ya |
| `order_estimated_delivery_date` | `TIMESTAMP` | Tidak |

Natural key: `order_id`.

Tanggal pengiriman dapat kosong untuk status tertentu. Validitasnya diperiksa bersama `order_status` dan urutan kronologi pengiriman, bukan hanya berdasarkan ada atau tidaknya nilai null.

### 4.7 Products — `olist_products_dataset`

**Grain:** satu baris per produk.

| Kolom | Target PostgreSQL | Nullable |
|---|---|---|
| `product_id` | `VARCHAR(32)` | Tidak |
| `product_category_name` | `TEXT` | Ya |
| `product_name_lenght` | `INTEGER` | Ya |
| `product_description_lenght` | `INTEGER` | Ya |
| `product_photos_qty` | `INTEGER` | Ya |
| `product_weight_g` | `INTEGER` | Ya |
| `product_length_cm` | `INTEGER` | Ya |
| `product_height_cm` | `INTEGER` | Ya |
| `product_width_cm` | `INTEGER` | Ya |

Natural key: `product_id`.

Penamaan `lenght` dipertahankan pada kontrak sumber karena sesuai header CSV. Jika nama kolom dinormalisasi pada Silver, perubahan nama harus dicatat secara eksplisit.

### 4.8 Sellers — `olist_sellers_dataset`

**Grain:** satu baris per seller.

| Kolom | Target PostgreSQL | Nullable |
|---|---|---|
| `seller_id` | `VARCHAR(32)` | Tidak |
| `seller_zip_code_prefix` | `VARCHAR(5)` | Tidak |
| `seller_city` | `TEXT` | Tidak |
| `seller_state` | `VARCHAR(2)` | Tidak |

Natural key: `seller_id`.

### 4.9 Category Translation — `product_category_name_translation`

**Grain:** satu baris per kategori sumber.

| Kolom | Target PostgreSQL | Nullable |
|---|---|---|
| `product_category_name` | `TEXT` | Tidak |
| `product_category_name_english` | `TEXT` | Tidak |

Natural key: `product_category_name`.

File dibaca menggunakan `utf-8-sig` agar Byte Order Mark (BOM),
jika tersedia, tidak dianggap sebagai bagian nama kolom pertama.

**Hasil pemeriksaan BOM (T0):**

Pemeriksaan menggunakan `python scripts/check_bom.py`
menghasilkan:

- UTF-8: `'product_category_name'`
- UTF-8-SIG: `'product_category_name'`
- First 3 bytes: `b'\xef\xbb\xbf'`
- Has UTF-8 BOM: `True`

Hasil ini membuktikan bahwa file sumber mengandung UTF-8 BOM.
Versi pandas yang digunakan berhasil membaca nama kolom
dengan benar menggunakan kedua encoding tersebut.

**Keputusan penanganan:**
Pada T1 (Bronze), byte asli CSV dipertahankan.
Pada T2 (Silver), file dibaca menggunakan `utf-8-sig`
untuk memastikan nama kolom konsisten.

### 4.10 Aturan Parsing Umum

1. Semua identifier dan ZIP prefix dibaca sebagai string sebelum validasi tipe.
2. Timestamp diparsing menggunakan format `YYYY-MM-DD HH:MM:SS`.
3. Nilai uang menggunakan representasi desimal dengan skala dua digit.
4. Kolom integer harus gagal validasi jika berisi angka pecahan atau teks nonnumerik.
5. Koordinat harus bernilai numerik dan diperiksa terhadap batas geografis yang ditetapkan.
6. Null tidak boleh diubah menjadi nol secara otomatis untuk field numerik yang hilang.
7. Nilai kosong pada kolom komentar review diperbolehkan.
8. Data mentah tetap dipertahankan di Bronze, termasuk record yang gagal parsing atau validasi.
9. Status nullable dan aturan constraint akan diverifikasi kembali pada implementasi Silver dan PostgreSQL.

## 5. Data Quality Rules

Aturan kualitas berikut digunakan sebagai spesifikasi implementasi validasi pada tahap T2 (Silver).

**Kebijakan penanganan:**

- **Hard Rule:** record yang melanggar aturan dikirim ke karantina dengan `rule_id`, `source_table`, `source_row` atau identifier sumber, dan alasan kegagalan. Record asli tetap tersedia di Bronze.
- **Soft Rule:** record dipertahankan dalam Silver, sedangkan pelanggarannya disimpan sebagai flag atau laporan anomali.
- Pemeriksaan antar-tabel hanya dijalankan ketika semua dataset terkait sudah tersedia.
- Satu record dapat melanggar lebih dari satu aturan. Jumlah pelanggaran aturan tidak selalu sama dengan jumlah record unik bermasalah.

### 5.1 Hard Rules

| Rule ID | Dataset | Aturan validasi | Penanganan |
|---|---|---|---|
| H01 | Orders | `order_id` tidak boleh null atau kosong | Karantina |
| H02 | Orders | `order_id` harus unik | Karantina record duplikat; pemilihan record utama harus deterministik |
| H03 | Orders | `order_purchase_timestamp` wajib dapat diparsing menjadi timestamp | Karantina |
| H04 | Order items | `(order_id, order_item_id)` wajib lengkap dan unik | Karantina record dengan key invalid atau duplikat |
| H05 | Order items | `price` dan `freight_value` wajib numerik, tidak null, dan bernilai >= 0 | Karantina |
| H06 | Payments | `(order_id, payment_sequential)` wajib lengkap dan unik | Karantina record dengan key invalid atau duplikat |
| H07 | Payments | `payment_value` wajib numerik, tidak null, dan bernilai >= 0 | Karantina |
| H08 | Customers | `customer_id` dan `customer_unique_id` wajib terisi; `customer_id` harus unik | Karantina |
| H09 | Products | `product_id` wajib terisi dan unik | Karantina |
| H10 | Reviews | `(review_id, order_id)` wajib lengkap dan unik; `review_score` harus integer antara 1 dan 5 | Karantina |

### 5.2 Soft Rules

| Rule ID | Dataset | Aturan pemantauan | Penanganan |
|---|---|---|---|
| S01 | Orders | Status `delivered` tetapi `order_delivered_customer_date` null | Flag `delivered_missing_date` |
| S02 | Orders | Tanggal diterima pelanggan lebih awal dari tanggal penyerahan ke kurir | Flag `delivery_before_carrier` |
| S03 | Orders | `order_approved_at` lebih awal dari `order_purchase_timestamp` | Flag `approval_before_purchase` |
| S04 | Geolocation | Koordinat di luar latitude [-34, 5] atau longitude [-74, -35] | Flag `geo_outside_bounds` |
| S05 | Reviews | Satu `order_id` memiliki lebih dari satu review | Flag `multiple_reviews_per_order` |
| S06 | Orders dan items | Order tidak memiliki record item | Flag `order_without_items` |
| S07 | Orders dan payments | Order tidak memiliki record pembayaran | Flag `order_without_payments` |
| S08 | Items dan payments | Selisih absolut antara total item + ongkir dan pembayaran per order > BRL 0,01 | Flag `payment_mismatch` |

### 5.3 Ketentuan Implementasi

1. Setiap aturan harus mempunyai ID tetap agar dapat ditelusuri dari Data Contract ke kode T2, hasil pengujian, dan laporan kualitas.
2. Pemeriksaan keunikan dilakukan berdasarkan natural key yang tercantum pada Bagian 3.
3. Pelanggaran hard pada satu baris tidak boleh menyebabkan penghapusan data dari Bronze.
4. Setiap record karantina harus menyertakan alasan yang dapat diaudit.
5. Soft Rules tidak otomatis menghapus record atau mengubah nilai sumber.
6. Pemeriksaan rekonsiliasi dilakukan setelah agregasi item dan pembayaran per `order_id`, untuk menghindari double counting.
7. Missing item dan missing payment harus dibedakan dari nilai total yang benar-benar nol.
8. Untuk pemeriksaan koordinat, batas geografis yang digunakan merupakan pendekatan profiling dan tidak boleh dianggap sebagai batas administrasi resmi Brasil.
9. Rekonsiliasi dan aturan referensial antar-tabel tidak boleh membuat order tanpa item atau pembayaran hilang dari hasil analisis.
10. Jumlah pelanggaran dan jumlah record unik terdampak harus dilaporkan secara terpisah jika terdapat kemungkinan overlap.

## 6. Temuan Profiling dan Penanganan

Temuan berikut berasal dari profiling sembilan CSV Olist pada tahap T0. Hasil terukur tersimpan dalam `outputs/profile.md` dan `outputs/profile.json`.

Angka merupakan baseline dataset saat ini, bukan hasil pengujian implementasi Silver.

### 6.1 Daftar Temuan

#### Pemetaan Tahap Implementasi Temuan

Tabel ini melengkapi keputusan penanganan pada daftar temuan F01–F19. Setiap temuan memiliki tahap implementasi agar penanganannya dapat ditelusuri dari Data Contract ke pipeline.

| ID | Tahap implementasi | Tindakan yang direncanakan |
|---|---|---|
| F01 | T2 — Silver | Deduplikasi baris geolocation yang identik secara deterministik |
| F02 | T4 — Data Warehouse | Membentuk satu representasi lokasi per ZIP prefix pada `dim_geo` |
| F03 | T2 — Silver | Memvalidasi keunikan composite key `(review_id, order_id)` |
| F04 | T2 — Silver; T4 — DW | Menandai multiple reviews dan memilih review representatif per order |
| F05 | T2 — Silver; T4 — DW | Menandai order tanpa item dan mempertahankannya di `fact_order` |
| F06 | T2 — Silver; T5 — Mart | Menandai order tanpa pembayaran dan melaporkannya pada rekonsiliasi |
| F07 | T4 — Data Warehouse | Menggunakan `customer_unique_id` sebagai identitas orang di `dim_customer` |
| F08 | T2 — Silver; T4 — DW | Menandai tanggal pengiriman yang hilang dan menjaga metrik terkait tetap null |
| F09 | T2 — Silver | Menandai anomali kronologi pengiriman tanpa mengubah tanggal sumber |
| F10 | T2 — Silver; T4 — DW | Menandai koordinat di luar batas dan mengecualikannya dari agregasi lokasi valid |
| F11 | T2 — Silver; T5 — Mart | Menandai selisih pembayaran dan menyediakan analisis rekonsiliasi per order |
| F12 | T2 — Silver | Mempertahankan null pada tanggal persetujuan dan memeriksa konteks status |
| F13 | T2 — Silver | Mempertahankan null pada tanggal penyerahan ke kurir dan memeriksa konteks status |
| F14 | T2 — Silver; T4 — DW | Mempertahankan null tanggal diterima dan mencegah perhitungan durasi yang tidak valid |
| F15 | T2 — Silver | Mempertahankan null judul komentar review sebagai atribut opsional |
| F16 | T2 — Silver | Mempertahankan null isi komentar review sebagai atribut opsional |
| F17 | T2 — Silver; T4 — DW | Mempertahankan null atribut produk serta menggunakan fallback jika dibutuhkan untuk analisis |
| F18 | T2 — Silver | Mempertahankan null berat dan dimensi produk tanpa menggantinya menjadi nol |
| F19 | T2 — Silver | Menandai tanggal batas pengiriman yang menyimpang untuk investigasi, tanpa menghapus otomatis |

**Catatan:** Tahap di atas merupakan rencana implementasi. Bukti bahwa aturan benar-benar berjalan akan dihasilkan saat T2, T4, dan T5 dikerjakan.

### 6.2 Kebijakan Prioritas Penanganan

**Prioritas tinggi:** keunikan key, data tidak dapat diparsing, dan nilai numerik penting yang tidak valid. Penanganan dilakukan dengan Hard Rules dan karantina pada T2.

**Prioritas menengah:** anomali tanggal, koordinat, multiple reviews, missing relationships, dan selisih pembayaran. Penanganan dilakukan melalui Soft Rules, flag, atau rekonsiliasi khusus.

**Prioritas rendah:** kolom komentar yang opsional dan atribut deskriptif yang hilang. Data dipertahankan selama tidak melanggar aturan hard.

### 6.3 Ketentuan Pelaporan

1. Bronze mempertahankan data asli, termasuk record yang bermasalah.
2. Semua perubahan atau pengecualian di Silver harus memiliki alasan yang dapat ditelusuri.
3. Deduplikasi tidak boleh menghilangkan observasi berbeda hanya karena mempunyai ZIP prefix yang sama.
4. `fact_order` tetap mencakup seluruh order yang lolos aturan hard, termasuk order tanpa item atau pembayaran.
5. Temuan rekonsiliasi tidak otomatis berarti terjadi kesalahan pembayaran; perlu analisis penyebab.
6. Jumlah pelanggaran setiap aturan dapat saling tumpang tindih sehingga tidak boleh dijumlahkan begitu saja menjadi total record bermasalah.
7. Temuan F19 merupakan anomali rentang tanggal yang perlu investigasi, bukan bukti kesalahan timestamp.
8. Angka temuan harus dihitung ulang jika dataset sumber berubah.

### 6.4 Referensi Evidence

- `outputs/dataset_check.md`: hasil validasi kelengkapan CSV.
- `outputs/profile.md`: laporan profiling yang dapat dibaca manusia.
- `outputs/profile.json`: metrik terstruktur untuk audit dan pengujian.
- `python pipeline.py check`: menjalankan validasi dataset.
- `python pipeline.py profile`: menjalankan ulang profiling.

## 7. Kebijakan per Lapisan

**Bronze:** data mentah disimpan tanpa mengubah nilai sumber.

**Silver:** parsing tipe, validasi kualitas, deduplikasi sesuai aturan, dan penanganan record bermasalah.

**Data Warehouse:** penerapan grain, primary key, foreign key, dan aturan transformasi bisnis.

## 8. Reproduksibilitas

Validasi dan profiling dijalankan melalui:

```powershell
python pipeline.py check
python pipeline.py profile
```

Laporan hasilnya disimpan di folder `outputs/`.

## 9. Riwayat Perubahan

| Versi | Perubahan |
|---|---|
| 0.1 | Kerangka awal Data Contract berdasarkan profiling T0 |
