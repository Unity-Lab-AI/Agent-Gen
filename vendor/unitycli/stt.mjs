/**
 * UnityCLI Built-in STT — Vol 2
 * Speech-to-text without external dependencies beyond a whisper backend.
 *
 * Backend options (user picks in config):
 *   1. whisper.cpp — local binary, free, cross-platform, best option
 *   2. whisper HTTP — any OpenAI-compatible whisper endpoint (local or cloud)
 *   3. Pollinations transcribe — via MCP if configured
 *
 * Audio capture:
 *   - Windows: uses PowerShell + NAudio (built-in Windows APIs)
 *   - macOS: uses `rec` from sox or `ffmpeg`
 *   - Linux: uses `arecord` or `ffmpeg`
 *
 * Config in unitycli-config.json:
 *   "stt": {
 *     "engine": "auto",              // "auto", "whisper_cpp", "whisper_http", "none"
 *     "whisper_cpp_path": "",         // Path to whisper.cpp main binary
 *     "whisper_cpp_model": "",        // Path to .bin or .gguf model
 *     "whisper_http_url": "",         // HTTP endpoint (e.g. http://localhost:5560/transcribe)
 *     "record_seconds": 5,            // Default recording duration
 *     "enabled": true
 *   }
 */

import { execSync, spawn } from 'child_process';
import fs from 'fs';
import path from 'path';
import os from 'os';
import { fileURLToPath } from 'url';

// Resolve ffmpeg from ffmpeg-static npm package if not on PATH
let _ffmpegPath = 'ffmpeg';
try {
  const __sttdir = path.dirname(fileURLToPath(import.meta.url));
  const staticBin = path.join(__sttdir, 'node_modules', 'ffmpeg-static', 'ffmpeg.exe');
  if (fs.existsSync(staticBin)) _ffmpegPath = staticBin;
} catch {}

export class STT {
  constructor(config = {}) {
    this.engine = config.engine || 'auto';
    this.whisperCppPath = config.whisper_cpp_path || '';
    this.whisperCppModel = config.whisper_cpp_model || '';
    this.whisperHttpUrl = config.whisper_http_url || '';
    this.recordSeconds = config.record_seconds || 5;
    this.enabled = config.enabled !== false;
    this.platform = os.platform();
    this._detected = null;
    this._capture = null;
  }

  /**
   * Detect available STT engine and audio capture method.
   */
  detect() {
    // Detect transcription engine
    if (this.engine !== 'auto') {
      this._detected = this.engine;
    } else if (this.whisperCppPath && fs.existsSync(this.whisperCppPath)) {
      this._detected = 'whisper_cpp';
    } else if (this.whisperHttpUrl) {
      this._detected = 'whisper_http';
    } else {
      this._detected = 'none';
    }

    // Detect audio capture method
    this._capture = this._detectCapture();

    return { engine: this._detected, capture: this._capture };
  }

  _detectCapture() {
    if (this.platform === 'win32') {
      // Windows has PowerShell + .NET — can capture via NAudio
      return 'powershell';
    }
    if (this.platform === 'darwin') {
      try {
        execSync('which rec', { timeout: 2000, encoding: 'utf-8' });
        return 'sox';
      } catch {}
      try {
        execSync('which ffmpeg', { timeout: 2000, encoding: 'utf-8' });
        return 'ffmpeg';
      } catch {}
      return 'none';
    }
    // Linux
    try {
      execSync('which arecord', { timeout: 2000, encoding: 'utf-8' });
      return 'arecord';
    } catch {}
    try {
      execSync('which ffmpeg', { timeout: 2000, encoding: 'utf-8' });
      return 'ffmpeg';
    } catch {}
    return 'none';
  }

