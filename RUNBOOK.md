# RUNBOOK — Olist Data Platform

## 1. Tujuan

Dokumen ini menjelaskan cara menjalankan, memverifikasi, memulihkan, dan melakukan troubleshooting Olist Data Platform.

Arsitektur:

```text
9 Olist CSV
    |
    v
Bronze — MinIO (SHA-256, versioned objects)
    |
    v
Silver — Parquet + data quality gates
    |
    v
PostgreSQL raw
    |
    +-----------------------------+
    |                             |
    v                             v
Kafka order lifecycle       Data Warehouse
    |                         (dw.*)
    v                             |
stream.order_events               v
stream.order_current         Gold Marts
stream.order_dlq               (mart.*)
                                  |
                                  v
                         CSV exports + Jupyter
```

Komponen utama: Python, Docker Compose, PostgreSQL, Apache Kafka, MinIO, Pandas, Parquet, dan JupyterLab.

## 2. Prasyarat

- Windows PowerShell atau shell yang setara.
- Python 3.11 dan virtual environment proyek.
- Docker Desktop dengan Docker Compose.
- Dependensi Python telah diinstal dari konfigurasi proyek.
- Sembilan CSV Olist berada di `data/raw/`.
- File `.env` telah dikonfigurasi.
- Port yang dibutuhkan tersedia, terutama PostgreSQL `5432`, Kafka `29092`, MinIO `9000`, Jupyter `8888`, dan Kafka UI `8080`.

Seluruh perintah berikut dijalankan dari root repository dengan virtual environment aktif.

## 3. Urutan Menjalankan Pipeline

Untuk lingkungan yang sudah memiliki dependensi Python dan sembilan CSV sumber, gunakan urutan berikut:

```powershell
python pipeline.py init
python pipeline.py up
python pipeline.py check
python pipeline.py profile
python pipeline.py bronze
python pipeline.py silver
python pipeline.py load
python pipeline.py stream --run --limit 99441
python pipeline.py model
python pipeline.py marts
```

Urutan di atas berjumlah **10 perintah CLI utama**, tetapi bukan jaminan clean-run lengkap akan selesai tanpa langkah tambahan.

**Penting:** replay streaming dengan `--limit 99441` belum dibuktikan berhasil dari keadaan benar-benar kosong menggunakan versi CLI terbaru. Setelah replay, reconciliation harus diperiksa. Jika terdapat final status yang belum cocok, proses recovery dan konsumsi ulang diperlukan.

Untuk lingkungan yang telah terisi seperti hasil eksperimen proyek saat ini, gunakan:

```powershell
python pipeline.py stream --verify-only
python pipeline.py test
python pipeline.py status
python pipeline.py report
```

Perintah verifikasi tambahan ini tidak termasuk dalam hitungan sepuluh perintah eksekusi utama.

## 4. Verifikasi Tiap Lapisan

| Lapisan | Perintah atau artefak | Kriteria |
|---|---|---|
| Infrastruktur | `docker compose ps` | Semua service utama healthy |
| Sumber | `python pipeline.py check` | 9 CSV tersedia |
| Bronze | `outputs/bronze_report.md` | 9 dataset, manifest valid |
| Silver | `outputs/silver/dq_report.md` | Source = Silver + quarantine; quality gate PASS |
| PostgreSQL Raw | `outputs/load_report.md` | 9 tabel, jumlah baris sesuai |
| Streaming | `python pipeline.py stream --verify-only` | 0 missing, 0 status mismatch |
| Data Warehouse | `python pipeline.py model` | 0 integrity violations |
| Gold Marts | `python pipeline.py marts` | Semua business rules PASS |
| Automated tests | `python pipeline.py test` | Seluruh test lulus |
| Failure injection | `outputs/failure_tests.md` | F01–F05 terdeteksi dan dipulihkan sesuai skenario |
| Evaluation | `EVALUATION_EVIDENCE.md` | Angka dan batasan didukung artefak |

### Data quality

Quality gate Silver menggunakan batas quarantine maksimum 1% **per tabel**.

- `PASS`: tidak ada baris yang dikarantina.
- `PASS+KARANTINA`: quarantine lebih dari 0% sampai dengan 1%.
- `FAIL`: quarantine melebihi 1%.

Soft-quality flags tidak menghapus record dari Silver.

### Data Warehouse

Warehouse menggunakan dimensi dan fakta dengan grain berbeda. Jangan menjumlahkan semua row count DW sebagai satu total transaksi.

### Streaming

Event unik ditentukan menggunakan `event_id`. Kafka dapat menerima pesan duplikat, tetapi PostgreSQL mencegah duplikasi event melalui primary key dan `ON CONFLICT DO NOTHING`.

Offset Kafka di-commit setelah transaksi PostgreSQL. Jika consumer crash di antara dua commit tersebut, pesan dapat dibaca ulang dan harus diproses secara idempoten.

## 5. Recovery Streaming

Jika rekonsiliasi streaming gagal:

```powershell
python pipeline.py stream --verify-only
```

Periksa jumlah missing orders dan status mismatches.

Publikasikan ulang final event yang belum cocok:

```powershell
python pipeline.py stream --recover
```

**Perhatian:** perintah recovery hanya mempublikasikan event. Event tersebut masih harus dikonsumsi oleh consumer Kafka sebelum status dianggap pulih.

