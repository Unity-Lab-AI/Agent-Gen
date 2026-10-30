// DUNGEON MASTER: THE HUNT — mic input via MediaRecorder → local voice-server /stt.
// Captures audio from the visitor's mic, decodes it to int16 PCM in the browser using
// Web Audio API, POSTs to the local voice server (127.0.0.1:7861) which runs
// faster-whisper on the visitor's GPU (CPU fallback available). Returns the transcript.
//
// No cloud service. No API key. The voice server ships with this project (see
// local-services/voice-server/voice_server.py + scripts/install_voice.*) and sends
// Access-Control-Allow-Origin: * so this browser-direct fetch works from any origin.

(function () {
  'use strict';

  function cfg() { return window.DMTHConfig.LOCAL_VOICE; }

  let mediaRecorder = null;
  let chunks = [];
  let stream = null;
  let startedAt = 0;

  function isSupported() {
    return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
  }

  function isRecording() { return mediaRecorder && mediaRecorder.state === 'recording'; }

  async function start() {
    if (!isSupported()) throw new Error('MediaRecorder not supported in this browser');
    if (isRecording()) throw new Error('already recording');
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    chunks = [];
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data); };
    mediaRecorder.start();
    startedAt = Date.now();
  }

  // Browsers hand us webm/opus by default from MediaRecorder, but the local voice server
  // wants raw int16 PCM (or a WAV container). Decode with Web Audio API and hand-convert
  // Float32 samples to Int16, then base64-encode. Mono-mix by taking channel 0 — whisper
  // doesn't benefit from stereo and the server accepts one PCM stream.
  async function blobToPcmB64(blob) {
    const arrayBuffer = await blob.arrayBuffer();
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) throw new Error('AudioContext not supported');
    const ac = new AC();
    let audioBuf;
    try {
      audioBuf = await ac.decodeAudioData(arrayBuffer);
    } finally {
      // Close the AudioContext right after decode; keeping it open leaks a mic-tab tone
      // on some browsers.
      if (ac.close) ac.close();
    }
    const channelData = audioBuf.getChannelData(0);
    const sampleRate = audioBuf.sampleRate;
    const int16 = new Int16Array(channelData.length);
    for (let i = 0; i < channelData.length; i++) {
      const s = Math.max(-1, Math.min(1, channelData[i]));
      int16[i] = s < 0 ? Math.round(s * 0x8000) : Math.round(s * 0x7FFF);
    }
    const bytes = new Uint8Array(int16.buffer);
    // Chunked btoa to avoid stack-overflow from spreading a huge Uint8Array into
    // String.fromCharCode.apply — safe up to any recording length.
    let bin = '';
    const CHUNK = 0x8000;
    for (let i = 0; i < bytes.length; i += CHUNK) {
      bin += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
    }
    return { pcm_b64: btoa(bin), sample_rate: sampleRate };
  }

  async function stopAndTranscribe() {
    if (!isRecording()) throw new Error('not recording');
    const blob = await new Promise(resolve => {
      mediaRecorder.onstop = () => {
        const b = new Blob(chunks, { type: chunks[0]?.type || 'audio/webm' });
        resolve(b);
      };
      mediaRecorder.stop();
    });
    if (stream) stream.getTracks().forEach(t => t.stop());
    stream = null;
    mediaRecorder = null;

    // Decode webm/opus → int16 PCM base64 for the local STT server.
    let pcm;
    try {
      pcm = await blobToPcmB64(blob);
    } catch (err) {
      return { ok: false, error: `decode: ${err.message}`, durationMs: Date.now() - startedAt };
    }

    try {
      const c = cfg();
      const res = await fetch(c.endpoint + c.stt, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(pcm)
      });
      if (!res.ok) {
        return { ok: false, error: `stt HTTP ${res.status}`, durationMs: Date.now() - startedAt };
      }
      const data = await res.json().catch(() => null);
      const transcript = (data?.text || '').trim();
      return { ok: true, transcript, durationMs: Date.now() - startedAt };
    } catch (err) {
      return { ok: false, error: err.message, durationMs: Date.now() - startedAt };
    }
  }

  async function cancel() {
    if (isRecording()) mediaRecorder.stop();
    if (stream) stream.getTracks().forEach(t => t.stop());
    stream = null;
    mediaRecorder = null;
    chunks = [];
  }

  // Liveness probe for the setup wizard / detector. Returns true if the local voice
  // server answers GET /state (regardless of whether the model is loaded — that's
  // reported in the payload). False on network failure or non-2xx.
  async function isServerAvailable() {
    try {
      const c = cfg();
      const res = await fetch(c.endpoint + c.state, { method: 'GET' });
      return res.ok;
    } catch { return false; }
  }

  window.DMTHGame = window.DMTHGame || {};
  window.DMTHGame.voiceIn = Object.freeze({
    isSupported, isRecording, start, stopAndTranscribe, cancel, isServerAvailable
  });
})();
