# Traps

Every one of these produced output that looked plausible and was wrong. They are
ordered by how much time each cost.

## 1. The Action overwrites your pose at render time

Most rigs ship an Action holding the rest pose (the community R15 rig:
`ArmatureAction.001`, **447 F-curves at frame 0**). Blender re-evaluates it during
render.

**Symptom:** pose queries report your values correctly; rendered frames show the
default pose. No error, no warning, and the numbers actively vouch for the broken
result.

**Do not** clear the Action to fix it — it *is* the rest pose, and clearing it
collapses the limbs.

**Fix:** insert keyframes into that Action (start clear of its own frame-0 keys),
then `frame_set()` per frame and render.

## 2. Never blanket-zero all pose bones

On a Rigify-style rig the `MCH_` / `ORG_` mechanism bones carry non-zero defaults
the IK solve depends on. Zeroing all bones collapses the limbs into the torso.
Reset only what you animate, or restore a captured baseline.

## 3. Half the named controls do nothing

On the R6 rig, `Torso_FK`, `RightLeg_FK`, `LeftLeg_FK` and `LookToPoint` were
**completely inert** — every axis, zero delta. The keyframes looked perfectly
reasonable in the spec and did nothing at all, so only the arms ever moved.

On the R15 rig, every `FK_*` bone is inert because the rig ships in **IK mode**
(`ARM_IK_FK = 1.0`).

Run `calibrate_rig.py`. Never assume a control works because its name says so.

## 4. Pose the control rig, not the output rig

Some rigs (the R6 one) split into a control armature and a slave output armature
whose bones are `CHILD_OF` + `COPY_LOCATION` constrained to it. Blender evaluates
constraints **after** local pose transforms, so writing to the output rig is
partly overridden and **the character comes apart**. Translating that armature's
*object* is worse — it fights every constraint anchor at once.

`calibrate_rig.py` reports which armature is which.

## 5. Constraint influence can be 0

The R6 rig's `Head` had `COPY_ROTATION` + `TRACK_TO` at **influence 0.0** — so the
constraints were decorative and `Head` rotation was free, while `LookToPoint` (the
apparent control) did nothing. Check influence before concluding a bone is locked.

## 6. Axis conventions are per-bone and must be measured

Real examples, all discovered by sweeping:

