#include "c_api_shim.h"

#include <stdlib.h>
#include <string.h>

#include "apetag.h"
#include "gain_analysis.h"
#include "id3tag.h"
#include "mp3gain.h"
#include "rg_error.h"

extern int wrapGain;
extern short int saveTime;
extern int UsingTemp;

static int g_backend_last_error_code = 0;
static char g_backend_last_error_message[1024] = {0};

static void backend_set_error_code_only(int code)
{
    g_backend_last_error_code = code;
    g_backend_last_error_message[0] = '\0';
}

static void backend_set_error_message(int code, const char *message)
{
    g_backend_last_error_code = code;
    g_backend_last_error_message[0] = '\0';
    if (message == NULL) {
        return;
    }
    strncpy(g_backend_last_error_message, message, sizeof(g_backend_last_error_message) - 1);
    g_backend_last_error_message[sizeof(g_backend_last_error_message) - 1] = '\0';
}

static void backend_capture_legacy_error_if_any(void)
{
    if (mp3gainerr != MP3GAIN_NOERROR) {
        if (mp3gainerrstr != NULL && mp3gainerrstr[0] != '\0') {
            backend_set_error_message((int)mp3gainerr, mp3gainerrstr);
            return;
        }
        backend_set_error_code_only((int)mp3gainerr);
    }
}

static void backend_free_file_tags(struct FileTagsStruct *file_tags)
{
    if (file_tags == NULL) {
        return;
    }
    if (file_tags->apeTag != NULL) {
        if (file_tags->apeTag->otherFields != NULL) {
            free(file_tags->apeTag->otherFields);
            file_tags->apeTag->otherFields = NULL;
        }
        free(file_tags->apeTag);
        file_tags->apeTag = NULL;
    }
    if (file_tags->lyrics3tag != NULL) {
        free(file_tags->lyrics3tag);
        file_tags->lyrics3tag = NULL;
    }
    if (file_tags->id31tag != NULL) {
        free(file_tags->id31tag);
        file_tags->id31tag = NULL;
    }
}

static void backend_to_out_info(
    const struct MP3GainTagInfo *tag_info,
    int tag_format,
    mp3g_backend_tag_info *out_info
)
{
    memset(out_info, 0, sizeof(*out_info));
    out_info->found = 1;
    out_info->tag_format = tag_format;

    out_info->have_track_gain = tag_info->haveTrackGain;
    out_info->have_track_peak = tag_info->haveTrackPeak;
    out_info->have_album_gain = tag_info->haveAlbumGain;
    out_info->have_album_peak = tag_info->haveAlbumPeak;
    out_info->have_undo = tag_info->haveUndo;
    out_info->have_minmax_gain = tag_info->haveMinMaxGain;
    out_info->have_album_minmax_gain = tag_info->haveAlbumMinMaxGain;

    out_info->track_gain = tag_info->trackGain;
    out_info->track_peak = tag_info->trackPeak;
    out_info->album_gain = tag_info->albumGain;
    out_info->album_peak = tag_info->albumPeak;

    out_info->undo_left = tag_info->undoLeft;
    out_info->undo_right = tag_info->undoRight;
    out_info->undo_wrap = tag_info->undoWrap;

    out_info->min_gain = (int)tag_info->minGain;
    out_info->max_gain = (int)tag_info->maxGain;
    out_info->album_min_gain = (int)tag_info->albumMinGain;
    out_info->album_max_gain = (int)tag_info->albumMaxGain;
}

static void backend_from_in_info(
    const mp3g_backend_tag_info *in_info,
    struct MP3GainTagInfo *tag_info
)
{
    memset(tag_info, 0, sizeof(*tag_info));

    tag_info->haveTrackGain = in_info->have_track_gain;
    tag_info->haveTrackPeak = in_info->have_track_peak;
    tag_info->haveAlbumGain = in_info->have_album_gain;
    tag_info->haveAlbumPeak = in_info->have_album_peak;
    tag_info->haveUndo = in_info->have_undo;
    tag_info->haveMinMaxGain = in_info->have_minmax_gain;
    tag_info->haveAlbumMinMaxGain = in_info->have_album_minmax_gain;

    tag_info->trackGain = in_info->track_gain;
    tag_info->trackPeak = in_info->track_peak;
    tag_info->albumGain = in_info->album_gain;
    tag_info->albumPeak = in_info->album_peak;

    tag_info->undoLeft = in_info->undo_left;
    tag_info->undoRight = in_info->undo_right;
    tag_info->undoWrap = in_info->undo_wrap;

    tag_info->minGain = (unsigned char)in_info->min_gain;
    tag_info->maxGain = (unsigned char)in_info->max_gain;
    tag_info->albumMinGain = (unsigned char)in_info->album_min_gain;
    tag_info->albumMaxGain = (unsigned char)in_info->album_max_gain;
}

