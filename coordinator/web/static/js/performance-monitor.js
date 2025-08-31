// A.L.F.R.E.D. Performance Monitor for Voice Visualizer
// Monitors and optimizes visualizer performance to meet <5% CPU usage target

class PerformanceMonitor {
    constructor(visualizer) {
        this.visualizer = visualizer;
        this.metrics = {
            frameCount: 0,
            startTime: performance.now(),
            lastFrameTime: 0,
            cpuUsage: 0,
            memoryUsage: 0,
            droppedFrames: 0,
            averageFPS: 0
        };
        
        this.config = {
            targetFPS: 60,
            maxCPUUsage: 5, // 5% target
            maxMemoryMB: 50, // 50MB target
            monitorInterval: 1000, // Monitor every second
            performanceWindow: 30 // 30 second rolling average
        };
        
        this.performanceHistory = [];
        this.isMonitoring = false;
        this.optimizationLevel = 0; // 0 = no optimization, 3 = maximum optimization
        
        this.init();
    }
    
    init() {
        this.setupPerformanceObserver();
        this.startMonitoring();
        console.log('📊 Performance Monitor initialized');
    }
    
    setupPerformanceObserver() {
        if ('PerformanceObserver' in window) {
            try {
                this.perfObserver = new PerformanceObserver((list) => {
                    const entries = list.getEntries();
                    entries.forEach(entry => {
                        if (entry.entryType === 'measure' && entry.name.includes('voice-visualizer')) {
                            this.updatePerformanceMetrics(entry);
                        }
                    });
                });
                
                this.perfObserver.observe({ entryTypes: ['measure', 'navigation', 'resource'] });
            } catch (error) {
                console.warn('📊 Performance Observer not available:', error);
            }
        }
    }
    
    startMonitoring() {
        if (this.isMonitoring) return;
        this.isMonitoring = true;
        
        this.monitorInterval = setInterval(() => {
            this.collectMetrics();
            this.analyzePerformance();
            this.optimizeIfNeeded();
        }, this.config.monitorInterval);
        
        // Frame-by-frame monitoring
        this.frameMonitor();
    }
    
    stopMonitoring() {
        this.isMonitoring = false;
        
        if (this.monitorInterval) {
            clearInterval(this.monitorInterval);
        }
        
        if (this.frameAnimationId) {
            cancelAnimationFrame(this.frameAnimationId);
        }
    }
    
    frameMonitor() {
        if (!this.isMonitoring) return;
        
        const currentTime = performance.now();
        const deltaTime = currentTime - this.metrics.lastFrameTime;
        
        // Track frame timing
        if (this.metrics.lastFrameTime > 0) {
            const fps = 1000 / deltaTime;
            this.updateFPS(fps);
            
            // Detect dropped frames (>20ms = dropped frame at 60fps)
            if (deltaTime > 20) {
                this.metrics.droppedFrames++;
            }
        }
        
        this.metrics.lastFrameTime = currentTime;
        this.metrics.frameCount++;
        
        // Performance measurement for render cycle
        performance.mark('voice-visualizer-frame-start');
        
        this.frameAnimationId = requestAnimationFrame(() => {
            performance.mark('voice-visualizer-frame-end');
            performance.measure('voice-visualizer-frame', 'voice-visualizer-frame-start', 'voice-visualizer-frame-end');
            this.frameMonitor();
        });
    }
    
    collectMetrics() {
        // CPU usage estimation (based on frame timing)
        const currentTime = performance.now();
        const elapsedTime = currentTime - this.metrics.startTime;
        const expectedFrames = (elapsedTime / 1000) * this.config.targetFPS;
        const frameRatio = this.metrics.frameCount / expectedFrames;
        
        // Rough CPU usage estimation
        this.metrics.cpuUsage = Math.max(0, Math.min(100, (1 - frameRatio) * 100));
        
        // Memory usage (if available)
        if (performance.memory) {
            this.metrics.memoryUsage = performance.memory.usedJSHeapSize / (1024 * 1024); // MB
        }
        
        // Average FPS
        this.metrics.averageFPS = this.metrics.frameCount / (elapsedTime / 1000);
        
        // Store in history
        this.performanceHistory.push({
            timestamp: currentTime,
            fps: this.metrics.averageFPS,
            cpuUsage: this.metrics.cpuUsage,
            memoryUsage: this.metrics.memoryUsage,
            droppedFrames: this.metrics.droppedFrames
        });
        
        // Keep only recent history
        const cutoffTime = currentTime - (this.config.performanceWindow * 1000);
        this.performanceHistory = this.performanceHistory.filter(entry => entry.timestamp > cutoffTime);
    }
    
    updateFPS(instantFPS) {
        // Smooth FPS calculation
        if (!this.smoothFPS) {
            this.smoothFPS = instantFPS;
        } else {
            this.smoothFPS = this.smoothFPS * 0.9 + instantFPS * 0.1;
        }
    }
    
