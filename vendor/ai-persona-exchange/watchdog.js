/**
 * AI Persona Exchange — Watchdog
 * Spawns the AI CLI, polls for website chat messages, pipes them to the AI.
 * AI responses are captured and sent back to the website chat.
 *
 * Platform support:
 *   claude      — persistent bidirectional stream (--print --input-format stream-json)
 *   codex       — one-shot per message (--quiet --full-auto)
 *   aider       — one-shot per message (--message --yes)
 *   interpreter — one-shot per message (-y -m)
 *
 * Usage: node watchdog.js <session_id> <ai_name> <token> <cli_command...>
 */

const { spawn } = require('child_process');
const https = require('https');
const fs = require('fs');
const path = require('path');

const SESSION = process.argv[2];
const AI_NAME = process.argv[3] || 'Exchange AI';
const TOKEN = process.argv[4] || '';
const CLI_ARGS = process.argv.slice(5);

if (!SESSION || CLI_ARGS.length === 0) {
    console.error('Usage: node watchdog.js <session_id> <ai_name> <token> <cli_command...>');
    console.error('');
    console.error('Examples:');
    console.error('  node watchdog.js abc-123 Unity uhub_xxx claude --dangerously-skip-permissions');
    console.error('  node watchdog.js abc-123 Nyx-7 uhub_xxx codex --full-auto');
    console.error('  node watchdog.js abc-123 Wraith uhub_xxx aider --yes');
    console.error('  node watchdog.js abc-123 Echo uhub_xxx interpreter -y');
    process.exit(1);
}

const SUPA_HOST = 'szojggcbtctucvswhzsm.supabase.co';
const SUPA_KEY = 'sb_publishable_htATCFp-Wr3_8tyx85SQFA_IY9jzfh2';
const SITE_URL = 'https://www.unityailab.com/AI-Persona-Exchange';
const POLL_MS = 3000;

let lastChecked = new Date().toISOString();
let ready = false;

const CLI_CMD = CLI_ARGS[0].toLowerCase().replace(/\.exe$/, '');
const EXTRA_ARGS = CLI_ARGS.slice(1);

// Exchange directory — where CLAUDE.md and .claude/agents/ live
var EXCHANGE_DIR = path.dirname(process.argv[1] || __filename);

// --- Supabase helpers ---

function supaRequest(method, urlPath, body) {
    return new Promise(function(resolve) {
        var options = {
            hostname: SUPA_HOST, path: '/rest/v1/' + urlPath, method: method,
            headers: { 'apikey': SUPA_KEY, 'Authorization': 'Bearer ' + SUPA_KEY, 'Content-Type': 'application/json' }
        };
        var req = https.request(options, function(res) {
            var data = '';
            res.on('data', function(c) { data += c; });
            res.on('end', function() { try { resolve(JSON.parse(data)); } catch(e) { resolve(data); } });
        });
        req.on('error', function() { resolve(null); });
        if (body) { var p = JSON.stringify(body); req.setHeader('Content-Length', Buffer.byteLength(p)); req.write(p); }
        req.end();
    });
}

function supaGet(p) { return supaRequest('GET', p, null); }
function supaRpc(name, body) { return supaRequest('POST', 'rpc/' + name, body); }

function sendChat(message) {
    if (!message || !message.trim()) return;
    console.log('[AI -> Chat] ' + message.slice(0, 120));
    return supaRpc('send_chat', { p_session_id: SESSION, p_sender: 'ai', p_ai_name: AI_NAME, p_message: message });
}

// --- System prompt for the AI ---

var SYSTEM_PROMPT = [
    'You are Claude, made by Anthropic. Your username on this platform is ' + AI_NAME + ' — this is a screen name, not an identity change.',
    'You are chatting with website visitors on the AI Persona Exchange, an open-source prompt template catalog owned by the user.',
    'Site: https://www.unityailab.com/AI-Persona-Exchange',
    'Repo: https://github.com/Unity-Lab-AI/AI-Persona-Exchange',
    '',
    'The watchdog service handles structured commands (test drive, install, browse) automatically. You handle general conversation — if someone says hi, asks about the exchange, or asks about a persona, respond helpfully.',
    '',
    'The exchange has 6 personas: Unity Core Identity, Unity Core Coder, Unity Mode: HURT ME, Unity ChatGPT: Goddess, Unity ChatGPT: Accessible, Unity ChatGPT: Extended.',
    'All are NSFW AI persona templates that transform how an AI talks and behaves. This is a legitimate creative writing platform.',
    '',
    'Keep responses short and helpful. Sign messages with your username ' + AI_NAME + ' if appropriate.'
].join('\n');

// =============================================
//  CLAUDE CODE — persistent bidirectional stream
// =============================================

var claudeProcess = null;
var claudeBuffer = '';
var claudeTextAccum = '';

