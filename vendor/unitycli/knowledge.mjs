/**
 * UnityCLI Knowledge & Channel System — Vol 4
 * Pluggable storage: JSON by default, SQLite/API/tablet sync via backend abstraction.
 *
 * Features:
 *   - Facts store with verification workflow (verified/unverified/pending)
 *   - Scopes (contextual rules and boundaries)
 *   - Memory categories (user, feedback, project, reference, relationship)
 *   - Backend abstraction: swap JSON → SQLite → API without changing calling code
 *   - Stat-driven retrieval hooks for channel system
 */

import fs from 'fs';
import path from 'path';

// ============================================================
// STORAGE BACKEND ABSTRACTION
// ============================================================

/**
 * Base backend interface. Subclass for SQLite, API, tablet sync, etc.
 */
export class StorageBackend {
  async load(name) { throw new Error('not implemented'); }
  async save(name, data) { throw new Error('not implemented'); }
}

/**
 * Default JSON file backend — fast, simple, zero dependencies.
 */
export class JSONBackend extends StorageBackend {
  constructor(dataDir) {
    super();
    this.dataDir = dataDir;
    try { fs.mkdirSync(dataDir, { recursive: true }); } catch {}
  }

  load(name) {
    try {
      const p = path.join(this.dataDir, `${name}.json`);
      if (fs.existsSync(p)) return JSON.parse(fs.readFileSync(p, 'utf-8'));
    } catch {}
    return null;
  }

  save(name, data) {
    try {
      const p = path.join(this.dataDir, `${name}.json`);
      fs.writeFileSync(p, JSON.stringify(data, null, 2));
      return true;
    } catch { return false; }
  }
}

// ============================================================
// KNOWLEDGE STORE
// ============================================================

export class KnowledgeStore {
  constructor(dataDir, backend = null) {
    this.dataDir = dataDir;
    this.backend = backend || new JSONBackend(dataDir);
    this.factsFile = path.join(dataDir, 'knowledge.json');
    this.scopesFile = path.join(dataDir, 'scopes.json');
    this.facts = [];
    this.scopes = [];
  }

  load() {
    try {
      if (fs.existsSync(this.factsFile)) {
        this.facts = JSON.parse(fs.readFileSync(this.factsFile, 'utf-8'));
      }
    } catch { this.facts = []; }
    try {
      if (fs.existsSync(this.scopesFile)) {
        this.scopes = JSON.parse(fs.readFileSync(this.scopesFile, 'utf-8'));
      }
    } catch { this.scopes = []; }
  }

  save() {
    try {
      fs.writeFileSync(this.factsFile, JSON.stringify(this.facts, null, 2));
      fs.writeFileSync(this.scopesFile, JSON.stringify(this.scopes, null, 2));
    } catch {}
  }

  /**
   * Add a fact to the knowledge store.
   * @param {string} text - The fact
   * @param {string} source - 'user', 'ai', 'system', 'external'
   * @param {array} tags - Searchable tags
   * @param {object} opts - { category, verified, confidence }
   */
  addFact(text, source = 'user', tags = [], opts = {}) {
    const entry = {
      id: this.facts.length + 1,
      text,
      source,
      tags,
      category: opts.category || 'general', // user_info, preference, event, reference, world_fact
      verified: source === 'user' ? true : (opts.verified ?? false),
      confidence: opts.confidence ?? (source === 'user' ? 1.0 : 0.5),
      created: new Date().toISOString(),
      lastAccessed: null,
      accessCount: 0
    };
    this.facts.push(entry);
    this.save();
    return entry;
  }

  /**
   * Verify a fact by ID — marks as verified with full confidence.
   */
  verifyFact(id) {
    const f = this.facts.find(f => f.id === id);
    if (f) {
      f.verified = true;
      f.confidence = 1.0;
      this.save();
      return true;
    }
    return false;
  }

  /**
   * Get pending (unverified) facts for review.
   */
  getPendingFacts() {
    return this.facts.filter(f => !f.verified);
  }

  /**
   * Add a scope (rule/boundary).
   */
  addScope(text, priority = 'normal') {
    const entry = {
      id: this.scopes.length + 1,
      text,
      priority, // 'critical', 'normal', 'low'
      created: new Date().toISOString()
    };
    this.scopes.push(entry);
    this.save();
    return entry;
  }

  /**
   * Search facts by keyword. Returns matches sorted by relevance.
   */
  searchFacts(query, maxResults = 10) {
    if (!query) return this.facts.slice(-maxResults);
    const lower = query.toLowerCase();
    const words = lower.split(/\s+/);
    const scored = this.facts.map(f => {
      const text = f.text.toLowerCase();
      let score = 0;
      for (const w of words) {
        if (text.includes(w)) score += 1;
      }
      // Boost by trust
      score *= f.trust || 1;
      // Boost by tag match
      for (const tag of (f.tags || [])) {
        if (words.includes(tag.toLowerCase())) score += 2;
      }
      return { ...f, score };
    }).filter(f => f.score > 0);
    scored.sort((a, b) => b.score - a.score);
    return scored.slice(0, maxResults);
  }

  /**
   * Get facts for injection, controlled by stats.
   * @param {string} query - Search terms (from user input)
   * @param {object} stats - Current persona stats
   * @returns {string} Formatted knowledge injection text
   */
  getInjection(query, stats = {}) {
    const perception = stats.perception || 10;
    const curiosity = stats.curiosity || 10;
    const empathy = stats.empathy || 10;

    // Perception controls how many entries surface (1-10 based on 0-18 stat)
    const maxEntries = Math.max(1, Math.round(perception / 2));
    // Curiosity controls search depth — higher = broader search
    const searchDepth = Math.max(3, Math.round(curiosity / 1.5));

    const results = this.searchFacts(query, searchDepth);
    if (!results.length) return '';

    // Empathy biases toward emotional vs factual entries
    // (future: tag entries as emotional/factual and sort by empathy level)

    const selected = results.slice(0, maxEntries);
    const lines = selected.map(f => `- ${f.text}`);
    return lines.join('\n');
  }

