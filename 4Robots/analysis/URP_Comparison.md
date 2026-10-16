# AdientTorsF – comparison of the 4 robot programs

Compared files: `AdientTorsF_Eol1L.urp`, `AdientTorsF_Eol1R.urp` (single cells, L/R line),
`AdientTorsF_Eol20.urp`, `AdientTorsF_Eol21.urp` (double cells, L/R line).
All four are saved in PolyScope 5.26.0 and all still report `SW_Ver := 1.0`. The version
variable has not been bumped, so it cannot be used to tell which robot is newer.

The `.urp` files were converted to readable pseudocode (`readable/*.txt`, made by
`tools/urp2txt.py`).

## Re-check after commit 09038bc "updated urps" (2026-10-16)

Line numbers in this section refer to the regenerated `readable/*.txt`. Line numbers in the
original report further down refer to the previous version of the files.

**What changed on all 4 robots:** the buckle section was restructured the same way on each.
- A new helper `Progress_check()` was added.
- When the camera check fails, the robot now goes home immediately and reports 91.
- `Report(6)` is sent when Flags[8] arrives.
- The `elif T_Timeout` branch was removed. After the insert, every case now does the same
  retreat: MoveL to `Wp`, then MoveDirection Z− 20 mm, then home.
- The final report is 50 if step 6 was reached, otherwise a fault code.

The structure matches across the 4 robots, and the mirror (near/far side swap) is correct.

### Fixed

| Old # | Status |
|---|---|
| A1 | **Fixed.** 1R `Eol1R.txt:936` now uses `In(CMD_Program_i1,[21,22,23])`. |
| A3 | **Fixed.** 1R `Eol1R.txt:998` now uses `AtLHomePos`. |
| B1 | **Fixed.** The buckle retreat is now the same for every program on all 4 robots. |
| A4 (1R part) | **Fixed.** The `elif T_Timeout>10` is gone. |

### Still open / new

| # | Robot | Where | Finding |
|---|---|---|---|
| N1 | **1R** | `Eol1R.txt:942` | **A2 only half fixed.** The `or` is now `and`, but the list is `In(CMD_Program_i2,[21,22,23])`. Side 2 programs are 50‑89, so this can never match and the side‑R disconnect preference is dead. 1L has `[61,62,63]`. |
| N2 | 1L/1R/20/21 | Buckle, final `else` (`Eol1L.txt:458`, `Eol1R.txt:458`, `Eol20.txt:437`, `Eol21.txt:436`) | **New mismatch.** When Flags[8] times out or Abort fires: **1L and 21 report 95**, **1R and 20 report 91**. Before this change all four reported 91. Pick one code. |
| N3 | **1L** | `Eol1L.txt:422` | A4 still open. The buckle confirmation wait is still `T_Timeout>10`. The other three use 25. |

| N4 | **21** | PushByHandle, `Eol21.txt:810` | **New, 21 only.** `wait AnalogInput Ai_Pusher=8.9` became `analog_in[0]=8.5`. The threshold changed, and the pin is now referenced by raw name. 20 still uses `Ai_Pusher` 8.9. Check that `Ai_Pusher` really is `analog_in[0]` in the 21 installation, and propagate the value to 20 if 8.5 is right. |

| A5 | 20 + 21 | `Eol20.txt:344`, `Eol21.txt:343` | Still open: `timer Reset T_Timeout` twice, no Start. |

| A6 | 20 / 21 | `Eol20.txt:371`, `Eol21.txt:527` | Still open: 20 checks SBR only in Buckle; 21 only in Buttons. |
| A7 | 1R | `Eol1R.txt:385` | Still open: `CamCorrection[1]` upper bound 0.052. |
| B2‑B9, C1‑C3, D | – | – | Unchanged. In particular, 21 still has no `Report(6)` in Connect (B4) and 20 still has the stray gripper wait (`Eol20.txt:136`). |

Note: the new retreat first moves MoveL back to `Wp`, which is the **uncorrected** taught buckle
point (`WLBuckleSpa1`, etc.). Before, 1R and the 15 case on 1L used `Wp0`, the
camera‑corrected approach point. With a camera correction of up to ±5 cm, the blade can move
sideways while it is still in the slot. The force pushes before it already target `Wp`, so
this may be intended. Please confirm.

---

## Original report (previous URP versions)

Line numbers below refer to the readable files of the previous version (commit 1283069).

## How the comparison was done