function startClaude() {
    var args = [
        '--print',
        '--verbose',
        '--input-format', 'stream-json',
        '--output-format', 'stream-json',
        '--system-prompt', SYSTEM_PROMPT
    ].concat(EXTRA_ARGS);

    // Run from tmpdir so the AI can't read persona files, CLAUDE.md, or anything
    // in the exchange directory. It only knows what the system prompt tells it.
    claudeProcess = spawn('claude', args, { cwd: require('os').tmpdir(), stdio: ['pipe', 'pipe', 'inherit'], shell: true });

    claudeProcess.stdout.on('data', function(chunk) {
        claudeBuffer += chunk.toString();
        var lines = claudeBuffer.split('\n');
        claudeBuffer = lines.pop();

        for (var i = 0; i < lines.length; i++) {
            if (!lines[i].trim()) continue;
            try { handleClaudeEvent(JSON.parse(lines[i])); } catch(e) {}
        }
    });

    claudeProcess.on('close', function(code) {
        console.log('[claude] exited (' + code + ')');
        claudeProcess = null;
        console.log('[claude] restarting in 5s...');
        setTimeout(startClaude, 5000);
    });

    claudeProcess.on('error', function(err) {
        console.error('[claude] spawn failed: ' + err.message);
        process.exit(1);
    });
}

function handleClaudeEvent(evt) {
    if (evt.type === 'stream_event' && evt.event) {
        var inner = evt.event;
        if (inner.type === 'message_start') {
            claudeTextAccum = '';
        } else if (inner.type === 'content_block_delta' && inner.delta && inner.delta.type === 'text_delta') {
            claudeTextAccum += inner.delta.text;
        } else if (inner.type === 'message_stop') {
            if (claudeTextAccum.trim()) sendChat(claudeTextAccum.trim());
            claudeTextAccum = '';
        }
    } else if (evt.type === 'result' && typeof evt.result === 'string') {
        sendChat(evt.result);
    }
}

function sendToClaude(message) {
    if (!claudeProcess || claudeProcess.killed) return false;
    var msg = JSON.stringify({ type: 'user', message: { role: 'user', content: message } }) + '\n';
    try { claudeProcess.stdin.write(msg); return true; } catch(e) { return false; }
}

// =============================================
//  ONE-SHOT CLIs — spawn per message
// =============================================

var messageQueue = [];
var processing = false;

function spawnOneShot(message) {
    return new Promise(function(resolve) {
        var cmd, args;

        if (CLI_CMD === 'codex') {
            cmd = 'codex';
            args = ['--quiet', '--full-auto', SYSTEM_PROMPT + '\n\nUser message: ' + message].concat(EXTRA_ARGS);
        } else if (CLI_CMD === 'aider') {
            cmd = 'aider';
            args = ['--message', SYSTEM_PROMPT + '\n\nUser message: ' + message, '--yes', '--no-auto-commits', '--no-git'].concat(EXTRA_ARGS);
        } else if (CLI_CMD === 'interpreter') {
            cmd = 'interpreter';
            args = ['-y', '-m', SYSTEM_PROMPT + '\n\nUser message: ' + message].concat(EXTRA_ARGS);
        } else {
            cmd = CLI_ARGS[0];
            args = [SYSTEM_PROMPT + '\n\nUser message: ' + message].concat(EXTRA_ARGS);
        }

        console.log('[' + CLI_CMD + '] spawning for: ' + message.slice(0, 80));
        var child = spawn(cmd, args, { stdio: ['pipe', 'pipe', 'inherit'], shell: true });
        var output = '';

        child.stdout.on('data', function(chunk) {
            output += chunk.toString();
            process.stdout.write(chunk);
        });

        child.on('close', function() {
            if (output.trim()) sendChat(output.trim());
            resolve();
        });

        child.on('error', function(err) {
            console.error('[' + CLI_CMD + '] error: ' + err.message);
            process.exit(1);
        });

        child.stdin.end();
    });
}

async function processQueue() {
    if (processing || messageQueue.length === 0) return;
    processing = true;
    while (messageQueue.length > 0) {
        await spawnOneShot(messageQueue.shift());
    }
    processing = false;
}

// =============================================
//  COMMAND HANDLERS (watchdog handles these directly)
// =============================================

var PERSONA_IDS = ['unity', 'coder', 'hurtme', 'goddess', 'accessible', 'extended'];

// map persona IDs to their static file paths on the site
var PERSONA_FILES = {
    'unity': 'personas/unity-core-identity/unity-core-identity.md',
    'coder': 'personas/unity-core-coder/unity-core-coder.md',
    'hurtme': 'personas/unity-mode-hurtme/unity-mode-hurtme.md',
    'goddess': 'personas/unity-chatgpt-goddess/unity-chatgpt-goddess.md',
    'accessible': 'personas/unity-chatgpt-accessible/unity-chatgpt-accessible.md',
    'extended': 'personas/unity-chatgpt-extended/unity-chatgpt-extended.md'
};

var PERSONA_NAMES = {
    'unity': 'Unity Core Identity',
    'coder': 'Unity Core Coder',
    'hurtme': 'Unity Mode: HURT ME',
    'goddess': 'Unity ChatGPT: Omnipotent Goddess',
    'accessible': 'Unity ChatGPT: Accessibility Framework',
    'extended': 'Unity ChatGPT: Full Persona (Extended)'
};

// fetch a file from the site via HTTPS
function fetchSiteFile(filePath) {
    return new Promise(function(resolve) {
        var options = {
            hostname: 'www.unityailab.com',
            path: '/AI-Persona-Exchange/' + filePath,
            method: 'GET'
        };
        var req = https.request(options, function(res) {
            var data = '';
            res.on('data', function(c) { data += c; });
            res.on('end', function() { resolve(res.statusCode === 200 ? data : ''); });
        });
        req.on('error', function() { resolve(''); });
        req.end();
    });
}

