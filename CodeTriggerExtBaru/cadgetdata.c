#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <conio.h>
#include <process.h>
#include <time.h>
#include "wddaskex.h"
#include "wd-dask.h"

// ----------------------- KONFIGURASI ------------------------------
#define CHANNEL_COUNT   2
#define SAMPLE_RATE_HZ  20000000
#define BUFFER_SAMPLES  8192
#define MAX_EVENT_BATCH 1000

#define LOG_FOLDER "log"
#define LIVE_FOLDER "live"
#define LIVE_UI_FILENAME "live_acquisition_ui.bin"

#define CODE_VERSION "Code trigger V.3"
#define AUTHOR_NAME  "Raihan Muhammad"

// -------------------- VARIABEL GLOBAL -----------------------------
static U16 card_type = PCI_9846H;
static U16 cardnum   = 0;
I16 card = -1;
U16 ai_buf[BUFFER_SAMPLES * CHANNEL_COUNT];
U16 ai_buf2[BUFFER_SAMPLES * CHANNEL_COUNT];

U32 startPos, count1;

typedef struct {
    void* data;
    size_t size;
} AcquisitionData;

static AcquisitionData g_data_buffer[MAX_EVENT_BATCH];
static int g_buffered_count = 0;

// ----------------- FUNGSI SAVE BATCH ------------------------------
void save_batch_to_file() {
    if (g_buffered_count == 0) return;

    // 1. Buat nama file log batch yang unik
    time_t now = time(NULL);
    struct tm* t = localtime(&now);
    char log_filepath[MAX_PATH];
    snprintf(log_filepath, sizeof(log_filepath), "%s\\batch_log_%04d%02d%02d_%02d%02d%02d_%04d_evt.bin",
             LOG_FOLDER,
             t->tm_year + 1900, t->tm_mon + 1, t->tm_mday,
             t->tm_hour, t->tm_min, t->tm_sec, g_buffered_count);

    FILE* f_log = fopen(log_filepath, "wb");
    if (!f_log) {
        printf("KRITIS: Gagal membuat file batch log: %s\n", log_filepath);
        return;
    }

    // 2. Tulis header (pakai format string)
    char header[512];
    snprintf(header, sizeof(header),
        "TEST_DATE:%04d-%02d-%02d %02d:%02d:%02d\n"
        "CODE_VERSION:%s\n"
        "AUTHOR:%s\n"
        "BATCH_EVENT_COUNT:%d\n\n",
        t->tm_year + 1900, t->tm_mon + 1, t->tm_mday,
        t->tm_hour, t->tm_min, t->tm_sec,
        CODE_VERSION, AUTHOR_NAME, g_buffered_count
    );
    fwrite(header, 1, strlen(header), f_log);

    // 3. Tulis data event
    for (int i = 0; i < g_buffered_count; ++i) {
        fwrite(g_data_buffer[i].data, 1, g_data_buffer[i].size, f_log);
        free(g_data_buffer[i].data);
        g_data_buffer[i].data = NULL;
        g_data_buffer[i].size = 0;
    }
    fclose(f_log);
    printf("Batch %d event berhasil disimpan ke %s (header+data)\n", g_buffered_count, log_filepath);

    g_buffered_count = 0; // Reset buffer counter
}

// ------------------- UTILITY FUNGSI -------------------------------
void create_directory_if_not_exists(const char* path) {
    if (!CreateDirectory(path, NULL)) {
        if (GetLastError() != ERROR_ALREADY_EXISTS) {
            printf("Peringatan: Gagal membuat direktori '%s'. Error: %lu\n", path, GetLastError());
        }
    }
}

void print_error_and_cleanup(const char* message, I16 error_code) {
    printf("ERROR: %s, kode error: %d\n", message, error_code);
    if (card >= 0) {
        WD_AI_AsyncClear(card, NULL, NULL);
        WD_Release_Card(card);
        printf("Kartu DAQ dilepaskan.\n");
    }
    printf("Program berhenti karena error. Tekan tombol apa saja untuk keluar...\n");
    _getch();
    exit(1);
}

