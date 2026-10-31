# Hybrid propeller launcher

The base is **Kocyns**: print-in-place 3-stage planetary (64:1), with the original housing, size and handle. Merged in from **Lukas Hannert**:

- herringbone gear teeth
- the coned, splined propeller adapter nose
- the 100 mm propeller

The handle's bottom face carries an engraved B3D Labs logo.

## Parts

| File | Prints | Source |
|---|---|---|
| `Stage1_PropEnd_PIP.stl` | 1 | Kocyns `obj_6`, gears replaced |
| `Stage2_Middle_PIP.stl` | 1 | Kocyns `obj_5`, gears replaced |
| `Stage3_HandleEnd_PIP.stl` | 1 | Kocyns `obj_7`, gears replaced |
| `Handle_B3D.stl` | 1 | Kocyns `obj_1`, bottom recess closed, logo engraved 0.6 mm |
| `Propeller_Adapter.stl` | 1 | Kocyns `obj_8` hex + collar, Lukas `Adapter` spline + nose |
| `Propeller_100mm.stl` | 1+ | Lukas, unchanged |
| `Coupon_Clearance_0.15/0.20/0.25.stl` | test | one gear set at three flank clearances (1/2/3 notches) |
| `Assembly.glb` | — | assembled view, animated (see below); housings translucent |

Gears are **18/18/54 herringbone** (module 0.998, 35° helix, 0.20 mm flank clearance). They sit inside the Kocyns 45° retention cones. The ratio stays 4:1 per stage.

## Printing

- 0.4 mm nozzle, 0.2 mm layers, no supports.
- Print parts in the orientation of the file. Stages print sun-side down, the adapter hex-down, and the handle logo-down.
- **Print the coupons first.** Pick the clearance that turns freely without wobble.
  - If it isn't 0.20, rebuild the stages with `python src/build.py --clearance <value> --stages-only`.
- After printing, break each stage free by turning the carrier hex while holding the housing.

## Assembly (handle down, propeller up)

1. Snap the handle over the `Stage3` fingers. Its hex socket grips the Stage 3 carrier.
2. Stack `Stage2`, then `Stage1` on top. The 12-lobe spigots lock the housings, and each carrier hex enters the next sun.
3. Press the adapter's hex into the `Stage1` sun.
4. Drop the propeller onto the spline, where it rests on the collar.
5. To launch, hold the handle and twist the ribbed housing sharply. The propeller turns at 64× the relative speed.

## Animated assembly

`Assembly.glb` has a 20 s looping animation (`turn_handle`): the housings stay still while the handle makes one full turn. It turns the way its chevron grip ribs point: counter-clockwise when you look at the handle's logo face, clockwise from the propeller end.

| Part | Turns per handle turn |
|---|---|
| Handle, Stage 3 carrier | 1 |
| Stage 3 sun, Stage 2 carrier | 4 |
| Stage 2 sun, Stage 1 carrier | 16 |
| Stage 1 sun, adapter, propeller | 64 |

The planets orbit with their carrier and spin on their own axes at −3× its speed relative to it. Open the file in any glTF viewer that plays animations, for example sandbox.babylonjs.com, gltf-viewer.donmccurdy.com, Blender, or Windows 3D Viewer.

## Rebuilding

`src/` needs Python with `trimesh`, `manifold3d`, `shapely` and `numpy`. It reads the pristine originals in `../Original_*` and `../B3D_Labs.svg`.

```
python src/build.py      # all STLs
python src/check.py      # watertight, no fused bodies, gear-mesh sweep, fits
python src/assemble.py   # Assembly.glb
```