Consumer dapat dijalankan langsung:

```powershell
python -B -m scripts.consume_orders --idle-seconds 10
```

Setelah consumer selesai, ulangi:

```powershell
python pipeline.py stream --verify-only
```

Jika masih terdapat mismatch, periksa topic, consumer group, DLQ, serta log producer dan consumer. Jangan mengubah `stream.order_current` langsung untuk memaksakan hasil PASS.

## 6. Failure Injection

Skenario pengujian:

| ID | Gangguan | Perintah | Risiko |
|---|---|---|---|
| F01 | CSV missing column | `python pipeline.py inject --scenario f01` | Aman; file sementara |
| F02 | Producer dijalankan dua kali | `python pipeline.py inject --scenario f02` | Menambah pesan topic utama |
| F03 | Consumer crash sebelum offset commit | `python pipeline.py inject --scenario f03` | Menggunakan consumer group khusus |
| F04 | Kafka outage | `python pipeline.py inject --scenario f04 --yes` | Menghentikan Kafka sementara |
| F05 | Batch rerun | `python pipeline.py inject --scenario f05 --yes` | Membangun ulang tabel batch |

Jangan jalankan F04 dan F05 bersamaan dengan workload atau pengujian lain.

Laporan pengujian:

```powershell
python pipeline.py report
```

Bukti tersedia pada `outputs/failure_tests.md`, `outputs/f04_kafka_outage.json`, dan `outputs/f05_batch_rerun.json`.

## 7. Troubleshooting

| Gejala | Pemeriksaan termurah | Perbaikan |
|---|---|---|
| Docker container unhealthy | `docker compose ps` | Periksa `docker compose logs <service>`, lalu restart service yang bermasalah |
| PostgreSQL connection refused | Cek status container PostgreSQL dan port 5432 | `docker compose start postgres`; verifikasi `.env` |
| Kafka connection refused | Cek `docker compose ps` dan status `kafka` | `docker compose start kafka`; tunggu broker siap |
| MinIO S3 connection error | Cek service MinIO, port 9000, dan `.env` | Perbaiki endpoint/kredensial lalu ulangi Bronze |
| Header CSV berubah | `python pipeline.py inject --scenario f01` sebagai uji validator; periksa header CSV asli | Pulihkan header sesuai kontrak `TABLE_SCHEMAS`; ulangi validasi |
| Quarantine melebihi 1% | Baca `outputs/silver/dq_report.md` | Perbaiki sumber atau aturan kualitas yang keliru; jangan bypass gate |
| Raw row count tidak cocok | `python -B -m scripts.verify_raw_counts` | Periksa output Parquet dan load log; ulangi load transaksional setelah sumber valid |
| Event Kafka masuk berulang | Periksa `event_id` dan counter duplicate consumer | Pastikan primary key dan conflict handling aktif; jangan hapus data valid |
| Streaming status mismatch | `python pipeline.py stream --verify-only` | Jalankan recovery, konsumsi event, verifikasi ulang |
| Banyak event masuk DLQ | Periksa alasan error dalam `stream.order_dlq` | Perbaiki payload/schema pada producer; replay hanya event yang valid |
| DW FK atau grain gagal | Jalankan `python pipeline.py model` dan baca `outputs/dw_report.md` | Periksa mapping dimensi/fakta, unknown keys, dan deduplikasi |
| Gold reconciliation tidak MATCH | Periksa `outputs/marts_report.md` | Investigasi order dan payment item secara terpisah; jangan menganggap semua selisih sebagai bug teknis |

## 8. Reset dan Perlindungan Data

**Jangan menggunakan `docker compose down -v` untuk troubleshooting rutin.**

Perintah berikut menghentikan container tanpa menghapus volume:

```powershell
python pipeline.py down
```

Untuk menjalankan kembali:

```powershell
python pipeline.py up
```

Penghapusan volume merupakan operasi destruktif:

```powershell
python pipeline.py down --volumes --yes
```

Perintah destruktif tersebut dapat menghapus data PostgreSQL, pesan dan offset Kafka, serta objek MinIO.

Gunakan hanya ketika memang ingin melakukan reset penuh dan sudah memastikan data penting dicadangkan.

## 9. Bukti Operasional dan Batasan

Hasil eksperimen terakhir:

- 9 dataset Olist.
- 1.550.922 baris Bronze/Silver/Raw.
- 0 quarantine, 13.344 soft-quality flags.
- 99.441 status order cocok setelah streaming recovery.
- 20 integrity checks DW menghasilkan 0 pelanggaran.
- 55 test DW dan Gold lulus.
- F01–F05 tertangkap sesuai cakupan pengujian.

Batasan utama: full streaming consumer replay historis membutuhkan sekitar 528 detik, lebih lama dari target lima menit. Kafka masih single-broker dan tidak menyediakan failover. Pengujian F03 menggunakan event yang sebelumnya sudah ada di database.

Detail angka dan sumber evidence tersedia pada `EVALUATION_EVIDENCE.md`.

## 10. Shutdown

Setelah selesai menggunakan lingkungan:

```powershell
python pipeline.py down
```

Volume tetap disimpan agar eksekusi berikutnya dapat melanjutkan dari data yang sudah ada.
