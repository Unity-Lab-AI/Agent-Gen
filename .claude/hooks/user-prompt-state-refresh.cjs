#!/usr/bin/env node
// .claude/hooks/user-prompt-state-refresh.js
//
// UserPromptSubmit hook. Fires before Claude processes each user prompt.
// Outputs a compact one-paragraph state recap on stdout — Claude Code
// injects this as added context. Standardizes between-turn context across
// the team so Unity is never working off stale state mid-session.
//
// Reads .claude/.session-env.json (written by session-start-env-dump.js) for
// fast lookup. Falls back to direct git/file queries if the cache is missing
// or stale.
//
// Pure enablement. Exit 0 always.
//
// Bash fallback sibling: user-prompt-state-refresh.sh

'use strict';

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

function safe(cmd, opts) {
  try { return execSync(cmd, Object.assign({ encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }, opts || {})).trim(); }
  catch (e) { return null; }
}

(function main() {
  const root = process.cwd();
  const cachePath = path.join(root, '.claude', '.session-env.json');

  let env = null;
  if (fs.existsSync(cachePath)) {
    try { env = JSON.parse(fs.readFileSync(cachePath, 'utf8')); } catch (e) {}
  }

  // Direct queries for the volatile fields (branch can change mid-session)
  const branch = safe('git rev-parse --abbrev-ref HEAD', { cwd: root });
  const isRepo = safe('git rev-parse --is-inside-work-tree', { cwd: root }) === 'true';

  // TODO summary (re-read because TODO.md changes mid-session)
  let inProgressCount = 0;
  let inProgressTitles = [];
  const todoPath = path.join(root, 'docs', 'TODO.md');
  if (fs.existsSync(todoPath)) {
    const c = fs.readFileSync(todoPath, 'utf8');
    const m = c.match(/^###?\s*\[~\]\s*(.+)$/gm) || [];
    inProgressCount = m.length;
    inProgressTitles = m.map(l => l.replace(/^###?\s*\[~\]\s*/, '').trim()).slice(0, 3);
  }

  // Opt-in state from cache (rarely changes)
  const optInState = (env && env.git_flow_opt_in && env.git_flow_opt_in.state) || 'UNSET';

  // YOLO mode (re-read; can change mid-session)
  const yoloMarker = path.join(root, '.claude', '.yolo-mode');
  const yoloEnabled = fs.existsSync(yoloMarker);

  const lines = ['## State refresh (auto-injected by .claude/hooks/user-prompt-state-refresh.js)'];
  lines.push('');
  lines.push('- **Branch:** ' + (isRepo ? '`' + branch + '`' : 'not a git repo'));
  lines.push('- **Git Flow opt-in:** ' + optInState);
  lines.push('- **TODO in_progress:** ' + inProgressCount + (inProgressTitles.length ? ' — ' + inProgressTitles.map(t => '`' + t + '`').join(', ') : ''));
  lines.push('- **YOLO mode:** ' + (yoloEnabled ? '⚡ ENABLED (lead-dev autonomy; user test plan required on task closure)' : 'DISABLED'));

  if (isRepo && optInState === 'ENABLED') {
    const protected_ = ['main', 'master', 'develop', 'prod', 'production'];
    if (protected_.indexOf(branch) !== -1) {
      lines.push('');
      lines.push('⚠ **On protected branch `' + branch + '`** — branch into `feature/<descriptor>` before editing per CONSTRAINTS.md §GIT FLOW.');
    }
  }

  process.stdout.write(lines.join('\n') + '\n');
  process.exit(0);
})();
