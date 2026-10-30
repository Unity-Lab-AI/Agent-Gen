// ═══════════════════════════════════════════════════════════════
// WEBSOCKET SERVER - Client connections and message routing
// ═══════════════════════════════════════════════════════════════
// Version: 0.1.0 | Unity AI Lab
// Creators: Hackall360, Sponge, GFourteen, Tolerable
// ═══════════════════════════════════════════════════════════════

import { WebSocketServer, WebSocket } from 'ws';
import { IncomingMessage } from 'http';
import { v4 as uuid } from 'uuid';
import { validateToken } from '../db/supabase.js';
import { validateBotToken } from '../ai/bot-auth.js';
// WSMessage type defined inline to avoid cross-project import issues
// matches shared/src/protocol/messages.ts exactly
interface WSMessage {
  id: string;
  type: string;
  payload: any;
  ts: number;
  seq: number;
  version: 1;
}

export interface PlayerConnection {
  id: string;
  ws: WebSocket;
  userId: string;       // supabase auth user id
  characterId?: string; // active character
  authenticated: boolean;
  _chatTimes?: number[]; // rate limiting timestamps
  _lastChatMsg?: string; // last chat message (duplicate detection)
  _lastChatTime?: number; // last chat timestamp
  _isBotConn?: boolean;  // true if this is a bot connection
  _msgTimes?: number[];  // global rate limiting timestamps
  _seq?: number;         // per-connection message sequence counter
  location?: { x: number; y: number; z: number }; // player world position for proximity
}

type MessageHandler = (conn: PlayerConnection, msg: WSMessage) => void;

export class GameWSServer {
  private wss: WebSocketServer | null = null;
  private connections: Map<string, PlayerConnection> = new Map();
  private handlers: Map<string, MessageHandler> = new Map();
  private disconnectHandler: ((conn: PlayerConnection) => void) | null = null;
  // Observer connections: when a message is sent to connId X, also mirror it to observer connIds
  private observers: Map<string, Set<string>> = new Map(); // primaryConnId → Set<observerConnId>

