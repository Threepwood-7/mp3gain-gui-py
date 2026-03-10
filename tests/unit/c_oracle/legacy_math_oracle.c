#include <math.h>
#include <stdint.h>

/*
 * Minimal C oracle wrappers for legacy math and tag-update snippets
 * mirrored from mp3gain-1_5_2-src/mp3gain.c.
 */

#if defined(_WIN32) || defined(__CYGWIN__)
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif

typedef struct mp3gain_tag_state {
    int dirty;

    int have_undo;
    int undo_left;
    int undo_right;
    int undo_wrap;

    int have_track_gain;
    double track_gain;
    int have_track_peak;
    double track_peak;

    int have_album_gain;
    double album_gain;
    int have_album_peak;
    double album_peak;

    int have_minmax_gain;
    int min_gain;
    int max_gain;

    int have_album_minmax_gain;
    int album_min_gain;
    int album_max_gain;
} mp3gain_tag_state;

static int legacy_round_to_int(double value) {
    double abs_value = fabs(value);
    int truncated = (int)abs_value;
    double frac = abs_value - (double)truncated;
    int rounded = frac < 0.5 ? truncated : truncated + 1;
    return value < 0.0 ? -rounded : rounded;
}

EXPORT int mp3gain_c_legacy_round(double value) {
    return legacy_round_to_int(value);
}

EXPORT int mp3gain_c_db_to_steps(double db_gain, int mp3_gain_mod) {
    double dbl_gain_change = db_gain / (5.0 * log10(2.0));
    return legacy_round_to_int(dbl_gain_change) + mp3_gain_mod;
}

EXPORT double mp3gain_c_steps_to_db_exact(int steps) {
    return ((double)steps) * (5.0 * log10(2.0));
}

EXPORT double mp3gain_c_steps_to_db_approx(int steps) {
    return ((double)steps) * 1.505;
}

EXPORT int mp3gain_c_autoclip_track_gain(int requested_steps, double max_sample_pcm) {
    if (max_sample_pcm <= 0.0) {
        return requested_steps;
    }
    int max_no_clip = (int)(floor(4.0 * log10(32767.0 / max_sample_pcm) / log10(2.0)));
    if (requested_steps > max_no_clip) {
        return max_no_clip;
    }
    return requested_steps;
}

EXPORT int mp3gain_c_autoclip_album_gain(int requested_steps, double album_peak_norm) {
    if (album_peak_norm <= 0.0) {
        return requested_steps;
    }
    int max_no_clip = (int)(floor(-4.0 * log10(album_peak_norm) / log10(2.0)));
    if (requested_steps > max_no_clip) {
        return max_no_clip;
    }
    return requested_steps;
}

EXPORT void mp3gain_c_update_tag_state(
    mp3gain_tag_state *tag,
    int left_gain_change,
    int right_gain_change,
    int wrap_gain
) {
    if (tag == 0) {
        return;
    }

    if (left_gain_change == 0 && right_gain_change == 0) {
        return;
    }

    if (!tag->have_undo) {
        tag->undo_left = 0;
        tag->undo_right = 0;
    }
    tag->dirty = 1;
    tag->undo_right -= right_gain_change;
    tag->undo_left -= left_gain_change;
    tag->undo_wrap = wrap_gain;
    tag->have_undo = 1;

    if (left_gain_change != right_gain_change) {
        return;
    }

    {
        int step = left_gain_change;
        double dbl_gain_change = ((double)step) * 1.505;
        double peak_mult = pow(2.0, ((double)step) / 4.0);
        int cur_min;
        int cur_max;

        if (tag->have_track_gain) {
            tag->track_gain -= dbl_gain_change;
        }
        if (tag->have_track_peak) {
            tag->track_peak *= peak_mult;
        }
        if (tag->have_album_gain) {
            tag->album_gain -= dbl_gain_change;
        }
        if (tag->have_album_peak) {
            tag->album_peak *= peak_mult;
        }

        if (tag->have_minmax_gain) {
            cur_min = tag->min_gain + step;
            cur_max = tag->max_gain + step;
            if (wrap_gain) {
                if (cur_min < 0 || cur_min > 255 || cur_max < 0 || cur_max > 255) {
                    tag->have_minmax_gain = 0;
                }
            } else {
                if (tag->min_gain == 0) {
                    tag->min_gain = 0;
                } else if (cur_min < 0) {
                    tag->min_gain = 0;
                } else if (cur_min > 255) {
                    tag->min_gain = 255;
                } else {
                    tag->min_gain = cur_min;
                }

                if (cur_max < 0) {
                    tag->max_gain = 0;
                } else if (cur_max > 255) {
                    tag->max_gain = 255;
                } else {
                    tag->max_gain = cur_max;
                }
            }
        }

        if (tag->have_album_minmax_gain) {
            cur_min = tag->album_min_gain + step;
            cur_max = tag->album_max_gain + step;
            if (wrap_gain) {
                if (cur_min < 0 || cur_min > 255 || cur_max < 0 || cur_max > 255) {
                    tag->have_album_minmax_gain = 0;
                }
            } else {
                if (tag->album_min_gain == 0) {
                    tag->album_min_gain = 0;
                } else if (cur_min < 0) {
                    tag->album_min_gain = 0;
                } else if (cur_min > 255) {
                    tag->album_min_gain = 255;
                } else {
                    tag->album_min_gain = cur_min;
                }

                if (cur_max < 0) {
                    tag->album_max_gain = 0;
                } else if (cur_max > 255) {
                    tag->album_max_gain = 255;
                } else {
                    tag->album_max_gain = cur_max;
                }
            }
        }
    }
}
