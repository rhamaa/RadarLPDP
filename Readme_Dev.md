# Dokumentasi Developer - Aplikasi Panel Analisis Radar

Dokumen ini memberikan rincian teknis mengenai arsitektur, struktur kode, alur data, dan komponen utama dari aplikasi panel analisis radar. Tujuannya adalah untuk membantu developer baru memahami cara kerja sistem dan bagaimana cara mengembangkannya.

---

## 1. Ikhtisar & Arsitektur

Aplikasi ini dirancang untuk memvisualisasikan data radar secara real-time. Arsitektur utamanya didasarkan pada **pemisahan antara UI dan logika pemrosesan data** menggunakan model multi-threading untuk menjaga agar antarmuka pengguna (UI) tetap responsif.

- **Main Thread**: Didedikasikan sepenuhnya untuk menjalankan loop Dear PyGui (DPG), me-render UI, dan menangani interaksi pengguna. Thread ini tidak melakukan operasi I/O atau komputasi berat.
- **Worker Thread (`fft_data_worker`)**: Satu thread pekerja utama berjalan di latar belakang untuk menangani semua tugas berat, termasuk:
  - Membaca file data biner dari disk (`live/live_acquisition_ui.bin`).
  - Melakukan Transformasi Fourier Cepat (FFT) pada kedua channel.
  - Mengekstrak metrik puncak (frekuensi & magnitudo).
  - Menghitung jarak target berdasarkan metrik.
  - Mengelola logika sapuan radar 180 derajat (bolak-balik).
  - Menyiapkan data untuk dikirim ke UI.
- **Komunikasi Antar-Thread**: Menggunakan `queue.Queue` dari Python sebagai mekanisme komunikasi yang aman (thread-safe) untuk mengirim data dari worker thread ke main thread. Ada dua antrian utama: `fft_queue` dan `ppi_queue`.

---

## 2. Dependensi

Aplikasi ini memerlukan beberapa pustaka pihak ketiga. Anda dapat menginstalnya menggunakan pip dari virtual environment:

```bash
source .venv/bin/activate
pip install dearpygui numpy scipy
```

- **dearpygui**: Framework utama untuk membangun antarmuka pengguna (GUI).
- **numpy**: Digunakan untuk operasi numerik yang efisien pada array, terutama dalam pemrosesan sinyal.
- **scipy**: Digunakan untuk komputasi FFT (`scipy.fft`).

---

## 3. Struktur Proyek

```
/RadarLPDP
├── app/
│   ├── callbacks.py      # Logika untuk update UI dari antrian & event handling
│   └── setup.py          # Inisialisasi DPG, tema, dan worker thread
├── functions/
│   └── data_processing.py  # Logika inti: worker, FFT, kalkulasi target
├── live/
│   └── live_acquisition_ui.bin # File data biner real-time
├── widgets/
│   ├── PPI.py            # Widget Plan Position Indicator (180°)
│   ├── FFT.py            # Widget spektrum FFT
│   ├── Sinewave.py       # Widget plot sinyal mentah
│   ├── controller.py     # Widget kontrol aplikasi
│   └── metrics.py        # Widget tabel metrik frekuensi
├── config.py             # File konfigurasi terpusat
├── dumy_gen.py           # Skrip untuk menghasilkan data biner dummy
├── main.py               # Titik masuk utama aplikasi (mendefinisikan layout)
└── Readme_Dev.md         # Dokumentasi ini
```

---

## 4. Alur Data (Data Flow)

1.  **Generasi Data**: `dumy_gen.py` secara periodik menulis ulang `live/live_acquisition_ui.bin` dengan data sinyal baru.
2.  **Deteksi & Proses**: `fft_data_worker` di `functions/data_processing.py` memonitor perubahan file. Jika ada perubahan, ia memanggil fungsi pembantu untuk:
    a. Membaca file dan melakukan FFT (`process_channel_data`).
    b. Menghitung jarak target dari hasil FFT (`calculate_target_distance`).
3.  **Update Sudut Sapuan**: Secara bersamaan, worker memperbarui sudut sapuan radar, membuatnya bergerak bolak-balik antara 0 dan 180 derajat (`update_sweep_angle`).
4.  **Pengiriman Data**: Worker menempatkan dua paket data ke dalam antrian yang berbeda:
    - **`fft_queue`**: Berisi data spektrum lengkap (frekuensi, magnitudo) untuk widget FFT dan Metrik.
    - **`ppi_queue`**: Berisi sudut sapuan saat ini dan daftar riwayat target (sudut, jarak) untuk widget PPI.