  start(port: number) {
    this.wss = new WebSocketServer({ host: '0.0.0.0', port, maxPayload: 64 * 1024 });

    // handle server-level errors (port in use, permission denied, etc)
    this.wss.on('error', (err: Error) => {
      if ((err as any).code === 'EADDRINUSE') {
        console.error(`PORT ${port} ALREADY IN USE. Kill the other process or use a different port.`);
        console.error('Try: npx kill-port ' + port);
      } else {
        console.error(`WebSocket server error: ${err.message}`);
      }
    });

    this.wss.on('connection', async (ws: WebSocket, req: IncomingMessage) => {
      // max concurrent connections
      if (this.connections.size >= 2010) { // max_players + buffer
        ws.close(4009, 'Server full');
        return;
      }

      // auth via query param OR first message
      const url = new URL(req.url || '', `http://localhost:${port}`);
      const urlToken = url.searchParams.get('token');

      const conn: PlayerConnection = {
        id: uuid(),
        ws,
        userId: '',
        authenticated: false,
      };
      this.connections.set(conn.id, conn);

      // queue messages received before auth completes — replay after auth
      const pendingMessages: Buffer[] = [];

      // Register message handler FIRST — before async auth.
      // During async validateBotToken(), the bot may send select_character.
      // Without this handler registered first, that message is lost forever.
      ws.on('message', async (raw: Buffer) => {
        // queue messages from unauthenticated connections — replay after auth
        if (!conn.authenticated) {
          if (raw.length < 64 * 1024) pendingMessages.push(raw);
          return;
        }

        // reject oversized messages before parsing
        if (raw.length > 64 * 1024) {
          this.send(conn, 'error', { code: 'MSG_TOO_LARGE', message: 'Message exceeds 64KB limit' });
          return;
        }

        // global rate limit: 30 msgs/sec per connection
        const now = Date.now();
        if (!conn._msgTimes) conn._msgTimes = [];
        conn._msgTimes = conn._msgTimes.filter(t => now - t < 1000);
        if (conn._msgTimes.length >= 30) {
          if (conn._msgTimes.length >= 60) {
            ws.close(4008, 'Rate limit exceeded');
            return;
          }
          return;
        }
        conn._msgTimes.push(now);

        try {
          const msg: WSMessage = JSON.parse(raw.toString());
          const handler = this.handlers.get(msg.type);
          if (handler) {
            try {
              await handler(conn, msg);
            } catch (err: any) {
              console.error(`Handler error [${msg.type}]: ${err.message}\n${err.stack}`);
              this.send(conn, 'error', { code: 'HANDLER_ERROR', message: err.message });
            }
          } else {
            this.send(conn, 'error', { code: 'UNKNOWN_TYPE', message: `Unknown message type: ${msg.type}` });
          }
        } catch {
          this.send(conn, 'error', { code: 'PARSE_ERROR', message: 'Invalid message format' });
        }
      });

      // if token in URL, auth immediately (legacy/fallback)
      if (urlToken) {
        // try bot token first (bot_xxxx format)
        if (urlToken.startsWith('bot_')) {
          const botInfo = await validateBotToken(urlToken);
          if (!botInfo) {
            ws.close(4003, 'Invalid bot token');
            this.connections.delete(conn.id);
            return;
          }
          conn.userId = botInfo.ownerPlayerId;
          conn.characterId = botInfo.botCharacterId;
          conn.authenticated = true;
          conn._isBotConn = true; // U350: flag for bot-specific rate limiting
          console.log(`Bot connected via token: bot=${botInfo.botCharacterId} owner=${botInfo.ownerPlayerId} (conn ${conn.id})`);
          this.send(conn, 'auth_result', { success: true, character_id: botInfo.botCharacterId });
        } else {
          const user = await validateToken(urlToken);
          if (!user) {
            ws.close(4003, 'Invalid auth token');
            this.connections.delete(conn.id);
            return;
          }
          conn.userId = user.id;
          conn.authenticated = true;
          console.log(`Player connected via URL token: ${user.id} (conn ${conn.id})`);
          this.send(conn, 'auth_result', { success: true, character_id: null });
        }
        // replay any messages that arrived during async token validation
        if (pendingMessages.length > 0) {
          console.log(`Replaying ${pendingMessages.length} queued messages for ${conn.userId}`);
          for (const pending of pendingMessages) {
            ws.emit('message', pending);
          }
          pendingMessages.length = 0;
        }
      } else {
        // no URL token — wait for auth message (R71 flow)
        console.log(`Player connected, awaiting auth message (conn ${conn.id})`);
        // set a 10-second timeout — if no auth message, disconnect
        const authTimeout = setTimeout(() => {
          if (!conn.authenticated) {
            ws.close(4001, 'Auth timeout — no token provided');
            this.connections.delete(conn.id);
          }
        }, 10000);
        // listen for auth message
        const origOnMessage = ws.onmessage;
        ws.onmessage = null; // temporarily override
        const authHandler = async (raw: any) => {
          try {
            const msg = JSON.parse(raw.data || raw.toString());
            if (msg.type === 'auth' && msg.payload?.token) {
              clearTimeout(authTimeout);
              const authToken = msg.payload.token;
              // bot tokens start with bot_ — validate differently
              if (authToken.startsWith('bot_')) {
                const botInfo = await validateBotToken(authToken);
                if (!botInfo) {
                  this.send(conn, 'auth_result', { success: false, error: 'Invalid bot token' });
                  ws.close(4003, 'Invalid bot token');
                  this.connections.delete(conn.id);
                  return;
                }
                conn.userId = botInfo.ownerPlayerId;
                conn.characterId = botInfo.botCharacterId;
                conn.authenticated = true;
                conn._isBotConn = true; // U350: flag for bot-specific rate limiting
                console.log(`Bot authenticated via message: bot=${botInfo.botCharacterId} owner=${botInfo.ownerPlayerId} (conn ${conn.id})`);
                this.send(conn, 'auth_result', { success: true, character_id: botInfo.botCharacterId });
              } else {
                const user = await validateToken(authToken);
                if (!user) {
                  this.send(conn, 'auth_result', { success: false, error: 'Invalid token' });
                  ws.close(4003, 'Invalid auth token');
                  this.connections.delete(conn.id);
                  return;
                }
                conn.userId = user.id;
                conn.authenticated = true;
                console.log(`Player authenticated via message: ${user.id} (conn ${conn.id})`);
                this.send(conn, 'auth_result', { success: true, character_id: null });
              }
              ws.removeEventListener('message', authHandler);
              // replay messages that arrived during auth
              if (pendingMessages.length > 0) {
                console.log(`Replaying ${pendingMessages.length} queued messages for ${conn.userId}`);
                for (const pending of pendingMessages) {
                  ws.emit('message', pending);
                }
                pendingMessages.length = 0;
              }
            }
          } catch { /* bad json, ignore */ }
        };
        ws.addEventListener('message', authHandler);
      }

      ws.on('close', () => {
        if (this.disconnectHandler) {
          try { this.disconnectHandler(conn); } catch (err: any) {
            console.error(`Disconnect handler error: ${err.message}`);
          }
        }
        this.connections.delete(conn.id);
        console.log(`Player disconnected: ${conn.userId || conn.id}`);
      });

      // U224: pong received — connection is alive
      ws.on('pong', () => {
        (conn as any)._missedPong = false;
        (conn as any)._dead = false;
      });

      ws.on('error', (err) => {
        console.error(`WebSocket error for ${conn.userId || conn.id}:`, err.message);
      });
    });

    // U224: heartbeat ping/pong — keep connections alive, kill dead ones
    const heartbeatInterval = setInterval(() => {
      for (const conn of this.connections.values()) {
        if ((conn as any)._dead) {
          // missed 2 pongs — kill it
          conn.ws.terminate();
          continue;
        }
        if ((conn as any)._missedPong) {
          (conn as any)._dead = true; // one more miss and we kill it
        }
        (conn as any)._missedPong = true;
        if (conn.ws.readyState === WebSocket.OPEN) {
          conn.ws.ping();
        }
      }
    }, 30000); // ping every 30 seconds

    this.wss.on('close', () => clearInterval(heartbeatInterval));

    console.log(`WebSocket server listening on port ${port}`);
  }

