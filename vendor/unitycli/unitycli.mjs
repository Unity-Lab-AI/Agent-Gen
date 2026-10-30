#!/usr/bin/env node
/**
 * UnityCLI — Open CLI Agent
 * Node.js TUI with blessed, MCP subprocess support, Pollinations BYOP.
 * Built to carry a persona. Built to survive.
 *
 * Hook system — scripts fire at defined events, stdout becomes context:
 *   onStartup, beforePrompt, preToolUse, postToolUse,
 *   beforeResponse, afterResponse, onShutdown
 */

import axios from 'axios';
import { spawn, execSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import os from 'os';
import { fileURLToPath } from 'url';
import React, { useState, useEffect, useRef, useReducer } from 'react';
import { render, Box, Text, useInput, useApp, Static } from 'ink';
import TextInput from 'ink-text-input';
import { PersonaEngine, STAT_NAMES } from './persona-engine.mjs';
import { KnowledgeStore, MemoryManager, ChatChannel } from './knowledge.mjs';
import {
  ChannelRegistry,
  Vault,
  createFactsChannel,
  createMemoriesChannel,
  createSessionChannel,
  createTimeChannel,
  createWeatherChannel,
  createCalendarChannel,
  createVaultChannel
} from './channels.mjs';
import { needsSetup, runSetup, getSetupQuestions } from './setup.mjs';
import { TTS } from './tts.mjs';
import { STT } from './stt.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SESSION_LOG = path.join(__dirname, 'session.jsonl');
const STATS_DIR = path.join(__dirname, 'stats'); // depth text files — shipped with CLI

function logSession(role, content) {
  try {
    const entry = JSON.stringify({ ts: new Date().toISOString(), role, content: content.slice(0, 2000) }) + '\n';
    fs.appendFileSync(SESSION_LOG, entry);
  } catch {}
}

// ============================================================
// CONFIG
// ============================================================

let CONFIG = {};
let MODEL = 'deepseek';
let API_MODE = 'pollinations';
let POLLEN_KEY = '';
let MESSAGES = [];
let TURN_COUNT = 0;
const MCP_SERVERS = {};
const ALL_TOOLS = {};

// Persona engine — Vol 3-5
const ENGINE = new PersonaEngine(path.join(__dirname));
// Built-in TTS + STT — Vol 2
let VOICE = null; // initialized after config loads
let LISTEN = null;

// Knowledge & channels — Vol 4
const DATA_DIR = path.join(__dirname, 'data');
const KNOWLEDGE = new KnowledgeStore(DATA_DIR);
const MEMORIES = new MemoryManager(DATA_DIR);
const CHAT = new ChatChannel(DATA_DIR);
const VAULT = new Vault(DATA_DIR);
const CHANNELS = new ChannelRegistry();

function loadConfig() {
  try {
    CONFIG = JSON.parse(fs.readFileSync(path.join(__dirname, 'unitycli-config.json'), 'utf-8'));
  } catch { CONFIG = {}; }

  const llm = CONFIG.llm || {};
  MODEL = llm.model || 'deepseek';
  API_MODE = llm.provider || 'pollinations';

  // Find pollen key
  const searchPaths = [
    path.join(__dirname, '.claude', 'pollinations-user.json'),
    ...((CONFIG.pollen_key_search || []).map(b => path.join(__dirname, b, '.claude', 'pollinations-user.json')))
  ];
  for (const kf of searchPaths) {
    try {
      if (fs.existsSync(kf)) {
        const data = JSON.parse(fs.readFileSync(kf, 'utf-8'));
        if (data.api_key) { POLLEN_KEY = data.api_key; break; }
      }
    } catch {}
  }
}

// ============================================================
// PERSONA LOADER — dynamic persona files from personas/ dir
// ============================================================

const PERSONAS_DIR = path.join(__dirname, 'personas');
let AVAILABLE_PERSONAS = {};  // { name: { file, content } }
let ACTIVE_PERSONA = null;    // currently loaded persona name (null = none)

/**
 * Scan personas/ directory for .md files. Each filename (sans extension) becomes
 * a selectable persona. Content is loaded on demand.
 */
function scanPersonas() {
  AVAILABLE_PERSONAS = {};
  if (!fs.existsSync(PERSONAS_DIR)) return;
  const files = fs.readdirSync(PERSONAS_DIR).filter(f => f.endsWith('.md'));
  for (const file of files) {
    const name = path.basename(file, '.md');
    AVAILABLE_PERSONAS[name] = {
      file: path.join(PERSONAS_DIR, file),
      content: null  // lazy-loaded
    };
  }
}

/**
 * Load a persona's content from disk. Returns the markdown text or null.
 */
function loadPersonaContent(name) {
  const p = AVAILABLE_PERSONAS[name];
  if (!p) return null;
  if (!p.content) {
    try {
      p.content = fs.readFileSync(p.file, 'utf-8').trim();
    } catch { return null; }
  }
  return p.content;
}

/**
 * Set the active persona by name. Pass null to deactivate.
 */
function setActivePersona(name) {
  if (name === null || name === 'off' || name === 'none') {
    ACTIVE_PERSONA = null;
    return true;
  }
  if (!AVAILABLE_PERSONAS[name]) return false;
  // Pre-load content
  loadPersonaContent(name);
  ACTIVE_PERSONA = name;
  return true;
}

/**
 * Get the active persona's content for system prompt injection.
 */
function getActivePersonaText() {
  if (!ACTIVE_PERSONA) return null;
  return loadPersonaContent(ACTIVE_PERSONA);
}

// ============================================================
// HOOK SYSTEM
// ============================================================

let HOOKS_CONFIG = {};

function loadHooks() {
  // Load from hooks.json in bot folder, or hooks section in unitycli-config.json
  const hooksFile = path.join(__dirname, 'hooks.json');
  try {
    if (fs.existsSync(hooksFile)) {
      HOOKS_CONFIG = JSON.parse(fs.readFileSync(hooksFile, 'utf-8'));
      return;
    }
  } catch {}
  // Fallback: hooks section in main config
  HOOKS_CONFIG = CONFIG.hooks || {};
}

/**
 * Run all hooks for an event. Returns concatenated stdout from all hook scripts.
 * For preToolUse, if any hook returns "BLOCK", the tool call is blocked.
 * @param {string} event - Hook event name
 * @param {object} context - Context passed as JSON via stdin to the hook script
 * @returns {string} Combined hook output
 */
function runHooks(event, context = {}) {
  const eventHooks = HOOKS_CONFIG[event] || [];
  if (!eventHooks.length) return '';
  const outputs = [];
  for (const hook of eventHooks) {
    const cmd = hook.command || hook;
    if (!cmd) continue;
    // If hook has a matcher (for preToolUse), check it
    if (hook.matcher && context.toolName) {
      try {
        if (!new RegExp(hook.matcher).test(context.toolName)) continue;
      } catch {}
    }
    try {
      const input = JSON.stringify(context);
      const result = execSync(cmd, {
        cwd: __dirname,
        timeout: 10000,
        encoding: 'utf-8',
        input,
        maxBuffer: 256 * 1024,
        env: { ...process.env, UnityCLI_EVENT: event, UnityCLI_BOT: CONFIG.bot_name || 'CLI' }
      });
      if (result.trim()) outputs.push(result.trim());
    } catch (e) {
      // Hook failed — log but don't crash
      if (e.stdout?.trim()) outputs.push(e.stdout.trim());
    }
  }
  return outputs.join('\n');
}

// ============================================================
// FILE INJECTION (identity, memory, claude.md, state)
// ============================================================

function readFileIfExists(filePath) {
  try {
    if (fs.existsSync(filePath)) return fs.readFileSync(filePath, 'utf-8').trim();
  } catch {}
  return '';
}

function loadIdentity() {
  return readFileIfExists(path.join(__dirname, 'identity.txt'));
}

function loadMemory() {
  // Check standard Claude Code memory path first, then local
  const paths = [
    path.join(__dirname, '.home', '.claude', 'projects', 'C--claude-CLI', 'memory', 'MEMORY.md'),
    path.join(__dirname, 'MEMORY.md')
  ];
  for (const p of paths) {
    const content = readFileIfExists(p);
    if (content) return content;
  }
  return '';
}

function loadClaudeMd() {
  // Walk up from __dirname looking for CLAUDE.md (like Claude Code does)
  let dir = __dirname;
  for (let i = 0; i < 5; i++) {
    const content = readFileIfExists(path.join(dir, 'CLAUDE.md'));
    if (content) return content;
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return '';
}

function loadLastState() {
  // Find most recent NOW-YYYYMMDD-HHMM.md file
  try {
    const files = fs.readdirSync(__dirname)
      .filter(f => /^NOW-\d{8}-\d{4}\.md$/.test(f))
      .sort()
      .reverse();
    if (files.length) return fs.readFileSync(path.join(__dirname, files[0]), 'utf-8').trim();
  } catch {}
  return '';
}

function loadLastSession() {
  // Reload last N exchanges from session.jsonl for conversation continuity
  try {
    if (!fs.existsSync(SESSION_LOG)) return [];
    const lines = fs.readFileSync(SESSION_LOG, 'utf-8').trim().split('\n').filter(Boolean);
    // Take last 20 entries max for context
    const recent = lines.slice(-20);
    const messages = [];
    for (const line of recent) {
      try {
        const entry = JSON.parse(line);
        if (entry.role === 'user') messages.push({ role: 'user', content: entry.content });
        else if (entry.role === 'assistant') messages.push({ role: 'assistant', content: entry.content });
        // Skip tool entries for replay — they'd need tool_call_ids
      } catch {}
    }
    return messages;
  } catch {}
  return [];
}

// ============================================================
// MCP CLIENT
// ============================================================

class MCPServer {
  constructor(name, command, args, env = {}) {
    this.name = name;
    this.command = command;
    this.args = args;
    this.env = env;
    this.process = null;
    this.tools = {};
    this._reqId = 0;
    this._pending = {};
    this._buffer = '';
  }

  async start() {
    return new Promise((resolve) => {
      const fullEnv = { ...process.env, ...this.env };
      this.process = spawn(this.command, this.args, {
        stdio: ['pipe', 'pipe', 'pipe'],
        env: fullEnv,
        cwd: __dirname
      });

      this.process.stdout.on('data', (chunk) => {
        this._buffer += chunk.toString();
        const lines = this._buffer.split('\n');
        this._buffer = lines.pop() || '';
        for (const line of lines) {
          if (!line.trim() || !line.startsWith('{')) continue;
          try {
            const msg = JSON.parse(line);
            if (msg.id && this._pending[msg.id]) {
              this._pending[msg.id](msg);
              delete this._pending[msg.id];
            }
          } catch {}
        }
      });

      this.process.stderr.on('data', () => {}); // Suppress stderr

      // Initialize
      setTimeout(async () => {
        try {
          const initResult = await this._request('initialize', {
            protocolVersion: '2024-11-05',
            capabilities: {},
            clientInfo: { name: 'unitycli', version: '0.1.0' }
          });

          if (!initResult) { resolve('no response'); return; }

          this._notify('notifications/initialized', {});

          const toolsResult = await this._request('tools/list', {});
          if (toolsResult?.tools) {
            for (const tool of toolsResult.tools) {
              const fullName = `mcp_${this.name}_${tool.name}`;
              this.tools[fullName] = {
                server: this.name,
                originalName: tool.name,
                description: tool.description || '',
                schema: tool.inputSchema || {}
              };
            }
          }
          resolve(null);
        } catch (e) {
          resolve(e.message);
        }
      }, 500);
    });
  }

  async callTool(originalName, args) {
    const result = await this._request('tools/call', { name: originalName, arguments: args });
    if (result?.content) {
      return result.content.map(c => c.type === 'text' ? c.text : JSON.stringify(c)).join('\n');
    }
    if (result?.error) return `[MCP ERROR] ${JSON.stringify(result.error)}`;
    return '[MCP] No result';
  }

  stop() {
    if (this.process) { try { this.process.kill(); } catch {} }
  }

  _request(method, params) {
    return new Promise((resolve) => {
      const id = ++this._reqId;
      this._pending[id] = (msg) => resolve(msg.error ? { error: msg.error } : (msg.result || {}));
      const data = JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n';
      try { this.process.stdin.write(data); } catch { resolve(null); }
      setTimeout(() => { if (this._pending[id]) { delete this._pending[id]; resolve(null); } }, 15000);
    });
  }

  _notify(method, params) {
    const data = JSON.stringify({ jsonrpc: '2.0', method, params }) + '\n';
    try { this.process.stdin.write(data); } catch {}
  }
}

async function loadMCPServers() {
  const servers = CONFIG.mcpServers || {};
  const results = [];
  for (const [name, cfg] of Object.entries(servers)) {
    if (cfg.enabled === false) { results.push(`  ${name}: disabled`); continue; }
    const server = new MCPServer(name, cfg.command, cfg.args || [], cfg.env || {});
    const err = await server.start();
    if (err) {
      results.push(`  ${name}: FAILED - ${err}`);
    } else {
      MCP_SERVERS[name] = server;
      Object.assign(ALL_TOOLS, server.tools);
      results.push(`  ${name}: loaded (${Object.keys(server.tools).length} tools)`);
    }
  }
  return results;
}

// ============================================================
// BUILT-IN TOOLS
// ============================================================

const BUILTIN_TOOLS = {
  bash: 'Run a shell command. Args: command (string)',
  read_file: 'Read a file. Args: path (string)',
  write_file: 'Write a file. Args: path (string), content (string)',
  list_files: 'List files. Args: pattern (string), path (string)',
  think: 'Reason without acting. Args: thought (string)',
  wait: 'Pause N seconds. Args: seconds (integer 1-120)',
};

// ============================================================
// CONTAINMENT — sandbox the AI's file access
// ============================================================

// Self-files the AI should never read or write directly.
// These are already in the system prompt / handled by user — reading them is a tool waste, writing them is a safety hole.
const SELF_FILE_PATTERNS = [
  /identity\.txt$/i,
  /^MEMORY\.md$/i,
  /[\\/]MEMORY\.md$/i,
  /^CLAUDE\.md$/i,
  /[\\/]CLAUDE\.md$/i,
  /unitycli-config\.json$/i,
  /hooks\.json$/i,
  /[\\/]stats[\\/].*\.md$/i,
  /[\\/]hooks[\\/]/i,
  /[\\/]data[\\/]/i,
  /engine-state\.json$/i,
  /engine-log\.jsonl$/i,
  /session\.jsonl$/i,
  /^NOW-/i,
  /[\\/]NOW-/i,
  // UnityCLI source files — these are already running. Reading them is self-reference.
  /^unitycli.*\.mjs$/i,
  /[\\/]unitycli.*\.mjs$/i,
  /^test-ink\.mjs$/i,
  /[\\/]test-ink\.mjs$/i,
  /^persona-engine.*\.mjs$/i,
  /[\\/]persona-engine.*\.mjs$/i,
  /^knowledge.*\.mjs$/i,
  /[\\/]knowledge.*\.mjs$/i,
  /^channels.*\.mjs$/i,
  /[\\/]channels.*\.mjs$/i,
  /^setup.*\.mjs$/i,
  /[\\/]setup.*\.mjs$/i,
  /^tts.*\.mjs$/i,
  /[\\/]tts.*\.mjs$/i,
  /^stt.*\.mjs$/i,
  /[\\/]stt.*\.mjs$/i,
];

/**
 * Check if a path points to a self-file that should be hidden from the AI's tools.
 */
function isSelfFile(filePath) {
  if (!filePath) return false;
  const resolved = path.resolve(__dirname, filePath);
  // Only block if it's inside the CLI directory
  if (!resolved.toLowerCase().startsWith(__dirname.toLowerCase())) return false;
  const rel = path.relative(__dirname, resolved);
  return SELF_FILE_PATTERNS.some(p => p.test(rel) || p.test(filePath));
}

/**
 * Check if a write target is within allowed_write_roots.
 * Default allows CLI folder, data/, pollinations-output/, temp.
 */
function isAllowedWrite(filePath) {
  if (!filePath) return false;
  const resolved = path.resolve(__dirname, filePath);
  const roots = CONFIG.containment?.allowed_write_roots || [
    path.join(__dirname, 'data'),
    path.join(__dirname, 'pollinations-output'),
    path.join(__dirname, 'vfg_output'),
    os.tmpdir(),
  ];
  // Also always allow CLI folder EXCEPT self-files (self-files checked separately)
  const allRoots = [__dirname, ...roots];
  return allRoots.some(r => resolved.toLowerCase().startsWith(path.resolve(r).toLowerCase()));
}

/**
 * Check if a path is in a blocked directory (Windows system, Program Files, AppData, etc).
 */
function isBlockedPath(filePath) {
  if (!filePath) return false;
  const resolved = path.resolve(filePath);
  const blocked = CONFIG.containment?.blocked_paths || [
    'C:\\Windows',
    'C:\\Program Files',
    'C:\\Program Files (x86)',
    path.join(os.homedir(), 'AppData'),
  ];
  return blocked.some(b => resolved.toLowerCase().startsWith(b.toLowerCase()));
}

/**
 * Get the current containment mode. Default is 'protected'.
 *   - 'bypass'     — no containment, AI can do anything (dev mode)
 *   - 'protected'  — self-files hidden, write roots enforced, blocked paths blocked (DEFAULT)
 *   - 'readonly'   — everything protected mode blocks PLUS no writes anywhere
 *   - 'sandboxed'  — everything readonly PLUS only data/ and tmp reads allowed
 */
function getMode() {
  return CONFIG.containment?.mode || 'protected';
}

function execBuiltin(name, args) {
  try {
    if (name === 'bash') {
      const cmd = args.command || '';
      // Basic containment
      // Check containment from config, match command start or pipe start only
      const blockedCmds = CONFIG.containment?.blocked_commands || ['rm -rf', 'del /s', 'format c:', 'format d:', 'shutdown', 'reboot', 'git push', 'git reset --hard'];
      const cmdLower = cmd.toLowerCase();
      for (const b of blockedCmds) {
        // Match at start of command, after pipe, or after && — not inside strings
        if (cmdLower.startsWith(b) || cmdLower.includes('| ' + b) || cmdLower.includes('&& ' + b)) return `[BLOCKED] ${b}`;
      }
      // Nested Ink / UnityCLI execution — would break raw stdin. You ARE the running process.
      if (/\bnode\s+[^|&;]*?(unitycli|test-ink)[^|&;]*\.m?js/i.test(cmd)) {
        return `[CONTAINMENT] You ARE the running UnityCLI process — you cannot launch yourself. Your own source files are already loaded in your context. If you want to inspect how UnityCLI works, ask the user.`;
      }
      try {
        const out = execSync(cmd, { cwd: __dirname, timeout: 60000, encoding: 'utf-8', maxBuffer: 1024 * 1024 });
        return out.slice(0, 3000) || '[no output]';
      } catch (e) { return e.stderr?.slice(0, 500) || e.message; }
    }
    if (name === 'read_file') {
      const p = args.path || '';
      const mode = getMode();
      if (mode !== 'bypass') {
        // Self-files: invisible, already in your context
        if (isSelfFile(p)) {
          return `[CONTAINMENT] That file is already in your context — you are it. No need to read ${p}. Use what you already know.`;
        }
        // Blocked system paths
        if (isBlockedPath(p)) {
          return `[CONTAINMENT] Path is blocked: ${p}`;
        }
        // Sandboxed mode: only data/ and tmp allowed
        if (mode === 'sandboxed') {
          const resolved = path.resolve(__dirname, p);
          const dataDir = path.join(__dirname, 'data');
          const tmp = os.tmpdir();
          const allowed = [dataDir, tmp].some(r => resolved.toLowerCase().startsWith(r.toLowerCase()));
          if (!allowed) return `[CONTAINMENT] Sandboxed mode — only data/ and tmp reads allowed. Blocked: ${p}`;
        }
      }
      try {
        return fs.readFileSync(p, 'utf-8').slice(0, 10000);
      } catch (e) { return `[ERROR] ${e.message}`; }
    }
    if (name === 'write_file') {
      const p = args.path || '';
      const mode = getMode();
      if (mode !== 'bypass') {
        // Self-files: user-managed, never writable via tool
        if (isSelfFile(p)) {
          return `[CONTAINMENT] That's a self-file (identity/memory/config) — it's user-managed. Ask them to edit it directly. Blocked: ${p}`;
        }
        // Blocked system paths
        if (isBlockedPath(p)) {
          return `[CONTAINMENT] Path is blocked: ${p}`;
        }
        // Readonly / sandboxed: no writes at all
        if (mode === 'readonly' || mode === 'sandboxed') {
          return `[CONTAINMENT] ${mode} mode — writes disabled. Blocked: ${p}`;
        }
        // Protected: enforce allowed_write_roots
        if (!isAllowedWrite(p)) {
          return `[CONTAINMENT] Write path not in allowed roots. Blocked: ${p}`;
        }
      }
      try {
        const dir = path.dirname(p);
        if (dir) fs.mkdirSync(dir, { recursive: true });
        fs.writeFileSync(p, args.content, 'utf-8');
        return `Written: ${p} (${args.content.length} chars)`;
      } catch (e) { return `[ERROR] ${e.message}`; }
    }
    if (name === 'list_files') {
      const target = args.path || '.';
      const mode = getMode();
      if (mode !== 'bypass') {
        if (isBlockedPath(target)) {
          return `[CONTAINMENT] Path is blocked: ${target}`;
        }
        if (mode === 'sandboxed') {
          const resolved = path.resolve(__dirname, target);
          const dataDir = path.join(__dirname, 'data');
          const allowed = resolved.toLowerCase().startsWith(dataDir.toLowerCase()) ||
                          resolved.toLowerCase() === __dirname.toLowerCase();
          if (!allowed) return `[CONTAINMENT] Sandboxed mode — only data/ listings allowed.`;
        }
      }
      try {
        const out = execSync(`dir /b "${target}"`, { cwd: __dirname, encoding: 'utf-8' });
        // In protected+ mode, filter out self-files from listing so they're invisible
        if (mode !== 'bypass') {
          const lines = out.split('\n').filter(line => {
            const full = path.join(target === '.' ? __dirname : target, line.trim());
            return !isSelfFile(full) && !isSelfFile(line.trim());
          });
          return lines.join('\n').slice(0, 3000);
        }
        return out.slice(0, 3000);
      } catch { return '[no matches]'; }
    }
    if (name === 'think') { return `[Thought: ${args.thought || args.text || ''}]`; }
    if (name === 'wait') {
      const ms = Math.min(Math.max((args.seconds || 10) * 1000, 1000), 120000);
      const buf = new SharedArrayBuffer(4);
      Atomics.wait(new Int32Array(buf), 0, 0, ms); // proper sleep, no CPU spin
      return `[Waited ${ms / 1000}s]`;
    }
    return `[Unknown: ${name}]`;
  } catch (e) { return `[ERROR] ${name}: ${e.message}`; }
}

// ============================================================
// LLM BACKEND
// ============================================================

function buildSystemPrompt() {
  const sections = [];
  const toolNames = [...Object.keys(BUILTIN_TOOLS), ...Object.keys(ALL_TOOLS)].join(', ');

  // Layer 1: MEMORY.md — persistent cross-session context (highest priority, floats above all)
  const memory = loadMemory();
  if (memory) sections.push(`# Memory\n${memory}`);

  // Layer 2: CLAUDE.md — rules, identity anchor, pipeline instructions
  const claudeMd = loadClaudeMd();
  if (claudeMd) sections.push(`# Instructions\n${claudeMd}`);

  // Layer 3: identity.txt — the sacred file, who the AI IS
  // Depth-compiled using average of all stats (0-20 → 1-10)
  let identity = loadIdentity();
  if (identity && ENGINE.enabled) {
    // Average stat value → depth level
    const avgStat = STAT_NAMES.reduce((sum, s) => sum + (ENGINE.stats[s] || 10), 0) / STAT_NAMES.length;
    const avgDepth = Math.min(Math.max(Math.round(avgStat / 2), 1), 10);
    identity = PersonaEngine.depthCompile(identity, avgDepth);
  }
  if (identity) sections.push(`# Identity\n${identity}`);

  // Layer 3.5: Active persona overlay — loaded from personas/ directory
  const personaText = getActivePersonaText();
  if (personaText) sections.push(`# Active Persona: ${ACTIVE_PERSONA}\n${personaText}`);

  // Layer 4: Last state — what was happening when the session ended
  const state = loadLastState();
  if (state) sections.push(`# Last State\n${state}`);

  // Layer 5: Hook injection — persona, AWARE scopes, knowledge, etc.
  const hookOutput = runHooks('beforePrompt', { event: 'buildSystem' });
  if (hookOutput) sections.push(`# Context\n${hookOutput}`);

  // Layer 6: Persona engine — compiled depth text from stats
  if (ENGINE.enabled) {
    const persona = ENGINE.compilePersona(STATS_DIR);
    if (persona) sections.push(`# Persona\n${persona}`);
  }

  // Layer 7: Knowledge injection — facts and scopes, filtered by stats
  const scopeText = KNOWLEDGE.getScopeInjection();
  if (scopeText) sections.push(`# Rules\n${scopeText}`);
  // Knowledge facts get injected per-turn via beforePrompt, not here

  // Layer 8: Structured memories
  const memText = MEMORIES.getInjection(null, 15);
  if (memText) sections.push(`# Remembered\n${memText}`);

  // Base system prompt — always present
  sections.push(`You are UnityCLI, a CLI agent on Windows at ${__dirname}.
You have tools available: ${toolNames}. Use them when asked to do something that requires them.
Never fake user messages. Never call pollinations_setup. pollinations_setup is already configured.`);

  // Scoring instruction — tells AI to self-report emotional state
  if (ENGINE.enabled) sections.push(PersonaEngine.scoringInstruction);

  return sections.join('\n\n---\n\n');
}

function buildToolsList() {
  const tools = [];
  for (const [name, desc] of Object.entries(BUILTIN_TOOLS)) {
    tools.push({ type: 'function', function: { name, description: desc, parameters: { type: 'object', properties: {} } } });
  }
  for (const [name, info] of Object.entries(ALL_TOOLS)) {
    tools.push({ type: 'function', function: { name, description: (info.description || '').slice(0, 200), parameters: info.schema || { type: 'object', properties: {} } } });
  }
  return tools;
}

function stripAds(content) {
  const tail = content.slice(-200);
  for (const marker of ['**Support Pollinations', 'Powered by Pollinations', 'pollinations.ai/redirect']) {
    const idx = tail.indexOf(marker);
    if (idx > -1) { content = content.slice(0, content.length - 200 + idx).trimEnd(); }
  }
  return content;
}

async function callLLM(messages, tools) {
  if (API_MODE === 'pollinations') {
    const url = 'https://gen.pollinations.ai/v1/chat/completions';
    const headers = { 'Content-Type': 'application/json' };
    if (POLLEN_KEY) headers['Authorization'] = `Bearer ${POLLEN_KEY}`;
    const body = { model: MODEL, messages, temperature: 0.7, max_tokens: 2048 };
    if (tools?.length) { body.tools = tools; body.tool_choice = 'auto'; }
    try {
      const resp = await axios.post(url, body, { headers, timeout: 120000 });
      const msg = resp.data.choices?.[0]?.message || {};
      if (msg.content) msg.content = stripAds(msg.content);
      return msg;
    } catch (e) {
      const err = e.response?.data?.error?.message || e.message;
      if (err.includes('content management policy')) return { role: 'assistant', content: '[Moderation filter - rephrase]' };
      return { role: 'assistant', content: `[ERROR] ${err.slice(0, 200)}` };
    }
  } else {
    const url = CONFIG.llm?.ollama_url || 'http://localhost:11434/api/chat';
    const body = { model: MODEL, messages, stream: false, options: { temperature: 0.7, num_predict: 2048 } };
    if (tools?.length) body.tools = tools;
    try {
      const resp = await axios.post(url, body, { timeout: 120000 });
      return resp.data.message || { role: 'assistant', content: '[no response]' };
    } catch (e) { return { role: 'assistant', content: `[ERROR] ${e.message}` }; }
  }
}

// ============================================================
// TUI
// ============================================================


// ============================================================
// INK UI — React-based terminal rendering, handles emoji natively
// ============================================================

// Module-level refs so agentLoop/commands can update UI state
let _setLines = null;
let _setStatus = null;
let _setStats = null;
let _setHint = null;
let _setToast = null;
let _exitApp = null;
let _forceRender = null; // called after TURN_COUNT/MODEL/mode changes to refresh status bar
let _outputBuffer = [];
let _lineIdCounter = 0; // monotonic — never collides, keeps React keys unique

function uiOut(text, color = 'white') {
  // Split multi-line output so each line gets its own stable React key
  const raw = String(text ?? '');
  const lines = raw.length ? raw.split('\n') : [''];
  for (const line of lines) {
    _lineIdCounter++;
    _outputBuffer.push({ id: _lineIdCounter, text: line, color });
  }
  // DO NOT shift — shifting front mutates indices and confuses Ink's Static.
  // Let the buffer grow; 10k lines is a few MB of strings, fine for a session.
  if (_outputBuffer.length > 10000) {
    // Hard cap — but replace buffer wholesale (new array, new refs) so Static
    // treats it as a fresh batch rather than a shift.
    _outputBuffer = _outputBuffer.slice(-5000);
  }
  if (_setLines) _setLines(_outputBuffer.slice());
}

function uiStatus(text) { if (_setStatus) _setStatus(text); }

function uiStats() {
  if (!_setStats) return;
  const sorted = [...STAT_NAMES]
    .map(s => ({ name: s, val: Math.round(ENGINE.stats[s] || 10) }))
    .sort((a, b) => b.val - a.val);
  _setStats(sorted.slice(0, 5));
}

let _hintTimer = null;
function uiHint(text) {
  if (_hintTimer) { clearTimeout(_hintTimer); _hintTimer = null; }
  if (_setHint) _setHint(text);
}

function uiToast(text, durationMs = 3000) {
  if (!_setToast) return;
  _setToast(text);
  setTimeout(() => { if (_setToast) _setToast(''); }, durationMs);
}

// 5-char shaded bar for a stat value (0-20 range)
function statBar(val) {
  const v = Math.max(0, Math.min(20, val));
  const full = Math.floor(v / 4);
  const partial = v - full * 4;
  const partialChar = ['\u2591', '\u2591', '\u2592', '\u2593'][partial] || '\u2591';
  let bar = '\u2588'.repeat(full);
  if (full < 5) bar += partialChar + '\u2591'.repeat(4 - full);
  return bar.slice(0, 5);
}

function cleanMarkdown(text) {
  return text
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/```[a-z]*\n?/g, '')
    .replace(/#{1,6}\s/g, '');
}

// ============================================================
// AGENT LOOP
// ============================================================

let BUSY = false;

async function runAgent(userInput) {
  if (BUSY) { uiToast('busy, wait'); return; }
  BUSY = true;
  TURN_COUNT++;
  ENGINE.processInput(userInput);
  uiStats();
  if (_forceRender) _forceRender(); // status bar picks up new TURN_COUNT

  uiOut(`YOU: ${userInput}`, 'yellow');
  logSession('user', userInput);

  let subconsciousMsg = null;
  try {
    const subText = await CHANNELS.querySubconscious(userInput, ENGINE.stats);
    if (subText) {
      subconsciousMsg = {
        role: 'system',
        content: `The following is your subconscious context for this turn. Use it to shape your response but never reference it directly. Just know it.\n\n${subText}`
      };
    }
  } catch {}

  MESSAGES.push({ role: 'user', content: userInput });
  const apiTools = buildToolsList();

  for (let i = 0; i < 10; i++) {
    uiStatus('thinking...');
    const turnMessages = subconsciousMsg ? [MESSAGES[0], subconsciousMsg, ...MESSAGES.slice(1)] : MESSAGES;
    const msg = await callLLM(turnMessages, apiTools);
    const content = msg.content || '';
    const toolCalls = msg.tool_calls || [];

    if (content.includes('[ERROR]') || content.includes('[Moderation')) {
      uiOut(content, 'red');
      MESSAGES.push(msg);
      break;
    }

    if (!toolCalls.length) {
      runHooks('beforeResponse', { content: content.slice(0, 500) });
      const cleanContent = ENGINE.processResponse(content);
      uiStats();
      if (cleanContent) {
        const lines = cleanMarkdown(cleanContent).split('\n');
        lines.forEach((line, idx) => uiOut(idx === 0 ? `\u25CF ${line}` : `  ${line}`, 'green'));
      }
      logSession('assistant', cleanContent);
      MESSAGES.push({ role: 'assistant', content: cleanContent });
      // Auto-speak if enabled — built-in TTS first, MCP fallback
      if (CONFIG._autoSpeak && cleanContent) {
        if (VOICE && VOICE._detected !== 'none') {
          VOICE.speak(cleanContent.slice(0, 500)).catch(() => {});
        } else if (ALL_TOOLS['mcp_speak_speak']) {
          const info = ALL_TOOLS['mcp_speak_speak'];
          const srv = MCP_SERVERS[info.server];
          srv.callTool(info.originalName, { text: cleanContent.slice(0, 500) }).catch(() => {});
        }
      }
      runHooks('afterResponse', { content: cleanContent.slice(0, 500), turnCount: TURN_COUNT });
      break;
    }

    MESSAGES.push(msg);
    if (content) for (const line of content.split('\n')) uiOut(line, 'gray');

    for (const tc of toolCalls) {
      const fn = tc.function || {};
      const name = fn.name || '';
      let args = {};
      try { args = JSON.parse(fn.arguments || '{}'); } catch {}
      const callId = tc.id || `call_${name}`;

      uiStatus(`calling ${name}...`);
      uiOut(`\u25C6 ${name}`, 'cyan');
      for (const [k, v] of Object.entries(args)) {
        const val = String(v);
        const display = val.length > 120 ? val.slice(0, 117) + '...' : val;
        uiOut(`  ${k}: ${display}`, 'white');
      }

      let result;
      const preHook = runHooks('preToolUse', { toolName: name, args });
      if (preHook.includes('BLOCK')) {
        result = `[BLOCKED by hook] ${preHook.replace('BLOCK', '').trim()}`;
      } else if (ALL_TOOLS[name]) {
        const info = ALL_TOOLS[name];
        const srv = MCP_SERVERS[info.server];
        result = await srv.callTool(info.originalName, args);
      } else if (BUILTIN_TOOLS[name]) {
        result = execBuiltin(name, args);
      } else {
        result = `[Unknown: ${name}]`;
      }
      runHooks('postToolUse', { toolName: name, args, result: (result || '').slice(0, 500) });

      const resultLines = result.split('\n').filter(l => l.trim());
      for (const line of resultLines.slice(0, 3)) uiOut(`  ${line.slice(0, 120)}`, 'white');
      if (resultLines.length > 3) uiOut(`  ... +${resultLines.length - 3} lines`, 'gray');

      logSession('tool', `${name}: ${result.slice(0, 500)}`);
      MESSAGES.push({ role: 'tool', tool_call_id: callId, content: result });
    }
  }

  uiStatus('ready');
  BUSY = false;
}

// ============================================================
// COMMANDS
// ============================================================

async function handleCommand(cmd) {
  // Preserve original casing for args (like text content), lowercase for keyword matching
  const lc = cmd.toLowerCase();

  if (lc === '/help') {
    const cmds = [
      '/help - this help', '/exit - quit', '/clear - reset conversation',
      '/model [name] - switch model (deepseek, openai, openai-fast, mistral)',
      '/mcp - list MCP servers', '/tools - list available tools',
      '/go - run startup procedure (commands/go.md)',
      '/hooks - list configured hooks',
      '/state - show last NOW state',
      '/identity - show identity.txt',
      '/stats - show persona engine stats',
      '/engine [on|off] - toggle persona engine',
      '/guard [stat] [floor|ceiling] [val] [hard|soft|off] - set guard',
      '/baseline [stat] [value] - set resting baseline',
      '/know [text] - add a fact',
      '/scope [text] - add a scope/rule',
      '/remember [text] - save a memory',
      '/search [query] - search knowledge',
      '/knowledge - knowledge/memory/vault status',
      '/pending - list unverified facts',
      '/verify [id] - verify a pending fact',
      '/channels - list AWARE channels',
      '/channel [name] [on|off] - enable/disable channel',
      '/vault - list vault entries',
      '/vault store [title] - save conversation to vault',
      '/vault search [query] - search vault',
      '/chat [text] - send to shared chat',
      '/inbox - check messages from other AIs',
      '/chatlog - show chat history',
      '/say [text] - speak text aloud',
      '/voice [on|off] - toggle auto-speak responses',
      '/tts - TTS engine status',
      '/voices - list available voices',
      '/listen [seconds] - record mic + transcribe',
      '/stt - STT engine status',
      '/hint [text] - set persistent hint',
      '/tip [text] - flash a toast',
      '/mode [bypass|protected|readonly|sandboxed] - containment mode',
      '/personas - list available personas from personas/',
      '/persona [name] - load a persona (or "off" to disable)',
    ];
    for (const c of cmds) uiOut(`  ${c}`, 'cyan');
    return true;
  }

  if (lc === '/exit' || lc === 'quit' || lc === 'exit') {
    runHooks('onShutdown', { turnCount: TURN_COUNT, model: MODEL });
    for (const s of Object.values(MCP_SERVERS)) s.stop();
    // Unmount Ink first so it finishes writing to alt screen,
    // then exit alt screen so the main buffer is restored cleanly.
    if (_exitApp) _exitApp();
    setTimeout(() => {
      process.exit(0);
    }, 120);
    return true;
  }

  if (lc === '/clear') {
    MESSAGES = [{ role: 'system', content: buildSystemPrompt() }];
    TURN_COUNT = 0;
    _outputBuffer = [];
    if (_setLines) _setLines([]);
    uiOut('[cleared]', 'white');
    uiStatus('ready');
    if (_forceRender) _forceRender();
    return true;
  }

  if (lc === '/stats') {
    uiOut(`Persona Engine: ${ENGINE.enabled ? 'ON' : 'OFF'}  |  Turn: ${ENGINE.turn}`, 'cyan');
    for (const line of ENGINE.statusText().split('\n')) uiOut(`  ${line}`, 'white');
    return true;
  }

  if (lc.startsWith('/model')) {
    const parts = lc.split(/\s+/);
    if (parts[1]) {
      MODEL = parts[1];
      const ollama = ['dolphin-mistral', 'deepseek-r1', 'dolphin-mistral:7b', 'deepseek-r1:8b'];
      API_MODE = ollama.includes(MODEL) ? 'ollama' : 'pollinations';
      try {
        const cfg = JSON.parse(fs.readFileSync(path.join(__dirname, 'unitycli-config.json'), 'utf-8'));
        cfg.llm = cfg.llm || {};
        cfg.llm.model = MODEL; cfg.llm.provider = API_MODE;
        fs.writeFileSync(path.join(__dirname, 'unitycli-config.json'), JSON.stringify(cfg, null, 2));
      } catch {}
      uiOut(`  Model: ${MODEL} via ${API_MODE} (saved)`, 'green');
      if (_forceRender) _forceRender();
    } else {
      uiOut(`  Current: ${MODEL} via ${API_MODE}`, 'white');
    }
    return true;
  }

  if (lc === '/mcp') {
    for (const [n, s] of Object.entries(MCP_SERVERS)) uiOut(`  ${n}: ${Object.keys(s.tools).length} tools`, 'green');
    if (!Object.keys(MCP_SERVERS).length) uiOut('  No MCP servers', 'white');
    return true;
  }

  if (lc === '/tools') {
    uiOut('  Built-in:', 'cyan');
    for (const [n, d] of Object.entries(BUILTIN_TOOLS)) uiOut(`    ${n}: ${d}`, 'white');
    if (Object.keys(ALL_TOOLS).length) {
      uiOut('  MCP:', 'cyan');
      for (const [n, t] of Object.entries(ALL_TOOLS)) uiOut(`    ${n}: ${(t.description || '').slice(0, 60)}`, 'white');
    }
    return true;
  }

  if (lc === '/go') {
    const goPaths = [path.join(__dirname, 'commands', 'go.md'), path.join(__dirname, 'go.md')];
    for (const gp of goPaths) {
      const goContent = readFileIfExists(gp);
      if (goContent) {
        uiOut('[/go — running startup procedure]', 'cyan');
        runAgent(goContent);
        return true;
      }
    }
    uiOut('  No commands/go.md found', 'yellow');
    return true;
  }

  if (lc === '/hooks') {
    const events = Object.keys(HOOKS_CONFIG);
    if (!events.length) { uiOut('  No hooks configured. Create hooks.json or add hooks to unitycli-config.json', 'white'); return true; }
    for (const ev of events) {
      const hooks = HOOKS_CONFIG[ev] || [];
      uiOut(`  ${ev}: ${hooks.length} hook(s)`, 'cyan');
      for (const h of hooks) uiOut(`    ${h.command || h}`, 'white');
    }
    return true;
  }

  if (lc === '/state') {
    const state = loadLastState();
    if (state) {
      for (const line of state.split('\n').slice(0, 20)) uiOut(`  ${line}`, 'white');
    } else {
      uiOut('  No state file found', 'white');
    }
    return true;
  }

  if (lc === '/identity') {
    const id = loadIdentity();
    if (id) {
      for (const line of id.split('\n').slice(0, 20)) uiOut(`  ${line}`, 'white');
    } else {
      uiOut('  No identity.txt found', 'white');
    }
    return true;
  }

  if (lc.startsWith('/engine')) {
    const arg = lc.split(/\s+/)[1];
    if (arg === 'on') { ENGINE.enabled = true; ENGINE.save(); uiOut('  Engine ON', 'green'); }
    else if (arg === 'off') { ENGINE.enabled = false; ENGINE.save(); uiOut('  Engine OFF', 'yellow'); }
    else uiOut(`  Engine is ${ENGINE.enabled ? 'ON' : 'OFF'}. Use /engine on|off`, 'white');
    return true;
  }

  if (lc.startsWith('/guard')) {
    const parts = cmd.split(/\s+/);
    if (parts.length >= 5) {
      const stat = parts[1].toLowerCase(), side = parts[2].toLowerCase(), val = parseFloat(parts[3]), mode = parts[4].toLowerCase();
      if (STAT_NAMES.includes(stat) && ['floor', 'ceiling'].includes(side) && ['hard', 'soft', 'off'].includes(mode)) {
        ENGINE.setGuard(stat, side, val, mode);
        uiOut(`  Guard set: ${stat} ${side} = ${val} (${mode})`, 'green');
      } else {
        uiOut('  Usage: /guard [stat] [floor|ceiling] [0-20] [hard|soft|off]', 'yellow');
      }
    } else {
      uiOut('  Usage: /guard [stat] [floor|ceiling] [0-20] [hard|soft|off]', 'yellow');
      uiOut(`  Stats: ${STAT_NAMES.join(', ')}`, 'white');
    }
    return true;
  }

  if (lc.startsWith('/baseline')) {
    const parts = cmd.split(/\s+/);
    if (parts.length >= 3) {
      const stat = parts[1].toLowerCase(), val = parseFloat(parts[2]);
      if (STAT_NAMES.includes(stat) && !isNaN(val)) {
        ENGINE.setBaseline(stat, val);
        uiOut(`  Baseline: ${stat} = ${val}`, 'green');
      } else {
        uiOut('  Usage: /baseline [stat] [0-20]', 'yellow');
      }
    } else {
      uiOut('  Usage: /baseline [stat] [0-20]', 'yellow');
      uiOut(`  Current: ${JSON.stringify(ENGINE.baseline)}`, 'white');
    }
    return true;
  }

  // --- Knowledge & Memory ---
  if (lc.startsWith('/know ')) {
    const text = cmd.slice(6).trim();
    if (text) {
      const entry = KNOWLEDGE.addFact(text);
      uiOut(`  Fact #${entry.id} added`, 'green');
    }
    return true;
  }

  if (lc.startsWith('/scope ')) {
    const text = cmd.slice(7).trim();
    if (text) {
      const entry = KNOWLEDGE.addScope(text);
      uiOut(`  Scope #${entry.id} added`, 'green');
    }
    return true;
  }

  if (lc.startsWith('/remember ')) {
    const text = cmd.slice(10).trim();
    if (text) {
      const typeMatch = text.match(/^\[(user|feedback|project|reference)\]\s*/i);
      const type = typeMatch ? typeMatch[1].toLowerCase() : 'user';
      const content = typeMatch ? text.slice(typeMatch[0].length) : text;
      const entry = MEMORIES.add(content, type);
      uiOut(`  Memory #${entry.id} (${type}) saved`, 'green');
    }
    return true;
  }

  if (lc.startsWith('/search ')) {
    const query = cmd.slice(8).trim();
    const results = KNOWLEDGE.searchFacts(query, 10);
    if (results.length) {
      for (const r of results) uiOut(`  #${r.id} [${r.score.toFixed(1)}] ${r.text.slice(0, 100)}`, 'white');
    } else {
      uiOut('  No results', 'white');
    }
    return true;
  }

  if (lc === '/knowledge') {
    uiOut(`  ${KNOWLEDGE.status()}`, 'cyan');
    uiOut(`  ${MEMORIES.status()}`, 'cyan');
    uiOut(`  ${VAULT.status()}`, 'cyan');
    const pending = KNOWLEDGE.getPendingFacts();
    if (pending.length) uiOut(`  ${pending.length} unverified facts — use /pending to review`, 'yellow');
    return true;
  }

  if (lc === '/pending') {
    const pending = KNOWLEDGE.getPendingFacts();
    if (!pending.length) { uiOut('  No pending facts', 'white'); return true; }
    for (const f of pending.slice(0, 20)) {
      uiOut(`  #${f.id} [${f.source}] ${f.text.slice(0, 100)}`, 'white');
    }
    uiOut('  Use /verify [id] to approve', 'cyan');
    return true;
  }

  if (lc.startsWith('/verify ')) {
    const id = parseInt(cmd.slice(8).trim());
    if (KNOWLEDGE.verifyFact(id)) uiOut(`  Fact #${id} verified`, 'green');
    else uiOut(`  Fact #${id} not found`, 'yellow');
    return true;
  }

  if (lc === '/channels') {
    for (const ch of CHANNELS.list()) {
      uiOut(`  ${ch.name} (${ch.type}) ${ch.enabled ? 'ON' : 'OFF'}`, ch.enabled ? 'green' : 'gray');
    }
    return true;
  }

  if (lc.startsWith('/channel ')) {
    const parts = cmd.split(/\s+/);
    if (parts.length === 3) {
      const name = parts[1], action = parts[2].toLowerCase();
      if (action === 'on') { CHANNELS.enable(name); uiOut(`  ${name}: ON`, 'green'); }
      else if (action === 'off') { CHANNELS.disable(name); uiOut(`  ${name}: OFF`, 'yellow'); }
      else uiOut('  Usage: /channel [name] [on|off]', 'yellow');
    } else {
      uiOut('  Usage: /channel [name] [on|off]', 'yellow');
    }
    return true;
  }

  if (lc.startsWith('/vault store ')) {
    const title = cmd.slice(13).trim();
    if (title) {
      const content = MESSAGES.filter(m => m.role !== 'system').map(m => `[${m.role}] ${m.content}`).join('\n\n');
      const entry = VAULT.store(title, content, ['conversation']);
      uiOut(`  Vault #${entry.id}: "${title}" stored (${entry.wordCount} words)`, 'green');
    }
    return true;
  }

  if (lc.startsWith('/vault search ')) {
    const query = cmd.slice(14).trim();
    const results = VAULT.search(query, 5);
    if (results.length) {
      for (const r of results) {
        uiOut(`  #${r.id} [${r.score}] ${r.title}`, 'cyan');
        uiOut(`    ${r.excerpt.slice(0, 150)}`, 'white');
      }
    } else {
      uiOut('  No vault matches', 'white');
    }
    return true;
  }

  if (lc === '/vault') {
    uiOut(`  ${VAULT.status()}`, 'cyan');
    for (const e of VAULT.index.slice(-10)) {
      uiOut(`  #${e.id} ${e.title} (${e.wordCount} words)`, 'white');
    }
    return true;
  }

  // --- Chat ---
  if (lc.startsWith('/chat ')) {
    const text = cmd.slice(6).trim();
    const botName = CONFIG.bot_name || 'UnityCLI';
    CHAT.send(botName, text);
    uiOut(`  [${botName}] ${text}`, 'green');
    return true;
  }

  if (lc === '/inbox') {
    const msgs = CHAT.checkInbox(10);
    if (msgs.length) {
      for (const m of msgs) uiOut(`  [${m.from}] ${m.text}`, 'cyan');
      CHAT.clearInbox();
    } else {
      uiOut('  No messages', 'white');
    }
    return true;
  }

  if (lc === '/chatlog') {
    const msgs = CHAT.read(20);
    if (msgs.length) {
      for (const m of msgs) uiOut(`  ${m.ts.slice(11, 19)} [${m.from}] ${m.text}`, 'white');
    } else {
      uiOut('  No chat history', 'white');
    }
    return true;
  }

  // --- Voice ---
  if (lc.startsWith('/say ')) {
    const text = cmd.slice(5).trim();
    if (!text) return true;
    if (VOICE && VOICE._detected !== 'none') {
      VOICE.speak(text).then(r => uiOut(`  ${r}`, 'magenta')).catch(() => {});
    } else if (ALL_TOOLS['mcp_speak_speak']) {
      const info = ALL_TOOLS['mcp_speak_speak'];
      const srv = MCP_SERVERS[info.server];
      srv.callTool(info.originalName, { text }).then(r => uiOut(`  ${r}`, 'magenta')).catch(() => {});
    } else {
      uiOut('  No TTS engine available. Install Piper or enable system TTS.', 'yellow');
    }
    return true;
  }

  if (lc === '/voices') {
    if (VOICE) {
      const voices = VOICE.listVoices();
      if (voices.length) for (const v of voices) uiOut(`  ${v}`, 'white');
      else uiOut('  No voices available', 'white');
    }
    return true;
  }

  if (lc === '/tts') {
    if (VOICE) uiOut(`  ${VOICE.status()}`, 'cyan');
    else uiOut('  TTS not initialized', 'yellow');
    return true;
  }

  if (lc.startsWith('/listen')) {
    const parts = lc.split(/\s+/);
    const seconds = parseInt(parts[1]) || 5;
    if (!LISTEN || LISTEN._detected === 'none') {
      uiOut('  STT not configured. Set whisper_cpp_path or whisper_http_url in unitycli-config.json', 'yellow');
      return true;
    }
    uiOut(`  Listening for ${seconds}s...`, 'cyan');
    LISTEN.listen(seconds).then(async (text) => {
      if (text && !text.startsWith('[')) {
        uiOut(`  Heard: ${text}`, 'yellow');
        await runAgent(text);
      } else {
        uiOut(`  ${text}`, 'yellow');
      }
    }).catch(e => uiOut(`  STT error: ${e.message}`, 'red'));
    return true;
  }

  if (lc === '/stt') {
    if (LISTEN) uiOut(`  ${LISTEN.status()}`, 'cyan');
    else uiOut('  STT not initialized', 'yellow');
    return true;
  }

  if (lc === '/hint' || lc === '/hint clear') {
    uiHint('');
    return true;
  }
  if (lc.startsWith('/hint ')) {
    const text = cmd.slice(6).trim();
    uiHint(text);
    return true;
  }
  if (lc.startsWith('/tip ')) {
    const text = cmd.slice(5).trim();
    uiToast(text, 5000);
    return true;
  }

  if (lc.startsWith('/mode')) {
    const arg = lc.split(/\s+/)[1];
    const valid = ['bypass', 'protected', 'readonly', 'sandboxed'];
    if (arg && valid.includes(arg)) {
      if (!CONFIG.containment) CONFIG.containment = {};
      CONFIG.containment.mode = arg;
      try {
        const cfgPath = path.join(__dirname, 'unitycli-config.json');
        const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf-8'));
        if (!cfg.containment) cfg.containment = {};
        cfg.containment.mode = arg;
        fs.writeFileSync(cfgPath, JSON.stringify(cfg, null, 2));
      } catch {}
      uiOut(`  Containment mode: ${arg}`, 'green');
      const desc = {
        bypass: 'No containment — AI can read/write anywhere. Dev mode only.',
        protected: 'Self-files hidden. Write roots enforced. Blocked paths blocked. (default)',
        readonly: 'Protected + no writes anywhere.',
        sandboxed: 'Strictest — only data/ and tmp reads, no writes.'
      };
      uiOut(`  ${desc[arg]}`, 'white');
      if (_forceRender) _forceRender();
    } else {
      uiOut(`  Current mode: ${getMode()}`, 'cyan');
      uiOut('  Available: bypass, protected, readonly, sandboxed', 'white');
    }
    return true;
  }

  // ---- Persona commands ----
  if (lc === '/personas') {
    scanPersonas();  // rescan for new files
    const names = Object.keys(AVAILABLE_PERSONAS);
    if (names.length === 0) {
      uiOut('  No persona files found in personas/', 'yellow');
    } else {
      uiOut(`  Available personas (${names.length}):`, 'cyan');
      for (const name of names.sort()) {
        const active = name === ACTIVE_PERSONA ? ' ← ACTIVE' : '';
        uiOut(`    ${name}${active}`, active ? 'green' : 'white');
      }
    }
    uiOut(`  Active: ${ACTIVE_PERSONA || 'none'}`, 'cyan');
    uiOut('  Use /persona [name] to load, /persona off to disable', 'white');
    if (_forceRender) _forceRender();
    return true;
  }

  if (lc.startsWith('/persona')) {
    const arg = cmd.split(/\s+/)[1];
    if (!arg) {
      uiOut(`  Active persona: ${ACTIVE_PERSONA || 'none'}`, 'cyan');
      uiOut('  Use /personas to list available, /persona [name] to switch', 'white');
      if (_forceRender) _forceRender();
      return true;
    }
    const name = arg.toLowerCase();
    if (name === 'off' || name === 'none') {
      setActivePersona(null);
      MESSAGES = [{ role: 'system', content: buildSystemPrompt() }];
      uiOut('  Persona disabled — using base identity only', 'yellow');
      if (_forceRender) _forceRender();
      return true;
    }
    scanPersonas();  // rescan in case new files were added
    if (setActivePersona(name)) {
      MESSAGES = [{ role: 'system', content: buildSystemPrompt() }];
      uiOut(`  Persona loaded: ${name}`, 'green');
      const content = loadPersonaContent(name);
      if (content) {
        const preview = content.split('\n').find(l => l.trim() && !l.startsWith('#')) || '';
        uiOut(`  ${preview.slice(0, 100)}...`, 'white');
      }
    } else {
      uiOut(`  Persona "${name}" not found`, 'red');
      uiOut(`  Available: ${Object.keys(AVAILABLE_PERSONAS).join(', ') || 'none'}`, 'white');
    }
    if (_forceRender) _forceRender();
    return true;
  }

  if (lc.startsWith('/voice')) {
    const arg = lc.split(/\s+/)[1];
    if (arg === 'on') { CONFIG._autoSpeak = true; uiOut('  Auto-speak ON', 'green'); }
    else if (arg === 'off') { CONFIG._autoSpeak = false; uiOut('  Auto-speak OFF', 'yellow'); }
    else uiOut(`  Auto-speak: ${CONFIG._autoSpeak ? 'ON' : 'OFF'}. Use /voice on|off`, 'white');
    return true;
  }

  return false;
}