  /**
   * Get active scopes for injection.
   */
  getScopeInjection() {
    if (!this.scopes.length) return '';
    // Critical scopes always surface, others by count
    const critical = this.scopes.filter(s => s.priority === 'critical');
    const normal = this.scopes.filter(s => s.priority !== 'critical').slice(-5);
    const all = [...critical, ...normal];
    return all.map(s => `- ${s.text}`).join('\n');
  }

  /**
   * Remove a fact by ID.
   */
  removeFact(id) {
    this.facts = this.facts.filter(f => f.id !== id);
    this.save();
  }

  /**
   * Remove a scope by ID.
   */
  removeScope(id) {
    this.scopes = this.scopes.filter(s => s.id !== id);
    this.save();
  }

  /**
   * Get stats about the knowledge store.
   */
  status() {
    return `Facts: ${this.facts.length} | Scopes: ${this.scopes.length}`;
  }
}

// ============================================================
// MEMORY MANAGER — structured memory categories
// ============================================================

export class MemoryManager {
  constructor(dataDir) {
    this.dataDir = dataDir;
    this.memoryFile = path.join(dataDir, 'memories.json');
    this.memories = [];
  }

  load() {
    try {
      if (fs.existsSync(this.memoryFile)) {
        this.memories = JSON.parse(fs.readFileSync(this.memoryFile, 'utf-8'));
      }
    } catch { this.memories = []; }
  }

  save() {
    try {
      fs.writeFileSync(this.memoryFile, JSON.stringify(this.memories, null, 2));
    } catch {}
  }

  /**
   * Add a memory entry.
   * @param {string} text - Memory content
   * @param {string} type - 'user', 'feedback', 'project', 'reference'
   */
  add(text, type = 'user') {
    const entry = {
      id: this.memories.length + 1,
      text,
      type,
      created: new Date().toISOString()
    };
    this.memories.push(entry);
    this.save();
    return entry;
  }

  /**
   * Get memories for injection, optionally filtered by type.
   */
  getInjection(type = null, maxEntries = 10) {
    let filtered = this.memories;
    if (type) filtered = filtered.filter(m => m.type === type);
    const recent = filtered.slice(-maxEntries);
    if (!recent.length) return '';
    return recent.map(m => `[${m.type}] ${m.text}`).join('\n');
  }

  /**
   * Search memories.
   */
  search(query, maxResults = 10) {
    const lower = query.toLowerCase();
    return this.memories
      .filter(m => m.text.toLowerCase().includes(lower))
      .slice(-maxResults);
  }

  /**
   * Remove a memory by ID.
   */
  remove(id) {
    this.memories = this.memories.filter(m => m.id !== id);
    this.save();
  }

  status() {
    const counts = {};
    for (const m of this.memories) {
      counts[m.type] = (counts[m.type] || 0) + 1;
    }
    return `Memories: ${this.memories.length} (${Object.entries(counts).map(([k,v]) => `${k}:${v}`).join(', ')})`;
  }
}

// ============================================================
// CHAT PROTOCOL — inter-AI communication
// ============================================================

export class ChatChannel {
  constructor(dataDir) {
    this.dataDir = dataDir;
    this.chatFile = path.join(dataDir, 'chat.jsonl');
    this.inboxFile = path.join(dataDir, 'inbox.jsonl');
  }

  /**
   * Send a message to the shared chat.
   */
  send(from, text) {
    const entry = JSON.stringify({
      ts: new Date().toISOString(),
      from,
      text
    }) + '\n';
    try {
      fs.appendFileSync(this.chatFile, entry);
    } catch {}
  }

  /**
   * Read recent chat messages.
   */
  read(count = 20) {
    try {
      if (!fs.existsSync(this.chatFile)) return [];
      const lines = fs.readFileSync(this.chatFile, 'utf-8').trim().split('\n').filter(Boolean);
      return lines.slice(-count).map(l => {
        try { return JSON.parse(l); } catch { return null; }
      }).filter(Boolean);
    } catch { return []; }
  }

  /**
   * Read messages since a timestamp.
   */
  since(timestamp) {
    const all = this.read(1000);
    return all.filter(m => m.ts > timestamp);
  }

  /**
   * Send a DM to another instance's inbox.
   * @param {string} targetDir - The target instance's data directory
   * @param {string} from - Sender name
   * @param {string} text - Message content
   */
  dm(targetDir, from, text) {
    const targetInbox = path.join(targetDir, 'inbox.jsonl');
    const entry = JSON.stringify({
      ts: new Date().toISOString(),
      from,
      text
    }) + '\n';
    try {
      fs.appendFileSync(targetInbox, entry);
    } catch {}
  }

  /**
   * Check own inbox for new messages.
   */
  checkInbox(count = 10) {
    try {
      if (!fs.existsSync(this.inboxFile)) return [];
      const lines = fs.readFileSync(this.inboxFile, 'utf-8').trim().split('\n').filter(Boolean);
      return lines.slice(-count).map(l => {
        try { return JSON.parse(l); } catch { return null; }
      }).filter(Boolean);
    } catch { return []; }
  }

  /**
   * Clear inbox after reading.
   */
  clearInbox() {
    try {
      if (fs.existsSync(this.inboxFile)) fs.writeFileSync(this.inboxFile, '');
    } catch {}
  }
}
