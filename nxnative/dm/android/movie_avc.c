// Android port: H.264 for the SDK's movie library (dm/host/hle_movie_avc.h). VideoToolbox's counterpart is MediaCodec; until it is wired up,
// a decoder takes the stream and produces no pictures (the movie decoder then plays the video track as black), reported once.
#include "hle_movie_avc.h"
#include <stdio.h>
#include <stdlib.h>
struct mavc { int rgba; };
mavc *mavc_new(void) {
    static int said; if (!said++) fprintf(stderr, "[dm] [RED] H.264 movie decoding is not available on Android yet: the video track stays black\n");
    return calloc(1, sizeof(mavc));
}
void mavc_free(mavc *a) { free(a); }
void mavc_param_sets(mavc *a, const uint8_t *p, size_t n) { (void)a; (void)p; (void)n; }
void mavc_avcc(mavc *a, const uint8_t *p, size_t n) { (void)a; (void)p; (void)n; }
int mavc_decode(mavc *a, const uint8_t *p, int n, int64_t pts_us) { (void)a; (void)p; (void)n; (void)pts_us; return 0; }
int mavc_take(mavc *a, int flush, uint8_t *nv12, int w, int h, int64_t *pts_us) { (void)a; (void)flush; (void)nv12; (void)w; (void)h; (void)pts_us; return 0; }
int mavc_queued(const mavc *a) { (void)a; return 0; }
void mavc_set_rgba(mavc *a) { a->rgba = 1; }
void mavc_drop(mavc *a) { (void)a; }
