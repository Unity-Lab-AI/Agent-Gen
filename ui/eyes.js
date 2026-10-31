// Her eyes on the operator's side: webcam and screen share. Nothing is streamed; one still of each live source is
// taken at the moment the operator says or types something and goes with that message.
export function createEyes({ preview, onChange = () => {} }) {
  const live = { camera: null, screen: null };
  const vids = {};

  function videoFor(source) {
    if (!vids[source]) {
      const v = document.createElement('video');
      v.muted = true; v.playsInline = true; v.className = `eye-${source}`; v.title = source;
      preview.appendChild(v);
      vids[source] = v;
    }
    return vids[source];
  }

  async function start(source) {
    try {
      const stream = source === 'screen'
        ? await navigator.mediaDevices.getDisplayMedia({ video: { frameRate: 5 }, audio: false })
        : await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 }, audio: false });
      live[source] = stream;
      const v = videoFor(source);
      v.srcObject = stream; v.style.display = 'block';
      await v.play().catch(() => {});
      // the operator can end a screen share from the OS bar too
      stream.getVideoTracks()[0].addEventListener('ended', () => stop(source));
      onChange(source, true);
      return { ok: true };
    } catch (e) {
      onChange(source, false, String(e.message || e));
      return { ok: false, reason: `${source}: ${e.message || e}` };
    }
  }

  function stop(source) {
    live[source]?.getTracks().forEach(t => t.stop());
    live[source] = null;
    if (vids[source]) { vids[source].srcObject = null; vids[source].style.display = 'none'; }
    onChange(source, false);
  }

  const toggle = source => live[source] ? (stop(source), { ok: true, on: false }) : start(source).then(r => ({ ...r, on: r.ok }));

  /** One JPEG per live source, longest side capped (the vision model sees 1024 fine, more only costs time). */
  function grab(maxSide = 1024) {
    const frames = [];
    for (const source of ['camera', 'screen']) {
      const v = vids[source];
      if (!live[source] || !v?.videoWidth) continue;
      const k = Math.min(1, maxSide / Math.max(v.videoWidth, v.videoHeight));
      const c = document.createElement('canvas');
      c.width = Math.round(v.videoWidth * k); c.height = Math.round(v.videoHeight * k);
      c.getContext('2d').drawImage(v, 0, 0, c.width, c.height);
      frames.push({ source, b64: c.toDataURL('image/jpeg', 0.85).split(',')[1] });
    }
    return frames;
  }

  return { toggle, grab, isOn: s => !!live[s] };
}
