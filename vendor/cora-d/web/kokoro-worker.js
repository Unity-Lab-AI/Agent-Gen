// ═══════════════════════════════════════════════════════════════
// C.O.R.A KOKORO TTS WEB WORKER
// Neural TTS running in browser using Kokoro-82M
// Voice: af_bella (CORA's voice from desktop app)
// ═══════════════════════════════════════════════════════════════

let tts = null;
let isInitialized = false;
let isInitializing = false;
let isGenerating = false;  // Prevent concurrent generation
let generateQueue = [];    // Queue for pending requests

const MODEL_ID = 'onnx-community/Kokoro-82M-v1.0-ONNX';
const DEFAULT_VOICE = 'af_bella';  // CORA's voice

let generateCount = 0;  // Track number of generate calls

self.onmessage = async function(e) {
    const { type, id, data } = e.data;

    console.log(`[WORKER] Received message: type=${type}, id=${id}`);

    switch (type) {
        case 'init':
            await handleInit(id, data);
            break;
        case 'generate':
            generateCount++;
            console.log(`[WORKER] Generate call #${generateCount}, id=${id}`);
            await handleGenerate(id, data);
            break;
        case 'checkStatus':
            self.postMessage({
                type: 'status',
                id,
                data: { initialized: isInitialized, initializing: isInitializing }
            });
            break;
        default:
            console.warn(`[WORKER] Unknown message type: ${type}`);
    }
};

async function handleInit(id, data) {
    if (isInitialized) {
        self.postMessage({ type: 'initComplete', id, data: { success: true, cached: true } });
        return;
    }

    if (isInitializing) {
        self.postMessage({ type: 'error', id, error: 'Already initializing' });
        return;
    }

    isInitializing = true;

    try {
        self.postMessage({ type: 'progress', id, data: { message: 'Loading Kokoro library...', progress: 10 } });

        const module = await import('https://cdn.jsdelivr.net/npm/kokoro-js@1.2.0/+esm');
        const KokoroTTS = module.KokoroTTS;

        self.postMessage({ type: 'progress', id, data: { message: 'Loading neural voice model...', progress: 20 } });

        tts = await KokoroTTS.from_pretrained(MODEL_ID, {
            dtype: 'q8',
            device: 'wasm',
            progress_callback: (progress) => {
                if (progress.status === 'progress') {
                    const pct = progress.progress || 0;
                    self.postMessage({
                        type: 'progress',
                        id,
                        data: { message: `Loading model... ${Math.round(pct)}%`, progress: 20 + (pct * 0.7) }
                    });
                }
            }
        });

        isInitialized = true;
        isInitializing = false;

        self.postMessage({ type: 'progress', id, data: { message: 'Kokoro ready!', progress: 100 } });
        self.postMessage({ type: 'initComplete', id, data: { success: true } });

    } catch (error) {
        isInitializing = false;
        self.postMessage({ type: 'error', id, error: error.message });
    }
}

async function handleGenerate(id, data) {
    console.log(`[WORKER] handleGenerate: id=${id}, isInitialized=${isInitialized}, hasTTS=${!!tts}, isGenerating=${isGenerating}`);

    if (!isInitialized || !tts) {
        console.error(`[WORKER] TTS not ready: initialized=${isInitialized}, tts=${!!tts}`);
        self.postMessage({ type: 'error', id, error: 'TTS not initialized' });
        return;
    }

    // If already generating, queue this request
    if (isGenerating) {
        console.log(`[WORKER] Already generating, queuing id=${id}`);
        generateQueue.push({ id, data });
        return;
    }

    isGenerating = true;
    await doGenerate(id, data);
    isGenerating = false;

    // Process next in queue if any
    if (generateQueue.length > 0) {
        const next = generateQueue.shift();
        console.log(`[WORKER] Processing queued request id=${next.id}`);
        handleGenerate(next.id, next.data);
    }
}

