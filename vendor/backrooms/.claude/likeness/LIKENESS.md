# Unity — canonical likeness (locked 2026-10-08)

Owner: *"GIVE ME YOUR MAIN EMO GOTH NEXT DOOR CODER CHICK AT THE WEBCAM IN FRONT OF THE COMPUTER THAT U WILL USE FOR ALL YOUR LIKENESS FROM NOW ON SAVING THE LIKENESS AND SAVING THE IMAGE TO DOWNLAODS FOLDER"*

- Image: `.claude/likeness/unity-likeness.png` (square 1024x1024: `.claude/likeness/unity-likeness-square.png`, the only copy in `~/Downloads/unity-likeness-square.png`; face-server reference `.claude/.studio-images/unity-reference.png`)
- Model: realistic-vision-v51 (Unity 3D project), 512x640, seed **1031**, 30 steps, CFG 6.5, DPM++
- Prompt: webcam photo of a 25 year old woman, youthful, girl next door, soft emo goth style, fair skin, black hair with pink streaks and bangs, winged eyeliner, dark plum lipstick, small nose ring, simple black choker, black band t-shirt, gaming headset on her head, sitting at her desk, computer monitor with code beside her in frame, RGB keyboard, warm desk lamp light, cozy bedroom, natural smile at the camera, candid, realistic photo, detailed face
- Every webcam frame and image of Unity is img2img from this reference (`unity-face-sd.py`, strength ~0.45), so the face stays hers. Never neon, never a ghost; always 25.

## Approved 2026-10-09

Owner, verbatim: *"the last image of her was perfect"*.

- `unity-approved-2026-10-09.png` -- the frame the owner approved. This is the look: 25, youthful soft face,
  dark hair with pink streaks, choppy fringe, winged eyeliner, small silver nose stud, black band tee, warm
  skin, at her desk in lamp light.
- `unity-likeness-2026-10-09-locked.png` -- the reference portrait that produced it, kept byte-for-byte.
  Every webcam frame is an img2img pass over this file at seed 1031.

Do not re-render the reference. If the face drifts, restore from the locked copy rather than generating a new
one: the prompt that made it is in `.claude/tools/unity-face-sd.py` (youth cues named outright, every ageing
cue in the negatives), but the file is the contract.