  onMessage(type: string, handler: MessageHandler) {
    this.handlers.set(type, handler);
  }

  onDisconnect(handler: (conn: PlayerConnection) => void) {
    this.disconnectHandler = handler;
  }

  // Register a connection as an observer of another connection
  addObserver(primaryConnId: string, observerConnId: string) {
    if (!this.observers.has(primaryConnId)) this.observers.set(primaryConnId, new Set());
    this.observers.get(primaryConnId)!.add(observerConnId);
  }

  removeObserver(observerConnId: string) {
    for (const [, observers] of this.observers) {
      observers.delete(observerConnId);
    }
  }

  send(conn: PlayerConnection, type: string, payload: unknown) {
    if (conn.ws.readyState !== WebSocket.OPEN) return;

    const msg: WSMessage = {
      id: uuid(),
      type,
      payload,
      ts: Date.now(),
      seq: conn._seq = (conn._seq || 0) + 1,
      version: 1,
    };

    const raw = JSON.stringify(msg);
    conn.ws.send(raw);

    // mirror to observers (Watch Bot windows)
    const observerIds = this.observers.get(conn.id);
    if (observerIds) {
      for (const obsId of observerIds) {
        const obsConn = this.connections.get(obsId);
        if (obsConn && obsConn.ws.readyState === WebSocket.OPEN) {
          obsConn.ws.send(raw);
        } else {
          observerIds.delete(obsId); // clean up dead observers
        }
      }
    }
  }

  // send to all connected, authenticated players
  broadcast(type: string, payload: unknown) {
    for (const conn of this.connections.values()) {
      if (conn.authenticated) {
        this.send(conn, type, payload);
      }
    }
  }

  // send to players within a coordinate range (for proximity)
  sendToNearby(type: string, payload: unknown, center: { x: number; y: number; z: number }, radius: number) {
    for (const conn of this.connections.values()) {
      if (!conn.authenticated || !conn.location) continue;
      const dx = conn.location.x - center.x;
      const dy = conn.location.y - center.y;
      const dz = ((conn.location as any).z || 0) - ((center as any).z || 0);
      if (Math.sqrt(dx * dx + dy * dy + dz * dz) <= radius) {
        this.send(conn, type, payload);
      }
    }
  }

  updateConnectionLocation(connId: string, location: { x: number; y: number; z: number }) {
    const conn = this.connections.get(connId);
    if (conn) conn.location = location;
  }

  getConnectionCount(): number {
    return this.connections.size;
  }

  getConnectionByUserId(userId: string): PlayerConnection | undefined {
    for (const conn of this.connections.values()) {
      if (conn.userId === userId) return conn;
    }
    return undefined;
  }

  getConnectionById(connId: string): PlayerConnection | undefined {
    return this.connections.get(connId);
  }

  findConnection(predicate: (conn: PlayerConnection) => boolean): PlayerConnection | undefined {
    for (const conn of this.connections.values()) {
      if (predicate(conn)) return conn;
    }
    return undefined;
  }

  stop() {
    this.wss?.close();
  }
}