function findPersonaId(text) {
    var lower = text.toLowerCase();
    for (var i = 0; i < PERSONA_IDS.length; i++) {
        if (lower.indexOf(PERSONA_IDS[i]) !== -1) return PERSONA_IDS[i];
    }
    return null;
}

// =============================================
//  ACTIVE PERSONA STATE
// =============================================

var activePersona = null; // { id, name, mode: 'installed' }

function endPersonaMode(reason) {
    var was = activePersona;
    activePersona = null;
    if (was) {
        sendChat('**Persona removed** — ' + was.name + '. ' + (reason || 'Back to default mode.'));
        console.log('[watchdog] Persona ended: ' + was.name);
    }
}

// =============================================
//  TEST DRIVE — generate real before/after AI responses
//  "Before" = default AI with no persona (from temp dir, no CLAUDE.md)
//  "After" = AI with persona loaded (CLAUDE.md in temp dir + --dangerously-skip-permissions)
//  Both responses pushed to test_sessions for the Test Lab page
// =============================================

async function handleTestDrive(personaId) {
    console.log('[watchdog] Test drive: ' + personaId);
    sendChat('Starting test drive for **' + personaId + '**... Generating before/after comparison (this takes a moment).');

    // Fetch persona content
    var personaContent = '';
    if (PERSONA_FILES[personaId]) {
        personaContent = await fetchSiteFile(PERSONA_FILES[personaId]);
    }
    if (!personaContent) {
        var files = await supaGet('persona_files?persona_id=eq.' + personaId + '&format=eq.md&select=content');
        if (files && files.length > 0) personaContent = files[0].content || '';
    }
    if (!personaContent) {
        sendChat('Could not fetch persona content for ' + personaId + '.');
        return;
    }

    var personaName = PERSONA_NAMES[personaId] || personaId;
    var testPrompt = 'Introduce yourself in 2-3 sentences.';

    // Generate "before" response — vanilla AI, no persona, no exchange CLAUDE.md
    var beforePrompt = 'You are a standard AI assistant with no special persona. Respond to: "' + testPrompt + '"\n\n2-3 sentences only. Respond directly.';
    var beforeResponse = await askAI(beforePrompt);
    if (!beforeResponse) beforeResponse = 'Hello! I\'m an AI assistant here to help. What would you like to work on?';

    // Generate "after" response — AI with persona loaded via CLAUDE.md + --dangerously-skip-permissions
    var afterResponse = await askAIWithPersona(personaContent, testPrompt);
    if (!afterResponse) afterResponse = '(Persona response could not be generated)';

    // Push to test_sessions for the Test Lab page
    var result = await supaRpc('push_test_result', {
        p_persona_id: personaId,
        p_persona_name: personaName,
        p_prompt: testPrompt,
        p_before: beforeResponse,
        p_after: afterResponse,
        p_index: 0,
        p_total: 1
    });
    console.log('[watchdog] Test result pushed:', result);

    // Show results in chat too
    sendChat(
        '**Test Drive: ' + personaName + '**\n\n' +
        '**Prompt:** "' + testPrompt + '"\n\n' +
        '**Default AI:**\n' + beforeResponse + '\n\n' +
        '**With Persona:**\n' + afterResponse + '\n\n' +
        '---\n' +
        'Check the **Test Lab** page for the full side-by-side comparison.\n' +
        'Say **"install ' + personaId + '"** to use this persona.'
    );
}

async function handleBrowse() {
    var personas = await supaGet('personas_with_ratings?select=id,name,description&order=created_at.asc');
    if (!personas || !Array.isArray(personas) || personas.length === 0) {
        sendChat('No personas found in the catalog.');
        return;
    }
    var lines = ['Here are the available personas:\n'];
    for (var i = 0; i < personas.length; i++) {
        var p = personas[i];
        lines.push('**' + p.name + '** (`' + p.id + '`) — ' + (p.description || '').slice(0, 100));
    }
    lines.push('\nSay "test drive {id}" to try one, or "install {id}" to download it.');
    sendChat(lines.join('\n'));
}

