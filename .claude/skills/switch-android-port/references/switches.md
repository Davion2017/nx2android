# Host and backend switches (Android)

**How to set them:**
- **Start-up switches:** put them in the app's `env.txt` (`/sdcard/Android/data/<package>/files/env.txt`, one `KEY=VALUE` per line), then restart the app.
- **Live switches:** append `env KEY=VALUE` to `ctl.txt` while the game runs. These are re-read at each submission or present. `ctl.txt` needs a development build with `DM_CTL=<files>/ctl.txt` in `env.txt`; release builds ignore it.

The source of each switch is in `nxnative/dm/android/` unless noted. Check the code comment there before relying on a description below: switches are added and retired as bugs are found.

## Diagnostics

| Switch | When read | What it does |
|---|---|---|
| `DM_VK_VALIDATE=1` | start-up | Khronos validation layer; its messages go to the log. The APK must carry it (`mkapk.py --extra-so <libVkLayer_khronos_validation.so>`; built copy in `tools/vvl`) |
| `DM_VK_SHOTS=N` | live | save each of the next N presented frames as `frame_<n>.ppm` in the files folder (logs "frame shots: presents a to b") |
| `DM_VK_SHOT=n1,n2` | start-up | headless runs: save those presents (`DM_VK_SHOT_DIR`) |
| `DM_VK_PASSDUMP=1` / `=N` | live | dump each pass's first colour target and its depth (PPM, NaN counts, depth stretched) for one frame; `=N` waits N−1 presents first. **The dump adds barriers and depth reads, which can hide bugs** |
| `DM_VK_TRACE_PASS=-2` / `=n` | live | `-2` lists one submission's passes; `n` logs every draw of pass n once |
| `DM_VK_PASS_TIMES=1` | start-up | GPU timestamps around every pass; the per-frame line lists the costliest passes. Disturbs Adreno's binning: compare runs only |
| `DM_SLOWFRAME=1` | start-up (`gfx/nvn/hle_nvn.c`) | one `[slowframe]` line per dropped frame with a breakdown (frame, work, NVN, wait, thread and process CPU) |
| `DM_VK_LOG_UPLOADS=1` | start-up | which packaged textures are uploaded or re-uploaded |
| `DM_VK_SKIP_OPS`, `DM_VK_DBG_DRAW` | start-up | bisection aids: skip command kinds; 1 no draw calls, 2 no vertex buffers, 4 no descriptor sets |
| `DM_VK_NOCULL=1` | start-up | no face culling (test for winding bugs) |

## Behaviour toggles (for A/B; defaults are the fixes)

| Switch | When read | Default and meaning |
|---|---|---|
| `DM_VK_CB_DRAWS=N` | live | split the frame into command buffers every N draws (128), only before passes with a new depth image; `0` = never |
| `DM_VK_SUBMIT_SPLIT=0` | live | don't submit the pieces early |
| `DM_VK_X_CUTANY=1` | live | cut before any pass (the old rule that caused LRZ flicker) |
| `DM_VK_LRZ_TOUCH=0` | live | drop the one-texel depth read before passes that load a depth-stencil buffer (brings the menu-wipe flicker back) |
| `DM_VK_FLIPY=0` | live | the old clip-space y convention (pictures flip) |
| `DM_VK_X_NOBAR`, `X_DEPTH`, `X_COLOR` | live | cost measurements that **draw wrong**: no barrier before a pass; depth neither loaded nor stored; colour not loaded unless cleared |
| `DM_VK_X_NOSETC`, `X_NODRVC`, `X_LANDCUT`, `X_NOKEEP`, `X_NOSHC` | live | flicker experiments: no descriptor-set reuse; no driver-segment reuse; deferred uniform updates land at each cut; no pass kept for repeated targets; no uniform-shadow reuse |
| `DM_VK_DYN_UBO=0` | start-up | no dynamic uniform-buffer offsets (descriptor reuse drops) |
| `DM_VK_NOPREWARM=1` | start-up | no pipeline prewarm |
| `DM_VK_UBWC=1` | start-up | experiment: format lists instead of mutable formats on colour images |
| `DM_VK_SYNC_PRESENT=1` | start-up | present on the game thread instead of the present thread |

## Frame pacing and modes

| Switch | When read | Meaning |
|---|---|---|
| `DM_FPS_PIN=60/40/30` | live | hold that frame-rate step; any other value lets it adapt again |
| `DM_ADAPTIVE_FPS=0` | start-up | keep the game's own period |
| `DM_NO_ADPF=1` | start-up | no Android performance hints |
| `DM_OPMODE=0/1` | start-up (`host/hle_oe.c`) | handheld / docked at launch. The pause menu's Mode setting (`docked=` in `settings.txt`) overrides it and switches live |
| `DM_AUDIO=0` | start-up (`host/hle_audio.c`) | silent sink (Android defaults to real output) |

## Control file lines (`ctl.txt`)
- **Buttons:** `A`, `B`, `X`, `Y`, `L`, `R`, `ZL`, `ZR`, `Plus`, `Minus`, `Up`, `Down`, `Left`, `Right`, `LS`, `RS`.
- **Sticks:** `LUp`, `LDown`, `LLeft`, `LRight` (same for `R…`).
- **Hold and combine:** `~seconds` sets the hold (default 0.15), e.g. `A~0.2`. `+` combines keys.
- **Touch:** `T<x>x<y>` taps a normalized point.
- **Other lines:** `env KEY=VALUE`, `shot <path>`, `passdump <n>`, `drag x0 y0 x1 y1 [s]`. A line starting with `#` is ignored.
- **Delays:** an unknown key name logs `[RED]` but still waits its hold, so `none~0.1` works as a delay between lines.
- **Replay:** the reader starts at the file's end when the app launches; lines from earlier runs are never replayed.
