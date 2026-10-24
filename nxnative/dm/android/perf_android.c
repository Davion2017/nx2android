// Android port: display rate and CPU performance hints for the presents (gfx_vk_present.c calls dm_perf_frame before each present).
// - Display rate: Android's FIFO swapchain follows the display, which on many devices runs at 90, 120 or 144 Hz; the NVN layer paces
//   presents to the game's period (hle_nvn.c acquire), and the window asks the display for a rate that period divides (dm_perf_window).
// - ADPF (APerformanceHint, Android 13): the presenting thread reports how long each frame's work took against the frame period, so the
//   CPU governor raises clocks before a frame runs late instead of after (the hint is ignored where the API is missing).
#include <android/native_window.h>
#include <dlfcn.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <dirent.h>
#include <sys/syscall.h>
#include "dm.h"

typedef struct APerformanceHintManager APerformanceHintManager;
typedef struct APerformanceHintSession APerformanceHintSession;
static struct {
    APerformanceHintManager *(*get)(void);
    APerformanceHintSession *(*create)(APerformanceHintManager *, const int32_t *, size_t, int64_t);
    int (*update)(APerformanceHintSession *, int64_t);
    int (*report)(APerformanceHintSession *, int64_t);
    int (*set_threads)(APerformanceHintSession *, const int32_t *, size_t);
} H;
static APerformanceHintSession *g_hint; static int64_t g_hint_target; static int32_t g_hint_tids[8]; static int g_hint_n;

static int64_t perf_now(void) { struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return (int64_t)ts.tv_sec * 1000000000 + ts.tv_nsec; }

static void hint_init(int64_t target) {
    static int tried; if (tried) return; tried = 1;
    if (getenv("DM_NO_ADPF")) return;
    void *lib = dlopen("libandroid.so", RTLD_NOW); if (!lib) return;
    H.get = dlsym(lib, "APerformanceHint_getManager"); H.create = dlsym(lib, "APerformanceHint_createSession");
    H.update = dlsym(lib, "APerformanceHint_updateTargetWorkDuration"); H.report = dlsym(lib, "APerformanceHint_reportActualWorkDuration");
    H.set_threads = dlsym(lib, "APerformanceHint_setThreads");   // Android 14
    if (!H.get || !H.create || !H.report) { LOG("[perf] no APerformanceHint on this Android: CPU hints off"); return; }
    APerformanceHintManager *m = H.get(); if (!m) return;
    g_hint_tids[0] = (int32_t)gettid(); g_hint_n = 1;
    g_hint = H.create(m, g_hint_tids, (size_t)g_hint_n, target); g_hint_target = target;
    LOG("[perf] ADPF session %s (target %.2f ms, thread %d)", g_hint ? "open" : "refused", target / 1e6, g_hint_tids[0]);
}
// The other threads that do frame work: the presenting thread is the game's render thread, and its main thread (the simulation) and job workers set
// the pace as much. Every 300 frames the threads that used at least 15% of a core since the last look join the session (up to 5 besides the
// presenting one), the ones that went idle leave it. Without them NEO's main thread ran on mid cores at 1.9 of 3.5 GHz and its bursts made
// 45 to 80 ms frames. Needs APerformanceHint_setThreads (Android 14)
static uint64_t task_ticks(int tid) {
    char p[64], b[512]; snprintf(p, sizeof p, "/proc/self/task/%d/stat", tid);
    FILE *f = fopen(p, "r"); if (!f) return 0;
    size_t n = fread(b, 1, sizeof b - 1, f); fclose(f); b[n] = 0;
    char *c = strrchr(b, ')'); if (!c) return 0;
    unsigned long long ut = 0, st = 0; int field = 2;
    for (char *t = c + 1; *t && field < 15; t++) if (*t == ' ') { field++; if (field == 14) ut = strtoull(t + 1, NULL, 10); else if (field == 15) st = strtoull(t + 1, NULL, 10); }
    return ut + st;
}
static void hint_threads_scan(int32_t self) {
    static struct { int tid; uint64_t ticks; } prev[512]; static int np; static int64_t last;
    int64_t now = perf_now(); double secs = last ? (now - last) / 1e9 : 0; last = now;
    DIR *d = opendir("/proc/self/task"); if (!d) return;
    struct { int tid; uint64_t used; } cur[512]; int nc = 0; struct dirent *e;
    while ((e = readdir(d)) && nc < 512) { int tid = atoi(e->d_name); if (tid <= 0) continue; cur[nc].tid = tid; cur[nc].used = task_ticks(tid); nc++; }
    closedir(d);
    int32_t pick[8]; int npick = 0; pick[npick++] = self;
    if (secs > 0) {
        long hz = sysconf(_SC_CLK_TCK); double need = 0.15 * secs * (double)(hz > 0 ? hz : 100);
        for (int k = 0; k < 5; k++) {   // the busiest first
            int best = -1; uint64_t bu = 0;
            for (int i = 0; i < nc; i++) {
                if (cur[i].tid == self) continue;
                int taken = 0; for (int j = 0; j < npick; j++) taken |= pick[j] == cur[i].tid; if (taken) continue;
                uint64_t was = 0; for (int j = 0; j < np; j++) if (prev[j].tid == cur[i].tid) { was = prev[j].ticks; break; }
                uint64_t u = cur[i].used > was ? cur[i].used - was : 0;
                if (was && u >= need && u > bu) { bu = u; best = i; }
            }
            if (best < 0) break;
            pick[npick++] = cur[best].tid;
        }
    }
    np = 0; for (int i = 0; i < nc; i++) { prev[np].tid = cur[i].tid; prev[np].ticks = cur[i].used; np++; }
    if (!g_hint || !H.set_threads) return;
    int same = npick == g_hint_n; for (int i = 0; same && i < npick; i++) { int in = 0; for (int j = 0; j < g_hint_n; j++) in |= g_hint_tids[j] == pick[i]; same = in; }
    if (same) return;
    if (H.set_threads(g_hint, pick, (size_t)npick)) { LOG("[perf] ADPF: the session refused threads"); return; }
    memcpy(g_hint_tids, pick, sizeof(int32_t) * (size_t)npick); g_hint_n = npick;
    char l[160]; size_t o = 0; for (int i = 0; i < npick; i++) o += snprintf(l + o, sizeof l - o, " %d", pick[i]);
    LOG("[perf] ADPF session threads:%s", l);
}

