// A.L.F.R.E.D. Voice Visualizer - Geometric Radial Audio Waveform
// Electric blue themed radial waveform that responds to AI voice frequency data

class VoiceVisualizer {
    constructor(canvasId, options = {}) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        
        // Configuration
        this.config = {
            // Visual settings
            centerRadius: options.centerRadius || 30,
            maxRadius: options.maxRadius || 150,
            segments: options.segments || 64,
            lineWidth: options.lineWidth || 2,
            
            // Colors (matching bat-theme.css)
            primaryColor: options.primaryColor || '#00FFFF', // --bat-electric
            secondaryColor: options.secondaryColor || '#0B0B0B', // --bat-black
            glowColor: options.glowColor || '#00FFFF',
            
            // Animation
            animationSpeed: options.animationSpeed || 0.1,
            smoothing: options.smoothing || 0.85,
            rotationSpeed: options.rotationSpeed || 0.005,
            
            // Audio processing
            fftSize: options.fftSize || 1024,
            minDecibels: options.minDecibels || -100,
            maxDecibels: options.maxDecibels || -30,
            sampleRate: options.sampleRate || 44100
        };
        
        // State
        this.isActive = false;
        this.audioContext = null;
        this.analyser = null;
        this.mediaSource = null;
        this.frequencyData = new Uint8Array(this.config.fftSize / 2);
        this.smoothedData = new Float32Array(this.config.segments);
        this.rotation = 0;
        this.animationId = null;
        
        // Error handling
        this.errorState = false;
        this.errorMessage = '';
        