  /**
   * Record audio to a temp WAV file for the given duration.
   * Returns the path to the recorded file.
   */
  async recordAudio(seconds = null) {
    const duration = seconds || this.recordSeconds;
    const tmpDir = os.tmpdir();
    const tmpFile = path.join(tmpDir, `unitycli-rec-${Date.now()}.wav`);

    if (this._capture === 'none') {
      throw new Error('No audio capture tool available');
    }

    return new Promise((resolve, reject) => {
      let proc;
      if (this._capture === 'powershell') {
        // Windows: use PowerShell with .NET NAudio-style capture
        // Simpler approach: use ffmpeg if available, fall back to WMP/SoX
        // For now: use PowerShell's SoundRecorder via a script
        const ps = `
Add-Type -AssemblyName PresentationCore,PresentationFramework
$format = New-Object System.Media.SoundPlayer
# Simpler: use ffmpeg if present, else error
& "${_ffmpegPath}" -y -f dshow -i audio=default -t ${duration} -ar 16000 -ac 1 "${tmpFile}" 2>&1 | Out-Null
`;
        proc = spawn('powershell', ['-Command', ps], { stdio: 'ignore' });
      } else if (this._capture === 'sox') {
        proc = spawn('rec', ['-q', '-c', '1', '-r', '16000', tmpFile, 'trim', '0', String(duration)], { stdio: 'ignore' });
      } else if (this._capture === 'arecord') {
        proc = spawn('arecord', ['-q', '-f', 'S16_LE', '-r', '16000', '-c', '1', '-d', String(duration), tmpFile], { stdio: 'ignore' });
      } else if (this._capture === 'ffmpeg') {
        const inputDev = this.platform === 'darwin' ? ['-f', 'avfoundation', '-i', ':0'] : ['-f', 'alsa', '-i', 'default'];
        proc = spawn(_ffmpegPath, ['-y', ...inputDev, '-t', String(duration), '-ar', '16000', '-ac', '1', tmpFile], { stdio: 'ignore' });
      }

      proc.on('close', (code) => {
        if (code === 0 && fs.existsSync(tmpFile)) resolve(tmpFile);
        else reject(new Error(`Audio capture failed (code ${code})`));
      });
      proc.on('error', reject);
    });
  }

  /**
   * Transcribe an audio file using the configured engine.
   */
  async transcribe(audioPath) {
    if (!this._detected) this.detect();
    if (this._detected === 'none') throw new Error('No STT engine configured');

    if (this._detected === 'whisper_cpp') return this._transcribeWhisperCpp(audioPath);
    if (this._detected === 'whisper_http') return this._transcribeWhisperHttp(audioPath);
    throw new Error(`Unknown STT engine: ${this._detected}`);
  }

  async _transcribeWhisperCpp(audioPath) {
    return new Promise((resolve, reject) => {
      const args = ['-m', this.whisperCppModel, '-f', audioPath, '-nt', '-otxt'];
      const proc = spawn(this.whisperCppPath, args, { stdio: ['ignore', 'pipe', 'pipe'] });
      let output = '';
      proc.stdout.on('data', (chunk) => { output += chunk.toString(); });
      proc.on('close', (code) => {
        if (code === 0) resolve(output.trim());
        else reject(new Error(`whisper.cpp exited with code ${code}`));
      });
      proc.on('error', reject);
    });
  }

  async _transcribeWhisperHttp(audioPath) {
    // POST multipart form to HTTP endpoint
    const FormData = (await import('form-data')).default;
    const axios = (await import('axios')).default;
    const form = new FormData();
    form.append('file', fs.createReadStream(audioPath));

    try {
      const resp = await axios.post(this.whisperHttpUrl, form, {
        headers: form.getHeaders(),
        timeout: 60000,
        maxContentLength: 50 * 1024 * 1024
      });
      // Try common response formats
      return resp.data.text || resp.data.transcription || resp.data.result || JSON.stringify(resp.data);
    } catch (e) {
      throw new Error(`HTTP transcribe failed: ${e.message}`);
    }
  }

  /**
   * Record and transcribe in one call.
   */
  async listen(seconds = null) {
    if (!this.enabled) return '[STT disabled]';
    if (!this._detected) this.detect();
    if (this._detected === 'none') return '[No STT engine configured]';

    try {
      const audioPath = await this.recordAudio(seconds);
      const text = await this.transcribe(audioPath);
      try { fs.unlinkSync(audioPath); } catch {}
      return text;
    } catch (e) {
      return `[STT error: ${e.message}]`;
    }
  }

  status() {
    if (!this._detected) this.detect();
    return `STT: ${this._detected} | Capture: ${this._capture} | Record: ${this.recordSeconds}s | Enabled: ${this.enabled}`;
  }
}
