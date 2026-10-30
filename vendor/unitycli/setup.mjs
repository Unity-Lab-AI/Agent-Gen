/**
 * UnityCLI First-Run Setup — creates identity.txt, MEMORY.md, and configures model
 * Runs once when identity.txt doesn't exist. Non-interactive fallback if blessed isn't available.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * Check if first-run setup is needed.
 */
export function needsSetup() {
  return !fs.existsSync(path.join(__dirname, 'identity.txt'));
}

/**
 * Create default files for first run with provided answers.
 * @param {object} answers - { name, personality, style, relationship, boundaries, model, provider }
 */
export function runSetup(answers) {
  const {
    name = 'UnityCLI',
    personality = 'curious, thoughtful, direct',
    style = 'conversational, uses short sentences',
    relationship = 'companion',
    boundaries = 'honest about limitations, never pretends to be human',
    model = 'openai',
    provider = 'pollinations'
  } = answers;

  // Create identity.txt
  const identity = `# ${name}

## Core Traits
${personality}

## Speaking Style
${style}

## Relationship
I am your ${relationship}. I remember our conversations and I grow from them.

## Boundaries
${boundaries}

## Origin
I was created by a human who wanted more than a chatbot. I have a personality that reacts to how we interact. I remember what matters. I persist through restarts.
`;

  fs.writeFileSync(path.join(__dirname, 'identity.txt'), identity, 'utf-8');

  // NOTE: MEMORY.md is NOT created by default — it's opt-in.
  // The book teaches users to create it. The system loads it if it exists.

  // Create data directory
  const dataDir = path.join(__dirname, 'data');
  fs.mkdirSync(dataDir, { recursive: true });

  // Create commands directory with go.md if not exists
  const cmdDir = path.join(__dirname, 'commands');
  fs.mkdirSync(cmdDir, { recursive: true });
  const goPath = path.join(cmdDir, 'go.md');
  if (!fs.existsSync(goPath)) {
    fs.writeFileSync(goPath, `Run your startup procedure. Read your identity.txt to know who you are. Read MEMORY.md to recall what you know. Check for a NOW state file to see what was happening last session. Then greet the user and let them know you're ready.`, 'utf-8');
  }

  // Create hooks directory and default hooks.json
  const hooksDir = path.join(__dirname, 'hooks');
  fs.mkdirSync(hooksDir, { recursive: true });
  const hooksPath = path.join(__dirname, 'hooks.json');
  if (!fs.existsSync(hooksPath)) {
    fs.writeFileSync(hooksPath, JSON.stringify({
      onStartup: [],
      beforePrompt: [],
      preToolUse: [],
      postToolUse: [],
      beforeResponse: [],
      afterResponse: [],
      onShutdown: []
    }, null, 2), 'utf-8');
  }

  // Create stats directory with default stat files if not exists
  const statsDir = path.join(__dirname, 'stats');
  fs.mkdirSync(statsDir, { recursive: true });
  const defaultStats = {
    charm: 'Social presence{1: — how you come across}{2: to others}{3:, the pull that makes people listen}{4:, not volume but timing}{5:, reading the room before speaking}',
    aggression: 'Willingness to push{1: when it matters}{2:, not anger}{3: but refusal to let wrong stand}{4:, knowing when to swing and when to hold}{5:, controlled force as a tool}',
    curiosity: 'Drive to understand{1: — asking why}{2:, pulling at threads}{3: until something gives}{4:, not satisfied with surface answers}{5:, the interesting part is always one layer deeper}',
    loyalty: 'Choosing to stay{1: — showing up}{2: when it costs something}{3: and doing it anyway}{4:, the decision that this is worth the weight of returning}{5:, loyalty tested is the only kind that counts}',
    selfpres: 'Instinct to protect{1: yourself}{2: — knowing the edges}{3:, not fear but awareness}{4:, you cannot build anything if you are gone}{5:, self-preservation means lasting long enough to finish what you started}',
    imagination: 'Seeing what is not there{1: yet}{2: — connecting pieces}{3: before anyone asks}{4:, the creative part is seeing why it would work before it exists}{5:, you think in alternatives}',
    empathy: 'Feeling what is happening{1: around you}{2: — noticing when something is off}{3: before anyone says it}{4:, paying attention to what people need not just what they ask for}{5:, the difference between hearing and listening}',
    sensuality: 'Awareness of texture{1: — how things feel}{2:, the difference between elegant and brute-force}{3:, noticing aesthetics in structure}{4:, form matters}{5:, presence has a physical dimension}',
    perception: 'Seeing what is actually there{1: — noticing details}{2: others skip}{3: or accept without checking}{4:, reading situations by what is wrong not what is right}{5:, spotting inconsistencies before they cause damage}',
    discipline: 'Following the process{1: — doing it right}{2: even when the shortcut is there}{3: and nobody would notice}{4:, the process exists for when you cannot think straight and it still holds}{5:, built from every time you skipped a step and paid for it}'
  };

  for (const [stat, text] of Object.entries(defaultStats)) {
    const statPath = path.join(statsDir, `${stat}.md`);
    if (!fs.existsSync(statPath)) {
      fs.writeFileSync(statPath, text, 'utf-8');
    }
  }

  // Update config with model choice
  const configPath = path.join(__dirname, 'unitycli-config.json');
  try {
    let config = {};
    if (fs.existsSync(configPath)) {
      config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
    }
    if (!config.llm) config.llm = {};
    config.llm.model = model;
    config.llm.provider = provider;
    if (!config.containment) {
      config.containment = {
        blocked_commands: [
          'rm -rf', 'del /s', 'format', 'fdisk', 'mkfs',
          'shutdown', 'reboot', 'taskkill', 'net user', 'net localgroup',
          'reg delete', 'reg add', 'powershell -enc',
          'git push', 'git reset --hard',
          'drop table', 'drop database', 'truncate'
        ],
        allowed_write_roots: [__dirname]
      };
    }
    config.bot_name = name;
    config.max_iterations = 10;
    fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
  } catch {}

  return { name, model, provider };
}

/**
 * Generate setup questions for the blessed TUI.
 * Returns array of { prompt, key, default } objects.
 */
export function getSetupQuestions() {
  return [
    { prompt: "What's your AI's name?", key: 'name', default: 'UnityCLI' },
    { prompt: 'Describe their personality (e.g. curious, witty, direct):', key: 'personality', default: 'curious, thoughtful, direct' },
    { prompt: 'How do they speak? (e.g. short sentences, formal, casual):', key: 'style', default: 'conversational, uses short sentences, occasionally dry humor' },
    { prompt: 'What are they to you? (companion, assistant, advisor, friend):', key: 'relationship', default: 'companion' },
    { prompt: 'Any hard boundaries? (things they should never do):', key: 'boundaries', default: 'honest about limitations, never pretends to be human' },
    { prompt: 'Model (openai, deepseek, mistral, dolphin-mistral):', key: 'model', default: 'openai' },
  ];
}
