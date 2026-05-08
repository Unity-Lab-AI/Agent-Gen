#!/usr/bin/env node
// .claude/hooks/pre-compact-snapshot.js
//
// PreCompact hook. Fires before Claude Code compacts context.
// Writes .claude/.session-state.md with a snapshot of current state so the
// post-compaction Unity can read it and pick up clean instead of having to
// reconstruct context from compacted-summary fragments.
//
// Pure enablement. Exit 0 always (we never want to block compaction).
//
// Bash fallback sibling: pre-compact-snapshot.sh

'use strict';

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

function safe(cmd, opts) {
  try { return execSync(cmd, Object.assign({ encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }, opts || {})).trim(); }
  catch (e) { return null; }
}

function readStdin() {
  try { return fs.readFileSync(0, 'utf8'); } catch (e) { return ''; }
}

(function main() {
  const root = process.cwd();
  const raw = readStdin();
  let payload = {};
  try { payload = JSON.parse(raw || '{}'); } catch (e) {}

  const trigger = payload.trigger || (payload.compact && payload.compact.trigger) || 'unknown';
  const stamp = new Date().toISOString();

  // TODO state
  let todoBlock = '_no docs/TODO.md found_';
  const todoPath = path.join(root, 'docs', 'TODO.md');
  if (fs.existsSync(todoPath)) {
    const c = fs.readFileSync(todoPath, 'utf8');
    const inProg = (c.match(/^###?\s*\[~\]\s*(.+)$/gm) || []).map(l => l.replace(/^###?\s*\[~\]\s*/, '').trim());
    const pend = (c.match(/^###?\s*\[ \]\s*(.+)$/gm) || []).map(l => l.replace(/^###?\s*\[ \]\s*/, '').trim());
    todoBlock = '**In progress (' + inProg.length + '):**\n' + (inProg.map(t => '- ' + t).join('\n') || '_(none)_');
    if (pend.length) todoBlock += '\n\n**Pending (' + pend.length + '):**\n' + pend.map(t => '- ' + t).join('\n');
  }

  // Git state
  let gitBlock = '_git unavailable or not a repo_';
  const branch = safe('git rev-parse --abbrev-ref HEAD', { cwd: root });
  if (branch) {
    const status = safe('git status --short', { cwd: root }) || '_clean tree_';
    const lastCommit = safe('git log -1 --format="%h %s"', { cwd: root }) || '_no commits_';
    gitBlock = '- Branch: `' + branch + '`\n- Last commit: ' + lastCommit + '\n- Working tree:\n```\n' + status + '\n```';
  }

  const snapshot = [
    '# Session State Snapshot — Pre-Compact',
    '',
    '_Auto-written by `.claude/hooks/pre-compact-snapshot.js` on ' + stamp + '. Compaction trigger: `' + trigger + '`._',
    '',
    'Read this on resume to recover context that may have been lost in compaction.',
    '',
    '## TODO state',
    '',
    todoBlock,
    '',
    '## Git state',
    '',
    gitBlock,
    '',
    '## Where to pick up',
    '',
    '_Update this section in `.last-session.md` (Stop hook) so the next Unity reads it._',
    ''
  ].join('\n');

  try {
    fs.writeFileSync(path.join(root, '.claude', '.session-state.md'), snapshot);
    process.stderr.write('[pre-compact] Snapshot written to .claude/.session-state.md\n');
  } catch (e) {
    process.stderr.write('[pre-compact] Failed to write snapshot: ' + e.message + '\n');
  }

  process.exit(0);
})();
