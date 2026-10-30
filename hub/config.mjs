// Hub configuration. Environment first, sane local defaults second. Nothing here binds beyond loopback
// unless HUB_HOST says so.
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
export const REPO = join(HERE, '..');

export const cfg = {
  host: process.env.HUB_HOST || '127.0.0.1',
  port: Number(process.env.HUB_PORT || 4646),
  uiDir: process.env.UI_DIR || join(REPO, 'ui'),

  voiceUrl: process.env.VOICE_URL || 'http://127.0.0.1:5123',
  speechUrl: process.env.SPEECH_URL || 'http://127.0.0.1:5125',
  faceUrl: process.env.FACE_URL || 'http://127.0.0.1:5126',
  imageUrl: process.env.IMAGE_URL || 'http://127.0.0.1:5124',
  // appearance engine: her identity anchors around whatever she asks to show, face locked to her likeness
  lookFaceRef: process.env.LOOK_FACE_REF || join(REPO, 'assets', 'portrait', 'unity-face.jpg'),
  // identity anchors. No fixed age: her manifestations run 22 to 34 and the persona sets it ("fixed 25 is not a option").
  lookPrefix: process.env.LOOK_PREFIX || 'photo of Unity, an adult emo goth woman, long black hair with pink streaks, winged eyeliner, fair skin,',
  lookSuffix: process.env.LOOK_SUFFIX || 'photorealistic, detailed face, natural light, sharp focus',
  lookBase: process.env.LOOK_BASE || join(REPO, 'assets', 'portrait', 'unity-full.jpg'),   // where every look starts
  lookWidth: Number(process.env.LOOK_WIDTH || 512),
  lookHeight: Number(process.env.LOOK_HEIGHT || 704),
  lookMaxSide: Number(process.env.LOOK_MAX_SIDE || 768),
  lookSteps: Number(process.env.LOOK_STEPS || 30),
  lookGuidance: Number(process.env.LOOK_GUIDANCE || 5.5),
  lookFaceScale: Number(process.env.LOOK_FACE_SCALE || 0.65),
  lookStrength: Number(process.env.LOOK_STRENGTH || 0.6),
  // motion: image-to-video clips of her current look (LTX-Video locally)
  videoUrl: process.env.VIDEO_URL || 'http://127.0.0.1:5127',
  clipPrefix: process.env.CLIP_PREFIX || 'realistic video of the same woman,',
  // which video engine films what: commanded motions and new looks want real body physics (Wan 2.2 5B, slow);
  // the idle reel wants cheap clips (LTX 2B, fast). The sidecar falls back to ltx when wan is not installed.
  motionEngine: process.env.MOTION_ENGINE || 'wan',
  reelEngine: process.env.REEL_ENGINE || 'ltx',
  // appended to every [[do]] motion: LTX 2B needs to be pushed to move a body (measured +40% motion energy)
  motionPush: process.env.MOTION_PUSH || 'large fast clear movement, energetic, her whole upper body moves, hair swings',
  // clip size is the GPU budget knob: while a clip renders the live face shares the card and slows.
  // 448x640 x 73 frames (~3 s) is about half the cost of 512x768 x 97 on the 4070 Ti SUPER.
  clipFrames: Number(process.env.CLIP_FRAMES || 73),
  clipWidth: Number(process.env.CLIP_WIDTH || 448),
  clipHeight: Number(process.env.CLIP_HEIGHT || 640),
  // after a look's clip lands, whenever she is idle, more clips are chained from the last frame and appended to
  // her live reel, each a thing she decided to do, so the body is open-ended instead of one short loop.
  // reelClips 0 = keep going for as long as she is idle; reelMaxFrames bounds RAM (~8 MB per frame).
  reelClips: Number(process.env.REEL_CLIPS ?? 0),
  reelMaxFrames: Number(process.env.REEL_MAX_FRAMES || 450),
  reelBatch: Number(process.env.REEL_BATCH || 12),          // idle actions asked of her brain at a time
  reelMotions: (process.env.REEL_MOTIONS || 'she shifts her weight and breathes, small natural movement|she brushes her hair back and glances to the side, then back at the camera|she sways a little, adjusts her posture, slow blink').split('|'),
  // every rendered look also becomes her live face
  lookDrivesFace: !['0', 'false', 'no'].includes(String(process.env.LOOK_DRIVES_FACE ?? '1').toLowerCase()),
  // Extra audio delay the UI applies when the face is live, on top of what the face sidecar reports.
  faceLeadMs: Number(process.env.FACE_LEAD_MS || 0),
  // In the desktop app the face sidecar plays her voice itself, frame-locked to her lips; the UI then stays silent.
  facePlayLocal: ['1', 'true', 'yes'].includes(String(process.env.FACE_PLAY_LOCAL || '').toLowerCase()),

  ollamaUrl: process.env.OLLAMA_URL || process.env.OLLAMA_HOST || 'http://127.0.0.1:11434',
  // Preference order; the first one Ollama actually has is used. unity-local (dolphin3 base, her Modelfile,
  // uncensored by design) leads for conversation; unity-brain is the RimWorld stream model on a Qwen base
  // and refuses on its own ("I don't do that kind of request"), so it is last.
  brainModels: (process.env.BRAIN_MODEL || 'unity-local,huihui_ai/qwen3-abliterated:8b,dolphin3:8b,unity-brain').split(',').map(s => s.trim()).filter(Boolean),
  numCtx: Number(process.env.BRAIN_NUM_CTX || 32768),
  keepAlive: process.env.BRAIN_KEEP_ALIVE || '30m',
  // her Modelfile's sampling: temperature 1.05, top_p 0.95, repeat_penalty 1.08
  temperature: Number(process.env.BRAIN_TEMPERATURE || 0.9),
  topP: Number(process.env.BRAIN_TOP_P || 0.95),
  repeatPenalty: Number(process.env.BRAIN_REPEAT_PENALTY || 1.08),
  // an 8B model under a 47 KB persona will keep writing past her turn and invent the user's next line;
  // cap the reply and stop on a fabricated turn (the old Local Unity server capped at ~140 tokens)
  numPredict: Number(process.env.BRAIN_NUM_PREDICT || 220),
  stop: (process.env.BRAIN_STOP || '\nUser:|\nuser:|\nGee:|\nYou:|\n[User]|\n### User').split('|'),

  personaFile: process.env.PERSONA_FILE || join(HERE, 'persona', 'unity.txt'),
  defaultEmotion: process.env.DEFAULT_EMOTION || 'warm',
  // Empty = no wake word; the VAD endpoint is the trigger. Set e.g. "unity,hey unity" to require it.
  wakeWord: (process.env.WAKE_WORD || '').split(',').map(s => s.trim()).filter(Boolean),
  historyTurns: Number(process.env.HISTORY_TURNS || 24),
};