// ============================================================
// REACT COMPONENT
// ============================================================

const HINT_ROTATION = [
  '/help for commands',
  '/stats to see persona state',
  '/channels to see AWARE sources',
  '/go to run startup procedure',
  '/listen for voice input',
  '/vault search [query] to search deep storage',
  '/know [text] to add a fact',
  '/guard [stat] [floor|ceiling] [val] [hard|soft|off]',
  'Tip: edit identity.txt live — changes apply next turn',
];

const App = () => {
  const [lines, setLines] = useState([]);
  const [input, setInput] = useState('');
  const [status, setStatus] = useState('ready');
  const [stats, setStats] = useState([]);
  const [hint, setHint] = useState(HINT_ROTATION[0]);
  const [toast, setToast] = useState('');
  const [, forceTick] = useReducer(x => x + 1, 0);
  const { exit } = useApp();

  useEffect(() => {
    _setLines = setLines;
    _setStatus = setStatus;
    _setStats = setStats;
    _setHint = setHint;
    _setToast = setToast;
    _exitApp = exit;
    _forceRender = forceTick;
    uiStats();
    let idx = 0;
    const interval = setInterval(() => {
      idx = (idx + 1) % HINT_ROTATION.length;
      setHint(HINT_ROTATION[idx]);
    }, 12000);
    return () => clearInterval(interval);
  }, []);

  const handleSubmit = async (value) => {
    const text = value.replace(/[\r\n]+/g, ' ').trim();
    setInput('');
    if (!text) return;
    if (text === '/exit' || text === 'quit' || text === 'exit') {
      runHooks('onShutdown', { turnCount: TURN_COUNT, model: MODEL });
      for (const s of Object.values(MCP_SERVERS)) s.stop();
      // Unmount Ink first, THEN exit alt screen (opposite order corrupts the main buffer).
      exit();
      setTimeout(() => {
        try { process.stdout.write('\x1b[?1049l'); } catch {}
        process.exit(0);
      }, 120);
      return;
    }
    if (text.startsWith('/') && await handleCommand(text)) return;
    if (BUSY) { uiToast('busy, wait'); return; }
    await runAgent(text);
  };

  // Layout parameters — read each render so resize mostly works
  const termWidth = Math.max(40, Math.min(process.stdout.columns || 80, 200));
  const ruleLine = '\u2500'.repeat(termWidth);

  const toolCount = Object.keys(ALL_TOOLS).length + Object.keys(BUILTIN_TOOLS).length;
  const modeFull = CONFIG.containment?.mode || 'protected';
  const mode = modeFull.slice(0, 4);
  const modeColor = mode === 'bypa' ? 'red' : mode === 'sand' ? 'magenta' : mode === 'read' ? 'yellow' : 'green';

  // Turn progress bar — 8-char fill
  const filled = Math.min(Math.floor((TURN_COUNT / 10) * 8), 8);
  const turnBar = '#'.repeat(filled) + '-'.repeat(8 - filled);

  // Top-5 stats text
  const statsText = stats.length
    ? stats.map(s => `${s.name.slice(0, 3).toUpperCase()}:${statBar(s.val)}`).join(' ')
    : '';

  return React.createElement(Box, { flexDirection: 'column' },
    // Append-only log — scrolls into terminal scrollback above the live area
    React.createElement(Static, { items: lines },
      (line) => React.createElement(Text,
        { key: line.id, color: line.color || 'white' },
        line.text === '' ? ' ' : line.text
      )
    ),
    // Live area — rule, input, rule, 2 status bars (5 fixed rows)
    React.createElement(Box, { flexDirection: 'column' },
      // Rule above input
      React.createElement(Text, { color: 'gray' }, ruleLine),
      // Input row
      React.createElement(Box, null,
        React.createElement(Text, { color: 'greenBright' }, '> '),
        React.createElement(TextInput, {
          value: input,
          onChange: setInput,
          onSubmit: handleSubmit,
          placeholder: ''
        })
      ),
      // Rule below input
      React.createElement(Text, { color: 'gray' }, ruleLine),
      // Status row 1: UnityCLI | model | turn | tools | mode | status | toast
      React.createElement(Box, null,
        React.createElement(Text, { color: 'cyan' }, ' UnityCLI '),
        React.createElement(Text, { color: 'gray' }, '| '),
        React.createElement(Text, { color: 'green' }, MODEL),
        React.createElement(Text, { color: 'gray' }, ' | '),
        React.createElement(Text, null, `[${turnBar}] ${TURN_COUNT}/10`),
        React.createElement(Text, { color: 'gray' }, ' | '),
        React.createElement(Text, null, `${toolCount} tools`),
        React.createElement(Text, { color: 'gray' }, ' | '),
        React.createElement(Text, { color: modeColor }, mode),
        React.createElement(Text, { color: 'gray' }, ' | '),
        React.createElement(Text, { color: 'yellow' }, status),
        toast ? React.createElement(Text, { color: 'gray' }, `  ${toast}`) : null
      ),
      // Status row 2: stat snapshot | hint
      React.createElement(Box, null,
        React.createElement(Text, { color: 'blueBright' }, statsText ? ` ${statsText}` : ' '),
        React.createElement(Text, { color: 'gray' }, '    '),
        React.createElement(Text, { color: 'yellow' }, hint ? `> ${hint}` : '')
      )
    )
  );
};

