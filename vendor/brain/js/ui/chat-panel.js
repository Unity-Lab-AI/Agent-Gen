/**
 * chat-panel.js — Full conversation log panel
 *
 * Opens when the Unity avatar is clicked. Shows complete message
 * history with text input at the bottom. Mic toggle inside panel.
 */

export class ChatPanel {
  constructor({ storage, onSend, onMicToggle }) {
    this._storage = storage;
    this._onSend = onSend;
    this._onMicToggle = onMicToggle;
    this._open = false;
    this._el = null;
    this._messagesEl = null;
    this._inputEl = null;
    this._build();
  }

  _build() {
    this._el = document.createElement('div');
    this._el.id = 'chat-panel';
    this._el.className = 'chat-panel hidden';
    this._el.innerHTML = `
      <div class="chat-header">
        <span class="chat-title">Unity</span>
        <div class="chat-header-btns">
          <button class="chat-mute-btn" title="Mute Unity's voice (she still types responses — just silences TTS in the moment)">🔊</button>
          <button class="chat-mic-btn" title="Mute your mic (stops her from hearing you)">🎤</button>
          <button class="chat-min-btn" title="Minimise — collapse to the title bar, keeps the conversation">&minus;</button>
          <button class="chat-full-btn" title="Fullscreen — fill the window">&#9974;</button>
          <button class="chat-close-btn" title="Close">&times;</button>
        </div>
      </div>
      <div class="chat-messages" id="chat-messages"></div>
      <div class="chat-input-wrap">
        <input type="text" class="chat-input" id="chat-input" placeholder="Talk to Unity..." autocomplete="off" spellcheck="false">
        <button class="chat-send-btn" title="Send">→</button>
      </div>
    `;
    document.body.appendChild(this._el);

    this._messagesEl = this._el.querySelector('#chat-messages');
    this._inputEl = this._el.querySelector('#chat-input');
    const sendBtn = this._el.querySelector('.chat-send-btn');
    const closeBtn = this._el.querySelector('.chat-close-btn');
    const muteBtn = this._el.querySelector('.chat-mute-btn');
    const micBtn = this._el.querySelector('.chat-mic-btn');
    const minBtn = this._el.querySelector('.chat-min-btn');
    const fullBtn = this._el.querySelector('.chat-full-btn');

    // ── WINDOW CONTROLS ──────────────────────────────────────────────────
    // This is the panel every visitor talks to her through, and it was a
    // fixed 380×520 box in the corner with only a close button: no way to
    // give a long conversation more room, and no way to push it aside
    // without losing it. Minimise collapses to the title bar and KEEPS the
    // conversation; fullscreen fills the window.
    // ⚠ The two states are mutually exclusive and entering one clears the
    //   other — a minimised fullscreen panel is a title bar stretched across
    //   the whole screen, which is nobody's intent.
    // ⚠ Persisted, because a visitor who chose fullscreen means it for the
    //   next message too, not just this one. Wrapped: storage throws in
    //   private-mode browsers and a thrown preference must not cost a chat.
    const KEY = 'unity_chat_panel_view';
    const applyView = (v, persist) => {
      const full = v === 'fullscreen';
      const mini = v === 'minimized';
      this._el.classList.toggle('fullscreen', full);
      this._el.classList.toggle('minimized', mini);
      // The glyph shows what the button WILL DO, not the state it is in.
      fullBtn.innerHTML = full ? '&#10066;' : '&#9974;';
      fullBtn.title = full ? 'Exit fullscreen' : 'Fullscreen — fill the window';
      minBtn.innerHTML = mini ? '&#9633;' : '&minus;';
      minBtn.title = mini ? 'Restore the conversation' : 'Minimise — collapse to the title bar, keeps the conversation';
      this._view = v;
      if (persist) { try { localStorage.setItem(KEY, v); } catch { /* private mode */ } }
      // A restored or enlarged panel should show the newest message, not
      // wherever the scroll happened to be when it was collapsed.
      if (!mini && this._messagesEl) this._messagesEl.scrollTop = this._messagesEl.scrollHeight;
    };
    let _saved = 'normal';
    try { _saved = localStorage.getItem(KEY) || 'normal'; } catch { /* private mode */ }
    applyView(_saved === 'fullscreen' || _saved === 'minimized' ? _saved : 'normal', false);

    minBtn.addEventListener('click', () => applyView(this._view === 'minimized' ? 'normal' : 'minimized', true));
    fullBtn.addEventListener('click', () => applyView(this._view === 'fullscreen' ? 'normal' : 'fullscreen', true));
    // Clicking the title bar of a minimised panel restores it — the whole
    // visible surface is a target, not just the small button.
    this._el.querySelector('.chat-header').addEventListener('click', (e) => {
      if (this._view === 'minimized' && !e.target.closest('button')) applyView('normal', true);
    });
    this._applyChatView = applyView;

    // In-the-moment mute toggles. These reflect and update
    // window.unityChannels (the same state the setup-modal checkboxes
    // write to) so the chat panel's mute button is a live mirror of the
    // persistent toggle, not a separate ephemeral state. Flipping the
    // chat mute immediately calls voice.stopSpeaking if she's talking.
    // T4.13 — rely on CSS .chat-mute-btn / .chat-mic-btn rules to
    // carry the off-state styling (red tint + dim) via data-muted
    // attribute. Removed the inline .style.opacity override that was
    // competing with the CSS theme and producing the white default-
    // browser button background the operator called out.
    const syncButtons = () => {
      const ch = window.unityChannels || { userMic: true, unitySpeech: true };
      muteBtn.textContent = ch.unitySpeech ? '🔊' : '🔇';
      muteBtn.dataset.muted = ch.unitySpeech ? 'false' : 'true';
      micBtn.textContent = ch.userMic ? '🎤' : '🚫';
      micBtn.dataset.muted = ch.userMic ? 'false' : 'true';
    };
    muteBtn.addEventListener('click', () => {
      const ch = window.unityChannels = window.unityChannels || { userMic: true, unityVision: true, unitySpeech: true };
      ch.unitySpeech = !ch.unitySpeech;
      localStorage.setItem('unity_channel_unity_speech', ch.unitySpeech ? 'true' : 'false');
      // Update the setup-modal checkbox if it exists so both stay in sync
      const modalCb = document.getElementById('toggle-unity-speech');
      if (modalCb) modalCb.checked = ch.unitySpeech;
      // Live-apply: stop any in-progress TTS, set muted flag
      if (window.voice) {
        window.voice._muted = !ch.unitySpeech;
        if (!ch.unitySpeech) window.voice.stopSpeaking?.();
      }
      syncButtons();
    });
    micBtn.addEventListener('click', () => {
      const ch = window.unityChannels = window.unityChannels || { userMic: true, unityVision: true, unitySpeech: true };
      ch.userMic = !ch.userMic;
      localStorage.setItem('unity_channel_user_mic', ch.userMic ? 'true' : 'false');
      const modalCb = document.getElementById('toggle-user-mic');
      if (modalCb) modalCb.checked = ch.userMic;
      if (window.voice) {
        if (ch.userMic) window.voice.startListening?.();
        else window.voice.stopListening?.();
      }
      syncButtons();
    });
    syncButtons();

    // Send on Enter or button click
    this._inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && this._inputEl.value.trim()) {
        this._send();
      }
      // ⚠ Escape leaves FULLSCREEN first and only closes from the normal
      //   size. Every other fullscreen surface on the web behaves this way,
      //   and closing a full-window chat on one keypress would throw a
      //   visitor out of a conversation when they meant to shrink it.
      if (e.key === 'Escape') {
        if (this._view === 'fullscreen') this._applyChatView('normal', true);
        else this.close();
      }
    });
    sendBtn.addEventListener('click', () => this._send());
    closeBtn.addEventListener('click', () => this.close());
  }

  _send() {
    const text = this._inputEl.value.trim();
    if (!text) return;
    this._inputEl.value = '';
    this._inputEl.placeholder = 'Unity is thinking...';

    // Add user message to UI immediately
    this._appendMessage('user', text);

    // Call the handler. The brain's 'response' event is what actually
    // renders the assistant message into the chat (wired in app.js via
    // brain.on('response', ...) → chatPanel.addMessage). We MUST NOT
    // also append it here — doing so produced two identical messages
    // in the chat for every user input (double-display bug).
    if (this._onSend) {
      this._onSend(text).then(() => {
        this._inputEl.placeholder = 'Talk to Unity...';
      }).catch(() => {
        this._inputEl.placeholder = 'Talk to Unity...';
      });
    }
  }

  _appendMessage(role, text) {
    const msg = document.createElement('div');
    msg.className = `chat-msg chat-msg-${role}`;

    const label = document.createElement('span');
    label.className = 'chat-msg-label';
    label.textContent = role === 'user' ? 'You' : 'Unity';

    const body = document.createElement('span');
    body.className = 'chat-msg-text';
    // Render HTML for images, escape text for everything else
    if (text.includes('<img ') || text.includes('<a ')) {
      body.innerHTML = text;
    } else {
      body.textContent = text;
    }

    msg.appendChild(label);
    msg.appendChild(body);
    this._messagesEl.appendChild(msg);
    this._messagesEl.scrollTop = this._messagesEl.scrollHeight;
  }

  _loadHistory() {
    this._messagesEl.innerHTML = '';
    const history = this._storage.getHistory();
    for (const entry of history) {
      this._appendMessage(entry.role, entry.text);
    }
  }

  toggle() {
    if (this._open) this.close();
    else this.open();
  }

  open() {
    this._open = true;
    this._loadHistory();
    this._el.classList.remove('hidden');
    setTimeout(() => this._inputEl.focus(), 100);
  }

  close() {
    this._open = false;
    this._el.classList.add('hidden');
  }

  isOpen() {
    return this._open;
  }

  /** Add a message from outside (e.g., voice result) */
  addMessage(role, text, skipSave = false) {
    // Save to storage so history persists across open/close
    // skipSave=true when the router already saved it
    if (!skipSave) {
      this._storage.saveMessage(role, text);
    }
    if (this._open) {
      this._appendMessage(role, text);
    }
  }

  /**
   * Ghost bubble for when Unity went silent on purpose. Rendered as a
   * greyed-out italic message with a reason label ("pre-K — can't speak
   * yet", "motor unstable — try rephrasing", etc.) so the user sees
   * WHY she didn't answer instead of being ghosted. Silent bubbles are
   * NOT persisted to chat history — they're session-only signals.
   */
  addSilentMessage(reason, detail, minGrade) {
    if (!this._open) return;
    const msg = document.createElement('div');
    msg.className = 'chat-msg chat-msg-silent';
    msg.style.cssText = 'opacity:0.55; font-style:italic; border-left:2px solid #666; padding-left:8px; margin:6px 0; font-size:12px; color:#9a9aa8;';

    const label = document.createElement('span');
    label.className = 'chat-msg-label';
    label.style.cssText = 'color:#ff4d9a; font-weight:600; display:block; font-size:10px; letter-spacing:0.5px; text-transform:uppercase; margin-bottom:2px;';
    const reasonLabel = reason === 'pre_kindergarten' ? 'Unity — pre-K, not speaking yet'
      : reason === 'motor_unstable' ? 'Unity — motor unstable'
      : reason === 'language_not_ready' ? 'Unity — language booting'
      : 'Unity — silent';
    label.textContent = minGrade ? `${reasonLabel} (lowest grade: ${minGrade})` : reasonLabel;

    const body = document.createElement('span');
    body.className = 'chat-msg-text';
    body.textContent = detail || 'She heard you but her motor region couldn\'t commit a stable letter sequence.';

    msg.appendChild(label);
    msg.appendChild(body);
    this._messagesEl.appendChild(msg);
    this._messagesEl.scrollTop = this._messagesEl.scrollHeight;
  }
}
