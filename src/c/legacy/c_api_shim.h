#ifndef MP3GAIN_C_API_SHIM_H
#define MP3GAIN_C_API_SHIM_H

#include <stddef.h>

#if defined(_WIN32) || defined(__CYGWIN__)
#define MP3G_BACKEND_EXPORT __declspec(dllexport)
#else
#define MP3G_BACKEND_EXPORT
#endif

#define MP3G_TAG_FORMAT_NONE 0
#define MP3G_TAG_FORMAT_APEV2 1
#define MP3G_TAG_FORMAT_ID3 2

typedef struct mp3g_backend_tag_info {
    int found;
    int tag_format;

    int have_track_gain;
    int have_track_peak;
    int have_album_gain;
    int have_album_peak;

    int have_undo;
    int undo_left;
    int undo_right;
    int undo_wrap;

    int have_minmax_gain;
    int min_gain;
    int max_gain;

    int have_album_minmax_gain;
    int album_min_gain;
    int album_max_gain;

    double track_gain;
    double track_peak;
    double album_gain;
    double album_peak;
} mp3g_backend_tag_info;

MP3G_BACKEND_EXPORT int mp3g_backend_initialize(void);
MP3G_BACKEND_EXPORT void mp3g_backend_shutdown(void);

MP3G_BACKEND_EXPORT void mp3g_backend_reset_error(void);
MP3G_BACKEND_EXPORT int mp3g_backend_get_last_error_code(void);
MP3G_BACKEND_EXPORT int mp3g_backend_get_last_error_message(char *buffer, int buflen);

MP3G_BACKEND_EXPORT int mp3g_backend_analyzer_init(long sample_rate);
MP3G_BACKEND_EXPORT int mp3g_backend_analyzer_reset_sample_frequency(long sample_rate);
MP3G_BACKEND_EXPORT int mp3g_backend_analyzer_feed_f64(
    const double *left,
    const double *right,
    size_t num_samples,
    int num_channels
);
MP3G_BACKEND_EXPORT double mp3g_backend_analyzer_get_title_gain(void);
MP3G_BACKEND_EXPORT double mp3g_backend_analyzer_get_album_gain(void);
MP3G_BACKEND_EXPORT int mp3g_backend_scan_file(
    const char *filename,
    int include_gain,
    double *out_track_gain,
    double *out_max_sample,
    int *out_min_gain,
    int *out_max_gain
);
MP3G_BACKEND_EXPORT int mp3g_backend_album_scan_begin(void);
MP3G_BACKEND_EXPORT int mp3g_backend_album_scan_finish(double *out_album_gain);

MP3G_BACKEND_EXPORT int mp3g_backend_apply_gain_file(
    const char *filename,
    int left_gain_steps,
    int right_gain_steps,
    int wrap_gain_flag,
    int preserve_timestamp_flag,
    int use_temp_file_flag
);

MP3G_BACKEND_EXPORT int mp3g_backend_read_tags(
    const char *filename,
    mp3g_backend_tag_info *out_info
);
MP3G_BACKEND_EXPORT int mp3g_backend_write_tags(
    const char *filename,
    const mp3g_backend_tag_info *in_info,
    int tag_format,
    int preserve_timestamp_flag
);
MP3G_BACKEND_EXPORT int mp3g_backend_delete_tags(
    const char *filename,
    int tag_format,
    int preserve_timestamp_flag
);

#endif
