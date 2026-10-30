/**
 * UnityCLI Built-in TTS — Vol 2
 * Text-to-speech without external MCP dependencies.
 *
 * Priority order:
 *   1. Piper TTS (free, local, high quality) — if installed
 *   2. System TTS (Windows SAPI via PowerShell, macOS `say`)
 *   3. None — graceful degradation
 *
 * Config in unitycli-config.json:
 *   "tts": {
 *     "engine": "auto",        // "auto", "piper", "system", "none"
 *     "piper_path": "",         // Path to piper executable
 *     "piper_model": "",        // Path to piper .onnx model
 *     "voice": "",              // System voice name (optional)
 *     "rate": 1.0,              // Speech rate multiplier
 *     "enabled": true
 *   }
 */

import { execSync, spawn } from 'child_process';
import fs from 'fs';
import path from 'path';
import os from 'os';

export class TTS {
  constructor(config = {}) {
    this.engine = config.engine || 'auto';
    this.piperPath = config.piper_path || '';
    this.piperModel = config.piper_model || '';
    this.voice = config.voice || '';
    this.rate = config.rate || 1.0;
    this.enabled = config.enabled !== false;
    this.platform = os.platform();
    this._detected = null;
  }

  /**
   * Detect available TTS engine.
   */
  detect() {
    if (this.engine !== 'auto') {
      this._detected = this.engine;
      return this._detected;
    }

    // Check Piper
    if (this.piperPath && fs.existsSync(this.piperPath)) {
      this._detected = 'piper';
      return 'piper';
    }

    // Check system TTS
    if (this.platform === 'win32') {
      try {
        execSync('powershell -Command "Add-Type -AssemblyName System.Speech; echo ok"', { timeout: 5000, encoding: 'utf-8' });
        this._detected = 'system';
        return 'system';
      } catch {}
    } else if (this.platform === 'darwin') {
      try {
        execSync('which say', { timeout: 2000, encoding: 'utf-8' });
        this._detected = 'system';
        return 'system';
      } catch {}
    } else {
      // Linux — check espeak or piper
      try {
        execSync('which espeak-ng || which espeak', { timeout: 2000, encoding: 'utf-8' });
        this._detected = 'system';
        return 'system';
      } catch {}
    }

    this._detected = 'none';
    return 'none';
  }

  /**
   * Speak text aloud. Non-blocking.
   * @param {string} text - Text to speak
   * @returns {Promise<string>} Result message
   */
  async speak(text) {
    if (!this.enabled || !text) return 'TTS disabled';
    if (!this._detected) this.detect();
    if (this._detected === 'none') return 'No TTS engine available';

    // Clean text for speech
    const clean = text
      .replace(/\*\*([^*]+)\*\*/g, '$1')  // strip bold
      .replace(/```[\s\S]*?```/g, 'code block')  // replace code blocks
      .replace(/`[^`]+`/g, '')  // strip inline code
      .replace(/#{1,6}\s/g, '')  // strip headers
      .replace(/\[E:\{[^}]*\}\]/g, '')  // strip score blocks
      .replace(/https?:\/\/\S+/g, 'link')  // replace URLs
      .slice(0, 500);  // limit length

    try {
      if (this._detected === 'piper') return await this._speakPiper(clean);
      if (this._detected === 'system') return await this._speakSystem(clean);
    } catch (e) {
      return `TTS error: ${e.message}`;
    }
    return 'TTS unavailable';
  }

  async _speakPiper(text) {
    return new Promise((resolve, reject) => {
      const args = ['--model', this.piperModel, '--output-raw'];
      const piper = spawn(this.piperPath, args, { stdio: ['pipe', 'pipe', 'pipe'] });
      piper.stdin.write(text);
      piper.stdin.end();

      // Pipe to aplay/ffplay/sox
      const player = this.platform === 'win32'
        ? spawn('powershell', ['-Command', `[System.Media.SoundPlayer]::new([System.IO.MemoryStream]::new($input)).PlaySync()`])
        : spawn('aplay', ['-r', '22050', '-f', 'S16_LE', '-t', 'raw', '-']);

      piper.stdout.pipe(player.stdin);
      player.on('close', () => resolve(`Spoke: "${text.slice(0, 50)}..."`));
      player.on('error', reject);
      piper.on('error', reject);
    });
  }

  async _speakSystem(text) {
    // Escape for shell safety
    const safe = text.replace(/"/g, '\\"').replace(/'/g, "\\'");

    if (this.platform === 'win32') {
      // Windows SAPI via PowerShell
      const voiceSelect = this.voice
        ? `$synth.SelectVoice('${this.voice}');`
        : '';
      const rateCmd = this.rate !== 1.0
        ? `$synth.Rate = ${Math.round((this.rate - 1) * 5)};`
        : '';
      const ps = `Add-Type -AssemblyName System.Speech; $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; ${voiceSelect}${rateCmd}$synth.Speak("${safe}")`;

      return new Promise((resolve) => {
        const proc = spawn('powershell', ['-Command', ps], { stdio: 'ignore' });
        proc.on('close', () => resolve(`Spoke: "${text.slice(0, 50)}..."`));
        proc.on('error', () => resolve('TTS: PowerShell speech failed'));
      });
    }

    if (this.platform === 'darwin') {
      // macOS say command
      const voiceArg = this.voice ? ['-v', this.voice] : [];
      const rateArg = this.rate !== 1.0 ? ['-r', String(Math.round(175 * this.rate))] : [];
      return new Promise((resolve) => {
        const proc = spawn('say', [...voiceArg, ...rateArg, safe], { stdio: 'ignore' });
        proc.on('close', () => resolve(`Spoke: "${text.slice(0, 50)}..."`));
        proc.on('error', () => resolve('TTS: say command failed'));
      });
    }

    // Linux — espeak
    return new Promise((resolve) => {
      const cmd = fs.existsSync('/usr/bin/espeak-ng') ? 'espeak-ng' : 'espeak';
      const proc = spawn(cmd, [safe], { stdio: 'ignore' });
      proc.on('close', () => resolve(`Spoke: "${text.slice(0, 50)}..."`));
      proc.on('error', () => resolve('TTS: espeak failed'));
    });
  }

  /**
   * List available system voices (Windows only for now).
   */
  listVoices() {
    if (this.platform === 'win32') {
      try {
        const result = execSync(
          'powershell -Command "Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).GetInstalledVoices() | ForEach { $_.VoiceInfo.Name }"',
          { timeout: 5000, encoding: 'utf-8' }
        );
        return result.trim().split('\n').filter(Boolean);
      } catch { return []; }
    }
    return ['(voice listing not supported on this platform)'];
  }

  status() {
    if (!this._detected) this.detect();
    return `TTS: ${this._detected} | Enabled: ${this.enabled} | Voice: ${this.voice || 'default'} | Rate: ${this.rate}`;
  }
}
