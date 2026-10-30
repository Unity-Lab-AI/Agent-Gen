// ═══════════════════════════════════════════════════════════════
// BOT SCRIPT SANDBOX — Safe execution of player-written bot scripts
// ═══════════════════════════════════════════════════════════════
// Player scripts can ONLY call the bot API. No access to:
// - Game internals, server state, other players' data
// - Network (fetch, http, ws), filesystem (fs, path)
// - Process (process.exit, child_process)
// - Timers beyond the tick (no setTimeout/setInterval)
// Max execution: 50ms per tick. Max script size: 10KB.
// ═══════════════════════════════════════════════════════════════

import { Script, createContext } from 'vm';

export interface BotAPI {
  walk: (direction: number, distance: number) => void;
  gather: (targetId: string) => void;
  craft: (recipeId: string) => void;
  examine: (targetId: string) => void;
  attack: (targetId: string) => void;
  eat: () => void;
  drink: () => void;
  follow_owner: () => void;
  get_senses: () => any;
  get_inventory: () => any[];
  get_nearby: () => any[];
  get_health: () => number;
  get_hunger: () => number;
  get_thirst: () => number;
  get_stamina: () => number;
  log: (msg: string) => void;
}

const MAX_SCRIPT_SIZE = 10 * 1024; // 10KB
const MAX_EXECUTION_MS = 50;

// Blocked globals — anything dangerous
const BLOCKED = [
  'process', 'require', 'import', 'eval', 'Function',
  'fetch', 'XMLHttpRequest', 'WebSocket',
  'setTimeout', 'setInterval', 'setImmediate',
  'clearTimeout', 'clearInterval', 'clearImmediate',
  '__dirname', '__filename', 'module', 'exports',
  'global', 'globalThis', 'Proxy', 'Reflect',
];

export function validateScript(code: string): { valid: boolean; error?: string } {
  if (!code || code.trim().length === 0) return { valid: false, error: 'Empty script' };
  if (code.length > MAX_SCRIPT_SIZE) return { valid: false, error: `Script too large (${code.length} bytes, max ${MAX_SCRIPT_SIZE})` };

  // Check for blocked keywords
  for (const blocked of BLOCKED) {
    if (code.includes(blocked)) {
      return { valid: false, error: `Forbidden keyword: ${blocked}` };
    }
  }

  // Try to compile
  try {
    new Script(code);
    return { valid: true };
  } catch (e: any) {
    return { valid: false, error: `Syntax error: ${e.message}` };
  }
}

export function executeScript(code: string, botApi: BotAPI): { success: boolean; error?: string; action?: string } {
  const validation = validateScript(code);
  if (!validation.valid) return { success: false, error: validation.error };

  // Create sandboxed context with ONLY the bot API
  const lastAction = { type: 'idle', target: '' };
  const sandbox = {
    bot: {
      walk: (dir: number, dist: number) => { lastAction.type = 'walk'; lastAction.target = `${dir},${dist}`; botApi.walk(dir, dist); },
      gather: (id: string) => { lastAction.type = 'gather'; lastAction.target = id; botApi.gather(id); },
      craft: (id: string) => { lastAction.type = 'craft'; lastAction.target = id; botApi.craft(id); },
      examine: (id: string) => { lastAction.type = 'examine'; lastAction.target = id; botApi.examine(id); },
      attack: (id: string) => { lastAction.type = 'attack'; lastAction.target = id; botApi.attack(id); },
      eat: () => { lastAction.type = 'eat'; botApi.eat(); },
      drink: () => { lastAction.type = 'drink'; botApi.drink(); },
      follow_owner: () => { lastAction.type = 'follow'; botApi.follow_owner(); },
      get_senses: () => botApi.get_senses(),
      get_inventory: () => botApi.get_inventory(),
      get_nearby: () => botApi.get_nearby(),
      get_health: () => botApi.get_health(),
      get_hunger: () => botApi.get_hunger(),
      get_thirst: () => botApi.get_thirst(),
      get_stamina: () => botApi.get_stamina(),
      log: (msg: string) => botApi.log(String(msg).slice(0, 200)),
    },
    Math: Math,
    console: { log: (msg: any) => botApi.log(String(msg).slice(0, 200)) },
  };

  const ctx = createContext(sandbox);

  try {
    const script = new Script(code);
    script.runInContext(ctx, { timeout: MAX_EXECUTION_MS });
    return { success: true, action: lastAction.type };
  } catch (e: any) {
    if (e.message?.includes('Script execution timed out')) {
      return { success: false, error: 'Script timed out (50ms limit)' };
    }
    return { success: false, error: `Runtime error: ${e.message}` };
  }
}