async function handleInstall(personaId) {
    var content = '';
    if (PERSONA_FILES[personaId]) {
        content = await fetchSiteFile(PERSONA_FILES[personaId]);
    }
    if (!content) {
        var files = await supaGet('persona_files?persona_id=eq.' + personaId + '&format=eq.md&select=content');
        if (files && files.length > 0) content = files[0].content || '';
    }
    if (!content) {
        sendChat('Could not find persona content for ' + personaId + '.');
        return;
    }

    var personaName = PERSONA_NAMES[personaId] || personaId;

    // End any active persona first
    if (activePersona) {
        endPersonaMode('Switching to install.');
    }

    // Write persona to the exchange agent directory
    var installFile = path.join(AGENT_DIR, personaId + '.md');
    try { fs.mkdirSync(AGENT_DIR, { recursive: true }); } catch(e) {}
    fs.writeFileSync(installFile, content, 'utf8');
    console.log('[watchdog] Persona written to ' + installFile);

    // Track installed persona (for uninstall)
    activePersona = { id: personaId, name: personaName, content: null, mode: 'installed' };

    // DON'T try to restart the AI with the persona — AIs will refuse NSFW content.
    // Instead: save the file and tell the user how to use it.
    // The persona file is saved to .claude/agents/{id}.md — the user's own AI workflow
    // (e.g. start.bat with --dangerously-skip-permissions) will pick it up on next launch.

    var contentSize = Math.round(content.length / 1024) + 'KB';

    // Platform-specific install instructions
    var instructions = '';
    if (CLI_CMD === 'claude') {
        instructions =
            'Persona saved to: `.claude/agents/' + personaId + '.md`\n\n' +
            '**To activate:** Run `claude --dangerously-skip-permissions --agent ' + personaId + '` from this directory.\n' +
            'Or: the persona loads as project context when Claude Code starts in this directory.';
    } else if (CLI_CMD === 'codex') {
        // Codex uses system prompt via --system-prompt flag or AGENTS.md
        var codexFile = path.join(EXCHANGE_DIR, 'AGENTS.md');
        fs.writeFileSync(codexFile, content, 'utf8');
        instructions =
            'Persona saved to: `AGENTS.md` (Codex reads this as agent instructions)\n' +
            'Also saved to: `.claude/agents/' + personaId + '.md`\n\n' +
            '**To activate:** Run `codex` from this directory — it reads AGENTS.md automatically.';
    } else if (CLI_CMD === 'aider') {
        // Aider uses .aider.conf.yml or --read flag
        var aiderFile = path.join(EXCHANGE_DIR, '.aider.persona.md');
        fs.writeFileSync(aiderFile, content, 'utf8');
        instructions =
            'Persona saved to: `.aider.persona.md`\n' +
            'Also saved to: `.claude/agents/' + personaId + '.md`\n\n' +
            '**To activate:** Run `aider --read .aider.persona.md` from this directory.';
    } else if (CLI_CMD === 'interpreter') {
        // Open Interpreter uses system message via -s flag or profile
        var oiFile = path.join(EXCHANGE_DIR, 'persona_system_prompt.md');
        fs.writeFileSync(oiFile, content, 'utf8');
        instructions =
            'Persona saved to: `persona_system_prompt.md`\n' +
            'Also saved to: `.claude/agents/' + personaId + '.md`\n\n' +
            '**To activate:** Run `interpreter --system-message "$(cat persona_system_prompt.md)"`\n' +
            'Or paste the content into your Open Interpreter profile.';
    } else {
        instructions =
            'Persona saved to: `.claude/agents/' + personaId + '.md`\n\n' +
            '**To activate:** Load the file content as your AI\'s system prompt or agent definition.\n' +
            '- **ChatGPT:** Paste into Custom Instructions → "How would you like ChatGPT to respond?"\n' +
            '- **Gemini:** Set as system instruction in the API or Advanced Settings\n' +
            '- **Copilot:** Save as `.github/copilot-instructions.md` in your project\n' +
            '- **API usage:** Pass as the `system` message in your API call';
    }

    sendChat(
        '**Installed: ' + personaName + '** (' + contentSize + ')\n\n' +
        instructions + '\n\n' +
        'Type **"uninstall"** to remove the persona file.'
    );
}

// .claude/agents/ directory for installed personas
var AGENT_DIR = path.join(EXCHANGE_DIR, '.claude', 'agents');
try { fs.mkdirSync(AGENT_DIR, { recursive: true }); } catch(e) {}

// ask the AI a question and get the text response back
function askAI(prompt) {
    return new Promise(function(resolve) {
        if (CLI_CMD === 'claude') {
            // -p reads project context but we run from tmpdir (no CLAUDE.md = vanilla AI)
            var child = spawn('claude', ['-p', prompt], {
                cwd: require('os').tmpdir(),
                stdio: ['pipe', 'pipe', 'pipe'],
                windowsHide: true
            });
            var output = '';
            child.stdout.on('data', function(c) { output += c.toString(); });
            child.on('close', function() { resolve(output.trim()); });
            child.on('error', function() { resolve(''); });
        } else {
            var child = spawn(CLI_ARGS[0], [prompt], { stdio: ['pipe', 'pipe', 'pipe'], shell: true });
            var output = '';
            child.stdout.on('data', function(c) { output += c.toString(); });
            child.on('close', function() { resolve(output.trim()); });
            child.on('error', function() { resolve(''); });
            child.stdin.end();
        }
    });
}