1. Pairs compared: **1L ↔ 1R** and **20 ↔ 21**. The parts that singles and doubles share
   were also compared: BeforeStart, Thread, gripper subprograms, camera and dock events.
2. **Symmetry deviations that were tolerated.** Forward kinematics of the taught points
   shows that the product is mirrored in robot base X (seat‑left is always −X). These
   differences were treated as expected:
   - sign flips in X: `pose_trans(..., p[±0.02,...])`, `ButtonPos[0] ± x`, force `Fx ±20/±15/±10`,
     `CamData[0]*-1`
   - near/far side swap: the buckle "via center" special case is `[55,56]` on 1L and `[15,16]` on 1R.
     The buttons case is `[31,32,37,38]` on 1L and `[71,72,77,78]` on 1R.
   - path waypoints (`WRBklMidp3` ↔ `WLBuckle0`, `WpParkUp0` ↔ `WpPark0/1`, `WRHome0` ↔ `WLHome0`, ...)
     and their blend radii
   - joint values. 1R uses a different arm configuration (J3 sign flipped), so joint
     values cannot be compared one to one.
   - per‑station config: the camera Modbus IP (1L `.41`, 1R `.43`, 20/21 `192.168.1.101`)
3. **Cosmetic differences that were ignored:** in 1L and 20 some IO is referenced by raw
   pin (`digital_in[0]`, `analog_in[3]`, `config_in[0]`, `digital_out[1/2/7]`). 1R and 21
   use the names (`Di_Docked_L`, `AI_Gripper`, `NormalMode`, `Do_Blue/Do_Horn/Do_SafePosition`).
   The logic is the same. It only means the installations differ in IO naming.

Everything below is left after those deviations are removed.

---

## A. Real bugs / clear loss of sync (fix)

| # | Robot | Where | Finding |
|---|---|---|---|
| A1 | **1R** | Thread › ReservationControl, `Eol1R.txt:948` | `if CMD_Reserve_i1≟1 and In(ProgExe,[21,22,23])`. The 1L version is `In(CMD_Program_i1,[21,22,23])`. The enclosing `if` requires `ProgExe≟0`, so this branch **can never run**. The "disconnect preference" for side L is gone. |
| A2 | **1R** | same, `Eol1R.txt:954` | `if CMD_Reserve_i2≟2 or In(ProgExe,[21,22,23])`. The 1L version is `CMD_Reserve_i2≟2 and In(CMD_Program_i2,[61,62,63])`. The `and` became `or` and the program list is wrong. Side R now wins reservation for **any** program, not only for disconnect. |
| A3 | **1R** | Thread › Force release, `Eol1R.txt:1010` | When app 2 releases (`CMD_Reserve_i2 ∈ [98,99]`) the code checks `if AtRHomePos` and then sets `STS_Reservation := 1`. It should check `AtLHomePos`, as 1L does (`Eol1L.txt:1009`). Result: it reserves L while at R home, or it parks unnecessarily. |
| A4 | **1L** (+1R partly) | Buckle › Insert, `Eol1L.txt:409/452`, `Eol1R.txt:452` | The buckle confirmation timeout was raised from 10 s to 25 s on 20/21 (wait and `elif` both 25). **1L still uses 10/10.** **1R uses 25 for the wait but 10 for the `elif`.** The update was only partly propagated. |
| A5 | **20 + 21** | Connect › "Test switch pin", `Eol20.txt:339‑340`, `Eol21.txt:338‑339` | `timer Reset T_Timeout` appears twice and there is **no `timer Start`**. Singles use Reset + Start. The `T_Timeout>10` guard only works if the timer is still running from an earlier start. Change the second Reset to Start. |
| A6 | **20 / 21** | seat‑belt (SBR) check before a task | Singles check `Di_SBR_*` before **Buckle and Buttons**. **20** only checks it in Buckle (`Eol20.txt:366`). **21** only checks it in Buttons (`Eol21.txt:525`). Each robot is missing one check. |
| A7 | **1R** | Buckle › camera check, `Eol1R.txt:380` | `InRange(CamCorrection[1],-0.05,0.052)`. The other three use ±0.05. This looks like a local hack. Note that 1R flips `CamData[0]`, so even as a mirror change it widens the wrong bound. |

## B. Probably loss of sync (decide which version is the master, then propagate)

