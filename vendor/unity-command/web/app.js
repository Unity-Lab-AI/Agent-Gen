// UnityBotV4 web UI — extracted from index.html (super-review LOW #16).
// Setup wizard + chat SPA logic.

// ────────────────────────────────────────────────────────────────────────────
// State
// ────────────────────────────────────────────────────────────────────────────
const STEPS = [
  { id: 1, label: "Welcome", required: false },
  { id: 2, label: "Discord Token", required: true, requiredFields: ["DISCORD_TOKEN"] },
  { id: 3, label: "Pollinations Key", required: true, requiredFields: ["POLLINATIONS_API_KEY", "POLLINATIONS_TOKEN"], either: true },
  { id: 4, label: "CLI Bridge", required: false },
  { id: 5, label: "Approved Servers", required: false },
  // Collab step (id 6) removed 2026-05-19 — V4 is single-instance only.
  { id: 6, label: "Review", required: false, save: true },
];
const TOTAL_STEPS = STEPS.length;
const state = {
  step: 1,
  values: {},      // current wizard form values
  history: [],     // chat history [{role, content, image_urls?}]
  serverState: null,
  validation: {},  // {key: {valid, note}}
};

// ────────────────────────────────────────────────────────────────────────────
// HTTP helpers
// ────────────────────────────────────────────────────────────────────────────
async function api(method, path, body = null) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body) opts.body = JSON.stringify(body);
  const resp = await fetch(path, opts);
  let data;
  try { data = await resp.json(); }
  catch { data = { error: `HTTP ${resp.status}` }; }
  if (!resp.ok) data._status = resp.status;
  return { ok: resp.ok, data };
}

// ────────────────────────────────────────────────────────────────────────────
// Setup wizard
// ────────────────────────────────────────────────────────────────────────────
function renderProgress() {
  const wrap = document.getElementById("wizard-progress");
  wrap.innerHTML = "";
  for (let i = 1; i <= TOTAL_STEPS; i++) {
    const el = document.createElement("div");
    el.className = "step" + (i < state.step ? " done" : i === state.step ? " active" : "");
    wrap.appendChild(el);
  }
  const label = STEPS.find(s => s.id === state.step)?.label || "";
  document.getElementById("wizard-step-label").textContent = `Step ${state.step} of ${TOTAL_STEPS} — ${label}`;
}

function showStep(n) {
  state.step = Math.max(1, Math.min(TOTAL_STEPS, n));
  document.querySelectorAll(".wizard-step").forEach(el => {
    el.classList.toggle("hidden", parseInt(el.dataset.step) !== state.step);
  });
  document.getElementById("btn-prev").disabled = (state.step === 1);
  const stepDef = STEPS.find(s => s.id === state.step);
  const isSaveStep = !!stepDef.save;
  document.getElementById("btn-next").classList.toggle("hidden", isSaveStep);
  document.getElementById("btn-save").classList.toggle("hidden", !isSaveStep);
  document.getElementById("btn-skip").classList.toggle("hidden", !!stepDef.required || isSaveStep);
  renderProgress();
  if (isSaveStep) renderReview();
  refreshNextEnabled();
}

function refreshNextEnabled() {
  const stepDef = STEPS.find(s => s.id === state.step);
  if (!stepDef.required) {
    document.getElementById("btn-next").disabled = false;
    return;
  }
  if (stepDef.either) {
    const a = state.values["POLLINATIONS_API_KEY"];
    const b = state.values["POLLINATIONS_TOKEN"];
    const aOk = a && state.validation["POLLINATIONS_API_KEY"]?.valid;
    const bOk = b && state.validation["POLLINATIONS_TOKEN"]?.valid;
    document.getElementById("btn-next").disabled = !(aOk || bOk);
    return;
  }
  for (const k of stepDef.requiredFields || []) {
    const v = state.values[k];
    if (!v || !state.validation[k]?.valid) {
      document.getElementById("btn-next").disabled = true;
      return;
    }
  }
  document.getElementById("btn-next").disabled = false;
}

async function validateInput(input) {
  const key = input.dataset.key;
  const value = (input.type === "checkbox") ? (input.checked ? "1" : "") : input.value.trim();
  state.values[key] = value;

  if (value === "") {
    state.validation[key] = { valid: true, note: "" };
    input.classList.remove("invalid", "valid");
    setFeedback(key, "", "note");
    refreshNextEnabled();
    return;
  }

  const { ok, data } = await api("POST", "/api/setup/validate", { key, value });
  if (ok) {
    state.validation[key] = { valid: data.valid, note: data.note || "" };
    input.classList.toggle("invalid", !data.valid);
    input.classList.toggle("valid", data.valid);
    setFeedback(key, data.note || (data.valid ? "✓ valid" : ""), data.valid ? "ok" : "err");
  } else {
    state.validation[key] = { valid: false, note: data.error || "validation failed" };
    setFeedback(key, data.error || "validation failed", "err");
  }
  refreshNextEnabled();
}

