import time
import shutil
from pathlib import Path

def snapshot_live_file_sequentially(
    directory: str = "./live",
    filename: str = "live_acquisition_ui.bin",
    start_index: int = 1,
    end_index: int = 40,
    delay_seconds: int = 2,
) -> Path:
    """
    Salin isi 'live_acquisition_ui.bin' menjadi berkas baru berurutan '1.bin' ... 'N.bin'
    tanpa menimpa file yang sudah ada, dengan jeda antar snapshot selama delay_seconds.

    - directory: folder tempat file berada
    - filename: nama awal file (default 'live_acquisition_ui.bin')
    - start_index: angka mulai (default 1)
    - end_index: angka akhir snapshot (default 8)
    - delay_seconds: jeda antar snapshot (default 2 detik)

    Return: Path ke file terakhir yang dibuat (misal '8.bin').
    """
    base_dir = Path(directory)
    source_path = base_dir / filename
    print(f"Mulai: sumber snapshot di '{base_dir}' bernama '{filename}'")

    # Jika file awal tidak ada, coba lanjut dari nama yang sudah terlanjur diubah
    if not source_path.exists():
        raise FileNotFoundError(
            f"Sumber tidak ditemukan: '{source_path}'. Pastikan file live tersedia."
        )

    last_created = None
    for i in range(start_index, end_index + 1):
        target_path = base_dir / f"{i}.bin"

        if target_path.exists():
            print(f"Lewati: '{target_path.name}' sudah ada.")
        else:
            print(f"Salin '{source_path.name}' -> '{target_path.name}'")
            shutil.copy2(source_path, target_path)
            last_created = target_path

        if i < end_index:
            print(f"Menunggu {delay_seconds} detik sebelum snapshot berikutnya...")
            time.sleep(delay_seconds)

    return last_created if last_created is not None else (base_dir / f"{end_index}.bin")


if __name__ == "__main__":
    try:
        hasil = snapshot_live_file_sequentially(directory="./live", delay_seconds=2)
        print(f"Selesai. File terakhir dibuat: '{hasil}'")
    except Exception as exc:
        print(f"Error: {exc}")