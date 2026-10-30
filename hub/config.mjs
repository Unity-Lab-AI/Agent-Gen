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
  temperature: Number(process.env.BRAIN_TEMPERATURE || 1.05),
  topP: Number(process.env.BRAIN_TOP_P || 0.95),
  repeatPenalty: Number(process.env.BRAIN_REPEAT_PENALTY || 1.08),

  personaFile: process.env.PERSONA_FILE || join(HERE, 'persona', 'unity.txt'),
  defaultEmotion: process.env.DEFAULT_EMOTION || 'warm',
  // Empty = no wake word; the VAD endpoint is the trigger. Set e.g. "unity,hey unity" to require it.
  wakeWord: (process.env.WAKE_WORD || '').split(',').map(s => s.trim()).filter(Boolean),
  historyTurns: Number(process.env.HISTORY_TURNS || 24),
};
