import type { WSMessage, MessageTypeMap } from '@carbon/shared';

/* ─── WebSocket URL resolution ─── */

/** Get the WebSocket URL from session storage, env, or derive from window.location */
// force ws:// to wss:// when page is served over HTTPS — browsers block mixed content
function ensureSecureWs(url: string): string {
  if (window.location.protocol === 'https:' && url.startsWith('ws://')) {
    return url.replace('ws://', 'wss://');
  }
  return url;
}

export function getWsUrl(): string {
  // 1. Explicit session override (set when joining a specific server)
  const stored = sessionStorage.getItem('carbon_ws_url');
  if (stored) return ensureSecureWs(stored);
  // 2. Build-time env var
  const envUrl = import.meta.env.VITE_WS_URL as string;
  if (envUrl) return ensureSecureWs(envUrl);
  // 3. Derive from current page origin (works in production and dev)
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.hostname;
  const port = window.location.port === '5173' ? '3002' : window.location.port || '3002';
  return `${proto}//${host}:${port}`;
}

/* ─── WebSocket client ─── */

type MessageType = keyof MessageTypeMap;
type Handler<T extends MessageType> = (payload: MessageTypeMap[T], msg: WSMessage<MessageTypeMap[T]>) => void;

interface PendingRequest {
  resolve: (payload: unknown) => void;
  reject: (error: Error) => void;
  timer: ReturnType<typeof setTimeout>;
}

const REQUEST_TIMEOUT_MS = 15_000;
const RECONNECT_BASE_MS = 1_000;
const RECONNECT_MAX_MS = 30_000;
const RECONNECT_MAX_ATTEMPTS = 5;
const HEARTBEAT_INTERVAL_MS = 30_000;

let ws: WebSocket | null = null;
let seq = 0;
let reconnectAttempts = 0;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let heartbeatTimer: ReturnType<typeof setInterval> | null = null;
let serverUrl = '';
let authToken = '';

const handlers = new Map<string, Set<Handler<any>>>();
const pendingRequests = new Map<string, PendingRequest>();
const onceHandlers = new Map<string, Set<Handler<any>>>();

// ── Connection state ──

type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'reconnecting';
let connectionState: ConnectionState = 'disconnected';
const stateListeners = new Set<(state: ConnectionState) => void>();

function setState(state: ConnectionState) {
  connectionState = state;
  stateListeners.forEach(fn => fn(state));
}

export function onConnectionState(fn: (state: ConnectionState) => void): () => void {
  stateListeners.add(fn);
  fn(connectionState); // immediate callback with current state
  return () => stateListeners.delete(fn);
}

export function getConnectionState(): ConnectionState {
  return connectionState;
}

// ── Connect / Disconnect ──

export function connect(url: string, token: string) {
  // smart host swap — if browsing from localhost but url has LAN IP, use localhost (and vice versa)
  try {
    const wsUrl = new URL(url);
    const pageHost = window.location.hostname;
    if ((pageHost === 'localhost' || pageHost === '127.0.0.1') && wsUrl.hostname !== 'localhost' && wsUrl.hostname !== '127.0.0.1') {
      wsUrl.hostname = 'localhost';
      url = wsUrl.toString().replace(/\/$/, '');
    } else if (pageHost !== 'localhost' && pageHost !== '127.0.0.1' && (wsUrl.hostname === 'localhost' || wsUrl.hostname === '127.0.0.1')) {
      wsUrl.hostname = pageHost;
      url = wsUrl.toString().replace(/\/$/, '');
    }
  } catch { /* bad url, use as-is */ }

  // Already connected to this URL — don't reconnect
  if (url === serverUrl && token === authToken && ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) {
    return;
  }
  serverUrl = url;
  authToken = token;
  reconnectAttempts = 0;
  doConnect();
}

export function disconnect() {
  clearReconnect();
  clearHeartbeat();
  if (ws) {
    ws.onclose = null; // prevent reconnect
    ws.close();
    ws = null;
  }
  setState('disconnected');
}