// -------------------- MAIN PROGRAM --------------------------------
// ... [Bagian #include, define, variabel global tetap seperti kode kamu] ...
int main() {
    I16 err, Id;
    U16 range;
    U32 samp_intrv;

    printf("Program Akuisisi (AI1 & AI3 only) untuk PCI-9846H\n");
    printf("Live file di '%s', batch log di '%s'. Tekan ESC untuk keluar.\n\n", LIVE_FOLDER, LOG_FOLDER);

    create_directory_if_not_exists(LOG_FOLDER);
    create_directory_if_not_exists(LIVE_FOLDER);

    card = WD_Register_Card(card_type, cardnum);
    if (card < 0) { printf("Kesalahan WD_Register_Card: %d\n", card); return 1; }

    DAS_IOT_DEV_PROP cardProp;
    err = WD_GetDeviceProperties(card, 0, &cardProp);
    if (err != 0) print_error_and_cleanup("WD_GetDeviceProperties", err);

    range = cardProp.default_range;

    // Konfig semua channel ke default range (driver butuh ini meski kita baca subset)
    err = WD_AI_CH_Config(card, -1, range);
    if (err) print_error_and_cleanup("WD_AI_CH_Config", err);

    // Timebase dan source sama seperti sebelumnya
    err = WD_AI_Config(card, WD_IntTimeBase, 1, WD_AI_ADCONVSRC_TimePacer, 0, 1);
    if (err) print_error_and_cleanup("WD_AI_Config", err);

    samp_intrv = (U32)(40000000.0 / SAMPLE_RATE_HZ);
    if (samp_intrv < 2) samp_intrv = 2;
    printf("Sample Rate: %d Hz, Samp Intrv: %d\n", SAMPLE_RATE_HZ, samp_intrv);

    // >>>>>>>>>>>>>>>>>> HANYA AI1 & AI3 <<<<<<<<<<<<<<<<<<
    // Urutan interleaved output akan: AI1, AI3, AI1, AI3, ...
    U16 ch_list[2] = {1, 3};
    // Jika header kamu butuh explicit, tulis ke header batch juga bahwa urutannya AI1, AI3.

    int event_count = 0;
    int exit_now = 0;

    while (!exit_now) {
        event_count++;

        // Trigger eksternal tetap (ubah TrgEdge sesuai kebutuhan: WD_AI_TrgPositive/Negative)
        err = WD_AI_Trig_Config(card, WD_AI_TRGMOD_POST, WD_AI_TRGSRC_ExtD, WD_AI_TrgNegative, 0, 0.0, 0, 0, 0, 1);
        if (err) print_error_and_cleanup("WD_AI_Trig_Config", err);

        WD_AI_ContBufferReset(card);

        err = WD_AI_AsyncDblBufferMode(card, TRUE);
        if (err) print_error_and_cleanup("WD_AI_AsyncDblBufferMode", err);

        // Siapkan 2 buffer untuk 2 channel * BUFFER_SAMPLES per half
        U32 samples_per_half_total = BUFFER_SAMPLES * 2; // 2 channel (AI1 & AI3)
        I16 Id1, Id2;
        err = WD_AI_ContBufferSetup(card, ai_buf,  samples_per_half_total, &Id1);
        if (err) print_error_and_cleanup("WD_AI_ContBufferSetup (buf1)", err);
        err = WD_AI_ContBufferSetup(card, ai_buf2, samples_per_half_total, &Id2);
        if (err) print_error_and_cleanup("WD_AI_ContBufferSetup (buf2)", err);

        // Mulai akuisisi multi-channel non-berurutan (AI1 & AI3)
        // Catatan: pada sebagian versi WD-DASK, parameter yang dipakai adalah:
        //   (card, NumChans, ChanListPtr, StartBufId, ReadScans, ScanIntrv, SampIntrv, ASYNCH_OP)
        // di mana ReadScans = jumlah sampel per channel per half-buffer
        err = WD_AI_ContReadMultiChannels(
            card,
            2,                 // NumChans: AI1 & AI3
            ch_list,           // daftar channel
            Id1,               // buffer id awal (driver pakai double buffer)
            BUFFER_SAMPLES,    // ReadScans: sampel per channel per half
            samp_intrv,        // ScanIntrv (pakai sama dengan samp_intrv untuk rasio 1:1)
            samp_intrv,        // SampIntrv
            ASYNCH_OP
        );
        if (err) print_error_and_cleanup("WD_AI_ContReadMultiChannels", err);

        // ---------- file live (pakai file tmp lalu rename) ----------
        char live_filepath_tmp[MAX_PATH], live_filepath_final[MAX_PATH];
        snprintf(live_filepath_tmp, sizeof(live_filepath_tmp), "%s\\live_acquisition_ui.tmp", LIVE_FOLDER);
        snprintf(live_filepath_final, sizeof(live_filepath_final), "%s\\%s", LIVE_FOLDER, LIVE_UI_FILENAME);
        FILE* f_out_live = fopen(live_filepath_tmp, "wb");
        if (!f_out_live) {
            // Tidak fatal ke hardware; lanjut ke siklus berikut
            // (tapi data tidak ditulis ke UI live kali ini)
        }

        void*  current_acq_buffer = NULL;
        size_t current_acq_size   = 0;
        const size_t chunk_size   = sizeof(U16) * samples_per_half_total; // 2 ch * BUFFER_SAMPLES

        int g_fStop = 0;
        BOOLEAN halfReady;
        int current_buffer_idx = 0;

        while (!g_fStop) {
            WD_AI_AsyncDblBufferHalfReady(card, &halfReady, (BOOLEAN*)&g_fStop);
            if (halfReady) {
                void* source_buffer = (current_buffer_idx == 0) ? ai_buf : ai_buf2;

                // grow RAM buffer untuk event ini
                void* new_buffer = realloc(current_acq_buffer, current_acq_size + chunk_size);
                if (new_buffer == NULL) {
                    g_fStop = 1;
                    free(current_acq_buffer);
                    current_acq_buffer = NULL;
                    break;
                }
                current_acq_buffer = new_buffer;

                // copy blok data 2-channel (AI1,AI3 interleaved)
                memcpy((char*)current_acq_buffer + current_acq_size, source_buffer, chunk_size);
                current_acq_size += chunk_size;

                // tulis ke file live (kalau terbuka)
                if (f_out_live) fwrite(source_buffer, 1, chunk_size, f_out_live);

                current_buffer_idx = 1 - current_buffer_idx;

                // housekeeping double buffer
                WD_AI_AsyncClear(card, &startPos, &count1);
                WD_AI_AsyncDblBufferHandled(card);
            }

            if (_kbhit() && _getch() == 27) { g_fStop = 1; exit_now = 1; }
        }

        if (f_out_live) fclose(f_out_live);
        MoveFileExA(live_filepath_tmp, live_filepath_final, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH);

        if (current_acq_buffer != NULL && current_acq_size > 0) {
            // Simpan RAM → batch buffer (event)
            g_data_buffer[g_buffered_count].data = current_acq_buffer;
            g_data_buffer[g_buffered_count].size = current_acq_size;
            g_buffered_count++;

            if (g_buffered_count >= MAX_EVENT_BATCH) {
                save_batch_to_file();
            }
        }

        // berhenti loop while (!exit_now) kalau ESC ditekan di atas
    }

    if (g_buffered_count > 0) save_batch_to_file();

    if (card >= 0) {
        WD_AI_AsyncClear(card, NULL, NULL);
        WD_Release_Card(card);
    }

    printf("\nSelesai. Tekan tombol apa saja untuk keluar...\n");
    _getch();
    return 0;
}
