(() => {
    if (typeof window !== 'undefined') {
        window.addEventListener('error', (event) => {
            if (event?.message) {
                console.error('Talk to Unity runtime error:', event.message, event.error?.stack || '');
            }
        });
    }

    const landingSection = document.getElementById('landing');
    const appRoot = document.getElementById('app-root');
    const heroStage = document.getElementById('hero-stage');
    const heroImage = document.getElementById('hero-image');
    const muteIndicator = document.getElementById('mute-indicator');
    const indicatorText = muteIndicator?.querySelector('.indicator-text') ?? null;
    const aiCircle = document.querySelector('[data-role="ai"]');
    const userCircle = document.querySelector('[data-role="user"]');
    const dependencyLight = document.querySelector('[data-role="dependency-light"]');
    const dependencySummary = document.getElementById('dependency-summary');
    const dependencyList = document.getElementById('dependency-list');
    const launchButton = document.getElementById('launch-app');
    const recheckButton = document.getElementById('recheck-dependencies');
    const statusMessage = document.getElementById('status-message');
    const assetBaseOverride = typeof window !== 'undefined' ? window.__talkToUnityAssetBase : '';
    const assetVersion = typeof window !== 'undefined' ? window.__talkToUnityAssetVersion : '';

    if (heroImage) {
        heroImage.setAttribute('crossorigin', 'anonymous');
        heroImage.decoding = 'async';
    }

    const bodyElement = document.body;
    if (bodyElement) {
        bodyElement.classList.remove('no-js');
        bodyElement.classList.add('js-enabled');
        if (!bodyElement.dataset.appState) {
            bodyElement.dataset.appState = 'landing';
        }
    }

    let currentImageModel = 'flux';
    let chatHistory = [];
    let systemPrompt = '';
    let recognition = null;
    let isMuted = true;
    let hasMicPermission = false;
    let currentHeroUrl = '';
    let pendingHeroUrl = '';
    let currentTheme = 'dark';
    let recognitionRestartTimeout = null;
    let appStarted = false;
    let allowLaunchOverride = false;
    let defaultLaunchLabel = '';
    let appShellReady = false;
    let systemPromptLoaded = false;
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const synth = typeof window !== 'undefined' ? window.speechSynthesis : undefined;
    let compatibilityBanner = null;
    let dependencyState = { results: [], allMet: false, missing: [] };
    let unmuteInProgress = false;

    const LOOPBACK_HOST_PATTERN = /^(?:localhost|127(?:\.\d{1,3}){3}|::1|\[::1\])$/;
    const UNITY_ALLOWED_HOST_SUFFIXES = ['unityailab.com', 'unityailab.online'];

    const dependencyChecks = [
        {
            id: 'secure-context',
            label: 'Secure connection (HTTPS or localhost)',
            friendlyName: 'secure connection light',
            check: () => Boolean(window.isSecureContext) || LOOPBACK_HOST_PATTERN.test(window.location.hostname)
        },
        {
            id: 'speech-recognition',
            label: 'Web Speech Recognition API',
            friendlyName: 'speech listening light',
            check: () => Boolean(SpeechRecognition)
        },
        {
            id: 'speech-synthesis',
            label: 'Speech synthesis voices',
            friendlyName: 'talk-back voice light',
            check: () => typeof synth !== 'undefined' && typeof synth.speak === 'function'
        },
        {
            id: 'microphone',
            label: 'Microphone access',
            friendlyName: 'microphone light',
            check: () => Boolean(navigator.mediaDevices && navigator.mediaDevices.getUserMedia)
        }
    ];

    function formatDependencyList(items) {
        const labels = items
            .map((item) => item.friendlyName ?? item.label ?? item.id)
            .filter(Boolean);

        if (labels.length === 0) {
            return '';
        }

        if (labels.length === 1) {
            return labels[0];
        }

        const head = labels.slice(0, -1).join(', ');
        const tail = labels[labels.length - 1];
        return `${head} and ${tail}`;
    }

    function setStatusMessage(message, tone = 'info') {
        if (!statusMessage) {
            return;
        }

        statusMessage.textContent = message;
        if (message) {
            statusMessage.dataset.tone = tone;
        } else {
            delete statusMessage.dataset.tone;
        }
    }

    function updateLaunchButtonState({ allMet, missing }) {
        if (!launchButton) {
            return;
        }

        launchButton.disabled = false;
        launchButton.setAttribute('aria-disabled', 'false');
        launchButton.dataset.state = allMet ? 'ready' : 'warn';

        if (missing.length > 0) {
            const summary = formatDependencyList(missing);
            launchButton.title = `Talk to Unity with limited support: ${summary}`;
        } else {
            launchButton.removeAttribute('title');
        }
    }

    function ensureCompatibilityBanner() {
        if (compatibilityBanner) {
            return compatibilityBanner;
        }

        const banner = document.createElement('div');
        banner.className = 'compatibility-notice';
        banner.setAttribute('role', 'status');
        banner.setAttribute('aria-live', 'polite');

        const statusBanner = appRoot?.querySelector('.status-banner');
        if (statusBanner) {
            statusBanner.append(banner);
        } else if (appRoot) {
            appRoot.prepend(banner);
        }

        compatibilityBanner = banner;
        return compatibilityBanner;
    }

    function showRecheckInProgress() {
        allowLaunchOverride = false;
        setLaunchButtonState(false);
        if (launchButton) {
            launchButton.dataset.state = 'pending';
        }

        if (dependencyLight) {
            dependencyLight.dataset.state = 'pending';
            dependencyLight.setAttribute('aria-label', 'Re-checking requirements');
        }

        if (dependencySummary) {
            dependencySummary.textContent = 'Re-checking your setup…';
        }

        if (dependencyList) {
            dependencyList.querySelectorAll('.dependency-item').forEach((item) => {
                item.dataset.state = 'pending';
                const statusElement = item.querySelector('.dependency-status');
                if (statusElement) {
                    statusElement.textContent = 'Checking…';
                }
            });
        }

        setStatusMessage('Running the readiness scan again…', 'info');
    }

    if (heroStage && !heroStage.dataset.state) {
        heroStage.dataset.state = 'empty';
    }

    const currentScript = document.currentScript;
    const directoryUrl = (() => {
        const fromOverride = typeof assetBaseOverride === 'string' && assetBaseOverride ? assetBaseOverride : null;
        if (fromOverride) {
            return fromOverride.endsWith('/') ? fromOverride : `${fromOverride}/`;
        }

        if (currentScript?.src) {
            try {
                return new URL('./', currentScript.src).toString();
            } catch (error) {
                console.error('Failed to derive directory from script src:', error);
            }
        }

        const href = window.location.href;
        const pathname = window.location.pathname || '';
        const lastSegment = pathname.substring(pathname.lastIndexOf('/') + 1);

        if (href.endsWith('/')) {
            return href;
        }

        if (lastSegment && lastSegment.includes('.')) {
            return href.substring(0, href.lastIndexOf('/') + 1);
        }

        return `${href}/`;
    })();

    function resolveAssetPath(relativePath) {
        try {
            const url = new URL(relativePath, directoryUrl);
            if (assetVersion) {
                try {
                    const params = url.searchParams;
                    if (!params.has('v')) {
                        params.append('v', assetVersion);
                    }
                    return url.toString();
                } catch (paramError) {
                    console.warn('Falling back to manual cache busting for asset:', relativePath, paramError);
                    const separator = url.search ? '&' : '?';
                    return `${url.toString()}${separator}v=${assetVersion}`;
                }
            }

            return url.toString();
        } catch (error) {
            console.error('Failed to resolve asset path:', error);
            return relativePath;
        }
    }

    const shouldAutoStartExperience = !launchButton && !landingSection;

    document.addEventListener('DOMContentLoaded', () => {
        evaluateDependencies();

        if (shouldAutoStartExperience) {
            void startApplication();
        } else {
            void startApplication({ auto: true });
        }

        launchButton?.addEventListener('click', () => {
            const { allMet } = evaluateDependencies({ announce: true });
            if (!allMet && !allowLaunchOverride) {
                allowLaunchOverride = true;
                setLaunchButtonState(false);

                if (statusMessage) {
                    const advisory =
                        'Some requirements are still missing. Select “Talk to Unity (limited mode)” to continue with reduced functionality.';
                    statusMessage.textContent = statusMessage.textContent
                        ? `${statusMessage.textContent} ${advisory}`
                        : advisory;
                }
                return;
            }

            void startApplication();
        });

        recheckButton?.addEventListener('click', () => {
            showRecheckInProgress();
            evaluateDependencies({ announce: true });
        });
    });

    window.addEventListener('focus', () => {
        if (!appStarted) {
            evaluateDependencies();
        }
    });

    function setLaunchButtonState(allMet) {
        if (!launchButton) {
            return;
        }

        if (!defaultLaunchLabel) {
            defaultLaunchLabel = launchButton.textContent?.trim() ?? 'Talk to Unity';
        }

        launchButton.disabled = false;
        launchButton.setAttribute('aria-disabled', 'false');

        if (allMet) {
            allowLaunchOverride = false;
            launchButton.textContent = defaultLaunchLabel;
            launchButton.dataset.launchOverride = 'clear';
            return;
        }

        launchButton.dataset.launchOverride = allowLaunchOverride ? 'ready' : 'required';
        launchButton.textContent = allowLaunchOverride ? 'Talk to Unity (limited mode)' : defaultLaunchLabel;
    }

    function evaluateDependencies({ announce = false } = {}) {
        const results = dependencyChecks.map((descriptor) => {
            let met = false;
            try {
                met = Boolean(descriptor.check());
            } catch (error) {
                console.error(`Dependency check failed for ${descriptor.id}:`, error);
            }

            return {
                ...descriptor,
                met
            };
        });

        const missing = results.filter((result) => !result.met);
        const allMet = missing.length === 0;

        dependencyState = { results, allMet, missing };

        updateDependencyUI(results, allMet, { announce, missing });
        updateLaunchButtonState({ allMet, missing });

        setLaunchButtonState(allMet);

        if (announce) {
            if (allMet) {
                setStatusMessage('All systems look good. Launching Talk to Unity…', 'success');
            } else {
                const summary = formatDependencyList(missing);
                const message = summary
                    ? `Starting Talk to Unity in compatibility mode. Some features may be limited: ${summary}.`
                    : 'Starting Talk to Unity in compatibility mode. Some browser features may be limited.';
                setStatusMessage(message, 'warning');
                speak(message);
            }
        } else if (allMet && statusMessage?.textContent) {
            setStatusMessage('');
        }

        return { results, allMet, missing };
    }

    function updateDependencyUI(results, allMet, { announce = false, missing = [] } = {}) {
        if (dependencyList) {
            results.forEach((result) => {
                const item = dependencyList.querySelector(`[data-dependency="${result.id}"]`);
                if (!item) {
                    return;
                }

                item.dataset.state = result.met ? 'pass' : 'warn';
                const statusElement = item.querySelector('.dependency-status');
                if (statusElement) {
                    statusElement.textContent = result.met ? 'Ready' : 'Check settings';
                }
            });
        }

        if (dependencyLight) {
            dependencyLight.dataset.state = allMet ? 'pass' : 'warn';
            const summary = formatDependencyList(missing);
            dependencyLight.setAttribute(
                'aria-label',
                allMet
                    ? 'All dependencies satisfied'
                    : summary
                    ? `Compatibility mode enabled because ${summary} is unavailable`
                    : 'Compatibility mode enabled. Some requirements are missing'
            );
        }

        if (dependencySummary) {
            if (missing.length === 0) {
                dependencySummary.textContent = 'All the lights are green! Press "Talk to Unity" to start chatting.';
            } else {
                const summary = formatDependencyList(missing);
                dependencySummary.textContent = summary
                    ? `We spotted a few alerts (${summary}). Talk to Unity will still launch, but those features may be limited until they clear.`
                    : 'We spotted a few alerts. Talk to Unity will still launch, but some features may be limited.';
            }
        }

        if (!announce && !allMet) {
            setStatusMessage('');
        }
    }

    async function startApplication({ auto = false } = {}) {
        if (auto && appShellReady) {
            updateMuteIndicator();
            return;
        }

        if (!auto && appStarted) {
            return;
        }

        if (appRoot?.hasAttribute('hidden')) {
            appRoot.removeAttribute('hidden');
        }

        if (!auto && bodyElement) {
            bodyElement.dataset.appState = 'experience';
        } else if (!bodyElement?.dataset.appState) {
            bodyElement.dataset.appState = 'landing';
        }

        if (!auto && landingSection) {
            landingSection.setAttribute('aria-hidden', 'true');
        } else if (auto) {
            landingSection?.removeAttribute('aria-hidden');
        }

        if (heroStage) {
            if (!heroStage.dataset.state) {
                heroStage.dataset.state = 'idle';
            }
            heroStage.classList.add('is-visible');
        }

        applyTheme(currentTheme);
        setupSpeechRecognition();

        if (!systemPromptLoaded) {
            await loadSystemPrompt();
        }

        updateMuteIndicator();

        if (auto) {
            appShellReady = true;
            return;
        }

        const missing = dependencyState?.missing ?? [];
        if (missing.length > 0) {
            const banner = ensureCompatibilityBanner();
            const summary = formatDependencyList(missing);
            if (banner) {
                banner.textContent = summary
                    ? `Compatibility mode active. Some features may be limited: ${summary}.`
                    : 'Compatibility mode active. Some features may be limited.';
            }
            setStatusMessage('');
        }

        await initializeVoiceControl();
        appStarted = true;
        appShellReady = true;
        applyTheme(currentTheme, { force: true });
    }

    async function setMutedState(muted, { announce = false } = {}) {
        if (!recognition) {
            if (!muted && !hasMicPermission) {
                hasMicPermission = await requestMicPermission();
                if (!hasMicPermission) {
                    updateMuteIndicator();
                    if (announce) {
                        speak('Microphone permission is required to unmute.');
                    }
                    return false;
                }
            }

            isMuted = muted;
            updateMuteIndicator();
            if (muted) {
                setCircleState(userCircle, {
                    listening: false,
                    speaking: false,
                    label: 'Microphone is muted'
                });
                if (announce) {
                    speak('Microphone muted.');
                }
                return true;
            }

            setCircleState(userCircle, {
                listening: true,
                label: 'Listening for your voice'
            });
            if (announce) {
                speak('Microphone unmuted.');
            }
            return true;
        }

        if (muted) {
            if (!isMuted) {
                isMuted = true;
                setCircleState(userCircle, {
                    listening: false,
                    speaking: false,
                    label: 'Microphone is muted'
                });
                updateMuteIndicator();
                try {
                    recognition.stop();
                } catch (error) {
                    console.error('Failed to stop recognition:', error);
                }
            } else {
                updateMuteIndicator();
            }

            if (announce) {
                speak('Microphone muted.');
            }

            return true;
        }

        if (!hasMicPermission) {
            hasMicPermission = await requestMicPermission();
            if (!hasMicPermission) {
                updateMuteIndicator();
                if (announce) {
                    speak('Microphone permission is required to unmute.');
                }
                return false;
            }
        }

        if (!isMuted) {
            setCircleState(userCircle, {
                listening: true,
                label: 'Listening for your voice'
            });
            updateMuteIndicator();

            if (announce) {
                speak('Microphone is already listening.');
            }
            return true;
        }

        isMuted = false;
        setCircleState(userCircle, {
            listening: true,
            label: 'Listening for your voice'
        });
        updateMuteIndicator();

        try {
            recognition.start();
        } catch (error) {
            console.error('Failed to start recognition:', error);
            setCircleState(userCircle, {
                error: true,
                listening: false,
                label: 'Unable to start microphone recognition'
            });
            isMuted = true;
            updateMuteIndicator();
            if (announce) {
                speak('Unable to start microphone recognition.');
            }
            return false;
        }

        if (announce) {
            speak('Microphone unmuted.');
        }

        return true;
    }

    function applyTheme(theme, { announce = false, force = false } = {}) {
        const normalizedTheme = theme === 'light' ? 'light' : 'dark';
        const body = document.body;
        const root = document.documentElement;

        if (!body) {
            currentTheme = normalizedTheme;
            if (root) {
                root.dataset.theme = normalizedTheme;
            }
            return;
        }

        const previousTheme = currentTheme;
        const wasThemeChanged =
            force ||
            previousTheme !== normalizedTheme ||
            body.dataset.theme !== normalizedTheme ||
            (root?.dataset.theme ?? previousTheme) !== normalizedTheme;

        currentTheme = normalizedTheme;
        body.dataset.theme = normalizedTheme;
        if (root) {
            root.dataset.theme = normalizedTheme;
        }

        if (announce) {
            if (!wasThemeChanged) {
                speak(normalizedTheme === 'light' ? 'Light theme is already active.' : 'Dark theme is already active.');
            } else {
                speak(normalizedTheme === 'light' ? 'Light theme activated.' : 'Dark theme activated.');
            }
        }
    }

    function setCircleState(circle, { speaking = false, listening = false, error = false, label = '' } = {}) {
        if (!circle) {
            return;
        }

        if (speaking) {
            if (circle.classList.contains('is-speaking')) {
                circle.classList.remove('is-speaking');
                void circle.offsetWidth;
            }
            circle.classList.add('is-speaking');
        } else {
            circle.classList.remove('is-speaking');
        }
        circle.classList.toggle('is-listening', listening);
        circle.classList.toggle('is-error', error);

        if (label) {
            circle.setAttribute('aria-label', label);
        }
    }

    async function loadSystemPrompt({ force = false } = {}) {
        if (systemPromptLoaded && !force) {
            return;
        }

        const candidatePaths = ['../ai-instruct.txt', 'ai-instruct.txt'];
        for (const path of candidatePaths) {
            try {
                const response = await fetch(resolveAssetPath(path));
                if (!response.ok) {
                    continue;
                }

                systemPrompt = await response.text();
                systemPromptLoaded = true;
                return;
            } catch (error) {
                console.error('Error fetching system prompt from', path, error);
            }
        }

        systemPrompt = 'You are Unity, a helpful AI assistant.';
        systemPromptLoaded = true;
    }

    function setupSpeechRecognition() {
        if (!SpeechRecognition) {
            console.warn('Speech recognition is not supported in this browser.');
            setCircleState(userCircle, {
                label: 'Speech recognition is not supported in this browser',
                error: true
            });
            const banner = ensureCompatibilityBanner();
            if (banner) {
                banner.textContent = 'Compatibility mode active. Speech recognition is not supported in this browser.';
            }
            setStatusMessage('Compatibility mode active. Speech recognition is not supported in this browser.', 'warning');
            return;
        }

        if (recognition) {
            return;
        }

        recognition = new SpeechRecognition();
        recognition.continuous = true;
        recognition.lang = 'en-US';
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;

        recognition.onstart = () => {
            console.log('Voice recognition started.');
            setCircleState(userCircle, {
                listening: true,
                label: 'Listening for your voice'
            });
        };

        recognition.onaudiostart = () => {
            setCircleState(userCircle, {
                listening: true,
                label: 'Listening for your voice'
            });
        };

        recognition.onspeechstart = () => {
            setCircleState(userCircle, {
                speaking: true,
                listening: true,
                label: 'Hearing you speak'
            });
        };

        recognition.onspeechend = () => {
            setCircleState(userCircle, {
                listening: true,
                speaking: false,
                label: 'Processing what you said'
            });
        };

        recognition.onend = () => {
            console.log('Voice recognition stopped.');
            setCircleState(userCircle, {
                listening: false,
                speaking: false,
                label: isMuted ? 'Microphone is muted' : 'Listening for your voice'
            });

            if (recognitionRestartTimeout) {
                clearTimeout(recognitionRestartTimeout);
                recognitionRestartTimeout = null;
            }

            if (!isMuted) {
                recognitionRestartTimeout = window.setTimeout(() => {
                    recognitionRestartTimeout = null;
                    try {
                        recognition.start();
                    } catch (error) {
                        console.error('Failed to restart recognition:', error);
                        setCircleState(userCircle, {
                            error: true,
                            label: 'Unable to restart microphone recognition'
                        });

                        if (!isMuted) {
                            recognitionRestartTimeout = window.setTimeout(() => {
                                recognitionRestartTimeout = null;
                                try {
                                    recognition.start();
                                } catch (retryError) {
                                    console.error('Retry to restart recognition failed:', retryError);
                                }
                            }, 800);
                        }
                    }
                }, 280);
            }
        };

        recognition.onresult = (event) => {
            const transcript = event.results[event.results.length - 1][0].transcript.trim();
            console.log('User said:', transcript);

            setCircleState(userCircle, {
                listening: true,
                speaking: false,
                label: 'Processing what you said'
            });

            const isLocalCommand = handleVoiceCommand(transcript);
            if (!isLocalCommand) {
                getAIResponse(transcript);
            }
        };

        recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            setCircleState(userCircle, {
                error: true,
                listening: false,
                speaking: false,
                label: `Microphone error: ${event.error}`
            });
        };

        if (!isMuted) {
            try {
                recognition.start();
            } catch (error) {
                console.error('Failed to start recognition after initialization:', error);
            }
        }
    }

    async function initializeVoiceControl() {
        if (!recognition) {
            return;
        }

        hasMicPermission = await requestMicPermission();
        if (!hasMicPermission) {
            updateMuteIndicator();
            return;
        }

        if (!isMuted) {
            try {
                recognition.start();
            } catch (error) {
                console.error('Failed to start recognition:', error);
            }
        }
    }

    async function requestMicPermission() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            console.warn('Microphone access is not supported in this browser.');
            setCircleState(userCircle, {
                error: true,
                label: 'Microphone access is not supported in this browser'
            });
            setStatusMessage('Microphone access is not supported in this browser.', 'warning');
            return false;
        }

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            stream.getTracks().forEach((track) => track.stop());
            setCircleState(userCircle, {
                label: 'Microphone is muted'
            });
            return true;
        } catch (error) {
            console.error('Microphone permission denied:', error);
            setCircleState(userCircle, {
                error: true,
                label: 'Microphone permission denied'
            });
            setStatusMessage('Microphone permission denied. Some voice features will be limited.', 'warning');
            return false;
        }
    }

    function updateMuteIndicator() {
        if (!muteIndicator) {
            return;
        }

        muteIndicator.classList.add('is-visible');
        muteIndicator.setAttribute('aria-hidden', 'false');

        const missing = dependencyState?.missing ?? [];
        const recognitionMissing = missing.some((item) => item.id === 'speech-recognition');
        const microphoneMissing = missing.some((item) => item.id === 'microphone');

        if (isMuted) {
            let message;

            if (microphoneMissing) {
                message = 'Microphone access unavailable. Update your browser permissions to enable voice input.';
                muteIndicator.dataset.state = 'muted';
                muteIndicator.setAttribute('aria-label', 'Microphone unavailable. Update permissions to enable listening.');
            } else if (recognitionMissing) {
                message = 'Voice recognition unavailable. Continue with on-screen controls.';
                muteIndicator.dataset.state = 'compat';
                muteIndicator.setAttribute(
                    'aria-label',
                    'Voice recognition is not supported in this browser. You can still use on-screen controls.'
                );
            } else {
                message = hasMicPermission ? 'Tap or click anywhere to unmute' : 'Allow microphone access to start';
                muteIndicator.dataset.state = 'muted';
                muteIndicator.setAttribute('aria-label', 'Microphone muted. Tap to enable listening.');
            }

            indicatorText && (indicatorText.textContent = message);
        } else {
            if (recognitionMissing) {
                indicatorText &&
                    (indicatorText.textContent = 'Voice recognition unavailable. Microphone listening disabled.');
                muteIndicator.dataset.state = 'compat';
                muteIndicator.setAttribute(
                    'aria-label',
                    'Voice recognition unavailable. Microphone listening remains disabled.'
                );
                return;
            }

            indicatorText && (indicatorText.textContent = 'Listening… tap to mute');
            muteIndicator.dataset.state = 'listening';
            muteIndicator.setAttribute('aria-label', 'Microphone active. Tap to mute.');
        }
    }

    function showMicrophonePermissionRequest() {
        if (!muteIndicator) {
            return;
        }

        muteIndicator.dataset.state = 'pending';
        muteIndicator.setAttribute('aria-label', 'Requesting microphone permission…');
        if (indicatorText) {
            indicatorText.textContent = 'Requesting microphone permission…';
        }
    }

    async function attemptUnmute({ announce = false } = {}) {
        if (unmuteInProgress) {
            return;
        }

        const shouldShowProgress = isMuted && !hasMicPermission;
        if (shouldShowProgress) {
            showMicrophonePermissionRequest();
        }

        unmuteInProgress = true;
        try {
            await setMutedState(false, { announce });
        } finally {
            unmuteInProgress = false;
            updateMuteIndicator();
        }
    }

    function handleMuteToggle(event) {
        event?.stopPropagation();

        if (isMuted) {
            void attemptUnmute();
            return;
        }

        void setMutedState(true);
    }

    muteIndicator?.addEventListener('click', handleMuteToggle);

    const handleAmbientUnmute = () => {
        if (!isMuted || unmuteInProgress) {
            return;
        }

        void attemptUnmute();
    };

    document.addEventListener('click', handleAmbientUnmute);

    document.addEventListener('keydown', (event) => {
        if ((event.key === 'Enter' || event.key === ' ') && isMuted && !unmuteInProgress) {
            event.preventDefault();
            void attemptUnmute();
        }
    });


    function isLikelyUrlSegment(segment) {
        if (typeof segment !== 'string' || segment.trim() === '') {
            return false;
        }

        const cleaned = segment
            .replace(/^[<({\[\s'"“”‘’`]+/g, '')
            .replace(/[>)}\]\s'"“”‘’`]+$/g, '')
            .replace(/[.,!?;:]+$/g, '')
            .trim();

        if (cleaned === '') {
            return false;
        }

        const normalized = cleaned.toLowerCase();

        if (
            normalized.startsWith('http://') ||
            normalized.startsWith('https://') ||
            normalized.startsWith('www.') ||
            normalized.includes('://')
        ) {
            return true;
        }

        if (/^[a-z0-9.-]+\.[a-z]{2,}(?:[/?#].*)?$/.test(normalized)) {
            return true;
        }

        return false;
    }

    function removeMarkdownLinkTargets(value) {
        return value
            .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_match, altText, url) => {
                return isLikelyUrlSegment(url) ? altText : _match;
            })
            .replace(/\ \[([^]]*)\]\(([^)]+)\)/g, (_match, linkText, url) => {
                return isLikelyUrlSegment(url) ? linkText : _match;
            })
            .replace(/\ \[ (?:command|action)[^]]*\]\([^)]*\)/gi, ' ');
    }

    function removeCommandArtifacts(value) {
        if (typeof value !== 'string') {
            return '';
        }

        let result = value
            .replace(/\ \[^]]*\bcommand\b[^]]*\]/gi, ' ')
            .replace(/\([^)]*\bcommand\b[^)]*\)/gi, ' ')
            .replace(/<[^>]*\bcommand\b[^>]*>/gi, ' ')
            .replace(/\bcommands?\s*[:=-]\s*[a-z0-9_,\s-]+/gi, ' ')
            .replace(/\bactions?\s*[:=-]\s*[a-z0-9_,\s-]+/gi, ' ')
            .replace(/\b(?:execute|run)\s+command\s*(?:[:=-]\s*)?[a-z0-9_-]*/gi, ' ')
            .replace(/\bcommand\s*(?:[:=-]\s*|\s+)(?:[a-z0-9_-]+(?:\s+[a-z0-9_-]+)*)?/gi, ' ');

        result = result.replace(/^\s*[-*]?\s*(?:command|action)[^\n]*$/gim, ' ');

        return result;
    }

    function sanitizeForSpeech(text) {
        if (typeof text !== 'string') {
            return '';
        }

        const withoutDirectives = text
            .replace(/\ \[command:[^]]*\]/gi, ' ')
            .replace(/\ {command:[^}]*}/gi, ' ')
            .replace(/<command[^>]*>[^<]*<\/command>/gi, ' ')
            .replace(/\b(?:command|action)\s*[:=]\s*([a-z0-9_\-]+)/gi, ' ')
            .replace(/\bcommands?\s*[:=]\s*([a-z0-9_\-]+)/gi, ' ')
            .replace(/\b(?:command|action)\s*(?:->|=>|::)\s*([a-z0-9_\-]+)/gi, ' ')
            .replace(/\b(?:command|action)\b\s*[()\-:=]*\s*[a-z0-9_\-]+/gi, ' ')
            .replace(/\bcommand\s*\([^)]*\)/gi, ' ');

        const withoutPollinations = withoutDirectives
            .replace(/https?:\/\/\S*images? \.pollinations\.ai\S*/gi, '')
            .replace(/\b\S*images? \.pollinations\.ai\S*\b/gi, '');

        const withoutMarkdownTargets = removeMarkdownLinkTargets(withoutPollinations);
        const withoutCommands = removeCommandArtifacts(withoutMarkdownTargets);

        const withoutGenericUrls = withoutCommands
            .replace(/https?:\/\/\S+/gi, ' ')
            .replace(/\bwww\.[^\s)]+/gi, ' ');

        const withoutSpacedUrls = withoutGenericUrls
            .replace(/h\s*t\s*t\s*p\s*s?\s*:\s*\/\s*\/\s*[\w\-.\/?%#&=]+/gi, ' ')
            .replace(/\bhttps?\b/gi, ' ')
            .replace(/\bwww\b/gi, ' ');

        const withoutSpelledUrls = withoutSpacedUrls
            .replace(/h\s*t\s*t\s*p\s*s?\s*(?:[:=]|colon)\s*\/\s*\/\s*[\w\-.\/?%#&=]+/gi, ' ')
            .replace(/\b(?:h\s*t\s*t\s*p\s*s?|h\s*t\s*t\s*p)\b/gi, ' ')
            .replace(/\bcolon\b/gi, ' ')
            .replace(/\bslash\b/gi, ' ');

        const parts = withoutSpelledUrls.split(/(\s+)/);
        const sanitizedParts = parts.map((part) => {
            if (isLikelyUrlSegment(part)) {
                return '';
            }

            if (/(?:https?|www|:\/\/|\.com|\.net|\.org|\.io|\.ai|\.co|\.gov|\.edu)/i.test(part)) {
                return '';
            }

            if (/\bcommand\b/i.test(part)) {
                return '';
            }

            if (/(?:image|artwork|photo)\s+(?:url|link)/i.test(part)) {
                return '';
            }

            return part;
        });

        const commandTokens = [
            'open_image',
            'save_image',
            'copy_image',
            'mute_microphone',
            'unmute_microphone',
            'stop_speaking',
            'shutup',
            'set_model_flux',
            'set_model_turbo',
            'set_model_kontext',
            'clear_chat_history',
            'theme_light',
            'theme_dark'
        ];

        let sanitized = sanitizedParts
            .join('')
            .replace(/\s{2,}/g, ' ')
            .replace(/\s+([.,!?;:])/, '$1')
            .replace(/\(\s*\)/g, '')
            .replace(/\ [\s*]/g, '')
            .replace(/\{\s*\}/g, '')
            .replace(/\b(?:https?|www)\b/gi, '')
            .replace(/\b[a-z0-9]+\s+dot\s+[a-z0-9]+\b/gi, '')
            .replace(/\b(?:dot\s+)(?:com|net|org|io|ai|co|gov|edu|xyz)\b/gi, '')

            .replace(/<\s*>/g, '')
            .replace(/\bcommand\b/gi, '')
            .replace(/\b(?:image|artwork|photo)\s+(?:url|link)\b.*$/gim, '')
            .trim();

        return sanitized;
    }

    function sanitizeImageUrl(rawUrl) {
        if (typeof rawUrl !== 'string') {
            return '';
        }

        return rawUrl
            .trim()
            .replace(/^["'<\\\[({]+/, '')
            .replace(/["'>) \\]}]+$/, '')
            .replace(/[,.;!]+$/, '');
    }

    const FALLBACK_IMAGE_KEYWORDS = [
        'show',
        'picture',
        'image',
        'photo',
        'illustration',
        'draw',
        'paint',
        'render',
        'display',
        'visual',
        'wallpaper',
        'generate'
    ];

    function shouldRequestFallbackImage({ userInput = '', assistantMessage = '', fallbackPrompt = '', existingImageUrl = '' }) {
        if (existingImageUrl || !fallbackPrompt) {
            return false;
        }

        const combined = `${userInput} ${assistantMessage}`.toLowerCase();
        if (combined.includes('[image]')) {
            return true;
        }

        const keywordPattern = new RegExp(`\b(?:${FALLBACK_IMAGE_KEYWORDS.join('|')})\b`, 'i');
        if (keywordPattern.test(combined)) {
            return true;
        }

        const descriptiveCuePattern = /(here\s+(?:is|'s)|displaying|showing)\s+(?:an?\s+)?(?:image|picture|photo|visual)/i;
        return descriptiveCuePattern.test(combined);
    }

    function cleanFallbackPrompt(text) {
        return text
            .replace(/^["\'\s]+/, '')
            .replace(/["\'\s]+$/, '')
            .replace(/\s{2,}/g, ' ')
            .trim();
    }

    function buildFallbackImagePrompt(userInput = '', assistantMessage = '') {
        const sources = [assistantMessage, userInput];
        for (const source of sources) {
            if (!source) {
                continue;
            }

            const explicitPromptMatch = source.match(/(?:image\s+prompt|prompt)\s*[:=]\s*"?([^"\n]+)"?/i);
            if (explicitPromptMatch?.[1]) {
                const sanitized = cleanFallbackPrompt(explicitPromptMatch[1]);
                if (sanitized) {
                    return sanitized;
                }
            }
        }

        const rawCandidate = userInput || assistantMessage || '';
        if (!rawCandidate) {
            return '';
        }

        const cleaned = cleanFallbackPrompt(
            rawCandidate
                .replace(/\b(?:please|kindly)\b/gi, '')
                .replace(/\b(?:can|could|would|will|may|might|let's)\b\s+(?:you\s+)?/gi, '')
                .replace(
                    /\b(?:show|display|draw|paint|generate|create|make|produce|render|give|find|display)\b\s+(?:me\s+|us\s+)?/gi,
                    ''
                )
                .replace(
                    /\b(?:an?\s+)?(?:image|picture|photo|visual|illustration|render|drawing|art|shot|wallpaper)\b\s*(?:of|showing)?\s*/gi,
                    ''
                )
        );

        if (!cleaned) {
            return '';
        }

        return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
    }

    function buildPollinationsImageUrl(prompt, { model = currentImageModel } = {}) {
        if (typeof prompt !== 'string') {
            return '';
        }

        const sanitized = cleanFallbackPrompt(prompt);
        if (!sanitized) {
            return '';
        }

        const params = new URLSearchParams({
            model: model || 'flux',
            width: '1024',
            height: '1024',
            nologo: 'true',
            enhance: 'true',
            seed: Math.floor(Math.random() * 1_000_000_000).toString()
        });

        return `https://image.pollinations.ai/prompt/${encodeURIComponent(sanitized)}?${params.toString()}`;
    }

    function extractImageUrl(text) {
        if (typeof text !== 'string' || text.trim() === '') {
            return '';
        }

        const markdownMatch = text.match(/!\[[^\]]*\]\((https?:\/\/[^)\s]+)\)/i);
        if (markdownMatch?.[1]) {
            return sanitizeImageUrl(markdownMatch[1]);
        }

        const rawMatch = text.match(/https?:\/\/[^)\s]+/i);
        if (rawMatch?.[0]) {
            return sanitizeImageUrl(rawMatch[0]);
        }

        return '';
    }

    function escapeRegExp(value) {
        return value.replace(/[-/\\^$*+?.()|[\]{}]/g, '\\$&');
    }

    function removeImageReferences(text, imageUrl) {
        if (typeof text !== 'string') {
            return '';
        }

        if (!imageUrl) {
            return text.trim();
        }

        const sanitizedUrl = sanitizeImageUrl(imageUrl);
        if (!sanitizedUrl) {
            return text.trim();
        }

        let result = text;
        const escapedUrl = escapeRegExp(sanitizedUrl);

        const markdownImageRegex = new RegExp(`!\[[^\]]*\]\(${escapedUrl}\)`, 'gi');
        result = result.replace(markdownImageRegex, '');

        const markdownImageNoUrlRegex = new RegExp(`!\[[^\]]*\]\(\s*\)`, 'gi');
        result = result.replace(markdownImageNoUrlRegex, '');

        const markdownLinkRegex = new RegExp(`\[[^\]]*\]\(${escapedUrl}\)`, 'gi');
        result = result.replace(markdownLinkRegex, '');

        const rawUrlRegex = new RegExp(escapedUrl, 'gi');
        result = result.replace(rawUrlRegex, '');

        result = result
            .replace(/\bimage\s+url\s*:?/gi, '')
            .replace(/\bimage\s+link\s*:?/gi, '')
            .replace(/\bart(?:work)?\s+(?:url|link)\s*:?/gi, '')
            .replace(/<\s*>/g, '')
            .replace(/\(\s*\)/g, '')
            .replace(/\ [\s*]/g, '');

        return result
            .replace(/\n{3,}/g, '\n\n')
            .replace(/[ \t]{2,}/g, ' ')
            .replace(/\s+([.,!?;:])/, '$1')
            .trim();
    }

    function normalizeCommandValue(value) {
        return value.replace(/[\s-]+/g, '_').trim().toLowerCase();
    }

    function parseAiDirectives(responseText) {
        if (typeof responseText !== 'string' || responseText.trim() === '') {
            return { cleanedText: '', commands: [] };
        }

        const commands = [];
        let workingText = responseText;

        const patterns = [
            /\ \[command:\s*([^]]+)\]/gi,
            /\ {command:\s*([^}]+)}/gi,
            /<command[^>]*>\s*([^<]*)<\/command>/gi,
            /\bcommand\s*[:=]\s*([a-z0-9_\-]+)/gi,
            /\bcommands?\s*[:=]\s*([a-z0-9_\-]+)/gi,
            /\baction\s*[:=]\s*([a-z0-9_\-]+)/gi,
            /\b(?:command|action)\s*(?:->|=>|::)\s*([a-z0-9_\-]+)/gi,
            /\bcommand\s*\(\s*([^)]+?)\s*\)/gi
        ];

        for (const pattern of patterns) {
            workingText = workingText.replace(pattern, (_match, commandValue) => {
                if (commandValue) {
                    const normalized = normalizeCommandValue(commandValue);
                    if (normalized) {
                        commands.push(normalized);
                    }
                }
                return ' ';
            });
        }

        const slashCommandRegex = /(?:^|\s)\/ (open_image|save_image|copy_image|mute_microphone|unmute_microphone|stop_speaking|shutup|set_model_flux|set_model_turbo|set_model_kontext|clear_chat_history|theme_light|theme_dark)\b/gi;
        workingText = workingText.replace(slashCommandRegex, (_match, commandValue) => {
            const normalized = normalizeCommandValue(commandValue);
            if (normalized) {
                commands.push(normalized);
            }
            return ' ';
        });

        const directiveBlockRegex = /(?:^|\n)\s*(?:commands?|actions?)\s*:?\s*(?:\n|$)( (?:\s*[-*•]?\s*[a-z0-9_\-]+\s*(?:\(\))?\s*(?:\n|$))+)/gi;
        workingText = workingText.replace(directiveBlockRegex, (_match, blockContent) => {
            const lines = blockContent
                .split(/\n+/) 
                .map((line) => line.replace(/^[^a-z0-9]+/i, '').trim())
                .filter(Boolean);

            for (const line of lines) {
                const normalized = normalizeCommandValue(line.replace(/\(\)/g, ''));
                if (normalized) {
                    commands.push(normalized);
                }
            }

            return '\n';
        });

        const cleanedText = workingText.replace(/\n{3,}/g, '\n\n').trim();
        const uniqueCommands = [...new Set(commands)];

        return { cleanedText, commands: uniqueCommands };
    }

    async function executeAiCommand(command) {
        if (!command) {
            return false;
        }

        const normalized = normalizeCommandValue(command);

        switch (normalized) {
            case 'mute_microphone':
                await setMutedState(true, { announce: true });
                return true;
            case 'unmute_microphone':
                await setMutedState(false, { announce: true });
                return true;
            case 'stop_speaking':
            case 'shutup':
                if (synth && typeof synth.cancel === 'function') {
                    synth.cancel();
                }
                setCircleState(aiCircle, {
                    speaking: false,
                    label: 'Unity is idle'
                });
                return true;
            case 'copy_image':
                await copyImageToClipboard();
                return true;
            case 'save_image':
                await saveImage();
                return true;
            case 'open_image':
                openImageInNewTab();
                return true;
            case 'set_model_flux':
                currentImageModel = 'flux';
                speak('Image model set to flux.');
                return true;
            case 'set_model_turbo':
                currentImageModel = 'turbo';
                speak('Image model set to turbo.');
                return true;
            case 'set_model_kontext':
                currentImageModel = 'kontext';
                speak('Image model set to kontext.');
                return true;
            case 'clear_chat_history':
                chatHistory = [];
                speak('Chat history cleared.');
                return true;
            case 'theme_light':
                applyTheme('light', { announce: true });
                return true;
            case 'theme_dark':
                applyTheme('dark', { announce: true });
                return true;
            default:
                return false;
        }
    }

    function speak(text) {
        if (!synth || typeof synth.speak !== 'function') {
            console.warn('Speech synthesis is not available in this browser.');
            return;
        }

        if (synth.speaking) {
            synth.cancel();
            setCircleState(aiCircle, {
                speaking: false,
                label: 'Unity is idle'
            });
        }

        const sanitizedText = sanitizeForSpeech(text);

        if (sanitizedText === '') {
            return;
        }

        const utterance = new SpeechSynthesisUtterance(sanitizedText);
        const voices = typeof synth.getVoices === 'function' ? synth.getVoices() : [];
        const ukFemaleVoice = voices.find((voice) =>
            voice.name.includes('Google UK English Female') || (voice.lang === 'en-GB' && voice.gender === 'female')
        );

        if (ukFemaleVoice) {
            utterance.voice = ukFemaleVoice;
        } else {
            console.warn('UK English female voice not found, using default.');
        }

        utterance.onstart = () => {
            console.log('AI is speaking...');
            setCircleState(aiCircle, {
                speaking: true,
                label: 'Unity is speaking'
            });
        };

        utterance.onend = () => {
            console.log('AI finished speaking.');
            setCircleState(aiCircle, {
                speaking: false,
                label: 'Unity is idle'
            });
        };

        synth.speak(utterance);
    }


    function handleVoiceCommand(command) {
        const lowerCaseCommand = command.toLowerCase();

        if (
            lowerCaseCommand.includes('mute my mic') ||
            lowerCaseCommand.includes('mute microphone') ||
            lowerCaseCommand === 'mute'
        ) {
            setMutedState(true, { announce: true });
            return true;
        }

        if (
            lowerCaseCommand.includes('unmute my mic') ||
            lowerCaseCommand.includes('unmute microphone') ||
            lowerCaseCommand.includes('turn on the mic') ||
            lowerCaseCommand === 'unmute'
        ) {
            setMutedState(false, { announce: true });
            return true;
        }

        if (lowerCaseCommand.includes('shut up') || lowerCaseCommand.includes('be quiet')) {
            if (synth && typeof synth.cancel === 'function') {
                synth.cancel();
            }
            setCircleState(aiCircle, {
                speaking: false,
                label: 'Unity is idle'
            });
            return true;
        }

        if (
            lowerCaseCommand.includes('light mode') ||
            lowerCaseCommand.includes('light theme') ||
            lowerCaseCommand.includes('day mode')
        ) {
            applyTheme('light', { announce: true });
            return true;
        }

        if (
            lowerCaseCommand.includes('dark mode') ||
            lowerCaseCommand.includes('dark theme') ||
            lowerCaseCommand.includes('night mode')
        ) {
            applyTheme('dark', { announce: true });
            return true;
        }

        if (lowerCaseCommand.includes('copy image') || lowerCaseCommand.includes('copy this image')) {
            copyImageToClipboard();
            return true;
        }

        if (lowerCaseCommand.includes('save image') || lowerCaseCommand.includes('download image')) {
            saveImage();
            return true;
        }

        if (lowerCaseCommand.includes('open image') || lowerCaseCommand.includes('open this image')) {
            openImageInNewTab();
            return true;
        }

        if (lowerCaseCommand.includes('use flux model') || lowerCaseCommand.includes('switch to flux')) {
            currentImageModel = 'flux';
            speak('Image model set to flux.');
            return true;
        }

        if (lowerCaseCommand.includes('use turbo model') || lowerCaseCommand.includes('switch to turbo')) {
            currentImageModel = 'turbo';
            speak('Image model set to turbo.');
            return true;
        }

        if (lowerCaseCommand.includes('use kontext model') || lowerCaseCommand.includes('switch to kontext')) {
            currentImageModel = 'kontext';
            speak('Image model set to kontext.');
            return true;
        }

        if (
            lowerCaseCommand.includes('clear history') ||
            lowerCaseCommand.includes('delete history') ||
            lowerCaseCommand.includes('clear chat') ||
            lowerCaseCommand.includes('clear chat history')
        ) {
            chatHistory = [];
            speak('Chat history cleared.');
            return true;
        }

        if (
            lowerCaseCommand.includes('light mode') ||
            lowerCaseCommand.includes('light theme') ||
            lowerCaseCommand.includes('change to light') ||
            lowerCaseCommand.includes('switch to light') ||
            lowerCaseCommand.includes('change them to light')
        ) {
            const wasUpdated = currentTheme !== 'light';
            applyTheme('light');
            speak(wasUpdated ? 'Switched to the light theme.' : 'Light theme is already active.');
            return true;
        }

        if (
            lowerCaseCommand.includes('dark mode') ||
            lowerCaseCommand.includes('dark theme') ||
            lowerCaseCommand.includes('change to dark') ||
            lowerCaseCommand.includes('switch to dark') ||
            lowerCaseCommand.includes('change them to dark')
        ) {
            const wasUpdated = currentTheme !== 'dark';
            applyTheme('dark');
            speak(wasUpdated ? 'Switched to the dark theme.' : 'Dark theme is already active.');
            return true;
        }

        return false;
    }

    const POLLINATIONS_TEXT_URL = 'https://text.pollinations.ai/openai';
    const UNITY_REFERRER = 'https://www.unityailab.com/';

    function isUnityDomain(hostname) {
        return UNITY_ALLOWED_HOST_SUFFIXES.some((domain) => hostname === domain || hostname.endsWith(`.${domain}`));
    }

    function shouldUseUnityReferrer() {
        if (typeof window === 'undefined') {
            return false;
        }

        try {
            const { protocol, hostname } = window.location;
            if (protocol === 'file:') {
                return true;
            }

            if (LOOPBACK_HOST_PATTERN.test(hostname) || isUnityDomain(hostname)) {
                return true;
            }
        } catch (error) {
            console.warn('Unable to determine referrer eligibility:', error);
        }

        return false;
    }

    async function getAIResponse(userInput) {
        console.log(`Sending to AI: ${userInput}`);

        chatHistory.push({ role: 'user', content: userInput });

        if (chatHistory.length > 12) {
            chatHistory.splice(0, chatHistory.length - 12);
        }

        let aiText = '';

        try {
            const messages = [{ role: 'system', content: systemPrompt }, ...chatHistory];

            const pollinationsPayload = JSON.stringify({
                messages,
                model: 'unity'
            });

            const requestInit = {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: pollinationsPayload
            };

            if (shouldUseUnityReferrer()) {
                // Explicitly identify the Unity AI Lab referrer so the public
                // Pollinations endpoint treats the request as coming from the
                // approved web client when we are running on an authorised host.
                requestInit.referrer = UNITY_REFERRER;
                requestInit.referrerPolicy = 'strict-origin-when-cross-origin';
            }

            const textResponse = await fetch(POLLINATIONS_TEXT_URL, requestInit);

            if (!textResponse.ok) {
                throw new Error(`Pollinations text API returned ${textResponse.status}`);
            }

            const data = await textResponse.json();
            aiText = data.choices?.[0]?.message?.content ?? '';

            if (!aiText) {
                throw new Error('Received empty response from Pollinations AI');
            }

            const { cleanedText, commands } = parseAiDirectives(aiText);

            for (const command of commands) {
                await executeAiCommand(command);
            }

            const assistantMessage = cleanedText || aiText;
            const imageUrlFromResponse = extractImageUrl(aiText) || extractImageUrl(assistantMessage);

            const fallbackPrompt = buildFallbackImagePrompt(userInput, assistantMessage);
            let fallbackImageUrl = '';
            if (
                shouldRequestFallbackImage({
                    userInput,
                    assistantMessage,
                    fallbackPrompt,
                    existingImageUrl: imageUrlFromResponse
                })
            ) {
                fallbackImageUrl = buildPollinationsImageUrl(fallbackPrompt, { model: currentImageModel });
            }

            const selectedImageUrl = imageUrlFromResponse || fallbackImageUrl;

            const assistantMessageWithoutImage = selectedImageUrl
                ? removeImageReferences(assistantMessage, selectedImageUrl)
                : assistantMessage;

            const finalAssistantMessage = assistantMessageWithoutImage.replace(/\n{3,}/g, '\n\n').trim();
            const chatAssistantMessage = finalAssistantMessage || '[image]';

            chatHistory.push({ role: 'assistant', content: chatAssistantMessage });

            let heroImagePromise = Promise.resolve(false);
            if (selectedImageUrl) {
                heroImagePromise = updateHeroImage(selectedImageUrl);
            }

            const shouldSuppressSpeech = commands.includes('shutup') || commands.includes('stop_speaking');

            if (!shouldSuppressSpeech) {
                const spokenText = sanitizeForSpeech(finalAssistantMessage);
                if (spokenText) {
                    await heroImagePromise;
                    speak(spokenText);
                }
            }

        } catch (error) {
            console.error('Error getting text from Pollinations AI:', error);
            setCircleState(aiCircle, {
                error: true,
                label: 'Unity could not respond'
            });
            speak("Sorry, I couldn't get a text response.");
            setTimeout(() => {
                setCircleState(aiCircle, {
                    error: false,
                    label: 'Unity is idle'
                });
            }, 2400);
        }
    }

    function getImageUrl() {
        if (currentHeroUrl) {
            return currentHeroUrl;
        }

        if (heroImage?.getAttribute('src')) {
            return heroImage.getAttribute('src');
        }

        return '';
    }

    function updateHeroImage(imageUrl) {
        if (!heroStage || !heroImage || !imageUrl) {
            return Promise.resolve(false);
        }

        heroStage.classList.add('is-visible');

        if (imageUrl === currentHeroUrl && heroStage.dataset.state === 'loaded') {
            heroStage.setAttribute('aria-hidden', heroStage.classList.contains('has-image') ? 'false' : 'true');
            return Promise.resolve(true);
        }

        heroStage.setAttribute('aria-hidden', 'true');

        const hadImage = heroStage.classList.contains('has-image');

        pendingHeroUrl = imageUrl;
        heroStage.dataset.state = 'loading';
        if (!hadImage) {
            heroStage.classList.remove('has-image');
            heroImage.removeAttribute('src');
        }

        return new Promise((resolve) => {
            const image = new Image();
            image.decoding = 'async';
            image.crossOrigin = 'anonymous';

            image.onload = () => {
                if (pendingHeroUrl !== imageUrl) {
                    resolve(false);
                    return;
                }

                currentHeroUrl = imageUrl;
                pendingHeroUrl = '';
                heroImage.src = imageUrl;
                heroStage.dataset.state = 'loaded';
                heroStage.classList.add('has-image');
                heroStage.setAttribute('aria-hidden', 'false');
                resolve(true);
            };

            image.onerror = (error) => {
                if (pendingHeroUrl === imageUrl) {
                    pendingHeroUrl = '';
                }
                if (!hadImage) {
                    heroStage.dataset.state = 'error';
                    heroStage.classList.remove('has-image');
                    heroImage.removeAttribute('src');
                    heroStage.setAttribute('aria-hidden', 'true');
                } else {
                    heroStage.dataset.state = 'loaded';
                    heroStage.setAttribute('aria-hidden', 'false');
                }
                console.error('Failed to load hero image:', error);
                resolve(false);
            };

            image.src = imageUrl;
        });
    }

    async function copyImageToClipboard() {
        const imageUrl = getImageUrl();
        if (!imageUrl) {
            return;
        }

        try {
            const response = await fetch(imageUrl);
            const blob = await response.blob();
            await navigator.clipboard.write([new ClipboardItem({ [blob.type]: blob })]);
            speak('Image copied to clipboard.');
        } catch (error) {
            console.error('Failed to copy image: ', error);
            speak('Sorry, I could not copy the image. This might be due to browser limitations.');
        }
    }

    async function saveImage() {
        const imageUrl = getImageUrl();
        if (!imageUrl) {
            return;
        }

        try {
            const response = await fetch(imageUrl);
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.style.display = 'none';
            link.href = url;
            link.download = 'pollination_image.png';
            document.body.appendChild(link);
            link.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(link);
            speak('Image saved.');
        } catch (error) {
            console.error('Failed to save image: ', error);
            speak('Sorry, I could not save the image.');
        }
    }

    function openImageInNewTab() {
        const imageUrl = getImageUrl();
        if (!imageUrl) {
            return;
        }

        window.open(imageUrl, '_blank');
        speak('Image opened in new tab.');
    }

    if (typeof window !== 'undefined') {
        Object.assign(window, {
            applyTheme,
            setMutedState,
            startApplication,
            attemptUnmute
        });
    }
})();
