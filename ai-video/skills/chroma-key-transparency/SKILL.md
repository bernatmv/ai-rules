---
name: chroma-key-transparency
description: Use when generating images that need transparent backgrounds, including game sprites, item icons, cutout characters, decals, and UI assets. Also use to remove a deliberately flat chroma-key background from an existing image.
---

# Chroma-key transparency

Generate the artwork on an opaque, flat key color, then remove that color with image processing to produce actual alpha. Do not ask the image model for transparency or a checkerboard. This is the user's preferred transparency workflow; combine it with the available image-generation tool or skill for generation, and use code for the explicitly requested chroma removal. Respect higher-priority tool restrictions.

## Choose and generate

- Preserve the project's art direction, silhouette, framing, resolution, and palette. Choose a saturated key absent from the subject, including highlights and outlines: green `#00FF00` is a starting point, blue or magenta can suit green subjects. Do not change the subject's palette to fit the key.
- Prompt for a perfectly uniform, opaque key background with that exact hex color, no gradient, texture, vignette, backdrop shadow, checkerboard, or reflected key light. Request clean separation and enough padding for the complete silhouette, hair, weapons, and accessories. Lighting and self-shadow belong on the subject.
- Example addition: “Full object visible, isolated on a perfectly flat solid #00FF00 background, including gaps between parts. No background shadows, green reflections, green rim light, backdrop texture, or checkerboard. Preserve the requested artwork style and fine silhouette detail.”
- Save and inspect the original. Sample the actual background if it differs from the prompt. If the key occurs in the subject, regenerate with a better key or use a deliberate foreground mask; global keying cannot distinguish identical colors by meaning.
- For pixel art, request hard pixel edges and preserve native resolution; do not introduce smoothing. For sprite sheets preserve canvas size, frame boundaries, and pivots throughout processing.

## Remove the key

Use the bundled helper, or an available equivalent that supports a soft matte and edge-color decontamination. Paths below are relative to this skill's directory, not the user's project. Requires Python 3 and Pillow (`python3 -m pip install Pillow` in an appropriate environment if missing).

```bash
python3 scripts/remove_chroma.py source.png asset.png --key '#00FF00' --previews
```

The helper exports straight-alpha RGBA PNG without changing dimensions. It preserves the source and refuses to overwrite outputs. It uses RGB distance from the key: pixels within `--inner` (default 20) become transparent; pixels beyond `--outer` (default 150) retain their alpha; those between get a soft transition with key-color unmixing. These are starting parameters, not an automatic segmentation model. Read the emitted alpha counts and inspect the previews before accepting a result.

- Keep opaque subject pixels intact. Start with the narrowest transition that removes the backdrop. Tune `--inner` and `--outer` together based on the actual image; excessive tolerance erases subject detail. Reprocess from the original, never a previously keyed output.
- If green or blue fringe remains, add `--despill` for pure `#00FF00` or `#0000FF` keys. This caps excess of the key channel at the maximum of the other two channels, including opaque contaminated edge pixels. Only enable it when that color is absent from the intended subject; it operates globally and can alter legitimate colors. Compare to the original after applying it. For other keys use a suitable selective despill/matte tool.
- Use `--hard --inner 30` for intentionally hard-edged pixel art; no soft alpha is introduced. Tune the threshold to the actual key.
- Removal is global so enclosed gaps are cleared too. It can also remove matching subject colors; border flood fill alone avoids some of that damage but leaves enclosed gaps. Neither replaces inspection or a foreground mask.
- Soft matte estimation and color unmixing reduce key-colored edges, but cannot reconstruct unknown foreground color and alpha exactly from a single image. Keep glass, smoke, translucent cloth, motion blur, glow, and soft ground shadows as separate assets/passes where practical; do not silently erase them or present a damaged cutout as finished. Use a dedicated matte/compositing workflow when chroma cannot preserve them.

## Quality gate for game assets

1. Verify the delivered file is RGBA with both transparent background and visible foreground. A PNG extension or checkerboard-looking RGB image is not proof. Unexpectedly empty, fully opaque, or mostly translucent output needs investigation.
2. Inspect the generated `.light.png`, `.dark.png`, and `.checker.png` composites at intended display size and zoom into edges. Look for colored halos, dark rims, jagged edges, lost hair/thin parts, holes in the subject, clipped tips, and leftover key in internal gaps. View the files; counts alone do not establish quality.
3. Compare against the source for silhouette, colors, texture, and opaque interiors. Tune the matte or regenerate a cleaner source if necessary. Never fix fringe by repeatedly shrinking the whole silhouette.
4. For a project asset, inspect it in the game's actual renderer if available. Check texture filtering, alpha mode, scaling, atlas padding, and mipmaps. The helper writes straight alpha; use the renderer's corresponding import convention. Key-colored invisible texels are cleared, but atlas edge extrusion may still be needed. Do not change runtime configuration unless the task includes integration.
5. Deliver the RGBA asset, retain the keyed original for iteration, and report the key, processing settings, paths, and any unresolved issue. Preview composites are QA artifacts, not transparent deliverables. If visual inspection or runtime verification is unavailable, say so explicitly.

Prefer a targeted correction when quality fails. If repeated tuning damages the subject, stop eroding it and change the key/source or matting approach. Do not claim every asset is production-ready solely because this helper ran successfully.