int mp3g_backend_initialize(void)
{
    mp3g_backend_reset_error();
    return 0;
}

void mp3g_backend_shutdown(void)
{
    mp3g_backend_reset_error();
}

void mp3g_backend_reset_error(void)
{
    g_backend_last_error_code = 0;
    g_backend_last_error_message[0] = '\0';
    mp3gainerr = MP3GAIN_NOERROR;
    if (mp3gainerrstr != NULL) {
        free(mp3gainerrstr);
        mp3gainerrstr = NULL;
    }
}

int mp3g_backend_get_last_error_code(void)
{
    if (g_backend_last_error_code != 0) {
        return g_backend_last_error_code;
    }
    return (int)mp3gainerr;
}

int mp3g_backend_get_last_error_message(char *buffer, int buflen)
{
    if (buffer == NULL || buflen <= 0) {
        return -1;
    }
    buffer[0] = '\0';

    if (g_backend_last_error_message[0] != '\0') {
        strncpy(buffer, g_backend_last_error_message, (size_t)buflen - 1);
        buffer[buflen - 1] = '\0';
        return 0;
    }

    if (mp3gainerrstr != NULL && mp3gainerrstr[0] != '\0') {
        strncpy(buffer, mp3gainerrstr, (size_t)buflen - 1);
        buffer[buflen - 1] = '\0';
        return 0;
    }

    return 0;
}

int mp3g_backend_analyzer_init(long sample_rate)
{
    int rc = InitGainAnalysis(sample_rate);
    if (rc == INIT_GAIN_ANALYSIS_OK) {
        return 0;
    }
    backend_set_error_message(rc, "InitGainAnalysis failed");
    return rc;
}

int mp3g_backend_analyzer_reset_sample_frequency(long sample_rate)
{
    int rc = ResetSampleFrequency(sample_rate);
    if (rc == INIT_GAIN_ANALYSIS_OK) {
        return 0;
    }
    backend_set_error_message(rc, "ResetSampleFrequency failed");
    return rc;
}

int mp3g_backend_analyzer_feed_f64(
    const double *left,
    const double *right,
    size_t num_samples,
    int num_channels
)
{
    int rc = AnalyzeSamples(left, right, num_samples, num_channels);
    if (rc == GAIN_ANALYSIS_OK) {
        return 0;
    }
    backend_set_error_message(rc, "AnalyzeSamples failed");
    return rc;
}

double mp3g_backend_analyzer_get_title_gain(void)
{
    return GetTitleGain();
}

double mp3g_backend_analyzer_get_album_gain(void)
{
    return GetAlbumGain();
}

int mp3g_backend_scan_file(
    const char *filename,
    int include_gain,
    double *out_track_gain,
    double *out_max_sample,
    int *out_min_gain,
    int *out_max_gain
)
{
    int rc;
    unsigned char min_gain;
    unsigned char max_gain;
    double title_gain;
    double max_sample;

    if (filename == NULL || out_track_gain == NULL || out_max_sample == NULL ||
        out_min_gain == NULL || out_max_gain == NULL) {
        backend_set_error_message(-1, "filename and output pointers are required");
        return -1;
    }

    title_gain = 0.0;
    max_sample = 0.0;
    min_gain = 0;
    max_gain = 0;

    mp3g_backend_reset_error();
    rc = scanFile(
        (char *)filename,
        include_gain ? 1 : 0,
        &title_gain,
        &max_sample,
        &min_gain,
        &max_gain
    );
    backend_capture_legacy_error_if_any();
    if (rc != 0) {
        if (mp3g_backend_get_last_error_code() == 0) {
            backend_set_error_message(rc, "scanFile failed");
        }
        return rc;
    }

    *out_track_gain = title_gain;
    *out_max_sample = max_sample;
    *out_min_gain = (int)min_gain;
    *out_max_gain = (int)max_gain;
    return 0;
}

int mp3g_backend_album_scan_begin(void)
{
    mp3g_backend_reset_error();
    if (beginAlbumScan() != 0) {
        backend_capture_legacy_error_if_any();
        backend_set_error_message(-1, "beginAlbumScan failed");
        return -1;
    }
    return 0;
}

int mp3g_backend_album_scan_finish(double *out_album_gain)
{
    int rc;
    if (out_album_gain == NULL) {
        backend_set_error_message(-1, "out_album_gain is required");
        return -1;
    }
    mp3g_backend_reset_error();
    rc = finishAlbumScan(out_album_gain);
    backend_capture_legacy_error_if_any();
    if (rc != 0) {
        if (mp3g_backend_get_last_error_code() == 0) {
            backend_set_error_message(rc, "finishAlbumScan failed");
        }
        return rc;
    }
    return 0;
}