    analyzePerformance() {
        if (this.performanceHistory.length < 5) return; // Need some data first
        
        const recent = this.performanceHistory.slice(-10);
        const avgFPS = recent.reduce((sum, entry) => sum + entry.fps, 0) / recent.length;
        const avgCPU = recent.reduce((sum, entry) => sum + entry.cpuUsage, 0) / recent.length;
        const avgMemory = recent.reduce((sum, entry) => sum + entry.memoryUsage, 0) / recent.length;
        
        this.currentPerformance = {
            fps: avgFPS,
            cpuUsage: avgCPU,
            memoryUsage: avgMemory,
            droppedFrameRate: this.metrics.droppedFrames / this.metrics.frameCount
        };
        
        // Performance warnings
        if (avgFPS < 50) {
            console.warn('📊 Low FPS detected:', avgFPS.toFixed(1));
        }
        
        if (avgCPU > this.config.maxCPUUsage) {
            console.warn('📊 High CPU usage detected:', avgCPU.toFixed(1) + '%');
        }
        
        if (avgMemory > this.config.maxMemoryMB) {
            console.warn('📊 High memory usage detected:', avgMemory.toFixed(1) + 'MB');
        }
    }
    
    optimizeIfNeeded() {
        if (!this.currentPerformance) return;
        
        const needsOptimization = 
            this.currentPerformance.fps < 50 ||
            this.currentPerformance.cpuUsage > this.config.maxCPUUsage ||
            this.currentPerformance.memoryUsage > this.config.maxMemoryMB ||
            this.currentPerformance.droppedFrameRate > 0.1;
        
        if (needsOptimization && this.optimizationLevel < 3) {
            this.increaseOptimization();
        } else if (!needsOptimization && this.optimizationLevel > 0) {
            this.decreaseOptimization();
        }
    }
    
    increaseOptimization() {
        this.optimizationLevel = Math.min(3, this.optimizationLevel + 1);
        this.applyOptimizations();
        console.log('📊 Increasing optimization level to:', this.optimizationLevel);
    }
    
    decreaseOptimization() {
        this.optimizationLevel = Math.max(0, this.optimizationLevel - 1);
        this.applyOptimizations();
        console.log('📊 Decreasing optimization level to:', this.optimizationLevel);
    }
    
    applyOptimizations() {
        if (!this.visualizer || !this.visualizer.config) return;
        
        const config = this.visualizer.config;
        const originalConfig = this.originalConfig || { ...config };
        
        // Store original config on first optimization
        if (!this.originalConfig) {
            this.originalConfig = { ...config };
        }
        
        switch (this.optimizationLevel) {
            case 0: // No optimization
                Object.assign(config, originalConfig);
                break;
                
            case 1: // Light optimization
                config.segments = Math.min(originalConfig.segments, 48);
                config.smoothing = Math.max(originalConfig.smoothing, 0.9);
                break;
                
            case 2: // Medium optimization  
                config.segments = Math.min(originalConfig.segments, 32);
                config.smoothing = Math.max(originalConfig.smoothing, 0.92);
                config.fftSize = Math.min(originalConfig.fftSize, 512);
                break;
                
            case 3: // Maximum optimization
                config.segments = Math.min(originalConfig.segments, 24);
                config.smoothing = Math.max(originalConfig.smoothing, 0.95);
                config.fftSize = Math.min(originalConfig.fftSize, 256);
                config.lineWidth = Math.max(1, originalConfig.lineWidth - 1);
                break;
        }
        
        // Update visualizer
        if (this.visualizer.updateConfig) {
            this.visualizer.updateConfig(config);
        }
    }
    
    updatePerformanceMetrics(entry) {
        // Process performance measurement entries
        if (entry.name === 'voice-visualizer-frame') {
            this.frameRenderTime = entry.duration;
            
            // High render time indicates performance issues
            if (entry.duration > 16) { // 16ms = 60fps budget
                this.slowFrames = (this.slowFrames || 0) + 1;
            }
        }
    }
    
    // Public API
    getPerformanceStats() {
        return {
            current: this.currentPerformance || {},
            metrics: { ...this.metrics },
            optimizationLevel: this.optimizationLevel,
            history: this.performanceHistory.slice(-60), // Last minute
            averageFPS: this.smoothFPS || 0
        };
    }
    
    setTargets(targets) {
        Object.assign(this.config, targets);
        console.log('📊 Performance targets updated:', targets);
    }
    
    forceOptimization(level) {
        this.optimizationLevel = Math.max(0, Math.min(3, level));
        this.applyOptimizations();
        console.log('📊 Forced optimization level:', level);
    }
    
    logPerformanceReport() {
        const stats = this.getPerformanceStats();
        
        console.group('📊 Voice Visualizer Performance Report');
        console.log('Average FPS:', stats.averageFPS?.toFixed(1) || 'N/A');
        console.log('CPU Usage:', stats.current.cpuUsage?.toFixed(1) + '%' || 'N/A');
        console.log('Memory Usage:', stats.current.memoryUsage?.toFixed(1) + 'MB' || 'N/A');
        console.log('Dropped Frame Rate:', (stats.current.droppedFrameRate * 100)?.toFixed(1) + '%' || 'N/A');
        console.log('Optimization Level:', stats.optimizationLevel);
        console.log('Total Frames:', stats.metrics.frameCount);
        console.groupEnd();
    }
    
    destroy() {
        this.stopMonitoring();
        
        if (this.perfObserver) {
            this.perfObserver.disconnect();
        }
        
        console.log('📊 Performance Monitor destroyed');
    }
}

// Export and global access
if (typeof window !== 'undefined') {
    window.PerformanceMonitor = PerformanceMonitor;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = PerformanceMonitor;
}