function doConnect() {
  if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) {
    return;
  }

  setState(reconnectAttempts > 0 ? 'reconnecting' : 'connecting');

  // pass token in URL for immediate server-side auth (no race condition)
  const wsUrlWithToken = authToken ? `${serverUrl}${serverUrl.includes('?') ? '&' : '?'}token=${encodeURIComponent(authToken)}` : serverUrl;
  ws = new WebSocket(wsUrlWithToken);

  ws.onopen = () => {
    reconnectAttempts = 0;
    setState('connected');
    startHeartbeat();
  };

  ws.onmessage = (event) => {
    let msg: WSMessage;
    try {
      msg = JSON.parse(event.data);
    } catch {
      return;
    }

    // U252: respond to server pings to prevent disconnect
    if (msg.type === 'ping') {
      send('pong', { ts: (msg.payload as any)?.ts || Date.now() });
      return;
    }

    // check pending request/response pairing
    const pending = pendingRequests.get(msg.id);
    if (pending) {
      clearTimeout(pending.timer);
      pendingRequests.delete(msg.id);
      pending.resolve(msg.payload);
    }

    // fire registered handlers
    const typeHandlers = handlers.get(msg.type);
    if (typeHandlers) {
      typeHandlers.forEach(fn => fn(msg.payload, msg));
    }

    // fire once handlers
    const onceSet = onceHandlers.get(msg.type);
    if (onceSet) {
      onceSet.forEach(fn => fn(msg.payload, msg));
      onceHandlers.delete(msg.type);
    }
  };

  ws.onclose = () => {
    ws = null;
    clearHeartbeat();
    scheduleReconnect();
  };

  ws.onerror = () => {
    // onclose will fire after onerror
  };
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  if (reconnectAttempts >= RECONNECT_MAX_ATTEMPTS) {
    console.error(`WebSocket: gave up after ${RECONNECT_MAX_ATTEMPTS} attempts to ${serverUrl}`);
    setState('disconnected');
    // clear stale cached URL so next server select gets a fresh one
    sessionStorage.removeItem('carbon_ws_url');
    return;
  }
  setState('reconnecting');

  const delay = Math.min(
    RECONNECT_BASE_MS * Math.pow(2, reconnectAttempts),
    RECONNECT_MAX_MS,
  );
  reconnectAttempts++;

  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    doConnect();
  }, delay);
}

function clearReconnect() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
}

function startHeartbeat() {
  clearHeartbeat();
  heartbeatTimer = setInterval(() => {
    if (ws?.readyState === WebSocket.OPEN) {
      send('ping', { ts: Date.now() }); // U252: use send() for proper WSMessage format
    }
  }, HEARTBEAT_INTERVAL_MS);
}

function clearHeartbeat() {
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer);
    heartbeatTimer = null;
  }
}

// ── Send ──

function nextId(): string {
  return crypto.randomUUID();
}

export function isConnected(): boolean {
  return !!ws && ws.readyState === WebSocket.OPEN;
}

export function send<T extends MessageType>(type: T, payload: MessageTypeMap[T]) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;

  const msg: WSMessage<MessageTypeMap[T]> = {
    id: nextId(),
    type,
    payload,
    ts: Date.now(),
    seq: seq++,
    version: 1,
  };

  ws.send(JSON.stringify(msg));
}

/** Send and wait for a response with the same id */
export function request<T extends MessageType>(
  type: T,
  payload: MessageTypeMap[T],
  timeoutMs = REQUEST_TIMEOUT_MS,
): Promise<unknown> {
  return new Promise((resolve, reject) => {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      reject(new Error('WebSocket not connected'));
      return;
    }

    const id = nextId();

    const timer = setTimeout(() => {
      pendingRequests.delete(id);
      reject(new Error(`Request ${type} timed out after ${timeoutMs}ms`));
    }, timeoutMs);

    pendingRequests.set(id, { resolve, reject, timer });

    const msg: WSMessage<MessageTypeMap[T]> = {
      id,
      type,
      payload,
      ts: Date.now(),
      seq: seq++,
      version: 1,
    };

    ws.send(JSON.stringify(msg));
  });
}

// ── Subscribe ──

export function on<T extends MessageType>(
  type: T,
  handler: Handler<T>,
): () => void {
  if (!handlers.has(type)) handlers.set(type, new Set());
  handlers.get(type)!.add(handler);
  return () => handlers.get(type)?.delete(handler);
}

export function once<T extends MessageType>(
  type: T,
  handler: Handler<T>,
) {
  if (!onceHandlers.has(type)) onceHandlers.set(type, new Set());
  onceHandlers.get(type)!.add(handler);
  return () => onceHandlers.get(type)?.delete(handler);
}

export function off<T extends MessageType>(type: T, handler: Handler<T>) {
  handlers.get(type)?.delete(handler);
}