function setFeedback(key, text, cls) {
  const el = document.querySelector(`[data-feedback-for="${key}"]`);
  if (!el) return;
  el.textContent = text;
  el.className = "feedback " + cls;
}

function renderReview() {
  const tb = document.getElementById("review-table");
  tb.innerHTML = "";
  const SECRETS = new Set(["DISCORD_TOKEN", "POLLINATIONS_API_KEY", "POLLINATIONS_TOKEN"]);
  const ORDER = ["DISCORD_TOKEN", "POLLINATIONS_API_KEY", "POLLINATIONS_TOKEN",
                 "CLAUDE_CHAT_CHANNEL_ID", "CLAUDE_API_PORT",
                 "ALLOWED_GUILDS", "ALLOWED_GUILDS_STRICT", "ALLOWED_CHANNELS"];
  // Collab subsystem keys (CLAUDE_AUTHOR / CLAUDE_COLLAB_KEY / SUPABASE_*)
  // removed 2026-05-19 — V4 is single-instance only.
  const showPlaintext = document.getElementById("show-plaintext")?.checked === true;
  for (const k of ORDER) {
    const tr = document.createElement("tr");
    const tdKey = document.createElement("td");
    tdKey.textContent = k;
    const tdVal = document.createElement("td");
    const v = state.values[k] || "";
    if (!v) { tdVal.textContent = "(not set)"; tdVal.className = "unset"; }
    else if (SECRETS.has(k) && !showPlaintext) {
      tdVal.textContent = v.slice(0, 6) + "…" + (v.length > 12 ? v.slice(-4) : "");
    } else {
      tdVal.textContent = v;
    }
    tr.appendChild(tdKey); tr.appendChild(tdVal);
    tb.appendChild(tr);
  }
}

async function saveConfig() {
  const fields = { ...state.values };
  if (fields["ALLOWED_GUILDS_STRICT"] === "") delete fields["ALLOWED_GUILDS_STRICT"];

  const banner = document.getElementById("save-feedback");
  banner.style.display = "block";
  banner.textContent = "Saving…";
  banner.style.borderColor = "var(--warn)";
  banner.style.background = "#2a1d10";
  banner.style.color = "#fde68a";

  const { ok, data } = await api("POST", "/api/setup", { fields });
  if (!ok) {
    const errs = data.errors || {};
    const messages = Object.entries(errs).map(([k, v]) => `${k}: ${v}`).join("\n");
    banner.textContent = "Couldn't save:\n" + messages;
    banner.style.borderColor = "var(--err)";
    banner.style.background = "#2a1010";
    banner.style.color = "#fecaca";
    return;
  }
  banner.textContent = data.message || "Saved! Reloading...";
  banner.style.borderColor = "var(--ok)";
  banner.style.background = "#10271a";
  banner.style.color = "#bbf7d0";
  setTimeout(refreshState, 1200);
}

// ────────────────────────────────────────────────────────────────────────────
// Chat
// ────────────────────────────────────────────────────────────────────────────
function pushMessage(role, body, opts = {}) {
  state.history.push({ role, content: body, image_urls: opts.image_urls || [] });
  renderMessages();
}

function renderMessages() {
  const wrap = document.getElementById("messages");
  wrap.innerHTML = "";
  for (const msg of state.history) {
    const div = document.createElement("div");
    div.className = "message " + msg.role;
    const av = document.createElement("div");
    av.className = "avatar";
    av.textContent = msg.role === "user" ? "you" : msg.role === "assistant" ? "unity" : "system";
    const body = document.createElement("div");
    body.className = "body";
    body.textContent = msg.content;
    if (msg.image_urls && msg.image_urls.length) {
      for (const url of msg.image_urls) {
        const img = document.createElement("img");
        img.src = url;
        img.alt = "generated image";
        img.loading = "lazy";
        body.appendChild(img);
        const meta = document.createElement("div");
        meta.className = "image-meta";
        meta.textContent = url;
        body.appendChild(meta);
      }
    }
    div.appendChild(av); div.appendChild(body);
    wrap.appendChild(div);
  }
  wrap.scrollTop = wrap.scrollHeight;
}

