// A.L.F.R.E.D. Voice Integration - Connects VoiceVisualizer to AI voice output
// Handles advanced audio source detection and integration scenarios

class VoiceIntegration {
    constructor(visualizer) {
        this.visualizer = visualizer;
        this.audioSources = new Set();
        this.connectedElements = new WeakSet();
        this.observerActive = false;

        this.init();
    }

    init() {
        this.setupAudioDetection();
        this.setupSpeechSynthesisIntegration();
        this.startAudioSourceMonitoring();

        console.log('🔗 Voice Integration initialized');
    }

    // Detect and connect to audio elements automatically
    setupAudioDetection() {
        // Monitor for new audio/video elements
        this.audioObserver = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType === Node.ELEMENT_NODE) {
                        this.scanForAudioElements(node);
                    }
                });
            });
        });

        // Start observing for new audio elements
        this.audioObserver.observe(document.body, {
            childList: true,
            subtree: true
        });

        // Scan existing elements
        this.scanForAudioElements(document.body);
    }

    scanForAudioElements(container) {
        const audioElements = container.querySelectorAll('audio, video');

        audioElements.forEach(element => {
            if (!this.connectedElements.has(element)) {
                this.tryConnectAudioElement(element);
            }
        });

        // Also check if the container itself is an audio element
        if ((container.tagName === 'AUDIO' || container.tagName === 'VIDEO') &&
            !this.connectedElements.has(container)) {
            this.tryConnectAudioElement(container);
        }
    }

    async tryConnectAudioElement(element) {
        try {
            // Wait for element to be ready
            if (element.readyState === 0) {
                element.addEventListener('loadedmetadata', () => {
                    this.tryConnectAudioElement(element);
                }, { once: true });
                return;
            }

            // Connect to visualizer
            const success = await this.visualizer.connectAudioElement(element);
            if (success) {
                this.connectedElements.add(element);
                this.audioSources.add(element);

                // Monitor element lifecycle
                this.setupAudioElementListeners(element);

                console.log('🎵 Connected audio element to visualizer:', element.src || element.currentSrc);
            }
        } catch (error) {
            console.warn('🔇 Failed to connect audio element:', error);
        }
    }

    setupAudioElementListeners(element) {
        const onPlay = () => {
            this.updateVisualizerStatus('active', 'Playing');
        };

        const onPause = () => {
            this.updateVisualizerStatus('idle', 'Paused');
        };

        const onEnded = () => {
            this.updateVisualizerStatus('idle', 'Idle');
        };

        const onError = () => {
            this.updateVisualizerStatus('error', 'Audio Error');
        };

        element.addEventListener('play', onPlay);
        element.addEventListener('pause', onPause);
        element.addEventListener('ended', onEnded);
        element.addEventListener('error', onError);

        // Cleanup when element is removed
        element.addEventListener('remove', () => {
            element.removeEventListener('play', onPlay);
            element.removeEventListener('pause', onPause);
            element.removeEventListener('ended', onEnded);
            element.removeEventListener('error', onError);

            this.audioSources.delete(element);
            this.connectedElements.delete(element);
        });
    }

    // Speech synthesis integration for AI voice output
    setupSpeechSynthesisIntegration() {
        if (!window.speechSynthesis) {
            console.warn('🔇 Speech synthesis not available');
            return;
        }

        // Monitor speech synthesis events
        const originalSpeak = window.speechSynthesis.speak.bind(window.speechSynthesis);
        const integration = this;

        window.speechSynthesis.speak = function(utterance) {
            // Set up visualization for speech synthesis
            integration.handleSpeechSynthesis(utterance);
            return originalSpeak(utterance);
        };

        console.log('🗣️ Speech synthesis integration active');
    }

    handleSpeechSynthesis(utterance) {
        utterance.addEventListener('start', () => {
            this.updateVisualizerStatus('active', 'Speaking');
            // Note: Speech synthesis doesn't provide direct audio stream access
            // The visualizer will show a pulsing pattern during speech
            this.simulateSpeechVisualization();
        });

        utterance.addEventListener('end', () => {
            this.updateVisualizerStatus('idle', 'Idle');
            this.stopSpeechVisualizationSimulation();
        });

        utterance.addEventListener('error', (event) => {
            this.updateVisualizerStatus('error', 'Speech Error');
            console.error('🗣️ Speech synthesis error:', event.error);
        });
    }

    // Simulate visualization during speech synthesis (since we can't access audio stream directly)
    simulateSpeechVisualization() {
        if (this.speechSimulationInterval) {
            clearInterval(this.speechSimulationInterval);
        }

        let phase = 0;
        this.speechSimulationInterval = setInterval(() => {
            if (this.visualizer && this.visualizer.smoothedData) {
                // Generate simulated speech-like frequency data
                for (let i = 0; i < this.visualizer.smoothedData.length; i++) {
                    const frequency = (i / this.visualizer.smoothedData.length) * Math.PI * 4;
                    const amplitude = Math.sin(phase + frequency) * 0.3 + 0.2;
                    const speechPattern = Math.sin(phase * 0.5) * 0.4 + 0.6;

                    this.visualizer.smoothedData[i] = Math.max(0, amplitude * speechPattern);
                }
                phase += 0.2;
            }
        }, 50); // 20 FPS simulation
    }

    stopSpeechVisualizationSimulation() {
        if (this.speechSimulationInterval) {
            clearInterval(this.speechSimulationInterval);
            this.speechSimulationInterval = null;
        }
    }

    // Monitor for pygame audio playback (from Python voice interface)
    startAudioSourceMonitoring() {
        // Look for pygame-generated audio elements or Web Audio API usage
        this.sourceMonitorInterval = setInterval(() => {
            this.detectWebAudioSources();
            this.detectPygameAudio();
        }, 2000);
    }

    detectWebAudioSources() {
        // Check if any Web Audio API contexts are active
        if (window.AudioContext || window.webkitAudioContext) {
            // This is a basic check - in real scenarios, we'd need the audio source
            // to explicitly connect to our visualizer's analyser
        }
    }

    detectPygameAudio() {
        // pygame audio from Python backend might not be directly accessible
        // but we can listen for related DOM events or WebSocket messages
        if (window.batConsole && window.batConsole.websocket) {
            // Could implement WebSocket message handling for voice output events
            this.setupWebSocketAudioEvents();
        }
    }

    setupWebSocketAudioEvents() {
        if (this.websocketSetup) return;
        this.websocketSetup = true;

        // Listen for voice-related WebSocket messages
        const originalHandler = window.batConsole.handleWebSocketMessage;
        const integration = this;

        if (originalHandler) {
            window.batConsole.handleWebSocketMessage = function(data) {
                // Handle voice-related events
                if (data.type === 'voice_start') {
                    integration.updateVisualizerStatus('active', 'A.L.F.R.E.D. Speaking');
                    integration.simulateSpeechVisualization();
                } else if (data.type === 'voice_end') {
                    integration.updateVisualizerStatus('idle', 'Idle');
                    integration.stopSpeechVisualizationSimulation();
                }

                // Call original handler
                return originalHandler.call(this, data);
            };
        }
    }

    // Helper methods
    updateVisualizerStatus(state, text) {
        if (window.updateStatus) {
            window.updateStatus(state, text);
        }
    }

    // Public API
    connectToSource(source) {
        if (source instanceof HTMLAudioElement || source instanceof HTMLVideoElement) {
            return this.tryConnectAudioElement(source);
        } else if (source instanceof MediaStream) {
            return this.visualizer.connectToMicrophone(); // Reuse mic connection logic
        } else {
            console.warn('🔇 Unsupported audio source type');
            return Promise.resolve(false);
        }
    }

    disconnect() {
        this.visualizer.stop();
        this.audioSources.clear();
        this.stopSpeechVisualizationSimulation();

        if (this.sourceMonitorInterval) {
            clearInterval(this.sourceMonitorInterval);
        }

        if (this.audioObserver) {
            this.audioObserver.disconnect();
        }
    }

    getConnectedSources() {
        return Array.from(this.audioSources);
    }

    destroy() {
        this.disconnect();
        console.log('🔗 Voice Integration destroyed');
    }
}

// Auto-integration when visualizer is available
if (typeof window !== 'undefined') {
    window.VoiceIntegration = VoiceIntegration;

    // Auto-connect when voice visualizer is ready
    document.addEventListener('DOMContentLoaded', () => {
        if (window.voiceVisualizer) {
            window.voiceIntegration = new VoiceIntegration(window.voiceVisualizer);
            console.log('🔗 Auto-connected voice integration');
        } else {
            // Wait for visualizer to be ready
            let attempts = 0;
            const waitForVisualizer = setInterval(() => {
                if (window.voiceVisualizer || attempts > 20) {
                    clearInterval(waitForVisualizer);
                    if (window.voiceVisualizer) {
                        window.voiceIntegration = new VoiceIntegration(window.voiceVisualizer);
                        console.log('🔗 Auto-connected voice integration (delayed)');
                    }
                }
                attempts++;
            }, 500);
        }
    });
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = VoiceIntegration;
}
