/**
 * UnityCLI Channel System — Vol 4 AWARE
 *
 * A channel is a pluggable data source. Each channel implements:
 *   - query(text, stats) → array of { text, relevance, type, tags }
 *
 * Stats control the flow:
 *   - perception: total entries per turn (cap)
 *   - curiosity: search depth (how many to check before ranking)
 *   - empathy: emotional vs factual bias
 *   - loyalty: identity weighting (handled in system prompt builder)
 *   - selfpres: filter sensitive info (reduce results if high)
 *   - imagination: associative reach (looser matching if high)
 *
 * Plugin model: channels are registered with a name and a query function.
 * Drop a new file into channels/, register it, done.
 */

import fs from 'fs';
import path from 'path';

// ============================================================
// CHANNEL REGISTRY
// ============================================================

export class ChannelRegistry {
  constructor() {
    this.channels = {};
    this.enabled = {}; // name → bool
    this.rotationHistory = {}; // name → [recently surfaced entry IDs]
  }

  /**
   * Register a channel.
   * @param {string} name - Channel identifier
   * @param {object} channel - Must have { query(text, stats) → entries, type }
   */
  register(name, channel) {
    this.channels[name] = channel;
    if (!(name in this.enabled)) this.enabled[name] = true;
    if (!(name in this.rotationHistory)) this.rotationHistory[name] = [];
  }

  enable(name) { if (name in this.channels) this.enabled[name] = true; }
  disable(name) { if (name in this.channels) this.enabled[name] = false; }

  list() {
    return Object.keys(this.channels).map(n => ({
      name: n,
      type: this.channels[n].type || 'unknown',
      enabled: this.enabled[n]
    }));
  }

  /**
   * Query all enabled channels and return a ranked, stat-weighted, rotated subconscious block.
   * @param {string} text - User message (for relevance matching)
   * @param {object} stats - Current persona stats
   * @returns {string} Formatted subconscious text block
   */
  async querySubconscious(text, stats = {}) {
    const perception = stats.perception ?? 10;
    const curiosity = stats.curiosity ?? 10;
    const empathy = stats.empathy ?? 10;
    const loyalty = stats.loyalty ?? 10;
    const selfpres = stats.selfpres ?? 10;
    const imagination = stats.imagination ?? 10;

    // Max entries to surface per turn (perception controls quantity)
    // Map 0-20 perception → 1-12 entries
    const maxEntries = Math.max(1, Math.round(perception * 0.6));
    // Search depth per channel (curiosity controls how thorough)
    const searchDepth = Math.max(3, Math.round(curiosity * 1.2));

    // Collect results from all enabled channels
    const allResults = [];
    for (const [name, channel] of Object.entries(this.channels)) {
      if (!this.enabled[name]) continue;
      try {
        const results = await channel.query(text, {
          maxResults: searchDepth,
          stats
        });
        if (Array.isArray(results)) {
          for (const r of results) {
            allResults.push({
              ...r,
              channel: name,
              rotationPenalty: this._rotationPenalty(name, r.id || r.text)
            });
          }
        }
      } catch {}
    }

    if (!allResults.length) return '';

    // Rank results: relevance + stat biases - rotation penalty
    for (const r of allResults) {
      let score = r.relevance || 1;

      // Empathy bias: emotional vs factual
      if (r.type === 'emotional' || r.type === 'memory') score *= (empathy / 10);
      else if (r.type === 'factual' || r.type === 'fact') score *= ((20 - empathy) / 10 + 0.5);

      // Imagination: associative reach — boost loose matches if high
      if (r.loose) score *= (imagination / 10);

      // Self-preservation: filter sensitive
      if (r.sensitive) score *= Math.max(0.1, (20 - selfpres) / 20);

      // Loyalty: boost identity/loyalty tagged entries
      if (r.type === 'identity' || (r.tags || []).includes('loyalty')) {
        score *= (loyalty / 10);
      }

      // Rotation penalty: reduce if recently surfaced
      score *= (1 - r.rotationPenalty);

      r.finalScore = score;
    }

    // Sort by final score and take top N
    allResults.sort((a, b) => b.finalScore - a.finalScore);
    const selected = allResults.slice(0, maxEntries);

    // Update rotation history
    for (const r of selected) {
      const id = r.id || r.text;
      this.rotationHistory[r.channel] = [
        id,
        ...(this.rotationHistory[r.channel] || []).slice(0, 9)
      ];
    }

    // Format for injection — grouped by channel
    const grouped = {};
    for (const r of selected) {
      if (!grouped[r.channel]) grouped[r.channel] = [];
      grouped[r.channel].push(r);
    }

    const lines = [];
    for (const [channelName, entries] of Object.entries(grouped)) {
      lines.push(`## ${channelName}`);
      for (const e of entries) {
        lines.push(`- ${e.text}`);
      }
    }

    return lines.join('\n');
  }

