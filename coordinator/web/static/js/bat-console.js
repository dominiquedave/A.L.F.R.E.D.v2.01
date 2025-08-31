// A.L.F.R.E.D. Bat Cave Console JavaScript

class BatConsole {
    constructor() {
        this.websocket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectInterval = 5000;
        this.agentStatusInterval = null;
        
        this.init();
    }
    
    init() {
        this.connectWebSocket();
        this.setupEventListeners();
        this.startPeriodicUpdates();
        this.setupNotifications();
        
        // Add some atmospheric effects
        this.addAtmosphericEffects();
    }
    
    // WebSocket Connection
    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        try {
            this.websocket = new WebSocket(wsUrl);
            
            this.websocket.onopen = () => {
                console.log('🦇 Connected to Bat Cave Console');
                this.reconnectAttempts = 0;
                this.updateConnectionStatus('Connected to Lair', true);
                this.showNotification('Connected to the Bat Cave', 'success');
            };
            
            this.websocket.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            };
            
            this.websocket.onclose = () => {
                console.log('🦇 Disconnected from Bat Cave Console');
                this.updateConnectionStatus('Connection Lost', false);
                this.attemptReconnect();
            };
            
            this.websocket.onerror = (error) => {
                console.error('🦇 WebSocket error:', error);
                this.updateConnectionStatus('Connection Error', false);
            };
            
        } catch (error) {
            console.error('🦇 Failed to create WebSocket:', error);
            this.updateConnectionStatus('Connection Failed', false);
        }
    }
    
    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'connection_established':
                console.log('🦇 Connection established:', data.message);
                break;
                
            case 'command_result':
                this.updateCommandHistory(data);
                break;
                
            case 'agent_status_update':
                this.updateAgentCount(data.healthy_count, data.total_count);
                break;
                
            case 'agents_discovered':
                this.showNotification(`Discovery complete! Found ${data.count} agents.`, 'success');
                setTimeout(() => {
                    window.location.reload();
                }, 2000);
                break;
                
            default:
                console.log('🦇 Unknown message type:', data.type);
        }
    }
    
    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`🦇 Attempting to reconnect... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
            
            setTimeout(() => {
                this.connectWebSocket();
            }, this.reconnectInterval);
            
            this.updateConnectionStatus(`Reconnecting... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`, false);
        } else {
            console.log('🦇 Max reconnection attempts reached');
            this.updateConnectionStatus('Connection Failed', false);
            this.showNotification('Connection to Bat Cave lost. Please refresh the page.', 'error');
        }
    }
    
    // UI Updates
    updateConnectionStatus(status, connected) {
        const statusElement = document.getElementById('connection-status');
        const dot = statusElement?.querySelector('.pulse-dot');
        
        if (statusElement) {
            statusElement.innerHTML = `
                <span class="pulse-dot ${connected ? 'pulse-green' : 'pulse-red'}"></span>
                ${status}
            `;
        }
    }
    
    updateAgentCount(healthy, total) {
        const agentCountElement = document.getElementById('agent-count');
        if (agentCountElement) {
            agentCountElement.textContent = `${healthy}/${total}`;
        }
    }
    
    updateLastUpdateTime() {
        const lastUpdateElement = document.getElementById('last-update');
        if (lastUpdateElement) {
            lastUpdateElement.textContent = new Date().toLocaleTimeString();
        }
    }
    
    updateCommandHistory(data) {
        // This would update a command history display if present
        console.log('🦇 Command executed:', data.command, 'Result:', data.result.success);
    }
    
    // Event Listeners
    setupEventListeners() {
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Ctrl+Shift+D for discovery
            if (e.ctrlKey && e.shiftKey && e.key === 'D') {
                e.preventDefault();
                this.discoverAgents();
            }
            
            // Escape to focus command input
            if (e.key === 'Escape') {
                const commandInput = document.getElementById('command-input');
                if (commandInput) {
                    commandInput.focus();
                    commandInput.select();
                }
            }
        });
        
        // Click effects
        document.addEventListener('click', (e) => {
            // Add ripple effect to buttons
            if (e.target.matches('button, .btn-primary, .nav-link')) {
                this.createRippleEffect(e.target, e);
            }
        });
        
        // Auto-refresh system status
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                this.refreshAgentStatus();
            }
        });
    }
    
    // Periodic Updates
    startPeriodicUpdates() {
        // Update last update time every second
        setInterval(() => {
            this.updateLastUpdateTime();
        }, 1000);
        
        // Refresh agent status every 30 seconds
        this.agentStatusInterval = setInterval(() => {
            this.refreshAgentStatus();
        }, 30000);
    }
    
    // API Interactions
    async discoverAgents() {
        try {
            this.showNotification('🔍 Scanning territory for agents...', 'info');
            
            const response = await fetch('/agents/discover', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showNotification(result.message, 'success');
            } else {
                this.showNotification(`Discovery failed: ${result.error}`, 'error');
            }
            
        } catch (error) {
            console.error('🦇 Discovery error:', error);
            this.showNotification('Discovery failed: Network error', 'error');
        }
    }
    
    async refreshAgentStatus() {
        try {
            const response = await fetch('/agents/status');
            const data = await response.json();
            
            this.updateAgentCount(data.healthy_count, data.total_count);
            
            // Update agent cards if present
            this.updateAgentCards(data.agents);
            
        } catch (error) {
            console.error('🦇 Status refresh error:', error);
        }
    }
    
    updateAgentCards(agents) {
        agents.forEach(agent => {
            const agentCard = document.querySelector(`[data-agent-id="${agent.id}"]`);
            if (agentCard) {
                const statusDot = agentCard.querySelector('.status-dot');
                const lastSeenElement = agentCard.querySelector('.detail-value:last-child');
                
                if (statusDot) {
                    statusDot.className = `status-dot ${agent.is_healthy ? 'pulse-green' : 'pulse-red'}`;
                }
                
                if (lastSeenElement) {
                    const lastSeen = new Date(agent.last_seen);
                    lastSeenElement.textContent = lastSeen.toLocaleTimeString();
                }
                
                // Update card class
                agentCard.className = agentCard.className.replace(/\b(healthy|unhealthy)\b/g, '');
                agentCard.classList.add(agent.is_healthy ? 'healthy' : 'unhealthy');
            }
        });
    }
    
    // Visual Effects
    createRippleEffect(element, event) {
        const ripple = document.createElement('span');
        const rect = element.getBoundingClientRect();
        const size = Math.max(rect.width, rect.height);
        const x = event.clientX - rect.left - size / 2;
        const y = event.clientY - rect.top - size / 2;
        
        ripple.style.cssText = `
            position: absolute;
            width: ${size}px;
            height: ${size}px;
            left: ${x}px;
            top: ${y}px;
            background: rgba(255, 255, 255, 0.3);
            border-radius: 50%;
            transform: scale(0);
            animation: ripple 0.6s linear;
            pointer-events: none;
        `;
        
        // Add ripple styles to head if not present
        if (!document.querySelector('#ripple-styles')) {
            const style = document.createElement('style');
            style.id = 'ripple-styles';
            style.textContent = `
                @keyframes ripple {
                    to {
                        transform: scale(2);
                        opacity: 0;
                    }
                }
            `;
            document.head.appendChild(style);
        }
        
        // Ensure element is relatively positioned
        const position = getComputedStyle(element).position;
        if (position === 'static') {
            element.style.position = 'relative';
        }
        element.style.overflow = 'hidden';
        
        element.appendChild(ripple);
        
        setTimeout(() => {
            ripple.remove();
        }, 600);
    }
    
    addAtmosphericEffects() {
        
        // Add floating particles
        this.createFloatingParticles();
        
        // Dynamic title updates
        this.updateDynamicTitle();
    }
    
    createFloatingParticles() {
        const particleContainer = document.createElement('div');
        particleContainer.className = 'particle-container';
        particleContainer.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: -1;
            overflow: hidden;
        `;
        
        document.body.appendChild(particleContainer);
        
        // Create particles
        for (let i = 0; i < 20; i++) {
            this.createParticle(particleContainer);
        }
    }
    
    createParticle(container) {
        const particle = document.createElement('div');
        particle.style.cssText = `
            position: absolute;
            width: 2px;
            height: 2px;
            background: rgba(106, 13, 173, 0.3);
            border-radius: 50%;
            animation: float ${5 + Math.random() * 10}s linear infinite;
            left: ${Math.random() * 100}%;
            animation-delay: ${Math.random() * 10}s;
        `;
        
        container.appendChild(particle);
        
        // Remove and recreate after animation
        setTimeout(() => {
            particle.remove();
            this.createParticle(container);
        }, (5 + Math.random() * 10) * 1000);
    }
    
    updateDynamicTitle() {
        const originalTitle = document.title;
        let titleIndex = 0;
        const titleVariations = [
            originalTitle,
            '🦇 ' + originalTitle,
            '⚡ ' + originalTitle,
            '🌙 ' + originalTitle
        ];
        
        setInterval(() => {
            if (document.hidden) {
                document.title = titleVariations[titleIndex % titleVariations.length];
                titleIndex++;
            } else {
                document.title = originalTitle;
                titleIndex = 0;
            }
        }, 2000);
    }
    
    // Notifications
    setupNotifications() {
        const notificationContainer = document.getElementById('notifications');
        if (!notificationContainer) {
            const container = document.createElement('div');
            container.id = 'notifications';
            container.className = 'notifications-container';
            document.body.appendChild(container);
        }
    }
    
    showNotification(message, type = 'info', duration = 5000) {
        const container = document.getElementById('notifications');
        if (!container) return;
        
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        
        const icon = type === 'success' ? '✅' : 
                    type === 'error' ? '❌' : 
                    type === 'warning' ? '⚠️' : '🌙';
        
        notification.innerHTML = `
            <div style="display: flex; align-items: center; gap: 0.5rem;">
                <span style="font-size: 1.2rem;">${icon}</span>
                <span>${message}</span>
                <button onclick="this.parentElement.parentElement.remove()" 
                        style="margin-left: auto; background: none; border: none; color: white; cursor: pointer; font-size: 1.2rem;">×</button>
            </div>
        `;
        
        container.appendChild(notification);
        
        // Auto-remove after duration
        if (duration > 0) {
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.style.animation = 'slide-out 0.3s ease forwards';
                    setTimeout(() => {
                        notification.remove();
                    }, 300);
                }
            }, duration);
        }
    }
}

// Global functions
function discoverAgents() {
    if (window.batConsole) {
        window.batConsole.discoverAgents();
    }
}

// Add particle float animation
const particleStyles = document.createElement('style');
particleStyles.textContent = `
    @keyframes float {
        0% {
            transform: translateY(100vh) translateX(0px);
            opacity: 0;
        }
        10% {
            opacity: 0.5;
        }
        90% {
            opacity: 0.5;
        }
        100% {
            transform: translateY(-10vh) translateX(${Math.random() * 200 - 100}px);
            opacity: 0;
        }
    }
    
    @keyframes slide-out {
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(particleStyles);

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.batConsole = new BatConsole();
    console.log('🦇 Bat Cave Console initialized');
});

// Add some debug helpers
window.batDebug = {
    showNotification: (msg, type) => window.batConsole?.showNotification(msg, type),
    discoverAgents: () => window.batConsole?.discoverAgents(),
    refreshStatus: () => window.batConsole?.refreshAgentStatus()
};