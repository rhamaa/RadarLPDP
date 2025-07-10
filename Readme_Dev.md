# Dokumentasi Developer - Aplikasi Panel Analisis# RadarLPDP - Developer Documentation

Dokumen ini memberikan gambaran teknis tentang arsitektur, alur data, dan komponen utama dari aplikasi RadarLPDP. Tujuannya adalah untuk membantu developer memahami cara kerja sistem dan bagaimana cara memodifikasinya.

---

## Arsitektur Umum: Dekopling Sudut dan Data

Aplikasi ini menggunakan `dearpygui` untuk antarmuka pengguna (UI) dan `threading` untuk pemrosesan data secara konkuren. Arsitektur terbaru ini dirancang dengan prinsip **dekopling (pemisahan)** antara **sumber data sudut sapuan** dan **sumber data deteksi target**. Ini memungkinkan fleksibilitas maksimum, terutama untuk integrasi dengan hardware eksternal (seperti Arduino) di masa depan.

Komponen utama meliputi:

1.  **UI Widgets** (`widgets/`): Modul yang mendefinisikan elemen UI (plot PPI, plot sinewave, dll.).
2.  **Data Processing Workers** (`functions/data_processing.py`): Kumpulan thread independen yang masing-masing memiliki satu tanggung jawab spesifik.
3.  **UI Callbacks** (`app/callbacks.py`): Fungsi yang menjadi jembatan antara data dari worker dan pembaruan visual di UI.
4.  **Konfigurasi** (`config.py`): File terpusat untuk semua parameter penting.

---

## Alur Data Terpisah

Alur data dirancang agar *thread-safe* menggunakan `queue.Queue` dan sekarang sepenuhnya terpisah.

1.  **`dumy_gen.py`**: Skrip ini mensimulasikan **data deteksi** dengan menulis sinyal ke `live/live_acquisition_ui.bin`.

2.  **Worker Threads**:
    - **`angle_worker`**: **Sumber kebenaran untuk sudut sapuan**. Worker ini secara independen menghasilkan sudut sapuan (0°-180° bolak-balik) dengan kecepatan konstan. Di masa depan, worker inilah yang akan dimodifikasi untuk membaca data dari port serial Arduino. Ia mengirimkan pesan `{'type': 'sweep', 'angle': ...}` ke `ppi_queue`.
    - **`fft_data_worker`**: **Sumber kebenaran untuk deteksi target**. Worker ini hanya memantau `live_acquisition_ui.bin`. Jika ada file baru, ia melakukan FFT, menghitung jarak target, dan mengirimkan pesan `{'type': 'target', 'distance': ...}` ke `ppi_queue`. Worker ini **tidak tahu menahu tentang sudut sapuan**.
    - **`sinewave_data_worker`**: Memproses file yang sama untuk menampilkan plot sinewave mentah.

3.  **Antrian (Queues)**:
    - `ppi_queue`: Antrian kunci yang menerima **dua jenis pesan** dari dua worker yang berbeda: pesan `sweep` dari `angle_worker` dan pesan `target` dari `fft_data_worker`.
    - `fft_queue` & `sinewave_queue`: Berfungsi seperti sebelumnya untuk metrik dan plot sinewave.

4.  **`update_ui_from_queues` (di `app/callbacks.py`)**:
    - Fungsi ini berjalan di setiap frame dan bertindak sebagai **koordinator cerdas**.
    - Ia menyimpan `last_known_angle` terakhir yang diterima dari pesan `sweep`.
    - Ketika pesan `target` diterima, ia akan mem-plot target tersebut pada `last_known_angle` yang tersimpan.
    - Ini memastikan UI selalu responsif dan pergerakan sapuan tetap mulus, terlepas dari apakah ada target baru atau tidak.

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
