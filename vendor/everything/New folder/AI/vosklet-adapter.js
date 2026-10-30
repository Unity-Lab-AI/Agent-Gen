// Vosklet Speech Recognition Adapter for Firefox

async function createVoskletRecognizer(onresult, onerror) {
  let recognizer;
  let listening = false;
  let timeoutId;

  const modelUrl = 'https://cdn.jsdelivr.net/npm/vosklet@0.2.1/models/vosk-model-small-en-us-0.15.zip';

  async function loadModelAndRecognizer() {
    try {
      const model = await Vosklet.loadModel(modelUrl);
      recognizer = new Vosklet.Recognizer({ model: model, sampleRate: 16000 });
      await recognizer.init();
    } catch (error) {
      console.error('Failed to load Vosklet model:', error);
      onerror({ error: 'Failed to load Vosklet model' });
    }
  }

  await loadModelAndRecognizer();

  function start() {
    if (listening) {
      return;
    }
    listening = true;
    listen();
  }

  function stop() {
    if (!listening) {
      return;
    }
    listening = false;
    if (timeoutId) {
      clearTimeout(timeoutId);
      timeoutId = null;
    }
    if (recognizer) {
      recognizer.stop();
    }
  }

  async function listen() {
    if (!listening) {
      return;
    }

    try {
      const result = await recognizer.listen(8000); // 8-second polling window
      if (result && result.text) {
        if (onresult) {
          // Fire onspeechstart when speech is first detected
          if (recognizer.isListening()) {
            if (typeof this.onspeechstart === 'function') {
              this.onspeechstart();
            }
          }
          onresult({ results: [[{ transcript: result.text }]] });
        }
      }
    } catch (error) {
      console.error('Vosklet listening error:', error);
      if (onerror) {
        onerror({ error: error.message });
      }
    }

    if (listening) {
      timeoutId = setTimeout(listen, 0);
    }
  }

  return {
    start: start,
    stop: stop,
    get onspeechstart() {
        return this._onspeechstart;
    },
    set onspeechstart(value) {
        this._onspeechstart = value;
    }
  };
}