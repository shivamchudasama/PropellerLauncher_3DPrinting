# CLAUDE.md

## Routine

After a **significant change** — one that makes something in this file wrong or incomplete (files added/renamed/reorganized, a new convention adopted, git/LFS setup changed) — say which section is affected and ask:

> Would you like to modify `CLAUDE.md` accordingly?

Do not ask on turns that change nothing here (questions, inspection, small edits that fit existing conventions). Keep this file lean — only what's needed to understand the repo.

## Repository nature

A **3D printing asset repository** for a propeller launcher. It holds pristine upstream STLs and one derivative design, `Custom_HybridLauncher/`. That design's STLs are **generated** by Python scripts from the originals — edit the scripts, never the output STLs by hand. There is no package manifest or CI. The scripts need `trimesh`, `manifold3d`, `shapely` and `numpy`.

```
python Custom_HybridLauncher/src/build.py     # all STLs (--clearance X --stages-only adds a Stage*_PIP_X set)
python Custom_HybridLauncher/src/check.py     # verification; exit 1 on failure (slow: 15+ min with two stage sets)
python Custom_HybridLauncher/src/assemble.py  # Assembly.glb (animated)
```

## Layout

Pristine upstream files live in `Original_<Author>/` directories. Derivative work (remixes, resized parts, custom plates) goes in a sibling directory, never inside an `Original_*` one.

- `Original_Kocyns/` — 9 STLs (`obj_1` … `obj_9`, Czech part names).
- `Original_LukasHannert/` — 23 STLs for a three-stage planetary gearbox launcher: housings, internal toothing, sun/planet gears and carriers per stage, shafts, two propellers (100 mm, 67.4 mm). `Upper Housing_original_backup.stl` is an upstream variant kept alongside `Upper Housing.stl`.
- `Custom_HybridLauncher/` — Kocyns print-in-place stages with Lukas-style 18T herringbone gears, the Lukas propeller adapter nose and the Lukas 100 mm propeller. Contents:
  - `src/herringbone.py` — gear geometry
  - `src/build.py` — STLs, with parameters at the top
  - `src/check.py` — verification
  - `src/assemble.py` — the animated GLB
  - the generated STLs and `Assembly.glb`. Stage file names carry their flank clearance: `Stage*_PIP_0.20.stl` is the default (`CLEARANCE`) and `_0.25` is an alternative set. 0.15 seized in a test print. `check.py` verifies every set present, and `assemble.py` uses the default.
  - `README.md` — print and assembly notes
- `B3D_Labs.svg` — the user's branding logo (single even-odd path), engraved into the custom handle. `build.py` reads it from the repo root.

## Git

Remote `github.com/shivamchudasama/PropellerLauncher_3DPrinting`, default branch `main`.

- Binaries are tracked with **Git LFS** (`.gitattributes` routes `*.stl`, `*.3mf`, `*.pdf`, `*.glb`). A new binary extension needs a `.gitattributes` entry **before** its first commit, or it lands in history as a full blob — and GitHub rejects any blob over 100 MB (`Stage 2 Planetary Gear and Axle.stl` is 111 MB).
- ~520 MB of original STLs plus ~210 MB generated in `Custom_HybridLauncher/` (two stage sets) against GitHub's free 1 GB LFS storage / 1 GB monthly bandwidth. A single full clone uses most of the monthly bandwidth, and every regenerated STL committed adds a new LFS object, so commit regenerated outputs sparingly.
- `.gitignore` excludes local tool config (`.codex/`, `.claude/settings.local.json`).