- `TORSO`/`UpTorso` (R15): **X = lean (POSITIVE leans BACK), Y = TWIST (positive
  turns toward the character's left), Z = SIDEWAYS lean (negative leans right)**.
  Not 1:1 — the rig amplifies: `X = +15` swings the head 23° off vertical.
  Authoring the punch's twist on Z hunched the figure sideways for several passes.
  Get the **sign** from a sweep too, not just the axis.
- `IK_Hand.R` (R15): `+X` inward, `-Y` forward, `+Z` up, ~1:1.
- **`IK_Hand.L` X is INVERTED** — negative pulls inward. Mirroring by copying the
  right-hand values shoves the left arm out sideways.
- R6 `Right Arm` rest axis is `(+0.71, 0, -0.71)` — **45° out and 45° down, not
  hanging**. Every angle authored as though rest were vertical is offset.

**Never assume a mirror rule.** Solve each side independently.

## 7. Measure the right quantity

A numeric verifier is only as good as what it measures, and a wrong one looks
authoritative:

- Using the mesh **bounding-box diagonal** as a limb axis returned a
  non-monotonic, meaningless sweep. Use the pose bone's **head and tail**.
- Targeting the arm's **direction** leaves roll unconstrained, so a box-shaped limb
  presents at odd angles. Target **hand position** (or full orientation).
- Locking one Euler axis at 0 and searching the other two **cannot cover the sphere
  of limb directions**. Search all three.

## 8. Integrity metrics need per-rig calibration

Measure each deform bone's head distance to its **parent's** head.

- A single-root metric is wrong on R15 — the waist is a real joint, so torso bends
  legitimately change it.
- Exclude the body-root pair (`LowerTorso` ← `HumanoidRootPart`): the torso control
  is *designed* to move it.
- **Tolerance ≈ 5%, not 2%.** IK chains stretch a few percent by design (a good
  animation peaked at 0.0325 on a 0.76 forearm). Real breakage was an order of
  magnitude larger. Too tight a threshold rejects working animation.

## 9. Camera side is part of the spec

A right-arm punch is invisible from the character's left — the torso occludes it.
At rest, arms often sit exactly in the body's side plane, so a pure side view shows
a "torso column" and looks like the arms are missing. Render at least two angles.

## 10. Contact sheets hide detachment

At 300 px per tile, a floating limb reads as normal Roblox blockiness. The sheet
catches wrong *poses*; only a numeric assertion catches a broken *rig*. Run both.

## 11. Environment

- ffmpeg (Windows build): **`drawgrid` works, `drawtext` segfaults** (no
  fontconfig), and **glob input patterns are unsupported** — use `-start_number 0
  -i "name_%03d.png"`.
- Blender defaults on Roblox rigs: override **Cycles → EEVEE** and **Filmic →
  Standard**, or renders are slow and washed out.
- `--enable-autoexec` is required or rig bootstrap scripts are skipped.
- A `.blend` written by a newer Blender warns "expect loss of data" and can carry
  broken drivers. It usually still works; check.

---

# Traps found while building a kick (R15)

Same through-line as above: every one produced plausible-looking wrong output, and
several were in the skill's own tooling rather than the rig.

## 12. `aim`, not `target`, for any limb that has to look extended

A world-space IK target holds the *end effector* where you asked. It does **not**
hold the *limb* straight, and those come apart the moment the torso moves: the
twist swings the hip forward, hip-to-target drops below full reach, and the knee
quietly folds into a V. The solver reports a perfect hit, the numbers agree, and
the render shows a bent leg. Measured on the kick: ankle exactly on target, knee
1.16 from a hip whose thigh is only 0.822 long.

Author moving limbs as `aim: [dx, dy, dz, reach]` - a direction plus a **fraction
of the limb's straight length**, measured from the limb root **as it is on that
frame**. Keep `target` for things that are genuinely pinned in the world, which
is exactly what a planted support foot is. That split - `aim` for the kicking
leg, `target` for the standing one - is the whole idea.

It is also the only currency that survives a change of proportions, which
matching a human pose always involves: **a human leg is ~43% of standing height,
R15's is ~34%.** Copy grid distances and you get nonsense; copy angle and
extension and it transfers exactly. Expect the R15 version of a big kick to reach
noticeably shorter than the reference and do not "fix" that by pushing the target
out of reach.

## 13. The IK chain is singular at the rest pose

These rigs rest with limbs **exactly** straight - measured, not approximately:
hip->ankle 1.748 against segments of 0.822 + 0.926. So at rest the chain sits on
its reach singularity, the Jacobian loses rank along the limb axis, and a plain
Newton `J.inverted()` raises `ValueError` on the **first** iteration and leaves
the limb where it started. That reads identically to "target unreachable", so it
gets mis-diagnosed and the pose is thrown away.

Use damped least squares. And do not trust one descent: where the IK saturates,
the Jacobian columns decay toward zero, every step is "accepted" for a
thousandth of an improvement, and the solve asymptotes far from a target a coarse
grid search reaches easily. Measured: a descent stalled at z=-0.94 on a point
whose reachable envelope went to +0.37.

## 14. Limb IK has unreachable POCKETS, not just a reach limit

The reachable set is not a sphere with a hole in the middle. The right hand could
sit at z=-0.91, and well above -0.5, but **not** at z=-0.75 while tucked in to
x~1.07 - an elbow-solution flip. A path that crosses such a pocket fails on a run
of consecutive frames no matter how the endpoints are tuned, because the endpoints
are fine and the middle is not.

Route **around** it - send the hand out to full arm width while it passes that
height, then back in. It reads as a natural arm swing anyway. Do not raise the
tolerance until the red light goes green.

Other measured limits on this rig, all found the same way: the arms rest **fully
extended downward**, so a hand cannot go below z ~= -0.79 (there is no "lower"
left); a foot **behind** the body cannot be lifted much, so a step has to swing
forward before it rises.

## 15. `ROOT` locZ up drags planted feet with it

Because the legs are exactly straight at rest (#13), there is no extension left.
Raising the root lifts the hips, the IK has nothing to give, and the "planted"
foot rises. Dip (locZ < 0) freely; to rise, raise the foot targets too, or accept
the feet leaving the floor. A foot roll also genuinely raises the ankle - that is
what a ball-of-foot pivot does - so let the support foot's target follow it up
rather than fighting it.

## 16. Blanket-zeroing pose bones fakes a TEARS verdict

`calibrate_rig.py` used to reset by zeroing **every** pose bone between probes,
which is trap #2 committed by the tool that exists to warn about it. On a
Rigify-style rig that collapses the IK defaults, so the probes that followed
measured a broken rig and reported `ROOT:loc`, `TORSO:loc` and `IK_SuperLeg` as
tearing when all three are rigid. Restore each bone's own captured rest value
instead. **A calibration tool that is wrong is worse than none**, because its
output is what everything downstream is built on.

## 17. A position-only probe calls every rotation control INERT

`sweep_control.py` decided a control was dead if no bone **head** moved. Rotating
an end bone - a foot about its ankle, a hand about its wrist - moves no head at
all, so `IK_LEG.R:rot` was reported INERT while `calibrate_rig.py` (which also
compares bone direction) correctly showed it driving `RightFoot` 1:1 in degrees.
Given trap #3 tells you to trust the measurement over the name, a **false** INERT
is exactly as costly as a false alive. Measure head position **and** bone
direction.

## 18. Blender resolves a relative render path against the .BLEND, not the CWD

`render.filepath = "out/side_000.png"` writes next to the rig file, not next to
where you ran the command. The old script printed `done` and the caller found an
empty folder. Always `os.path.abspath()` the output directory, and **assert the
files exist** before claiming success - `anim_render.py` now does both.

## 19. Frame the camera on the WHOLE animation

Framing off the rest pose and a hand-tuned `fit` multiplier crops exactly the
thing you are trying to look at, because a kick puts the foot far outside the
standing silhouette. Gather bounds over every baked frame and solve the camera
distance from the actual field of view (`margin` defaults to 1.10). No magic
number, and nothing can leave frame.

## 20. Lean COMPOUNDS with twist

Copying the reference's numbers literally - 24 degrees of lean-back with 52
degrees of twist - made a blocky R15 read as **toppling over**, not kicking.
Halving both to 12/32, then settling at 16/18, kept the attitude and lost the
tumble. Budget lean and twist together; never tune them independently.

---

# The big one: IK was the wrong tool (found 2026-08-24)

Everything in section 12-20 above is true and was learned the hard way, but it was
solving the wrong problem. **Author Roblox animation in FK.** Sections 12-15 only
matter if something forces you onto IK.

## 21. A Roblox animation IS per-joint rotations, so author per-joint rotations

A `KeyframeSequence` stores a tree of Poses, one per Motor6D, each a rotation of a
child part relative to its parent. That is FK. Every R15 rig has one control bone
per joint to match. Driving the character by IK targets and baking the result is a
round trip through a solver that Roblox never asked for.

What IK cost, all of which vanished with FK:

- **Position-only targets leave ROLL FREE.** Blocky Roblox limbs then present
  whatever face the solver picks, and the part visibly snaps between frames. On a
  textured avatar this reads as **colours changing instantly** — the single most
  damning symptom, and the one that makes an animation look buggy.
  (traps #7 already said targeting position leaves roll unconstrained. It was
  written down and reintroduced anyway.)
- **Solver branch-hopping.** A multi-start or grid-search fallback finds an equally
  good but *different* solution on the next frame, and the limb pops. Both frames
  verify perfectly.
- **Speed.** The solver ran a 125-point grid per hard frame per limb.

FK has no branches, no singularities, no roll ambiguity, is exactly 1:1 in degrees,
and exports directly. **Set the rig's IK/FK switch to FK and use the FK_ bones.**

## 22. The rig ships in IK mode — flip the switch, do not conclude FK is dead

`calibrate_rig.py` reports every `FK_*` bone as inert, and trap #3 says believe the
measurement. Both are correct and the conclusion drawn from them was wrong: the
bones are inert *because* `PROPERTIES.ARM_IK_FK` / `LEG_IK_FK` are `1.0`. Set them
to `0.0` and all twelve FK bones come alive. **When a control is inert, check for a
switch that disables it before writing it off.**

Set them via the spec's `properties` field — and they must be KEYED, because
`frame_set` re-evaluates the action every frame and would otherwise flip the rig
back to IK mid-bake.

## 23. FK child angles COMPOUND with the parent

Shoulder 50° forward plus elbow 70° forward puts the forearm **120° from vertical**
— pointing up over the shoulder. This is why the hands looked wrong: they were
authored as if the elbow angle were absolute. Keep shoulder + elbow under roughly
110° for a guard, and read the numeric pose report rather than guessing.

## 24. Twist on TORSO drags the legs; twist on UpTorso does not

`TORSO` drives 13 parts including both legs, so leaning or twisting it tips the
whole figure and slides the planted foot. `UpTorso` drives only the upper body.
Put the lean and most of the twist on `UpTorso`, leave a smaller share on `TORSO`
for the hip rotation a kick genuinely needs. Copying the reference's lean onto
`TORSO` made the figure read as toppling over.

Also: the rig **amplifies** torso rotation — `X = +15` swings the head 23° off
vertical, not 15°.

## 25. Keep the support foot flat

With FK nothing holds a foot level. Counter-rotate the ankle:
`FK_Foot.X ≈ -(FK_UpperLeg.X + FK_LowerLeg.X)`. Without it the support foot tilts
with the leg and the character looks like it is standing on a slope — a large part
of why the feet look wrong.

## 26. Render plain grey, not the avatar's costume

A busy avatar texture turns a blocky rig into an unreadable jumble of coloured
panels, and you end up debugging the costume instead of the pose. Real Roblox
animations are showcased on a **plain untextured dummy** for exactly this reason.
`"plain": true`.

## 27. Roblox timing, not the reference's timing

The Animation Editor defaults to **30 FPS** and a combat move runs **0.3-0.7s**
with five poses: idle, anticipation, contact, follow-through, recovery. Real-life
timing is far too slow — copying it literally produced a 1.4s
kick roughly 3x too slow. Take the MECHANICS from how the move works and take the TIMING from
Roblox.

Use per-segment `ease`: a fixed smoothstep decelerates into every keyframe, so the
strike eases to a stop at its own contact frame and the whole thing reads mushy.
Accelerate in (`"ease": "in"`), decelerate out (`"out"`).

## 28. Roblox animation is exaggerated

Real-life mechanics do not tell you what the result should LOOK like on a
blocky avatar. Real Roblox combat animation is **heavily
exaggerated** — angles well past human range, big lean, fast snap — and reads off
the **silhouette**. Push past what looks natural on a human
before deciding your own is close.

---

# Getting it into Studio — verified end to end 2026-08-24

The stage that was "STILL UNVERIFIED" for months. It works, with no upload.

## 29. Modern rigs use AnimationConstraint, not Motor6D

An Avatar-Evolution R15 dummy reports **zero Motor6D** and instead carries 15
`AnimationConstraint`s plus `BallSocketConstraint`s. Do not conclude the rig is
unriggable. The Animator still binds poses **by part name**, so a
`KeyframeSequence` written for Motor6D plays unchanged. Find the joints by
`Attachment1.Parent.Name` (the child part).

## 30. The Blender to Roblox axis map

Blender rig space here: rest limb points DOWN, `X-` = forward, `Z+` = character's
right. Roblox: `+X` right, `+Y` up, **`-Z` forward**. Rotating a down vector:
about `+X` sends it to `-Z` (forward), about `+Z` sends it to `+X` (right). So:

```
rx = -bx        ry = by        rz = bz
```

Blender XYZ euler applies X **innermost** (`R = Rz·Ry·Rx`), and `CFrame.Angles`
applies Z first, so build it explicitly in Blender's order:

```lua
CFrame.Angles(0,0,rz) * CFrame.Angles(0,ry,0) * CFrame.Angles(rx,0,0)
```

Translation: Blender `(x, y, z)` → Roblox `(x, z, -y)`. The two rigs turned out to
be the **same scale** (foot at −2.75 in both), so no unit conversion was needed —
check that rather than assuming it.

`scripts/to_roblox.py` does this conversion and emits the Luau data table.

## 31. `Enum.PoseEasingStyle` has no `Quad`

It is `Linear`, `Constant`, `Cubic`, `Elastic`, `Bounce`. Map the spec's
`in`/`out`/`smooth` onto **Cubic** with `PoseEasingDirection` `In`/`Out`/`InOut`.
Using a style that does not exist throws at build time.

Also: every `Keyframe` needs the **full pose tree**, rooted at a
`HumanoidRootPart` Pose, with untouched joints present at identity.

## 32. No upload needed — register the sequence

`KeyframeSequenceProvider:RegisterKeyframeSequence(seq)` returns a ContentId you
assign straight to `Animation.AnimationId`. It needs only the **Animation**
capability, so a LocalScript can do it at runtime — no asset upload, no
moderation, no account involvement. Keep the `KeyframeSequence` objects in
`ReplicatedStorage` and register them on the client at startup.

Only the **bare** returned string works. `hash://` gives "unknown AssetId
protocol" and `rbxasset://` gives "file not found".

Verify the round trip: `GetKeyframeSequenceAsync(id)` should return the sequence
with the keyframe times and priority intact, and `AnimationTrack.Length` should
equal the spec's duration. `Length` reads **0 until the asset loads**, so wait on
it before believing it.

## 33. You cannot preview a pose by writing `.Transform` in edit mode

`Transform` is the animation channel; the Animator applies it during the animation
step. In edit mode nothing moves and the parts stay at rest, so this looks like
your pose data is wrong when it is fine.

Verify the axis map by **forward kinematics through the attachments instead**,
moving nothing:

```lua
world[child] = world[parent] * j.Attachment0.CFrame * poseCFrame * j.Attachment1.CFrame:Inverse()
```

Then compare the resulting part positions against the Blender pose report. That
caught nothing wrong here precisely because it was checked before building.

## 34. Studio verification via MCP has two blind spots

- `capture_screenshot` returns solid black, or times out with "viewport renders a
  solid color", whenever Studio is showing a **script tab** rather than the 3D
  view. Setting `workspace.CurrentCamera.CFrame` from the plugin does hold, so the
  camera is not the problem — ask for the viewport to be visible.
- **Play-mode output capture returned nothing** on this server. Do not rely on
  `get_playtest_output` to confirm a runtime script ran; verify what you can in
  edit mode and have a human press the key.

---

# Found 2026-10-08: the exporter was wrong, and every render vouched for it

## 35. to_roblox.py mirrored limb ROLL and inverted torso/head LEAN

The old rule `rx=-bx, ry=by, rz=bz` for every bone is right only for X and Z on
the limbs. Read straight off the bone matrices: limb FK bones point DOWN (local
X = -X, Y = down, Z = back), so their map is `rx=-bx, ry=-by, rz=bz`; UpTorso,
HEAD and TORSO point UP and share Roblox's frame, so their map is the identity.
Measured errors under the old rule: a cocked throwing arm 170 deg off, a bowed
head 120 deg off (it played tipped BACK), a hand-on-hip 12 deg. The contact sheet
cannot see it - it only proves render == spec. `scripts/rbx_axis_check.py` now
compares every keyed part's full rotation (roll included) between Blender and
the Roblox CFrame chain; `--legacy` reproduces the old failure so the checker
is proven able to fail. Residual 1.4 deg = the rig's own FK bone tilt (0.5-0.7
deg per bone), hence its tol 2.0.

## 36. Enum.PoseEasingDirection In/Out are backwards

Roblox's own docs: "for legacy compatibility reasons, the use of In and Out are
backwards". `Out` = accelerate, `In` = decelerate. The old map sent spec "in"
(accelerate into contact) to `In`, so strikes decelerated into contact in game.
Fixed in to_roblox.py.

## 37. Blender lerps Euler angles; Roblox slerps CFrames

Every key can match and the PATH between keys still differs - 42 deg at the
midpoint of a 4-frame throw. `rbx_axis_check.py --mid` reports it and prints the
slerp midpoint as a ready-made beat; insert it and the render shows the in-game
path.

---

# Found 2026-10-17 (a custom-mesh R6 monster)

## 38. anim_render.py's grip.json measures the hand's "rest" box on a POSED frame (OPEN)

`C_rest` is read from the RightHand mesh's bounding box at whatever frame the scene is on
after baking (the last frame), not at rest. With a raised arm it reported a Tool.Grip of
(0.82, -2.13, 1.83) for a lantern whose real grip is ~0. The PROP LANDMARKS lines are
correct (they matched an independent probe to 0.01 stud); only grip.json is wrong. Frame 0
is not rest either (FK bones extrapolate the first beat backwards). Fix: capture the hand
box before any keys are inserted. Until then, do not trust grip.json from an animated arm.

## 39. A rigid R6 leg with a forward-pointing foot is LONGER swung back than forward

Measured on a custom R6 monster rig: lowest-vertex depth below the hip 3.93 standing, 4.11 at 17 deg
back (toe down), 3.48 at 30 deg forward (heel). A symmetric stiff swing therefore never lets
the front foot land - the rear toe is always lowest and the ground solve keeps it planted
while it slides forward. r6_clip.py's stance-slip metric caught it (-17 studs/s samples).
Fix used: translate each hip (Pose position, hidden inside the body mesh) by depth(theta) - ref,
and drive the stance angle at the no-slip rate dtheta/dt = speed / depth(theta). Measure slip
on the MATERIAL contact vertex followed frame to frame - the lowest-point location jumps
heel -> toe as the foot rolls and reads as slip when there is none.

## 40. Blender exits 0 on a Python exception in --python unless told otherwise

`blender --background --python x.py` with an exception inside x.py returns 0. Pass
`--python-exit-code 1`. Also `os._exit()` skips the stdout flush - flush every print.

---

# Found 2026-10-22 (animation tutorial capture)

## 41. rbx_axis_check.py printed per-part errors only for FAILING parts

Its docstring promised "the worst error per part", but the loop printed only parts over
`--tol`, so a PASS showed one overall number and nothing per joint - you could not see that a
part sat at 1.97 of a 2.0 tolerance. Fixed: every keyed part prints, worst first, with
`<-- FAIL` on the ones over tolerance. Parts with exactly zero error (torso and head under the
identity map) still do not appear, because nothing beats the 0 start value.

## 42. Studio edit mode: StepAnimations poses a rig; new dummies draw gizmos

- `Animator:StepAnimations(0)` after `track:Play(); track:AdjustSpeed(0); track.TimePosition = t`
  DOES pose a rig in EDIT mode (plugin context, so `execute_luau` can call it). Trap 33 is about
  writing `.Transform` by hand; this is the Animator's own step and the parts move. Measured on a
  standard R6 dummy: the edit-mode pose matched the Play-mode pose to 0.0001 studs.
- `Players:CreateHumanoidModelFromDescription(HumanoidDescription.new(), ...)` makes a BLACK
  dummy (every body colour defaults to 0,0,0) and an R15 one is built from AnimationConstraints
  + BallSocketConstraints, which Studio draws as attachment dots and joint lines over the body in
  edit mode. Set the six body colours on the description, and for a recorded showcase swap each
  AnimationConstraint for a Motor6D (Part0/Part1 from the attachments' parents, C0/C1 = the
  attachments' CFrames) and destroy the constraints: clips bind by part name either way.
- Setting `workspace.CurrentCamera.CFrame` in edit mode reads back as set, but a window capture
  can show a stale or different view. For recordings, frame shots in Play mode with a
  `BindToRenderStep` camera after `Enum.RenderPriority.Camera`.
- An R6 model from `CreateHumanoidModelFromDescription(..., R6)` does NOT pivot at its
  HumanoidRootPart: the pivot sits 1.5 studs higher (the head), so `m:PivotTo(spot)` with the
  root's intended height sank the dummy 1.5 studs into the floor (shipped in a recording).
  Place it by the root: `m:PivotTo(want * hrp.CFrame:ToObjectSpace(m:GetPivot()))`, then
  check the lowest part's bottom equals the floor's top as a number.

## 43. Slerp between two GROUNDED R6 keys sags through the floor; a rigid R6 cannot roll over its head

Found 2026-10-22 (FlipRollStrike). Every key was placed with the lowest point of the whole body on y=0, yet
r6_clip measured a foot 0.35 studs under the floor between keys (landing absorb -> dive, roll exit): each joint
slerps on its own, so the in-between pose is not grounded. Fix: put a key on every whole frame of a grounded
segment along the same eased path and ground each one (FlipRollAttack/gen_flip.py densify pass) - lowest foot
y then 0.000. Watch keys at fractional frame times: a round()-based frame range skipped the frame in between.
Also: r6_clip's ground solve only looks at FEET; for rolls, flips and get-ups ground on every part's corners.
A straight forward roll on R6 passes through standing on the 1.25-stud head (torso centre rises ~1.5 studs
mid-roll); tuck limbs to ~110-128 deg swing and keep the tuck until the last quarter so the shape stays round.