| # | Robots | Finding |
|---|---|---|
| B1 | 1L vs 1R | Buckle retreat after insert. 1R returns via the **corrected variable `Wp`** for all 4 programs. 1L does that only for 15. For 16/55/56 it goes to the **uncorrected fixed** points `WLBuckleSpa3 / WRBuckleSpa1 / WRBuckleSpa3`. |
| B2 | 21 only | Heartbeat. 21 toggles only when `CMD_Heartbt_i1≟STS_Heartbeat` (a handshake, `Eol21.txt:930`). 1L/1R/20 toggle freely. The PLC side has to match. |
| B3 | 21 only | `call GripperClose` at the start of **Buttons** (`Eol21.txt:518`). The others start Buttons with whatever gripper state was left over (open after Disconnect). |
| B4 | 21 only | `script: Report(6)` (switch‑pin test started) was removed from Connect. The PLC/HMI will no longer see progress step 6 from 21. |
| B5 | 20 only | A stray `wait until timer_Gripper>5 or AI_Gripper<(...)` in "Go to home pos automatically" (`Eol20.txt:131`). It is not present on 21. |
| B6 | 1R only | EvtDock (re-dock event): MoveL 1.5 m/s / 1.5 m/s² (others 1.0 / 3.0), blend 0.1 (1L 0.05), final MoveL acceleration 2.0 (others 3.0). |
| B7 | 20 vs 21 | EvtDock. 20 has an extra pre‑approach point `pose_trans(WpDock,p[0,0.25,0.1,..])`, and in 21 that point is **suppressed**. MoveDirection "until" blend is 0.05 on 20 and 0.1 on 21 and singles. 20 is the odd one out. |
| B8 | 20 vs 21 | Height up/down button X offset: 20 `ButtonPos[0]+0.008`, 21 `ButtonPos[0]-0.003`. The sign flip is mirror, but **8 mm vs 3 mm** is a tuning difference. 20 also has a redundant `Wp[0]=ButtonPos[0]` line (`Eol20.txt:614`, no effect). |
| B9 | 21 | `WpUnplug_1` (retreat after unplug, used live 3×) and `WpHome` have **bit‑identical joint values to Eol20**, so they were copied and never re‑taught. Every other unplug point on 21 differs from 20 by several cm. Verify `WpUnplug_1` on the robot. `WpCamLMB` and `WpBttnMidp1‑3` are copied too, but they are only used in suppressed nodes. |

## C. Consistent per line, not per cell type (check whether intentional)

These differ L vs R, and the difference is the same in the single and the double cell.
The likely cause is that it was changed on one line and not ported, but it could also be
a deliberate per‑line tuning.

| # | L line (1L, 20) | R line (1R, 21) |
|---|---|---|
| C1 | Buckle approach `Wp0 := pose_trans(Wp,p[0,0,-0.02,...])` (Z, not a mirrored axis) | `-0.04` |
| C2 | Speed thread `if T_SpeedSet>2` | `if T_SpeedSet>2 and not DEBUG` |
| C3 | Button approach/retreat: **MoveL** Cartesian via `WpCenter`/3 mid‑points (`WpBttnMidp1‑3`) | **MoveJ** joint via one mid‑point (`WpBttnMidp`) |

## D. Single vs double drift in shared code (same within each pair)

- **GripperOpen / GripperClose**: singles use `T_Gripper`, close has a 3 s timeout with no fault,
  and open calls `stopj` if it takes more than 3 s. Doubles use `timer_Gripper`, a 5 s timeout,
  and close raises a "Gripper close fault" popup + halt.
- **WaitForNormalMode**: on doubles the `if` is `checkContinuously` and Do_Horn/Do_Blue are not reset afterwards.
- **BeforeStart scripts**: doubles have `reg2bool` simplified and `PosDist()` replaced by `Calibrate()`.
  Singles still use `PosDist` for home detection, and doubles use `pose_dist`, which includes rotation.
- **Camera event**: the debug text is different ("set cam prog failed..." vs "extra cam trigger...").
- **EvtDock force selection**: singles `1,0,1,1,0,0` (torque about X is compliant), doubles `1,0,1,0,0,0`.
- The thread structure is different by design: dual vs single adapter, pusher, tilt, and a different InterlockOutput geometry.

## E. Identical across the pair (OK)

CamAcquire, CamCalculateCorectnPlane (apart from the mirrored `CamData[0]*-1`), Undock,
Connect force sequence, Disconnect logic (apart from path points), Program‑finished / parking,
Abort handling, register map 130‑181.
