# Dokumentasi Developer - Aplikasi Panel Analisis Radar

Dokumen ini memberikan rincian teknis mengenai arsitektur, struktur kode, alur data, dan komponen utama dari aplikasi panel analisis radar. Tujuannya adalah untuk membantu developer baru memahami cara kerja sistem dan bagaimana cara mengembangkannya.

---

## 1. Ikhtisar & Arsitektur

Aplikasi ini dirancang untuk memvisualisasikan data radar secara real-time. Arsitektur utamanya didasarkan pada **pemisahan antara UI dan logika pemrosesan data** menggunakan model multi-threading untuk menjaga agar antarmuka pengguna (UI) tetap responsif.

- **Main Thread**: Didedikasikan sepenuhnya untuk menjalankan loop Dear PyGui (DPG), me-render UI, dan menangani interaksi pengguna. Thread ini tidak melakukan operasi I/O atau komputasi berat.
- **Worker Threads**: Berjalan di latar belakang untuk menangani tugas-tugas berat seperti:
  - Membaca file data biner dari disk.
  - Melakukan transformasi Fourier Cepat (FFT).
  - Mengekstrak metrik.
  - Menyiapkan data untuk visualisasi.
- **Komunikasi Antar-Thread**: Menggunakan `queue.Queue` dari Python sebagai mekanisme komunikasi yang aman (thread-safe) untuk mengirim data dari worker threads ke main thread.

 <!-- Placeholder untuk diagram arsitektur -->

---

## 2. Dependensi

Aplikasi ini memerlukan beberapa pustaka pihak ketiga. Anda dapat menginstalnya menggunakan pip:

```bash
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
│   ├── __init__.py
│   ├── callbacks.py      # Logika untuk update UI & event handling
│   └── setup.py          # Inisialisasi DPG, tema, dan threads
├── functions/
│   ├── __init__.py
│   └── data_processing.py  # Fungsi worker, FFT, & ekstraksi data
├── log/
│   └── (File log akan muncul di sini)
├── live/
│   └── live_acquisition_ui.bin # File data biner
├── widgets/
│   ├── __init__.py
│   ├── PPI.py            # Widget Plan Position Indicator
│   ├── FFT.py            # Widget spektrum FFT
│   ├── Sinewave.py       # Widget plot sinyal mentah
│   ├── controller.py     # Widget kontrol aplikasi
│   ├── file.py           # Widget file explorer untuk log
│   └── metrics.py        # Widget tabel metrik frekuensi
├── config.py             # File konfigurasi terpusat
├── dumy_gen.py           # Skrip untuk menghasilkan data biner dummy
├── main.py               # Titik masuk utama aplikasi (mendefinisikan layout)
└── Readme_Dev.md         # Dokumentasi ini
```

---

## 4. Alur Data (Data Flow)

1.  **Generasi Data**: `dumy_gen.py` menghasilkan file `live/live_acquisition_ui.bin` yang berisi data sinyal mentah.
2.  **Deteksi & Pembacaan**: Worker thread di `functions/data_processing.py` memonitor perubahan pada file tersebut. Jika ada perubahan, file dibaca.
3.  **Pemrosesan**: Data biner di-unpack, diubah menjadi array NumPy, dan diproses. Worker yang berbeda menghitung FFT, mengekstrak metrik puncak, dan menyiapkan data sinewave.
4.  **Pengiriman Data**: Hasil pemrosesan (array frekuensi, magnitudo, data waktu, metrik) dimasukkan ke dalam `queue` yang sesuai (`fft_queue`, `sinewave_queue`).
5.  **Penerimaan & Update UI**: Di main thread, fungsi `app/callbacks.py:update_ui_from_queues` secara terus-menerus memeriksa `queue`. Jika ada data baru, fungsi ini akan mengambilnya dan memperbarui elemen Dear PyGui yang relevan (misalnya, `dpg.set_value` pada series plot atau teks).

---

## 5. Rincian Modul

### `main.py`
- **Tujuan**: Titik masuk utama aplikasi.
- **Tanggung Jawab**: 
  - Mengimpor semua widget dari direktori `widgets/`.
  - Mendefinisikan struktur dan tata letak UI utama menggunakan `dpg.window`, `dpg.group`, dan `dpg.child_window`.
  - Memanggil fungsi setup dari `app/setup.py`.
  - Menjalankan loop utama `dpg.is_dearpygui_running()`.
- **Komunikasi**: Memanggil fungsi dari `app.setup`, `app.callbacks`, dan semua modul di `widgets`.

### `config.py`
- **Tujuan**: Konfigurasi terpusat.
- **Isi**: Menyimpan konstanta global seperti path file, sample rate, interval polling, warna tema, dan padding UI.
- **Keuntungan**: Menghindari *hardcoding* dan memudahkan perubahan parameter di satu tempat.

### `app/setup.py`
- **Tujuan**: Menangani semua logika inisialisasi.
- **Fungsi Kunci**:
  - `setup_dpg()`: Membuat viewport, mengatur tema, dan mendaftarkan `resize_callback`.
  - `initialize_queues_and_events()`: Membuat instance dari semua `queue` dan `threading.Event` yang diperlukan.
  - `start_worker_threads()`: Memulai semua worker thread (FFT, Sinewave, PPI).
- **Output**: Mengembalikan `queues` dan `threads` yang akan digunakan oleh `main.py` dan `app/callbacks.py`.

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