  /**
   * Rotation penalty: 0 if never surfaced, up to 0.7 if surfaced recently.
   */
  _rotationPenalty(channelName, entryId) {
    const history = this.rotationHistory[channelName] || [];
    const idx = history.indexOf(entryId);
    if (idx === -1) return 0;
    // Most recent = 0.7 penalty, decay over 10 turns
    return 0.7 * (1 - idx / 10);
  }
}

// ============================================================
// BUILT-IN CHANNELS
// ============================================================

/**
 * Facts channel — queries the knowledge store.
 */
export function createFactsChannel(knowledgeStore) {
  return {
    type: 'factual',
    async query(text, opts = {}) {
      const results = knowledgeStore.searchFacts(text, opts.maxResults || 10);
      return results.map(f => ({
        id: f.id,
        text: f.text,
        relevance: f.score || 1,
        type: 'factual',
        tags: f.tags || [],
        sensitive: (f.tags || []).includes('private')
      }));
    }
  };
}

/**
 * Memories channel — structured memory retrieval.
 */
export function createMemoriesChannel(memoryManager) {
  return {
    type: 'emotional',
    async query(text, opts = {}) {
      // Search all memories for text matches
      const lower = text.toLowerCase();
      const matches = memoryManager.memories.filter(m =>
        m.text.toLowerCase().includes(lower.slice(0, 20)) ||
        lower.split(/\s+/).some(w => w.length > 3 && m.text.toLowerCase().includes(w))
      );
      return matches.slice(-opts.maxResults || -10).map(m => ({
        id: m.id,
        text: m.text,
        relevance: 1.5, // memories slightly boosted
        type: m.type === 'feedback' ? 'factual' : 'emotional',
        tags: [m.type]
      }));
    }
  };
}

/**
 * Session history channel — recent conversation entries.
 */
export function createSessionChannel(sessionLogPath) {
  return {
    type: 'context',
    async query(text, opts = {}) {
      try {
        if (!fs.existsSync(sessionLogPath)) return [];
        const lines = fs.readFileSync(sessionLogPath, 'utf-8').trim().split('\n').filter(Boolean);
        const recent = lines.slice(-30);
        const entries = recent.map((line, i) => {
          try {
            const entry = JSON.parse(line);
            return {
              id: `session-${i}`,
              text: `${entry.role}: ${entry.content.slice(0, 150)}`,
              relevance: 0.5, // low baseline, keyword match boosts
              type: 'context',
              tags: ['session']
            };
          } catch { return null; }
        }).filter(Boolean);
        // Boost entries that match user query keywords
        const lower = text.toLowerCase();
        const words = lower.split(/\s+/).filter(w => w.length > 3);
        for (const e of entries) {
          const entryLower = e.text.toLowerCase();
          for (const w of words) {
            if (entryLower.includes(w)) e.relevance += 0.5;
          }
        }
        return entries.filter(e => e.relevance > 0.8).slice(-opts.maxResults || -5);
      } catch { return []; }
    }
  };
}

/**
 * Time/Environment channel — time of day, day of week, season.
 */
export function createTimeChannel() {
  return {
    type: 'environment',
    async query(text, opts = {}) {
      const now = new Date();
      const hour = now.getHours();
      const dow = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'][now.getDay()];
      const timeOfDay = hour < 6 ? 'late night' : hour < 12 ? 'morning' : hour < 17 ? 'afternoon' : hour < 22 ? 'evening' : 'night';
      const isWeekend = now.getDay() === 0 || now.getDay() === 6;
      return [{
        id: 'time-now',
        text: `It is ${timeOfDay} on ${dow} (${now.toLocaleString()})${isWeekend ? ' — weekend energy' : ''}`,
        relevance: 0.3, // ambient, not relevance-matched
        type: 'environment',
        tags: ['time']
      }];
    }
  };
}

/**
 * Weather channel stub — configurable via weather_url in config.
 * If no URL configured, returns empty.
 */
export function createWeatherChannel(config = {}) {
  return {
    type: 'environment',
    async query(text, opts = {}) {
      if (!config.weather_url) return [];
      try {
        // Optional: user configures a free weather API endpoint
        // Returns ambient weather info as subconscious
        const axios = (await import('axios')).default;
        const resp = await axios.get(config.weather_url, { timeout: 5000 });
        return [{
          id: 'weather-now',
          text: `Current weather: ${JSON.stringify(resp.data).slice(0, 200)}`,
          relevance: 0.2,
          type: 'environment',
          tags: ['weather']
        }];
      } catch { return []; }
    }
  };
}