        this.init();
    }
    
    init() {
        this.setupCanvas();
        this.setupErrorHandling();
        
        // Start with idle state (static orb)
        this.setState('idle');
        this.startRenderLoop();
        
        console.log('🦇 Voice Visualizer initialized');
    }
    
    setupCanvas() {
        // Set canvas size and high DPI support
        const resizeCanvas = () => {
            const rect = this.canvas.getBoundingClientRect();
            const dpr = window.devicePixelRatio || 1;
            
            this.canvas.width = rect.width * dpr;
            this.canvas.height = rect.height * dpr;
            
            this.ctx.scale(dpr, dpr);
            
            // Preserve existing CSS styles while setting dimensions
            const currentStyle = window.getComputedStyle(this.canvas);
            this.canvas.style.width = rect.width + 'px';
            this.canvas.style.height = rect.height + 'px';
            
            // Ensure centering styles are maintained
            if (currentStyle.display !== 'block') {
                this.canvas.style.display = 'block';
            }
            if (currentStyle.marginLeft === '0px' && currentStyle.marginRight === '0px') {
                this.canvas.style.margin = '0 auto';
            }
            
            // Update center and max radius based on canvas size
            this.centerX = rect.width / 2;
            this.centerY = rect.height / 2;
            this.config.maxRadius = Math.min(rect.width, rect.height) / 2 - 20;
        };
        
        resizeCanvas();
        window.addEventListener('resize', resizeCanvas);
    }
    
    setupErrorHandling() {
        window.addEventListener('error', (e) => {
            this.handleError('Runtime error', e.error);
        });
        
        window.addEventListener('unhandledrejection', (e) => {
            this.handleError('Promise rejection', e.reason);
        });
    }
    
    handleError(type, error) {
        console.error(`🦇 Voice Visualizer ${type}:`, error);
        this.errorState = true;
        this.errorMessage = `${type}: ${error.message || error}`;
        this.setState('error');
    }
    
    // Audio setup and management
    async setupAudio() {
        try {
            if (!this.audioContext) {
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            }
            
            // Resume context if suspended (required by browser policies)
            if (this.audioContext.state === 'suspended') {
                await this.audioContext.resume();
            }
            
            // Create analyzer
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = this.config.fftSize;
            this.analyser.minDecibels = this.config.minDecibels;
            this.analyser.maxDecibels = this.config.maxDecibels;
            this.analyser.smoothingTimeConstant = this.config.smoothing;
            
            this.frequencyData = new Uint8Array(this.analyser.frequencyBinCount);
            
            console.log('🎵 Audio context initialized');
            return true;
        } catch (error) {
            this.handleError('Audio setup failed', error);
            return false;
        }
    }
    
    // Connect to audio source (for live AI voice)
    async connectToAudioSource(audioElement) {
        try {
            if (!await this.setupAudio()) return false;
            
            // Connect HTML audio element to analyzer
            if (audioElement && audioElement.captureStream) {
                const stream = audioElement.captureStream();
                this.mediaSource = this.audioContext.createMediaStreamSource(stream);
            } else if (audioElement) {
                this.mediaSource = this.audioContext.createMediaElementSource(audioElement);
            }
            
            if (this.mediaSource) {
                this.mediaSource.connect(this.analyser);
                this.setState('active');
                console.log('🎵 Connected to audio source');
                return true;
            }
            
            return false;
        } catch (error) {
            this.handleError('Audio connection failed', error);
            return false;
        }
    }
    
    // Connect to microphone input
    async connectToMicrophone() {
        try {
            if (!await this.setupAudio()) return false;
            
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.mediaSource = this.audioContext.createMediaStreamSource(stream);
            this.mediaSource.connect(this.analyser);
            
            this.setState('active');
            console.log('🎤 Connected to microphone');
            return true;
        } catch (error) {
            this.handleError('Microphone access failed', error);
            return false;
        }
    }
    
    disconnect() {
        if (this.mediaSource) {
            this.mediaSource.disconnect();
            this.mediaSource = null;
        }
        
        this.setState('idle');
        console.log('🔇 Audio disconnected');
    }
    
    // State management
    setState(state) {
        this.currentState = state;
        
        switch (state) {
            case 'idle':
                this.isActive = false;
                break;
            case 'active':
                this.isActive = true;
                this.errorState = false;
                break;
            case 'error':
                this.isActive = false;
                break;
        }
    }
    
    // Frequency data processing
    processFrequencyData() {
        if (!this.analyser || !this.isActive) return;
        
        this.analyser.getByteFrequencyData(this.frequencyData);
        
        // Map frequency data to segments
        const samplesPerSegment = Math.floor(this.frequencyData.length / this.config.segments);
        
        for (let i = 0; i < this.config.segments; i++) {
            let sum = 0;
            const start = i * samplesPerSegment;
            const end = start + samplesPerSegment;
            
            for (let j = start; j < end; j++) {
                sum += this.frequencyData[j];
            }
            
            const average = sum / samplesPerSegment;
            const normalized = average / 255; // Normalize to 0-1
            
            // Apply smoothing
            this.smoothedData[i] = this.smoothedData[i] * this.config.smoothing + 
                                  normalized * (1 - this.config.smoothing);
        }
    }
    
    // Rendering methods
    startRenderLoop() {
        const render = () => {
            this.render();
            this.animationId = requestAnimationFrame(render);
        };
        render();
    }
    
    stopRenderLoop() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
    }
    
    render() {
        this.clearCanvas();
        
        if (this.errorState) {
            this.renderErrorState();
        } else if (this.isActive) {
            this.processFrequencyData();
            this.renderActiveWaveform();
        } else {
            this.renderIdleOrb();
        }
        
        this.rotation += this.config.rotationSpeed;
    }
    
    clearCanvas() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    }
    
    renderIdleOrb() {
        const ctx = this.ctx;
        const { centerX, centerY } = this;
        const radius = this.config.centerRadius + Math.sin(Date.now() * 0.003) * 5;
        
        // Glow effect
        ctx.save();
        ctx.shadowColor = this.config.glowColor;
        ctx.shadowBlur = 20;
        
        // Outer ring
        ctx.beginPath();
        ctx.strokeStyle = this.config.primaryColor;
        ctx.lineWidth = this.config.lineWidth;
        ctx.arc(centerX, centerY, radius + 10, 0, Math.PI * 2);
        ctx.stroke();
        
        // Inner orb
        ctx.beginPath();
        ctx.fillStyle = this.config.primaryColor + '40'; // 25% opacity
        ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
        ctx.fill();
        
        ctx.restore();
    }
    
    renderActiveWaveform() {
        const ctx = this.ctx;
        const { centerX, centerY } = this;
        
        ctx.save();
        ctx.translate(centerX, centerY);
        ctx.rotate(this.rotation);
        
        // Glow effect
        ctx.shadowColor = this.config.glowColor;
        ctx.shadowBlur = 15;
        
        // Draw radial segments
        const angleStep = (Math.PI * 2) / this.config.segments;
        
        for (let i = 0; i < this.config.segments; i++) {
            const angle = i * angleStep;
            const amplitude = this.smoothedData[i] || 0;
            const length = this.config.centerRadius + (amplitude * (this.config.maxRadius - this.config.centerRadius));
            
            const x1 = Math.cos(angle) * this.config.centerRadius;
            const y1 = Math.sin(angle) * this.config.centerRadius;
            const x2 = Math.cos(angle) * length;
            const y2 = Math.sin(angle) * length;
            
            // Color intensity based on amplitude
            const intensity = Math.min(1, amplitude + 0.3);
            ctx.strokeStyle = this.config.primaryColor + Math.floor(intensity * 255).toString(16).padStart(2, '0');
            ctx.lineWidth = this.config.lineWidth * (1 + amplitude);
            
            ctx.beginPath();
            ctx.moveTo(x1, y1);
            ctx.lineTo(x2, y2);
            ctx.stroke();
        }
        
        // Center orb
        ctx.shadowBlur = 25;
        ctx.beginPath();
        ctx.fillStyle = this.config.primaryColor + '60'; // 37% opacity
        ctx.arc(0, 0, this.config.centerRadius, 0, Math.PI * 2);
        ctx.fill();
        
        ctx.restore();
    }
    
    renderErrorState() {
        const ctx = this.ctx;
        const { centerX, centerY } = this;
        
        // Static orb with error color
        ctx.save();
        ctx.shadowColor = '#FF0000';
        ctx.shadowBlur = 20;
        
        ctx.beginPath();
        ctx.strokeStyle = '#FF0000';
        ctx.lineWidth = this.config.lineWidth;
        ctx.arc(centerX, centerY, this.config.centerRadius, 0, Math.PI * 2);
        ctx.stroke();
        
        ctx.restore();
        
        // Error text
        ctx.fillStyle = '#FF0000';
        ctx.font = '12px Orbitron';
        ctx.textAlign = 'center';
        ctx.fillText('Audio Error', centerX, centerY + this.config.centerRadius + 20);
    }
    
    // Public API methods
    async startMicrophoneInput() {
        return await this.connectToMicrophone();
    }
    
    async connectAudioElement(audioElement) {
        return await this.connectToAudioSource(audioElement);
    }
    
    stop() {
        this.disconnect();
    }
    
    destroy() {
        this.stopRenderLoop();
        this.disconnect();
        
        if (this.audioContext) {
            this.audioContext.close();
        }
        
        console.log('🦇 Voice Visualizer destroyed');
    }
    
    // Utility methods
    getState() {
        return {
            currentState: this.currentState,
            isActive: this.isActive,
            errorState: this.errorState,
            errorMessage: this.errorMessage,
            hasAudioContext: !!this.audioContext,
            hasMediaSource: !!this.mediaSource
        };
    }
    
    updateConfig(newConfig) {
        Object.assign(this.config, newConfig);
        console.log('🦇 Visualizer config updated');
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = VoiceVisualizer;
}

// Global access
window.VoiceVisualizer = VoiceVisualizer;