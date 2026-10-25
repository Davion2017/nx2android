// Android port: the on-screen gamepad's layout, shared by the touch handling (front_android.c) and its drawing (gfx_vk_present.c).
// Positions are fractions of the window: x of its width, y of its height; sizes are fractions of its height (round controls stay round on any aspect).
#pragma once
#include <math.h>
#include "dm_input.h"
enum { OV_STICK_L, OV_STICK_R, OV_BUTTON, OV_DPAD, OV_MENU };   // OV_MENU: the menu button (always shown, 70%): pauses the game and opens the settings
typedef struct { int kind; float x, y, r; uint64_t btn; const char *label; } ov_ctl;
// The layout: dm/android/overlay_default.tsv with the game profile's moves (android.tsv overlay rows), compiled by build.py into android_profile.h
#include "android_profile.h"
static const ov_ctl OV_CTLS[] = {DM_AOV_TABLE};
#define OV_N ((int)(sizeof OV_CTLS / sizeof *OV_CTLS))
#define OV_KNOB 0.42f        // a stick's knob radius, of the stick's
#define OV_MENU_ALPHA 0.70f
#define OV_FLASH_NS 180000000ll   // a pressed button's flash fades to its held glow in this time
// front_android.c → gfx_vk_present.c: what to draw (0 nothing, 1 the gamepad, 2 only the menu button: the player hid the gamepad or a controller is in use),
// where a stick's knob is (its offset from the stick's centre in stick radii, -1..1), and when each button was pressed (0 = not held; for the d-pad, its
// four directions by DM_BTN_* bit)
int dm_overlay_visible(void);
void dm_overlay_knob(int stick, float *dx, float *dy);
int64_t dm_overlay_pressed(int ctl, uint64_t bit);   // CLOCK_MONOTONIC ns of the press, 0 = not held
// the controls' size factor: 1, or more on a small screen so a face button stays at least OV_MIN_MM wide (sizes follow the window's height, which on a
// 6.7" phone made them 7 mm against 12 on an 8.8" tablet). Positions stay where they are
#define OV_MIN_MM 10.0f
float dm_overlay_scale(void);
static inline float ov_r(const ov_ctl *c) { return c->r * dm_overlay_scale(); }
// a d-pad direction's circle: centre offset and radius, in stick radii (k: 0 right, 1 left, 2 down, 3 up)
static inline void ov_dpad_dir(int k, float *ox, float *oy, float *r) { float s = 0.42f; *ox = k == 0 ? s * 1.2f : k == 1 ? -s * 1.2f : 0; *oy = k == 2 ? s * 1.2f : k == 3 ? -s * 1.2f : 0; *r = s * 0.75f; }
static const uint64_t OV_DPAD_BITS[4] = {DM_BTN_RIGHT, DM_BTN_LEFT, DM_BTN_DOWN, DM_BTN_UP};

// ---- the pause menu: a panel in the middle of the window, a title row and one row per item ----
enum { OVM_OVERLAY, OVM_RUMBLE, OVM_MODE, OVM_RESUME, OVM_N };   // OVM_MODE: Performance (handheld) or Resolution (docked)
#define OV_MENU_ROW 0.115f   // row height, of the window's height
#define OV_MENU_W 0.70f      // panel width, of the window's height
#define OV_MENU_PAD 0.03f
// what the menu shows (-1 = closed): bit 0 the gamepad is on, bit 1 rumble is on, bit 2 docked, bits 4..7 the highlighted item + 1 (0 = none)
int dm_menu_state(void);
static inline float ov_menu_scale(void) { float s = dm_overlay_scale(), fit = 0.92f / ((OVM_N + 1) * OV_MENU_ROW + 2 * OV_MENU_PAD); return s < fit ? s : fit; }
static inline void ov_menu_rect(float W, float H, float r[4]) {   // x, y, width, height in window pixels
    float s = ov_menu_scale(), pw = OV_MENU_W * H * s, ph = ((OVM_N + 1) * OV_MENU_ROW + 2 * OV_MENU_PAD) * H * s;
    if (pw > W * 0.96f) pw = W * 0.96f;
    r[0] = (W - pw) / 2; r[1] = (H - ph) / 2; r[2] = pw; r[3] = ph;
}
static inline int ov_menu_row_at(float x, float y, float W, float H) {   // the item under (x, y): 0..OVM_N-1, -1 the panel elsewhere, -2 outside it
    float r[4]; ov_menu_rect(W, H, r);
    if (x < r[0] || x >= r[0] + r[2] || y < r[1] || y >= r[1] + r[3]) return -2;
    float s = ov_menu_scale(), row = (y - r[1] - OV_MENU_PAD * H * s) / (OV_MENU_ROW * H * s);
    int i = (int)floorf(row) - 1;
    return i >= 0 && i < OVM_N ? i : -1;
}
