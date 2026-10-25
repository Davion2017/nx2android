---
name: switch-android-port
description: Port a Nintendo Switch game to Android with nx2android (porter, nxnative's Android host in nxnative/dm/android, the NVN-to-Vulkan replay backend) and bring it up on a real device - boot failures, rendering bugs (flicker, upside-down pictures, refused submissions, wrong textures), frame pacing and performance, the on-device test loop (env.txt, ctl.txt, soaks, screen recordings, pass dumps) and release builds. Use whenever the user wants a game ported to or fixed on Android, a new title brought up on the tablet, a rendering or speed problem in an Android port investigated, or device tests run, even if they don't name this skill. Built from the NEO - The World Ends with You port (references/neo-case-study.md).
---

# Porting a Switch game to Android

nx2android runs a Switch game's own ARM64 code natively on Android. A rewriter patches the few instructions Android can't run, a host answers the Switch's system calls, and the game's NVN graphics commands are replayed through Vulkan. This skill is the working method that got NEO: The World Ends with You from game files to a playable, crash-free app in about a day, and the traps that cost the most time on the way.

Read first, in this order:
1. `docs/ARCHITECTURE.md`: the layers (core, profile, porter, gui, devtools) and their rules, the port pipeline, how to add a game.
2. `nxnative/docs/agents/README.md` and pages 01–05: upstream's guide for extraction, survey, host bring-up (a catalogue of failure patterns), graphics and debugging. It was written for Apple. Everything there about the rewriter, the host and profiles applies on Android too; the Metal parts don't.
3. `references/neo-case-study.md`: what actually happened with NEO, bug by bug, with numbers.
4. `references/switches.md`: every host and backend switch, and whether it can be changed while the game runs.

## Ground rules

These came from mistakes, not theory.

- **The user's files and keys stay out of the repository and the app.** Game files, extracted data, keys and anything derived from game art stay in the game's own folder (`<NSP folder>/<title ID>-work`, `<title ID>_build`). Print key names, never values.
- **The device is shared.** The user may be holding it or playing. Before driving it (installing, restarting, pressing buttons), check what is on screen. If the user is using it, ask. Ask before installing a test app, and uninstall it afterwards.
- **Never press A (confirm) blindly in the user's save.** Blind presses advanced NEO's story. Boot to gameplay with a check after every press, and make soak tests move only the stick and camera.
- **Test on screen, in the app.** Headless `dmhost` runs are fine for the first frames. After that, users want to watch, and some bugs exist only in the app (a stack-scan crash appeared only under NativeActivity).
- **Measure before and after every change, in the same scene.** Numbers from different scenes aren't comparable. Prefer an A/B with a live switch inside one run over two separate runs.
- **Commit only when the user asks**, with `git -c user.name=seedds -c user.email=seedds@gmail.com commit`. Another session working in the same repository can't approve a commit for the user.
- **General fixes go in the core, per-game facts in the profile.** `nxnative/dm/games/<id>/android.tsv` holds Android-only keys; no title IDs in code. Comments may name the game a rule was found with, and should give the evidence (`AGENTS.md`, `docs/ARCHITECTURE.md`).

## The workflow

Each phase says what "done" means. Don't move on with the current phase half done; the next one hides its bugs.

### 0. Know the device (new GPU family or phone only)
On a device or GPU family not tried before, run `probes/` (cpuprobe, vkprobe, vkzc) and compare with `RESEARCH.md` §6. Things to check:
- x18 is preserved;
- `cntpct_el0` raises SIGILL (it must be rewritten);
- BCn textures are supported;
- an Android hardware buffer can be mapped at a fixed guest address (MAP_FIXED; the zero-copy memory pools depend on this).

Done when every assumption in §6 is confirmed or the design has been adapted.

### 1. Port it
```bash
python -m porter port "<game folder>" --experimental --debug --install
```
This runs extract → rewrite (`patch_nso.py`, `DM_TARGET=android`) → shader split → SPIR-V bundle (`shader_vk.py`) → host (`build.py`) → APK (`mkapk.py`) → data pack → install.
- Use `--debug` while bringing a game up: it gives a development build with debug info, a debuggable APK and `DM_CTL` (see the device loop).
- `--experimental` starts from the survey's provisional profile in `<title ID>_build/profile/`.
- Read the survey (`<title ID>_survey/survey.md`) for the SDK, engine, NVN surface and modules.

Watch these counts:
- **Rewriter sites per module.** Check them against `insn_census.py`.
- **Shaders translated vs total.** "No output" shaders are skipped draws later. NEO started at 25,514 of 25,523; a translator fix found with the next game made it 25,523 of 25,523.

Done when the APK installs and the data pack is on the device.

### 2. Boot to the frame loop
Read `log.txt` and work through the failure catalogue in `nxnative/docs/agents/03-bringup.md`. Android-specific causes seen so far:

| Symptom | Cause | Fix |
|---|---|---|
| `svcBreak` in nninitStartup / StandardAllocator, intermittent | the alignment of the big alias region depended on where Android placed it (ASLR) | over-reserve, then trim to the alignment the SDK wants (`host/hle_svc.c`) |
| SIGSEGV only in the app, about 16 MB below sp, in a garbage collector | IL2CPP's GC scans the main thread's stack from its reported bottom, which included a guard page | mmap the stack yourself, hand it over with `pthread_attr_setstack` (`front_android.c`) |
| null-pointer crash after a few frames | RomFS incomplete (a push still running) | check the file count and size on the device before debugging |
| link lists dozens of missing `mtl_*` symbols | expected: that list is the graphics backend's contract | implement them; a null backend boots without graphics |

Done when the game reaches its frame loop and presents frames (the per-frame `timing up to frame` lines appear).

### 3. First correct frames
Get the logo and title screen right before any 3D scene. Early breakages and their causes:
- **Frames that never appear:** a present path that returns early without completing its ticket.
- **Every draw skipped as "no program":** NVN binds vertex and fragment programs separately by stage mask, so a bind must replace only the masked stages.
- **Upside-down pictures:** NVN's upper-left origin means clip-space y points up, like Metal. That calls for a negative-height viewport with the scissor left alone. An even number of copies hides a wrong convention, so check docked and handheld.

Done when the title screen and one 3D scene match screenshots of the real game.

### 4. Correctness on device
Use the debugging playbook below. Done when the user has played it and reports nothing wrong. The user can compare against a real Switch; take that comparison seriously ("flicker is our bug, I've tested on switch").

### 5. Performance
Use the performance playbook below. Agree the target with the user early: for NEO it moved from "60 fps" to "30+ fps, adaptive to the display, playable".

### 6. The front end
The on-screen gamepad (layout in `dm/android/overlay_default.tsv` plus the profile's `android.tsv`; never edit `overlay_layout.h`'s table), the pause menu (settings in the files folder's `settings.txt`), external controllers (by position, Switch style), vibration, audio (AAudio; real output is on by default on Android) and the Performance/Resolution mode switch (`dm_set_opmode`).
- Phones: controls scale with screen density so a face button stays at least 10 mm wide, capped at ×1.45.
- The game's own UI: check what it really shows before wiring host data into it. NEO's battery-shaped icon is its level gauge, and the game never calls `nn::psm`.

### 7. Stability
- Run `devtools/soak.sh 30 <log>` in gameplay (movement only). Expect the same process id all 30 minutes and no new `[RED]` lines.
- A play session by the user counts too. The read-only watcher in `scripts/` records it without sending input.
- Re-run the soak on the build you hand over.

### 8. Release build
`porter port` without `--debug` (or `build.py --release` plus `mkapk.py --release`): no debug info, stripped, not debuggable, and `DM_CTL` ignored. Boot it with `adb shell input swipe` holds, since `ctl.txt` no longer works. NEO's APK went from 6.3 MB to 1.5 MB with the same `-O2` code.

## The device loop

```bash
eval "$(python devtools/device.py --sh)"     # sets ADB, PKG, F (the app's files folder) from devtools/device.json
export MSYS_NO_PATHCONV=1                     # Git Bash: keeps /sdcard and /data paths intact
```
- **`env.txt`** in the files folder holds `KEY=VALUE` switches read at start (restart the app after changing it). Put `DM_CTL=<files>/ctl.txt` there in development builds.
- **`ctl.txt`** lines take effect while the game runs:
  - `A~0.2` (press A for 0.2 s), `LUp~0.8`, `X`;
  - `env KEY=VALUE` changes a switch the backend re-reads at each submission or present;
  - `shot <path>`, `passdump <n>`.

  Use `scripts/ctl.sh 'X' 'B~0.15'` to append lines. The reader starts at the file's end on launch (it used to replay all old lines, which walked menus and pressed A by itself). If presses act strangely, compare `grep -c 'DM_CTL: press' log.txt` with what you sent.
- **Pressing keys:** `adb shell input tap` is too short for many games; use `input swipe x y x y 150` as a held press, or `A~0.2` in `ctl.txt`.
- **Getting to gameplay:** `scripts/boot_to_gameplay.sh` restarts the app and presses A only while a detector says the screen isn't gameplay yet.
  - The detector has to be per game: a bright title screen fooled a brightness test.
  - It must pass twice in a row, so a bright intro picture doesn't count.
- **The log:** `log.txt` is the current run and `log.prev.txt` the run before (each launch rotates them). After a crash, read the log before relaunching twice.
  - Per-frame lines worth grepping: `timing up to frame` (frame time p50/p95/max), `replay per frame` (draws, replay ms, GPU busy, descriptor reuse), `adaptive frame rate`, `passes by GPU time`.
- **Big transfers:** `adb push -Z` (no compression) or `devtools/push_chunked.py`. Compressed pushes of GBs wedged adbd over USB repeatedly. Wi-Fi adb (`adb tcpip 5555`) was steadier. Don't restart the adb server while a transfer hangs.
- **Background loops:** kill leftover loops when you stop a test (`TaskStop` may leave the shell's children running). A forgotten soak kept moving the stick and was mistaken for an input bug.

## Debugging playbook

| You see | First move | Causes found so far |
|---|---|---|
| Whole frames dropped; `VK_ERROR_OUT_OF_HOST_MEMORY` at `vkEndCommandBuffer`; looks like a fixed draw limit | build with the Khronos validation layer (`mkapk.py --extra-so .../libVkLayer_khronos_validation.so`, `DM_VK_VALIDATE=1`) | an image view made for sampling reused as a render target (cache key without usage). Bisecting draws on the device finds *where*, not *why* |
| Flicker: blocks of near objects vanish or change colour for a frame | record the screen (`devtools/rec_flicker.py`) and count bad frames; screenshots miss it | Adreno's low-resolution depth (LRZ) going stale: (1) at command-buffer cuts between passes sharing a depth buffer, (2) when a pass reloads a depth-stencil buffer in the same command buffer. Fixes: cut only before passes with a new depth image; a one-texel depth read before load passes (`lrz_touch`) |
| A glitch in a transition lasting 1–2 frames | `env DM_VK_SHOTS=N` right after the trigger: is it in the game's output or added at presentation? | the second LRZ case above |
| Fog everywhere, missing ground, dark silhouettes | pass dumps (`DM_VK_PASSDUMP`) incl. depth; try `DM_VK_NOCULL=1` | inverted front-face winding culled the ground, so depth was empty and the fog maxed out |
| Picture upside down in one mode only | pass dumps of each copy in that mode's chain | wrong clip-space y convention; an odd number of copies shows it |
| Shadows detached from characters, distant people flicker | check deferred uniform updates and the shadow copies built from them | a shadow mixed the newest update with memory a still-running GPU copy had not written yet |
| Brown/odd flat colour where a texture should be | `[alias] stale read` log lines (textures over the same memory with different descriptions are separate images); the fallback textures are black, so a non-black flat colour isn't the fallback | in NEO this was LRZ, not aliasing |
| No sound | look for "silent sink" in the log | real output was on by default for iOS only |
| Black screen, 0 draws in some runs | shader bundle lookups before it opened | `pthread_once` around the bundle open |

Method rules:
- **Make the bug countable first.** Turn "it flickers sometimes" into "58 of 118 frames bad" with `rec_flicker.py` or a colour-match count over frame shots (`scripts/count_matching_frames.py`). Then every change is a number.
- **Toggle, don't edit.** Most backend behaviours have a live switch (`references/switches.md`). Flip one with a `ctl.txt` `env` line and count again in the same run. If a switch you need is missing, add one, read in `x_read()` so it changes live.
- **Kill wrong theories fast with counters.** A CPU/GPU race theory died when a counter showed 0 races in about 3M reads; a texture-aliasing theory died at 0 stale reads.
- **Check that the tool isn't the cure.** The pass dump's own depth copy hid the brown wipe. When a debugging tool makes the bug disappear, repeat each thing the tool does on its own: that finds the fix.
- **Pin the frame with a countdown.** `DM_VK_PASSDUMP=N` waits N−1 presents. Arm it with `DM_VK_SHOTS` in the same `ctl.txt` write; the log order tells which present it caught. Expect to retry: frame timing jitters by one.

## Performance playbook

1. **Read the per-frame line first:** replay ms (CPU), GPU busy ms, draws and passes, descriptor reuse. GPU busy depends on clocks, so compare at the same frame rate.
2. **Overlap the CPU replay with the GPU.** Submit in pieces (`DM_VK_CB_DRAWS`, every 128 draws, between passes only). NEO went from 36.7 to 15.7 ms. Mind the LRZ cut rule.
3. **Cut passes.** Defer uniform updates instead of ending the pass, and keep the pass when the same targets are set again. NEO went from 145 passes for 148 draws to 28.
4. **Reuse descriptor sets.** Dynamic uniform-buffer offsets took NEO's reuse from 6% to 86%. Add a texture-view cache per submission.
5. **Frame pacing:**
   - The adaptive governor (`perf_android.c`) steps 60/40/30 fps and asks the display for a matching rate.
   - It judges p90 of frame work after 4 s at a new rate, because clocks need seconds to ramp.
   - Keep the ADPF target at the game's own period, or the clocks fall to fill the longer one.
   - Make sure frame start is recorded on every present path: NEO's governor never ran until that was fixed.
6. **Threads:** if hitches remain, sample per-thread core and CPU clocks over adb (`/proc/<pid>/task/*/stat`, cpufreq).
   - NEO's main thread was outside the ADPF session, on half-clocked mid cores, while the prime cores sat idle.
   - The busiest threads now join the session every 300 frames.
7. **Before blaming the port, test a rate directly:** `env DM_FPS_PIN=40` holds a rate. NEO's crowd held 40 fps pinned (GPU 20.6 → 15.2 ms once clocks rose), which showed the governor was giving up too early.
8. **GPU profile** with `DM_VK_PASS_TIMES=1` (start-up switch; it disturbs Adreno's binning, so compare runs).
   - If load/store A/B (`DM_VK_X_DEPTH`, `DM_VK_X_COLOR`) saves under about 1 ms, the cost is the game's own shading.
   - The only levers left then lower image quality (render resolution, shader precision). That is the user's call: say so instead of claiming 60 fps.

## Windows and tooling pitfalls

- Git Bash rewrites `/sdcard/...` arguments unless `MSYS_NO_PATHCONV=1` is set.
- Inline Python in bash heredocs breaks: lost backslashes, "unexpected EOF", `\n` turning into newlines. Write the script to a file in the scratchpad, or use the Edit tool.
- `python -I` hides user site-packages (Pillow, numpy, PyAV). Run analysis scripts without `-I`.
- Set `PYTHONUTF8=1` when engine tools print arrows or other non-ASCII text.
- `simpleperf` is refused on retail devices, and an in-process SIGPROF sampler crashed the game. Use the replay's own timers and per-thread `/proc` sampling.
- Thermal sysfs files can be stale; read several zones.
- The GPU clock (kgsl) isn't readable on retail devices; infer it from GPU busy at a fixed rate.

## Scripts in this skill

They use `devtools/device.py`, so they work for any game set in `devtools/device.json`.
- `scripts/ctl.sh LINE...` appends lines to the running app's `ctl.txt`.
- `scripts/frame_shots.sh N OUTDIR [LINE...]` sends the lines plus `env DM_VK_SHOTS=N` in one write, waits, and pulls the N presented frames.
- `scripts/count_matching_frames.py DIR_OR_MP4 R0 R1 G0 G1 B0 B1 [threshold]` reports which frames have more than the threshold of pixels inside a colour box (for a known glitch colour).
- `scripts/boot_to_gameplay.sh DETECTOR.py` restarts the app and presses A until the detector says gameplay, twice in a row. `scripts/detect_neo.py` is the example detector.
- `scripts/watch_session.sh MINUTES LOG` logs the process id, the latest timing line and the red-line count once a minute without sending any input (for the user's own play sessions).