5.  **Penerimaan & Update UI**: Di main thread, `app/callbacks.py:update_ui_from_queues` secara terus-menerus memeriksa kedua antrian. Jika ada data baru, ia mengambilnya dan memanggil fungsi yang relevan untuk memperbarui elemen UI, seperti `widgets.PPI:update_ppi_widget`.

---

## 5. Rincian Modul Penting

### `functions/data_processing.py`
- **Tujuan**: Rumah bagi semua logika pemrosesan data inti. Kode telah direfaktorisasi menjadi beberapa fungsi modular untuk kejelasan.
- **Fungsi Kunci**:
  - `fft_data_worker()`: Fungsi worker utama yang mengoordinasikan seluruh proses dari pembacaan data hingga pengiriman ke antrian.
  - `process_channel_data()`: Melakukan FFT pada data mentah dan mengembalikan hasil yang terstruktur.
  - `calculate_target_distance()`: Menerapkan formula untuk menghitung jarak target dari metrik FFT.
  - `update_sweep_angle()`: Mengelola logika sapuan radar 180 derajat bolak-balik.

### `widgets/PPI.py`
- **Tujuan**: Mendefinisikan dan mengontrol widget PPI.
- **Fungsi Kunci**:
  - `create_ppi_widget()`: Menginisialisasi plot PPI 180 derajat, termasuk sumbu, batas, dan busur penanda jarak.
  - `update_ppi_widget()`: Fungsi terpusat yang dipanggil dari `callbacks` untuk memperbarui visual PPI. Menerima sudut dan daftar target, lalu menggambar ulang garis sapuan dan titik-titik target.

### `app/callbacks.py`
- **Tujuan**: Bertindak sebagai jembatan antara data dari worker dan UI.
- **Fungsi Kunci**:
  - `update_ui_from_queues()`: Loop utama yang berjalan di setiap frame UI. Mengambil data dari `fft_queue` dan `ppi_queue` (tanpa memblokir) dan mendistribusikannya ke widget yang sesuai. Untuk PPI, ia memanggil `update_ppi_widget` dengan data yang relevan.

### `app/callbacks.py`
- **Tujuan**: Jantung dari interaktivitas UI.
- **Fungsi Kunci**:
  - `update_ui_from_queues()`: Dipanggil setiap frame di loop utama. Mengambil data dari semua `queue` dan memperbarui nilai widget DPG.
  - `resize_callback()`: Dipanggil saat jendela diubah ukurannya. Menghitung ulang dimensi semua panel secara dinamis untuk menciptakan tata letak yang responsif.
  - `cleanup_and_exit()`: Memastikan semua thread dihentikan dengan aman saat aplikasi ditutup.

### `functions/data_processing.py`
- **Tujuan**: Otak pemrosesan data.
- **Fungsi Kunci**:
  - `fft_data_worker()`, `sinewave_data_worker()`, `ppi_data_worker()`: Fungsi target untuk setiap worker thread. Berisi loop tak terbatas yang memonitor file, memproses data, dan memasukkan hasilnya ke `queue`.
  - `load_and_process_data()`: Membaca file biner dan mengubahnya menjadi array NumPy.
  - `compute_fft()`: Menghitung FFT dan mengonversi magnitudo ke dB.
  - `find_peak_metrics()`: Mengekstrak frekuensi dan magnitudo puncak.

### `widgets/` (Direktori)
- **Tujuan**: Berisi modul-modul yang masing-masing bertanggung jawab untuk membuat satu komponen UI.
- **Prinsip**: Setiap modul widget hanya berisi kode DPG untuk membuat elemen UI. Mereka tidak berisi logika aplikasi atau status. Mereka dirancang untuk menjadi komponen yang dapat digunakan kembali.
- **Contoh (`widgets/FFT.py`)**: Fungsi `create_fft_widget()` membuat `dpg.plot` dengan sumbu, legenda, dan `line_series` yang diberi tag unik (misalnya, `fft_ch1_series`). Tag ini kemudian digunakan oleh `app/callbacks.py` untuk memperbarui data plot.

---

## 6. Cara Menjalankan

1.  **Instal Dependensi**: 
    ```bash
    pip install -r requirements.txt # (Jika file ini dibuat)
    # atau
    pip install dearpygui numpy scipy
    ```
2.  **Jalankan Generator Data**: Buka terminal dan jalankan skrip untuk mulai menghasilkan data simulasi.
    ```bash
    python dumy_gen.py
    ```
    Biarkan terminal ini berjalan di latar belakang.

3.  **Jalankan Aplikasi Utama**: Buka terminal kedua dan jalankan aplikasi utama.
    ```bash
    python main.py
    ```

Jendela aplikasi akan muncul dan mulai menampilkan data secara real-time.
