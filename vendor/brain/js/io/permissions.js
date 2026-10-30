// permissions.js — Browser permission requests for mic/camera
// Stores grant status in localStorage so we know what's available

const STORAGE_KEY = 'unity_brain_permissions';

/**
 * Request microphone and camera permissions independently.
 * If one fails, the other still gets attempted.
 * Returns { mic, camera, micStream, cameraStream }
 *
 * @param {{requestMic?: boolean, requestCamera?: boolean}} opts —
 *   skip prompts for channels the user toggled off in the setup modal.
 */
export async function requestPermissions(opts = {}) {
  const wantMic = opts.requestMic !== false;
  const wantCam = opts.requestCamera !== false;
  const result = {
    mic: false,
    camera: false,
    micStream: null,
    cameraStream: null
  };

  // Request microphone
  if (wantMic) {
    try {
      const micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      result.mic = true;
      result.micStream = micStream;
    } catch (err) {
      console.warn('Microphone permission denied or unavailable:', err.message);
    }
  }

  // Request camera — independent of mic result
  if (wantCam) {
    try {
      const cameraStream = await navigator.mediaDevices.getUserMedia({ video: true });
      result.camera = true;
      result.cameraStream = cameraStream;
    } catch (err) {
      console.warn('Camera permission denied or unavailable:', err.message);
    }
  }

  // Persist what was granted
  const granted = {
    mic: result.mic,
    camera: result.camera,
    timestamp: Date.now()
  };

  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(granted));
  } catch (err) {
    console.warn('Could not save permission state to localStorage:', err.message);
  }

  return result;
}

/**
 * Returns what localStorage RECORDS about a previous grant.
 *
 * ⛔⛔ THIS IS A HINT ABOUT THE PAST, NOT THE CURRENT PERMISSION STATE, AND THE
 * DIFFERENCE IS THE WHOLE REASON THIS FUNCTION SAT UNREAD.
 *
 * `requestPermissions` wrote here and nothing ever read it back — the store was
 * WRITE-ONLY, which is how it was found. The obvious fix, "wire the read into
 * the boot path so a returning visitor's grant is remembered", is a trap: a user
 * can revoke microphone access in browser settings at any time and this record
 * would still cheerfully say `granted`. **An instrument that reports a state it
 * cannot observe is the defect class this project keeps paying for**, and a
 * stale `granted` here would show a green light over a dead channel.
 *
 * So it is deliberately NOT the boot path's source of truth. `queryLivePermissions`
 * below is, because the Permissions API answers about NOW. This one remains for
 * the one question it can honestly answer: *has this visitor ever granted before?*
 * — which is what distinguishes a first-time prompt from a re-prompt.
 *
 * @returns {{mic:boolean, camera:boolean, timestamp:number|null}} — `timestamp`
 *   is the age of the claim and must be surfaced with it, never dropped.
 */
export function getGrantedPermissions() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      return {
        mic: parsed.mic || false,
        camera: parsed.camera || false,
        timestamp: parsed.timestamp || null
      };
    }
  } catch (err) {
    console.warn('Could not read permission state from localStorage:', err.message);
  }

  return { mic: false, camera: false, timestamp: null };
}

/**
 * The CURRENT permission state, asked of the browser rather than remembered.
 *
 * ⭐ `navigator.permissions.query` is the only source that cannot go stale: it
 * reports `granted` / `denied` / `prompt` as of right now, so a permission the
 * user revoked in settings reads as revoked instead of as a remembered yes.
 *
 * ⚠ Support is uneven — Safari has historically not implemented the `camera`
 * and `microphone` descriptors — so an unsupported query resolves to `unknown`
 * rather than to `false`. **`unknown` is not `denied`.** Reporting "no" for a
 * question the browser refused to answer would be the same lie in the other
 * direction, and the caller must be able to tell those apart.
 *
 * @returns {Promise<{mic:string, camera:string}>} each one of
 *   `granted` | `denied` | `prompt` | `unknown`
 */
export async function queryLivePermissions() {
  const out = { mic: 'unknown', camera: 'unknown' };
  const perms = (typeof navigator !== 'undefined') && navigator.permissions;
  if (!perms || typeof perms.query !== 'function') return out;
  const ask = async (name) => {
    try {
      const st = await perms.query({ name });
      return (st && st.state) || 'unknown';
    } catch {
      // A thrown query means this browser does not know the descriptor. That is
      // "cannot tell", never "denied".
      return 'unknown';
    }
  };
  out.mic = await ask('microphone');
  out.camera = await ask('camera');
  return out;
}