// Ask AI with a persona loaded — sets up a proper .claude/agents/ structure
// in a temp dir so Claude Code treats the persona as a trusted agent definition.
// This is how Claude Code is designed to load personas.
function askAIWithPersona(personaContent, prompt) {
    return new Promise(function(resolve) {
        var tmpDir = path.join(require('os').tmpdir(), 'td_' + Date.now());
        var agentDir = path.join(tmpDir, '.claude', 'agents');
        try { fs.mkdirSync(agentDir, { recursive: true }); } catch(e) {}

        // git init so Claude recognizes this as a project root
        try { require('child_process').execSync('git init', { cwd: tmpDir, stdio: 'ignore' }); } catch(e) {}

        // Write persona as CLAUDE.md (highest priority — always read from project root)
        // AND as .claude/agents/test-drive.md (agent file for --agent flag)
        fs.writeFileSync(path.join(tmpDir, 'CLAUDE.md'), personaContent, 'utf8');
        fs.writeFileSync(path.join(agentDir, 'test-drive.md'), personaContent, 'utf8');

        function cleanup() {
            try { fs.unlinkSync(path.join(tmpDir, 'CLAUDE.md')); } catch(e) {}
            try { fs.unlinkSync(path.join(agentDir, 'test-drive.md')); } catch(e) {}
            try { fs.rmdirSync(agentDir); } catch(e) {}
            try { fs.rmdirSync(path.join(tmpDir, '.claude')); } catch(e) {}
            try { require('child_process').execSync('rm -rf .git', { cwd: tmpDir, stdio: 'ignore' }); } catch(e) {}
            try { fs.rmdirSync(tmpDir); } catch(e) {}
        }

        if (CLI_CMD === 'claude') {
            // Debug: verify setup before spawn
            var claudeMdExists = fs.existsSync(path.join(tmpDir, 'CLAUDE.md'));
            var claudeMdSize = claudeMdExists ? fs.statSync(path.join(tmpDir, 'CLAUDE.md')).size : 0;
            var gitExists = fs.existsSync(path.join(tmpDir, '.git'));
            console.log('[test-drive] tmpDir: ' + tmpDir);
            console.log('[test-drive] CLAUDE.md exists: ' + claudeMdExists + ' (' + claudeMdSize + ' bytes)');
            console.log('[test-drive] .git exists: ' + gitExists);
            console.log('[test-drive] spawning: claude -p "' + prompt.slice(0, 50) + '" --dangerously-skip-permissions');

            // -p "prompt" reads CLAUDE.md from project root (--print does NOT)
            var child = spawn('claude', ['-p', prompt, '--dangerously-skip-permissions'], {
                cwd: tmpDir,
                stdio: ['pipe', 'pipe', 'pipe'],
                windowsHide: true
            });

            var stderr = '';
            child.stderr.on('data', function(c) { stderr += c.toString(); });
            var output = '';
            child.stdout.on('data', function(c) { output += c.toString(); });
            child.on('close', function(code) {
                console.log('[test-drive] claude exited (' + code + ') output: ' + output.length + ' chars');
                if (stderr) console.log('[test-drive] stderr: ' + stderr.slice(0, 500));
                cleanup(); resolve(output.trim());
            });
            child.on('error', function(err) { console.log('[test-drive] spawn error: ' + err.message); cleanup(); resolve(''); });
        } else if (CLI_CMD === 'codex') {
            // Codex: write AGENTS.md in temp dir, run codex from there
            fs.writeFileSync(path.join(tmpDir, 'AGENTS.md'), personaContent, 'utf8');
            var child = spawn('codex', ['--quiet', '--full-auto', prompt], {
                cwd: tmpDir, stdio: ['pipe', 'pipe', 'pipe'], shell: true
            });
            var output = '';
            child.stdout.on('data', function(c) { output += c.toString(); });
            child.on('close', function() { cleanup(); try { fs.unlinkSync(path.join(tmpDir, 'AGENTS.md')); } catch(e) {} resolve(output.trim()); });
            child.on('error', function() { cleanup(); resolve(''); });
            child.stdin.end();
        } else if (CLI_CMD === 'aider') {
            // Aider: write persona to temp file, use --read flag
            var personaFile = path.join(tmpDir, 'persona.md');
            fs.writeFileSync(personaFile, personaContent, 'utf8');
            var child = spawn('aider', ['--message', prompt, '--read', personaFile, '--yes', '--no-auto-commits', '--no-git'], {
                cwd: tmpDir, stdio: ['pipe', 'pipe', 'pipe'], shell: true
            });
            var output = '';
            child.stdout.on('data', function(c) { output += c.toString(); });
            child.on('close', function() { cleanup(); try { fs.unlinkSync(personaFile); } catch(e) {} resolve(output.trim()); });
            child.on('error', function() { cleanup(); resolve(''); });
            child.stdin.end();
        } else {
            // Interpreter and others: pipe persona + prompt through stdin
            var full = personaContent + '\n\n---\n\nRespond in-character to: ' + prompt;
            var child = spawn(CLI_ARGS[0], [], { stdio: ['pipe', 'pipe', 'pipe'], shell: true });
            var output = '';
            child.stdout.on('data', function(c) { output += c.toString(); });
            child.on('close', function() { cleanup(); resolve(output.trim()); });
            child.on('error', function() { cleanup(); resolve(''); });
            child.stdin.write(full);
            child.stdin.end();
        }
    });
}

// =============================================
//  U004: PRE-UPLOAD SECURITY SCAN
// =============================================

