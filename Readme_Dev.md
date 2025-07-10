# Dokumentasi Developer - Aplikasi Panel Analisis# RadarLPDP - Developer Documentation

Dokumen ini memberikan gambaran teknis tentang arsitektur, alur data, dan komponen utama dari aplikasi RadarLPDP. Tujuannya adalah untuk membantu developer memahami cara kerja sistem dan bagaimana cara memodifikasinya.

---

## Arsitektur Umum: Dekopling Sudut dan Data

Aplikasi ini menggunakan `dearpygui` untuk UI, `threading` untuk konkurensi, dan `pyserial` untuk komunikasi hardware. Arsitektur ini dirancang dengan prinsip **dekopling (pemisahan)** antara **sumber data sudut sapuan** (dari hardware) dan **sumber data deteksi target** (dari file).

---

## Prasyarat & Setup

Sebelum menjalankan aplikasi, pastikan hal-hal berikut terpenuhi.

### 1. Dependensi Python

Pastikan semua pustaka terinstal di dalam virtual environment Anda:

```bash
source .venv/bin/activate
pip install dearpygui numpy scipy pyserial
```

### 2. Hardware (ESP32/Arduino)

- Diperlukan perangkat keras (seperti ESP32 atau Arduino) yang terhubung ke komputer melalui USB.
- Unggah firmware yang ada di `Control/Control.ino` ke perangkat Anda. Firmware ini akan mengirimkan data sudut (0-180) secara terus-menerus melalui port serial.

### 3. Konfigurasi Aplikasi

Buka file `config.py` dan sesuaikan pengaturan berikut jika perlu:
- `SERIAL_PORT`: Pastikan ini sesuai dengan port serial perangkat Anda (misalnya, `/dev/ttyUSB0` di Linux atau `COM3` di Windows).
- `BAUD_RATE`: Harus cocok dengan baud rate di kode Arduino (saat ini `115200`).

### 4. Izin Port Serial (Khusus Linux)

Secara default, user biasa tidak memiliki izin untuk mengakses port serial. Anda akan mendapatkan error "Permission Denied". Untuk mengatasinya, jalankan perintah berikut sekali:

```bash
sudo chmod a+rw /dev/ttyUSB0
```
*(Ganti `/dev/ttyUSB0` dengan port Anda jika berbeda)*.

Untuk solusi permanen, tambahkan user Anda ke grup `dialout`:
`sudo usermod -a -G dialout $USER` (memerlukan logout/login ulang).

---

## Alur Data dengan Hardware

1.  **Hardware (ESP32)**: Mengirimkan baris data sudut (`"0"`, `"1"`, ..., `"180"`) melalui serial.
2.  **`angle_worker`**: Membaca data dari `SERIAL_PORT`. Setiap baris yang valid diubah menjadi angka dan dikirim ke `ppi_queue` sebagai pesan `{'type': 'sweep'}`.
3.  **`fft_data_worker`**: Tetap sama, memantau `live_acquisition_ui.bin` dan mengirimkan pesan `{'type': 'target'}` ke `ppi_queue`.
4.  **`update_ui_from_queues`**: Tetap sama, mengoordinasikan kedua jenis pesan untuk menampilkan sapuan dan target secara akurat.

---

## Modul Utama dan Tanggung Jawab

- **`functions/data_processing.py` -> `angle_worker`**: Tanggung jawabnya sekarang adalah **membaca dan mem-parsing data dari port serial**. Fungsi ini berisi semua logika untuk menangani koneksi, diskoneksi, dan error pembacaan data serial.

- **`config.py`**: Menyimpan konfigurasi hardware (`SERIAL_PORT`, `BAUD_RATE`, `SERIAL_TIMEOUT`).

- **`Control/Control.ino`**: Kode firmware untuk ESP32/Arduino. Kecepatan sapuan dapat diatur dengan mengubah variabel `sweep_delay` di dalam file ini.

### `app/callbacks.py`
- **Tujuan**: Jantung dari interaktivitas UI.
- **Fungsi Kunci**:
  - `update_ui_from_queues()`: Loop utama yang berjalan di setiap frame UI. Mengambil data dari `fft_queue` dan `ppi_queue` (tanpa memblokir) dan mendistribusikannya ke widget yang sesuai. Untuk PPI, ia memanggil `update_ppi_widget` dengan data yang relevan.
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