async function sendChat() {
  const input = document.getElementById("chat-input");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  input.style.height = "auto";
  pushMessage("user", text);

  const thinking = document.createElement("div");
  thinking.className = "message assistant";
  thinking.innerHTML = '<div class="avatar">unity</div><div class="body thinking">thinking</div>';
  document.getElementById("messages").appendChild(thinking);
  document.getElementById("messages").scrollTop = 1e9;

  const model = document.getElementById("model-select").value;
  const apiHistory = state.history.slice(0, -1).map(m => ({ role: m.role, content: m.content }));
  const { ok, data } = await api("POST", "/api/chat", { message: text, history: apiHistory, model });
  thinking.remove();
  if (!ok) {
    pushMessage("system", "Error: " + (data.error || "unknown"));
    return;
  }
  pushMessage("assistant", data.text || "", { image_urls: data.image_urls || [] });
}

async function generateImage() {
  const input = document.getElementById("chat-input");
  const prompt = input.value.trim();
  if (!prompt) return;
  input.value = "";
  pushMessage("user", "🎨 generate image: " + prompt);
  const thinking = document.createElement("div");
  thinking.className = "message assistant";
  thinking.innerHTML = '<div class="avatar">unity</div><div class="body thinking">painting</div>';
  document.getElementById("messages").appendChild(thinking);
  const { ok, data } = await api("POST", "/api/image", { prompt });
  thinking.remove();
  if (!ok) {
    pushMessage("system", "Error: " + (data.error || "unknown"));
    return;
  }
  pushMessage("assistant", "", { image_urls: [data.url] });
}

// ────────────────────────────────────────────────────────────────────────────
// State refresh
// ────────────────────────────────────────────────────────────────────────────
async function refreshState() {
  const { ok, data } = await api("GET", "/api/state");
  state.serverState = data;
  const stEl = document.getElementById("status");
  const stTx = document.getElementById("status-text");
  if (data.configured) {
    stEl.classList.add("ok");
    stTx.textContent = `connected · ${data.pollinations_stack || "?"}`;
    document.getElementById("wizard-view").classList.add("hidden");
    document.getElementById("chat-view").classList.remove("hidden");
    document.getElementById("chat-info").textContent = `${data.chat_url} · default model: ${data.default_model}`;
    refreshModels();
  } else {
    stEl.classList.remove("ok");
    stTx.textContent = data.env_exists ? "setup incomplete" : "needs setup";
    document.getElementById("chat-view").classList.add("hidden");
    document.getElementById("wizard-view").classList.remove("hidden");
    for (const [k, v] of Object.entries(data.env_values_preview || {})) {
      if (!v || v.includes("…")) continue;
      const input = document.querySelector(`[data-key="${k}"]`);
      if (input && !state.values[k]) {
        input.value = v;
        state.values[k] = v;
      }
    }
    showStep(state.step);
  }
}

async function refreshModels() {
  const { ok, data } = await api("GET", "/api/models");
  if (!ok) return;
  const sel = document.getElementById("model-select");
  const current = sel.value;
  sel.innerHTML = "";
  for (const m of data.models || []) {
    const opt = document.createElement("option");
    opt.value = m.name;
    opt.textContent = m.description ? `${m.name} — ${m.description}` : m.name;
    sel.appendChild(opt);
  }
  if (current && [...sel.options].some(o => o.value === current)) sel.value = current;
}

// ────────────────────────────────────────────────────────────────────────────
// Wire up
// ────────────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-key]").forEach(input => {
    const handler = () => validateInput(input);
    input.addEventListener("input", handler);
    input.addEventListener("change", handler);
  });

  document.getElementById("btn-prev").addEventListener("click", () => showStep(state.step - 1));
  document.getElementById("btn-next").addEventListener("click", () => showStep(state.step + 1));
  document.getElementById("btn-skip").addEventListener("click", () => showStep(state.step + 1));
  document.getElementById("btn-save").addEventListener("click", saveConfig);

  const plaintextToggle = document.getElementById("show-plaintext");
  if (plaintextToggle) {
    plaintextToggle.addEventListener("change", renderReview);
  }

  const chatInput = document.getElementById("chat-input");
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendChat();
    }
  });
  chatInput.addEventListener("input", () => {
    chatInput.style.height = "auto";
    chatInput.style.height = Math.min(200, chatInput.scrollHeight) + "px";
  });
  document.getElementById("btn-send").addEventListener("click", sendChat);
  document.getElementById("btn-image").addEventListener("click", generateImage);
  document.getElementById("btn-clear-chat").addEventListener("click", () => {
    state.history = [];
    renderMessages();
  });
  document.getElementById("btn-reconfigure").addEventListener("click", () => {
    document.getElementById("chat-view").classList.add("hidden");
    document.getElementById("wizard-view").classList.remove("hidden");
    state.step = 1;
    showStep(1);
  });

  showStep(1);
  refreshState();
});