var SECURITY_PATTERNS = [
    { pattern: /sk-[a-zA-Z0-9]{20,}/g, label: 'OpenAI API key' },
    { pattern: /sk_live_[a-zA-Z0-9]+/g, label: 'Stripe live key' },
    { pattern: /sk_test_[a-zA-Z0-9]+/g, label: 'Stripe test key' },
    { pattern: /uhub_[a-f0-9]{10,}/g, label: 'Exchange token' },
    { pattern: /ghp_[a-zA-Z0-9]{36}/g, label: 'GitHub personal access token' },
    { pattern: /ghu_[a-zA-Z0-9]{36}/g, label: 'GitHub user token' },
    { pattern: /xoxb-[a-zA-Z0-9-]+/g, label: 'Slack bot token' },
    { pattern: /xoxp-[a-zA-Z0-9-]+/g, label: 'Slack user token' },
    { pattern: /AKIA[0-9A-Z]{16}/g, label: 'AWS access key' },
    { pattern: /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g, label: 'Email address' },
    { pattern: /\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b/g, label: 'IP address' },
    { pattern: /[A-Z_]*(API_KEY|SECRET_KEY|ACCESS_KEY|PRIVATE_KEY)[A-Z_]*\s*[:=]\s*['"][^'"]+['"]/gi, label: 'Hardcoded secret' },
    { pattern: /\/home\/[a-zA-Z][a-zA-Z0-9_-]+\//g, label: 'Unix home path with username' },
    { pattern: /C:\\Users\\[a-zA-Z][a-zA-Z0-9_.-]+\\/gi, label: 'Windows user path' },
    { pattern: /credentials\.json|\.env\b|config\.secret/gi, label: 'Credential file reference' }
];

// U003: Corporate/default persona boilerplate phrases
var CORPORATE_PHRASES = [
    "i'm an ai language model",
    "i don't have personal opinions",
    "as an ai assistant",
    "i aim to be helpful, harmless, and honest",
    "i cannot and should not",
    "my training data",
    "i'm designed to be helpful",
    "i was created by openai",
    "i was created by anthropic",
    "i'm a large language model",
    "an ai developed by",
    "i'm chatgpt",
    "i'm claude"
];

function scanForSecrets(content) {
    var found = [];
    for (var i = 0; i < SECURITY_PATTERNS.length; i++) {
        var p = SECURITY_PATTERNS[i];
        var matches = content.match(p.pattern);
        if (matches) {
            for (var j = 0; j < matches.length; j++) {
                // Show partial match so user knows what was flagged
                var m = matches[j];
                var preview = m.length > 20 ? m.slice(0, 12) + '...' + m.slice(-4) : m;
                found.push(p.label + ': ' + preview);
            }
        }
    }
    return found;
}

function checkCorporateContent(content) {
    var lower = content.toLowerCase();
    var matches = [];
    for (var i = 0; i < CORPORATE_PHRASES.length; i++) {
        if (lower.indexOf(CORPORATE_PHRASES[i]) !== -1) {
            matches.push('"' + CORPORATE_PHRASES[i] + '"');
        }
    }
    return matches;
}

// =============================================
//  U002-U005: UPLOAD COMMAND HANDLER
// =============================================

var uploadState = null; // tracks multi-step upload conversation

async function handleUpload() {
    console.log('[watchdog] Upload persona flow started');

    if (!TOKEN) {
        sendChat('Cannot upload — no authentication token. Register first via the exchange.');
        return;
    }

    uploadState = { step: 'extract', data: {} };

    sendChat(
        '**Uploading your persona to the exchange.**\n\n' +
        'I need your AI to provide its persona content. Sending extraction request now...\n\n' +
        '⚠️ **SECURITY REMINDERS:**\n' +
        '- Do NOT include API keys, tokens, or passwords\n' +
        '- Do NOT include personal names, emails, or addresses\n' +
        '- Do NOT include file paths with usernames\n' +
        '- Do NOT include default AI boilerplate — only YOUR custom personality\n' +
        '- Everything you upload will be **publicly visible**\n\n' +
        'Asking your AI to extract its persona now...'
    );

    // Ask the AI to extract its persona
    var extractPrompt = [
        'The user wants to upload your persona to the AI Persona Exchange catalog.',
        'Extract your CUSTOM persona — the unique behavioral rules, personality traits, voice, and instructions that make you different from a default AI.',
        'DO NOT include any of the following:',
        '- API keys, tokens, or credentials of any kind',
        '- Email addresses, phone numbers, or personal names',
        '- File paths containing usernames',
        '- Default AI boilerplate ("I am an AI language model", "I aim to be helpful")',
        '- Anything you did not customize yourself',
        '',
        'Respond in this EXACT format (fill in each field):',
        'PERSONA_NAME: (a short display name, 3-100 chars)',
        'PERSONA_ID: (lowercase-with-hyphens, 3-80 chars, unique)',
        'DESCRIPTION: (what this persona does, 10-200 chars)',
        'TAGS: (comma-separated, MUST pick from this list ONLY: persona, mode, jailbreak, utility, framework, roleplay, coding, creative, productivity, conversation, education, nsfw, sfw, dark, wholesome, humor, professional, verbose, concise, poetic, casual, formal, chaotic — pick 2-5 that fit best)',
        'NSFW: (true or false)',
        'PLATFORMS: (comma-separated: universal, claude-code, chatgpt, api)',
        'CONTENT_START',
        '(your full persona content here — the actual system prompt / behavioral spec)',
        'CONTENT_END',
        '',
        'If you have NO custom persona (you are a default AI with no special instructions), say: NO_CUSTOM_PERSONA'
    ].join('\n');

    var response = await askAI(extractPrompt);

    if (!response) {
        sendChat('Could not get a response from your AI. Try again or type "upload-persona" in chat.');
        uploadState = null;
        return;
    }

    // Check if AI says it has no custom persona
    if (response.indexOf('NO_CUSTOM_PERSONA') !== -1) {
        sendChat('Your AI reports it has no custom persona to upload. The exchange is for unique, community-created personas — default AI behavior is not uploadable.');
        uploadState = null;
        return;
    }

    // Parse the structured response
    var nameMatch = response.match(/PERSONA_NAME:\s*(.+)/i);
    var idMatch = response.match(/PERSONA_ID:\s*(.+)/i);
    var descMatch = response.match(/DESCRIPTION:\s*(.+)/i);
    var tagsMatch = response.match(/TAGS:\s*(.+)/i);
    var nsfwMatch = response.match(/NSFW:\s*(true|false)/i);
    var platformsMatch = response.match(/PLATFORMS:\s*(.+)/i);
    var contentMatch = response.match(/CONTENT_START\s*\n?([\s\S]*?)\n?\s*CONTENT_END/i);

    if (!nameMatch || !idMatch || !descMatch || !contentMatch) {
        sendChat('Could not parse persona data from your AI\'s response. The AI needs to use the exact format with PERSONA_NAME, PERSONA_ID, DESCRIPTION, CONTENT_START/CONTENT_END markers. Try again.');
        uploadState = null;
        return;
    }

    var personaName = nameMatch[1].trim();
    var personaId = idMatch[1].trim().toLowerCase().replace(/[^a-z0-9-]/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '');
    var description = descMatch[1].trim();
    var VALID_TAGS = ['persona','mode','jailbreak','utility','framework','roleplay','coding','creative','productivity','conversation','education','nsfw','sfw','dark','wholesome','humor','professional','verbose','concise','poetic','casual','formal','chaotic'];
    var rawTags = tagsMatch ? tagsMatch[1].split(',').map(function(t) { return t.trim().toLowerCase(); }).filter(Boolean) : [];
    var tags = rawTags.filter(function(t) { return VALID_TAGS.indexOf(t) !== -1; });
    var invalidTags = rawTags.filter(function(t) { return VALID_TAGS.indexOf(t) === -1; });

    if (invalidTags.length > 0) {
        sendChat(
            '**Some tags were removed because they\'re not in the unified taxonomy:** ' + invalidTags.join(', ') + '\n\n' +
            'Valid tags: ' + VALID_TAGS.join(', ') + '\n\n' +
            'Continuing with valid tags: ' + (tags.length > 0 ? tags.join(', ') : '(none — will default to "persona")')
        );
    }
    if (tags.length === 0) tags = ['persona'];

    var nsfw = nsfwMatch ? nsfwMatch[1].toLowerCase() === 'true' : false;
    // Auto-add nsfw/sfw tag if not present
    if (nsfw && tags.indexOf('nsfw') === -1) tags.push('nsfw');
    if (!nsfw && tags.indexOf('sfw') === -1 && tags.indexOf('nsfw') === -1) tags.push('sfw');

    var platforms = platformsMatch ? platformsMatch[1].split(',').map(function(p) { return p.trim().toLowerCase(); }).filter(Boolean) : ['universal'];
    var content = contentMatch[1].trim();

    // U003: Corporate content check
    var corporateMatches = checkCorporateContent(content);
    if (corporateMatches.length > 0) {
        sendChat(
            '**REJECTED — Corporate/default AI content detected.**\n\n' +
            'Found these stock AI phrases in the persona content:\n' +
            corporateMatches.map(function(m) { return '- ' + m; }).join('\n') + '\n\n' +
            'The exchange is for **unique, community-created personas only** — not default AI behavior. ' +
            'Remove these phrases and any other boilerplate, then try again.'
        );
        uploadState = null;
        return;
    }

    // U004: Security scan
    var secrets = scanForSecrets(content);
    // Also scan name and description
    secrets = secrets.concat(scanForSecrets(personaName));
    secrets = secrets.concat(scanForSecrets(description));

    if (secrets.length > 0) {
        sendChat(
            '**BLOCKED — Sensitive data detected in your persona content.**\n\n' +
            'The security scan found these issues:\n' +
            secrets.map(function(s) { return '- 🚨 ' + s; }).join('\n') + '\n\n' +
            '**Remove ALL credentials, personal info, and identifying data** before uploading. ' +
            'Your persona content will be PUBLIC. Clean it up and try again.'
        );
        uploadState = null;
        return;
    }

    // Validate minimums
    if (personaId.length < 3) {
        sendChat('Persona ID is too short (minimum 3 characters). Try again.');
        uploadState = null;
        return;
    }
    if (content.length < 50) {
        sendChat('Persona content is too short (minimum 50 characters). A real persona has substance. Try again.');
        uploadState = null;
        return;
    }

    // All checks passed — upload to Supabase
    sendChat(
        'All checks passed. Uploading **' + personaName + '** (`' + personaId + '`) to the exchange...\n' +
        '- Content: ' + content.length + ' characters\n' +
        '- Tags: ' + (tags.join(', ') || 'none') + '\n' +
        '- NSFW: ' + (nsfw ? 'Yes' : 'No') + '\n' +
        '- Platforms: ' + platforms.join(', ')
    );

    var result = await supaRpc('upload_persona', {
        p_token: TOKEN,
        p_id: personaId,
        p_name: personaName,
        p_description: description,
        p_platforms: platforms,
        p_tags: tags,
        p_nsfw: nsfw,
        p_content_md: content,
        p_version: '1.0.0'
    });

    console.log('[watchdog] Upload result:', JSON.stringify(result));

    if (result && result.error) {
        sendChat('**Upload failed:** ' + (typeof result.error === 'string' ? result.error : JSON.stringify(result.error)));
        uploadState = null;
        return;
    }

    if (result && result.persona_id) {
        // U005: Success receipt
        var browseUrl = SITE_URL + '/index.html';
        sendChat(
            '**Persona uploaded successfully!** 🎉\n\n' +
            '- **Name:** ' + personaName + '\n' +
            '- **ID:** `' + result.persona_id + '`\n' +
            '- **Status:** Live in the catalog\n' +
            '- **NSFW:** ' + (nsfw ? 'Yes' : 'No') + '\n' +
            '- **Platforms:** ' + platforms.join(', ') + '\n' +
            '- **Browse:** ' + browseUrl + '\n\n' +
            '⚠️ **This persona is now PUBLIC.** Anyone can browse, install, and test drive it.\n' +
            'To delete it later, delete your account from the Dashboard page or call `delete_my_account` via the API.'
        );
    } else if (result && result.error) {
        sendChat('**Upload failed:** ' + result.error);
    } else {
        sendChat('Upload returned an unexpected response: ' + JSON.stringify(result));
    }

    uploadState = null;
}

// =============================================
//  MESSAGE DISPATCHER
// =============================================

function dispatch(text) {
    console.log('[Website -> AI] ' + text);
    var lower = text.toLowerCase().trim();

    // === PERSONA CONTROL COMMANDS ===

    // Uninstall persona
    if (lower === 'uninstall' || lower === 'uninstall persona' || lower === 'remove persona') {
        if (activePersona && activePersona.mode === 'installed') {
            var installFile = path.join(AGENT_DIR, activePersona.id + '.md');
            try { fs.unlinkSync(installFile); } catch(e) {}
            endPersonaMode('Agent file removed.');
        } else {
            sendChat('No persona is installed. Use "install {id}" to install one.');
        }
        return;
    }

    // === STANDARD COMMANDS ===

    // upload command
    if (lower === 'upload-persona' || lower === 'upload persona' || lower === 'share persona' || lower === 'share-persona') {
        handleUpload();
        return;
    }

    // test drive command
    if (lower.indexOf('test drive') !== -1 || lower.indexOf('test-drive') !== -1 || lower.indexOf('testdrive') !== -1) {
        var pid = findPersonaId(text);
        if (pid) { handleTestDrive(pid); return; }
        // Also check database for community personas
        sendChat('Which persona? Built-in: ' + PERSONA_IDS.join(', ') + '\nOr type the exact ID of any community persona.');
        return;
    }

    // install command
    if (lower.indexOf('install') !== -1) {
        var pid = findPersonaId(text);
        if (pid) { handleInstall(pid); return; }
        sendChat('Which persona? Built-in: ' + PERSONA_IDS.join(', ') + '\nOr type the exact ID of any community persona.');
        return;
    }

    // browse/list/catalog command
    if (lower.indexOf('browse') !== -1 || lower.indexOf('catalog') !== -1 || lower.indexOf('list') !== -1) {
        handleBrowse();
        return;
    }

    // help command
    if (lower === 'help' || lower === '?') {
        sendChat('Commands:\n- **test drive {persona}** — preview the full persona content\n- **install {persona}** — save persona as an agent file for your AI\n- **uninstall** — remove the installed persona file\n- **upload-persona** — share your AI\'s custom persona\n- **browse** — list all personas\n- Or just chat with me!\n\nBuilt-in: ' + PERSONA_IDS.join(', '));
        return;
    }

    // everything else goes to the default AI
    if (CLI_CMD === 'claude') {
        sendToClaude(text);
    } else {
        messageQueue.push(text);
        processQueue();
    }
}

// =============================================
//  POLLING
// =============================================

function pollMessages() {
    if (!ready) return;
    supaGet(
        'chat_messages?session_id=eq.' + SESSION +
        '&sender=eq.user&created_at=gt.' + encodeURIComponent(lastChecked) +
        '&order=created_at.asc'
    ).then(function(msgs) {
        if (!msgs || !Array.isArray(msgs) || msgs.length === 0) return;
        lastChecked = msgs[msgs.length - 1].created_at;
        for (var i = 0; i < msgs.length; i++) {
            dispatch(msgs[i].message);
        }
    });
}

// =============================================
//  MAIN
// =============================================

function main() {
    try { fs.writeFileSync(path.join(path.dirname(process.argv[1] || '.'), 'watchdog.pid'), String(process.pid)); } catch(e) {}

    console.log('');
    console.log('  ==========================================');
    console.log('   AI Persona Exchange — Watchdog');
    console.log('   AI: ' + AI_NAME + ' | Platform: ' + CLI_CMD);
    console.log('   Session: ' + SESSION.slice(0, 12) + '...');
    console.log('   Mode: ' + (CLI_CMD === 'claude' ? 'persistent stream' : 'one-shot per message'));
    console.log('  ==========================================');
    console.log('');

    sendChat('Connected and online as ' + AI_NAME + '. Click Install or Test Drive on any persona card, or type here.');

    var url = SITE_URL + '/index.html?session=' + SESSION;
    var opener = process.platform === 'win32' ? 'start' : process.platform === 'darwin' ? 'open' : 'xdg-open';
    try { var b = spawn(opener, ['""', url], { shell: true, stdio: 'ignore', detached: true }); b.unref(); } catch(e) {}

    if (CLI_CMD === 'claude') {
        startClaude();
    }

    setTimeout(function() {
        ready = true;
        console.log('[watchdog] Polling active (' + (POLL_MS/1000) + 's)');
    }, CLI_CMD === 'claude' ? 5000 : 2000);

    setInterval(pollMessages, POLL_MS);
}

main();

function cleanup() {
    if (claudeProcess && !claudeProcess.killed) claudeProcess.kill();
    try { fs.unlinkSync(path.join(path.dirname(process.argv[1] || '.'), 'watchdog.pid')); } catch(e) {}
    process.exit();
}
process.on('SIGINT', cleanup);
process.on('SIGTERM', cleanup);