int mp3g_backend_apply_gain_file(
    const char *filename,
    int left_gain_steps,
    int right_gain_steps,
    int wrap_gain_flag,
    int preserve_timestamp_flag,
    int use_temp_file_flag
)
{
    int rc;
    if (filename == NULL || filename[0] == '\0') {
        backend_set_error_message(-1, "filename is required");
        return -1;
    }

    mp3g_backend_reset_error();
    wrapGain = wrap_gain_flag ? 1 : 0;
    saveTime = preserve_timestamp_flag ? 1 : 0;
    UsingTemp = use_temp_file_flag ? 1 : 0;

    rc = changeGain((char *)filename, left_gain_steps, right_gain_steps);
    backend_capture_legacy_error_if_any();
    if (rc != 0) {
        if (mp3g_backend_get_last_error_code() == 0) {
            backend_set_error_message(rc, "changeGain failed");
        }
        return rc;
    }
    return 0;
}

int mp3g_backend_read_tags(
    const char *filename,
    mp3g_backend_tag_info *out_info
)
{
    int ape_rc;
    int id3_rc;
    struct MP3GainTagInfo tag_info;
    struct FileTagsStruct file_tags;

    if (filename == NULL || out_info == NULL) {
        backend_set_error_message(-1, "filename and out_info are required");
        return -1;
    }

    memset(out_info, 0, sizeof(*out_info));
    memset(&tag_info, 0, sizeof(tag_info));
    memset(&file_tags, 0, sizeof(file_tags));

    ape_rc = ReadMP3GainAPETag((char *)filename, &tag_info, &file_tags);
    if (ape_rc > 0) {
        backend_to_out_info(&tag_info, MP3G_TAG_FORMAT_APEV2, out_info);
        backend_free_file_tags(&file_tags);
        return 0;
    }
    backend_free_file_tags(&file_tags);

    memset(&tag_info, 0, sizeof(tag_info));
    id3_rc = ReadMP3GainID3Tag((char *)filename, &tag_info);
    if (id3_rc > 0) {
        backend_to_out_info(&tag_info, MP3G_TAG_FORMAT_ID3, out_info);
        return 0;
    }

    return 0;
}

int mp3g_backend_write_tags(
    const char *filename,
    const mp3g_backend_tag_info *in_info,
    int tag_format,
    int preserve_timestamp_flag
)
{
    int rc;
    struct MP3GainTagInfo tag_info;
    struct MP3GainTagInfo existing_tag_info;
    struct FileTagsStruct file_tags;

    if (filename == NULL || in_info == NULL) {
        backend_set_error_message(-1, "filename and in_info are required");
        return -1;
    }

    mp3g_backend_reset_error();
    memset(&file_tags, 0, sizeof(file_tags));
    memset(&existing_tag_info, 0, sizeof(existing_tag_info));
    backend_from_in_info(in_info, &tag_info);

    if (tag_format == MP3G_TAG_FORMAT_APEV2) {
        /* Load side tag containers from file, but keep caller-provided MP3Gain values intact. */
        (void)ReadMP3GainAPETag((char *)filename, &existing_tag_info, &file_tags);
        rc = WriteMP3GainAPETag((char *)filename, &tag_info, &file_tags, preserve_timestamp_flag ? 1 : 0);
        backend_free_file_tags(&file_tags);
        if (rc > 0) {
            return 0;
        }
        backend_set_error_message(rc, "WriteMP3GainAPETag failed");
        return rc == 0 ? -1 : rc;
    }

    if (tag_format == MP3G_TAG_FORMAT_ID3) {
        rc = WriteMP3GainID3Tag((char *)filename, &tag_info, preserve_timestamp_flag ? 1 : 0);
        if (rc > 0) {
            return 0;
        }
        backend_set_error_message(rc, "WriteMP3GainID3Tag failed");
        return rc == 0 ? -1 : rc;
    }

    backend_set_error_message(-1, "unsupported tag_format");
    return -1;
}

int mp3g_backend_delete_tags(
    const char *filename,
    int tag_format,
    int preserve_timestamp_flag
)
{
    int rc;
    if (filename == NULL) {
        backend_set_error_message(-1, "filename is required");
        return -1;
    }

    mp3g_backend_reset_error();

    if (tag_format == MP3G_TAG_FORMAT_APEV2 || tag_format == MP3G_TAG_FORMAT_NONE) {
        rc = RemoveMP3GainAPETag((char *)filename, preserve_timestamp_flag ? 1 : 0);
        if (rc <= 0) {
            backend_set_error_message(rc, "RemoveMP3GainAPETag failed");
            return rc == 0 ? -1 : rc;
        }
    }

    if (tag_format == MP3G_TAG_FORMAT_ID3 || tag_format == MP3G_TAG_FORMAT_NONE) {
        rc = RemoveMP3GainID3Tag((char *)filename, preserve_timestamp_flag ? 1 : 0);
        if (rc <= 0) {
            backend_set_error_message(rc, "RemoveMP3GainID3Tag failed");
            return rc == 0 ? -1 : rc;
        }
    }

    return 0;
}
