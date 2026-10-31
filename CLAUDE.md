# CLAUDE.md

## Routine

After a **significant change** — one that makes something in this file wrong or incomplete (files added/renamed/reorganized, a new convention adopted, git/LFS setup changed) — say which section is affected and ask:

> Would you like to modify `CLAUDE.md` accordingly?

Do not ask on turns that change nothing here (questions, inspection, small edits that fit existing conventions). Keep this file lean — only what's needed to understand the repo.

## Repository nature

A **3D printing asset repository** for a propeller launcher. It currently holds only pristine upstream STLs — no build system, no scripts, no derivative designs yet. Do not fabricate build/lint/test commands.

## Layout

Pristine upstream files live in `Original_<Author>/` directories. Derivative work (remixes, resized parts, custom plates) goes in a sibling directory, never inside an `Original_*` one.

- `Original_Kocyns/` — 9 STLs (`obj_1` … `obj_9`, Czech part names).
- `Original_LukasHannert/` — 23 STLs for a three-stage planetary gearbox launcher: housings, internal toothing, sun/planet gears and carriers per stage, shafts, two propellers (100 mm, 67.4 mm). `Upper Housing_original_backup.stl` is an upstream variant kept alongside `Upper Housing.stl`.

## Git

Remote `github.com/shivamchudasama/PropellerLauncher_3DPrinting`, default branch `main`.

- Binaries are tracked with **Git LFS** (`.gitattributes` routes `*.stl`, `*.3mf`, `*.pdf`). A new binary extension needs a `.gitattributes` entry **before** its first commit, or it lands in history as a full blob — and GitHub rejects any blob over 100 MB (`Stage 2 Planetary Gear and Axle.stl` is 111 MB).
- ~520 MB of STLs against GitHub's free 1 GB LFS storage / 1 GB monthly bandwidth — a single full clone uses half the monthly bandwidth.
- `.gitignore` excludes local tool config (`.codex/`, `.claude/settings.local.json`).