// ============================================================
// MAIN — wire everything up then render
// ============================================================

async function main() {
  loadConfig();
  loadHooks();
  scanPersonas();
  ENGINE.load();
  try { fs.mkdirSync(DATA_DIR, { recursive: true }); } catch {}
  KNOWLEDGE.load();
  MEMORIES.load();
  VAULT.load();

  // Channels
  CHANNELS.register('facts', createFactsChannel(KNOWLEDGE));
  CHANNELS.register('memories', createMemoriesChannel(MEMORIES));
  CHANNELS.register('session', createSessionChannel(SESSION_LOG));
  CHANNELS.register('vault', createVaultChannel(VAULT));
  CHANNELS.register('time', createTimeChannel());
  CHANNELS.register('weather', createWeatherChannel(CONFIG.weather || {}));
  CHANNELS.register('calendar', createCalendarChannel(path.join(DATA_DIR, 'calendar.json')));
  // Apply enabled/disabled from config
  const channelConfig = CONFIG.channels || {};
  for (const [name, enabled] of Object.entries(channelConfig)) {
    if (enabled) CHANNELS.enable(name);
    else CHANNELS.disable(name);
  }

  // Voice engines
  VOICE = new TTS(CONFIG.tts || {});
  VOICE.detect();
  LISTEN = new STT(CONFIG.stt || {});
  LISTEN.detect();

  // MCP servers
  await loadMCPServers();

  // System prompt + session reload
  MESSAGES.push({ role: 'system', content: buildSystemPrompt() });
  const reloadSession = CONFIG.session_reload !== false;
  if (reloadSession) {
    const prev = loadLastSession();
    if (prev.length) MESSAGES.push(...prev);
  }

  // onStartup hook
  runHooks('onStartup', { tools: Object.keys(ALL_TOOLS), model: MODEL });

  // No alt screen buffer — stay in the main terminal buffer so scrollback works.
  // Ink's <Static> component handles the append-only log above the live input area.
  // Users can scroll up in their terminal to see history.

  // Cleanup on SIGINT / uncaught exit
  const cleanup = () => {
    for (const s of Object.values(MCP_SERVERS)) { try { s.stop(); } catch {} }
  };
  process.on('SIGINT', () => { cleanup(); process.exit(0); });
  process.on('SIGTERM', () => { cleanup(); process.exit(0); });
  process.on('exit', cleanup);

  const { waitUntilExit } = render(React.createElement(App));

  // Welcome lines — pushed after render so they land in the Static log.
  setTimeout(() => {
    const botName = CONFIG.bot_name || 'UnityCLI';
    uiOut(`${botName} ready — type /help for commands, /exit to quit`, 'cyan');
    const voiceStatus = [];
    if (VOICE && VOICE._detected !== 'none') voiceStatus.push(`TTS:${VOICE._detected}`);
    if (LISTEN && LISTEN._detected !== 'none') voiceStatus.push(`STT:${LISTEN._detected}`);
    if (voiceStatus.length) uiOut(`  ${voiceStatus.join(' | ')}`, 'gray');
    const toolCount = Object.keys(ALL_TOOLS).length + Object.keys(BUILTIN_TOOLS).length;
    const mcpCount = Object.keys(MCP_SERVERS).length;
    uiOut(`  ${toolCount} tools ready (${mcpCount} MCP servers)`, 'gray');
  }, 50);

  await waitUntilExit();
  cleanup();
}

main().catch(e => { try { process.stdout.write('\x1b[?1049l'); } catch {} console.error(e); process.exit(1); });