static int64_t g_work_start;
// ---- adaptive frame rate: when the frames do not fit the period the game asks for, presentation steps to a longer one the display divides evenly
// (60 → 40 → 30 fps; 40 asks the display for 120 Hz), and back when they fit the shorter one with room; a steady rate instead of alternating
// one-vsync and two-vsync frames. DM_ADAPTIVE_FPS=0 keeps the game's own period.
static const int64_t STEPS[] = {16666667, 25000000, 33333333};   // 60, 40, 30 fps
static int g_step = 0, g_adapt = -1; static int64_t g_work_hist[64]; static int g_nwork;
static int64_t g_last_change, g_last_up, g_up_hold = 2000000000; static int g_ok_frames; static uint64_t g_game_period;   // the period the game asks for, before the adaptive step
static int64_t work_p95(void) {   // the 95th percentile of the last 64 frames' work
    int n = g_nwork < 64 ? g_nwork : 64; if (n < 16) return 0;
    int64_t v[64]; memcpy(v, g_work_hist, sizeof(int64_t) * (size_t)n);
    for (int i = 1; i < n; i++) { int64_t x = v[i]; int j = i - 1; while (j >= 0 && v[j] > x) { v[j + 1] = v[j]; j--; } v[j + 1] = x; }
    return v[(n * 95) / 100];
}
uint64_t dm_present_period_adapt(uint64_t period) {
    if (g_adapt < 0) { const char *e = getenv("DM_ADAPTIVE_FPS"); g_adapt = !(e && !atoi(e)); }
    if (!g_adapt || !period) return period;
    g_game_period = period;
    int64_t want = STEPS[g_step];
    return (uint64_t)want > period ? (uint64_t)want : period;   // never faster than the game asks
}
static void adapt_frame(int64_t work, int64_t now) {
    if (!g_adapt) return;
    g_work_hist[g_nwork++ % 64] = work;
    { static unsigned k; if (++k % 600 == 0) LOG("[perf] adaptive frame rate: %.0f fps, frame work p95 %.1f ms (last %.1f ms)", 1e9 / STEPS[g_step], work_p95() / 1e6, work / 1e6); }
    if (now - g_last_change < 2000000000) return;   // 2 s between changes
    int64_t p95 = work_p95(); if (!p95) return;
    int nsteps = (int)(sizeof STEPS / sizeof *STEPS);
    if (g_step + 1 < nsteps && p95 > STEPS[g_step] * 95 / 100) {
        // back down soon after a step up: the next try waits twice as long (up to a minute), so the rate does not swing between two steps
        if (g_last_up && now - g_last_up < 10000000000ll) { g_up_hold = g_up_hold * 2 > 60000000000ll ? 60000000000ll : g_up_hold * 2; }
        g_step++; g_last_change = now; g_nwork = 0; g_ok_frames = 0; LOG("[perf] adaptive frame rate: %.0f fps (frames p95 %.1f ms)", 1e9 / STEPS[g_step], p95 / 1e6); return; }
    if (g_step > 0 && p95 < STEPS[g_step - 1] * 80 / 100) { if (++g_ok_frames > 120 && now - g_last_change >= g_up_hold) { g_step--; g_last_change = g_last_up = now; g_nwork = 0; g_ok_frames = 0; LOG("[perf] adaptive frame rate: %.0f fps (frames p95 %.1f ms)", 1e9 / STEPS[g_step], p95 / 1e6); } }
    else g_ok_frames = 0;
}
// hle_nvn.c, the first acquire after a present, right after its pacing wait. A frame's work is the time between two presents less that wait: what the
// render thread waited for besides the pacing (the game's main thread, its own syncs) is the frame's work too, or the hint would never ask for
// the clock a slow main thread needs
static int64_t g_prev_present, g_pace;
void dm_perf_frame_start(uint64_t pace_ns) { g_work_start = perf_now(); g_pace = (int64_t)pace_ns; }
// Called on the presenting thread right before a present; period in seconds (1/60, 1/30, ...).
void dm_perf_frame(double period) {
    int64_t p = period > 0 && period < 1 ? (int64_t)(period * 1e9) : 16666667, t = perf_now();
    // the CPU hint's target is the game's own period, not the adaptive one: with the longer target the CPU clocks drop until the work fills it,
    // and the work then never shows the room to step back up (NEO stayed at 30 fps with frames of 31 to 48 ms)
    if (g_game_period && (int64_t)g_game_period < p) p = (int64_t)g_game_period;
    hint_init(p);
    if (g_work_start) {   // (a longer span: the game was held, by the pause menu or the background)
        int64_t w = g_prev_present ? t - g_prev_present - g_pace : t - g_work_start;
        if (w > 0 && w < 250000000) { adapt_frame(w, t); if (g_hint) H.report(g_hint, w); }
        g_work_start = 0;
    }
    g_prev_present = t;
    static unsigned frames; if (frames++ % 300 == 0) hint_threads_scan((int32_t)gettid());
    if (!g_hint) return;
    if (p != g_hint_target && H.update) { H.update(g_hint, p); g_hint_target = p; }
}

// The window's frame rate: the game's rate, so the display can pick a mode it divides (60 / 120 Hz rather than 144 Hz for a 60 fps game).
void dm_perf_window(ANativeWindow *w, double fps) {
    if (!w || fps <= 0) return;
    int r = ANativeWindow_setFrameRate(w, (float)fps, ANATIVEWINDOW_FRAME_RATE_COMPATIBILITY_FIXED_SOURCE);
    LOG("[perf] window frame rate %.0f fps%s", fps, r ? " refused" : "");
}