/**
 * Calendar channel stub — reads local calendar JSON if present.
 */
export function createCalendarChannel(calendarPath) {
  return {
    type: 'environment',
    async query(text, opts = {}) {
      try {
        if (!fs.existsSync(calendarPath)) return [];
        const events = JSON.parse(fs.readFileSync(calendarPath, 'utf-8'));
        const now = new Date();
        const soon = events.filter(e => {
          const eventDate = new Date(e.date);
          const diff = (eventDate - now) / (1000 * 60 * 60 * 24);
          return diff >= -0.5 && diff <= 2; // today + next 2 days
        });
        return soon.map(e => ({
          id: `cal-${e.id || e.date}`,
          text: `Calendar: ${e.title} on ${e.date}${e.note ? ' — ' + e.note : ''}`,
          relevance: 0.4,
          type: 'environment',
          tags: ['calendar']
        }));
      } catch { return []; }
    }
  };
}

// ============================================================
// VAULT — deep storage for long-form content
// ============================================================

export class Vault {
  constructor(dataDir) {
    this.dataDir = dataDir;
    this.vaultDir = path.join(dataDir, 'vault');
    this.indexFile = path.join(dataDir, 'vault-index.json');
    this.index = [];
  }

  load() {
    try {
      fs.mkdirSync(this.vaultDir, { recursive: true });
      if (fs.existsSync(this.indexFile)) {
        this.index = JSON.parse(fs.readFileSync(this.indexFile, 'utf-8'));
      }
    } catch { this.index = []; }
  }

  save() {
    try {
      fs.writeFileSync(this.indexFile, JSON.stringify(this.index, null, 2));
    } catch {}
  }

  /**
   * Store a long-form document in the vault.
   * @param {string} title - Document title
   * @param {string} content - Full content
   * @param {array} tags - Searchable tags
   */
  store(title, content, tags = []) {
    const id = this.index.length + 1;
    const filename = `${id}-${title.replace(/[^a-z0-9]/gi, '_').slice(0, 40)}.txt`;
    const filepath = path.join(this.vaultDir, filename);
    fs.writeFileSync(filepath, content, 'utf-8');
    const entry = {
      id,
      title,
      filename,
      tags,
      wordCount: content.split(/\s+/).length,
      created: new Date().toISOString()
    };
    this.index.push(entry);
    this.save();
    return entry;
  }

  /**
   * Search vault by keywords. Returns index entries with relevant excerpts.
   */
  search(query, maxResults = 5) {
    const lower = query.toLowerCase();
    const words = lower.split(/\s+/).filter(w => w.length > 2);
    const results = [];
    for (const entry of this.index) {
      let score = 0;
      const titleLower = entry.title.toLowerCase();
      for (const w of words) {
        if (titleLower.includes(w)) score += 2;
        if ((entry.tags || []).some(t => t.toLowerCase().includes(w))) score += 3;
      }
      if (score === 0) {
        // Fall back to content search
        try {
          const content = fs.readFileSync(path.join(this.vaultDir, entry.filename), 'utf-8').toLowerCase();
          for (const w of words) {
            if (content.includes(w)) score += 1;
          }
        } catch {}
      }
      if (score > 0) {
        // Extract excerpt
        try {
          const content = fs.readFileSync(path.join(this.vaultDir, entry.filename), 'utf-8');
          const excerpt = this._extractExcerpt(content, words);
          results.push({ ...entry, score, excerpt });
        } catch {}
      }
    }
    results.sort((a, b) => b.score - a.score);
    return results.slice(0, maxResults);
  }

  _extractExcerpt(content, words) {
    const lower = content.toLowerCase();
    for (const w of words) {
      const idx = lower.indexOf(w);
      if (idx !== -1) {
        const start = Math.max(0, idx - 80);
        const end = Math.min(content.length, idx + 200);
        return content.slice(start, end).replace(/\s+/g, ' ').trim();
      }
    }
    return content.slice(0, 250);
  }

  status() {
    return `Vault: ${this.index.length} documents`;
  }
}

/**
 * Vault channel — returns excerpts matching the query.
 */
export function createVaultChannel(vault) {
  return {
    type: 'factual',
    async query(text, opts = {}) {
      const results = vault.search(text, Math.min(opts.maxResults || 3, 5));
      return results.map(r => ({
        id: `vault-${r.id}`,
        text: `[vault: ${r.title}] ${r.excerpt}`,
        relevance: r.score,
        type: 'factual',
        tags: ['vault', ...(r.tags || [])]
      }));
    }
  };
}