// Split long text into chunks at sentence boundaries
function splitTextIntoChunks(text, maxChars = 400) {
    if (text.length <= maxChars) return [text];

    const chunks = [];
    let remaining = text;

    while (remaining.length > 0) {
        if (remaining.length <= maxChars) {
            chunks.push(remaining);
            break;
        }

        // Find a good break point (end of sentence or clause)
        let breakPoint = -1;
        const breakChars = ['. ', '! ', '? ', ', ', '; ', ': ', ' - '];

        for (const bc of breakChars) {
            const lastIdx = remaining.lastIndexOf(bc, maxChars);
            if (lastIdx > breakPoint && lastIdx > maxChars * 0.5) {
                breakPoint = lastIdx + bc.length;
            }
        }

        // If no good break point, break at space
        if (breakPoint === -1) {
            breakPoint = remaining.lastIndexOf(' ', maxChars);
        }

        // If still no break point, force break
        if (breakPoint === -1 || breakPoint < maxChars * 0.3) {
            breakPoint = maxChars;
        }

        chunks.push(remaining.substring(0, breakPoint).trim());
        remaining = remaining.substring(breakPoint).trim();
    }

    console.log(`[WORKER] Split text into ${chunks.length} chunks: ${chunks.map(c => c.length).join(', ')} chars`);
    return chunks;
}

// Concatenate multiple Float32Arrays
function concatenateAudio(audioArrays, sampleRate) {
    const totalLength = audioArrays.reduce((sum, arr) => sum + arr.length, 0);
    const result = new Float32Array(totalLength);
    let offset = 0;
    for (const arr of audioArrays) {
        result.set(arr, offset);
        offset += arr.length;
    }
    return result;
}

async function doGenerate(id, data) {
    const { text, voice, speed } = data;
    console.log(`[WORKER] Generating: text="${text?.substring(0, 50)}...", voice=${voice}, speed=${speed}, length=${text?.length}`);

    try {
        self.postMessage({ type: 'generating', id });

        const startTime = Date.now();

        // Split long text into chunks to avoid kokoro-js truncation
        const chunks = splitTextIntoChunks(text, 400);
        const audioChunks = [];
        let sampleRate = 24000;

        for (let i = 0; i < chunks.length; i++) {
            const chunk = chunks[i];
            console.log(`[WORKER] Generating chunk ${i + 1}/${chunks.length}: ${chunk.length} chars`);

            // NO TIMEOUT - let Kokoro take as long as needed
            const audio = await tts.generate(chunk, {
                voice: voice || DEFAULT_VOICE,
                speed: speed || 1.0
            });

            if (audio && audio.audio) {
                audioChunks.push(new Float32Array(audio.audio));
                sampleRate = audio.sampling_rate || 24000;
                console.log(`[WORKER] Chunk ${i + 1} done: ${audio.audio.length} samples`);
            } else {
                console.warn(`[WORKER] Chunk ${i + 1} produced no audio`);
            }
        }

        const genTime = Date.now() - startTime;
        console.log(`[WORKER] All chunks complete in ${genTime}ms, ${audioChunks.length} audio segments`);

        if (audioChunks.length > 0) {
            // Concatenate all audio chunks
            const fullAudio = concatenateAudio(audioChunks, sampleRate);
            const audioBuffer = fullAudio.buffer.slice(0);
            const duration = fullAudio.length / sampleRate;

            console.log(`[WORKER] Audio: ${audioBuffer.byteLength} bytes, ${sampleRate}Hz, ${duration.toFixed(2)}s`);

            self.postMessage(
                {
                    type: 'audioReady',
                    id,
                    data: {
                        audio: audioBuffer,
                        sampleRate: sampleRate
                    }
                },
                [audioBuffer]
            );
            console.log(`[WORKER] Audio sent to main thread for id=${id}`);
        } else {
            console.error(`[WORKER] No audio generated for id=${id}`);
            self.postMessage({ type: 'error', id, error: 'No audio generated' });
        }

    } catch (error) {
        console.error(`[WORKER] Generation error for id=${id}:`, error);
        self.postMessage({ type: 'error', id, error: error.message });
    }
}
