// A.L.F.R.E.D. Web Interface JavaScript

// Global configuration
const config = {
    refreshInterval: 15000, // 15 seconds
    toastDuration: 5000,    // 5 seconds
    apiTimeout: 10000       // 10 seconds
};

// Utility functions
function showToast(message, type = 'info', duration = config.toastDuration) {
    const toastContainer = document.querySelector('.toast-container') || createToastContainer();
    const toast = createToast(message, type);
    toastContainer.appendChild(toast);
    
    const bsToast = new bootstrap.Toast(toast, { delay: duration });
    bsToast.show();
    
    // Remove toast element after it's hidden
    toast.addEventListener('hidden.bs.toast', () => {
        toast.remove();
    });
}

function createToastContainer() {
    const container = document.createElement('div');
    container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
    container.style.zIndex = '11';
    document.body.appendChild(container);
    return container;
}

function createToast(message, type) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.setAttribute('role', 'alert');
    
    const iconClass = {
        success: 'fas fa-check-circle text-success',
        error: 'fas fa-exclamation-circle text-danger',
        warning: 'fas fa-exclamation-triangle text-warning',
        info: 'fas fa-info-circle text-primary'
    }[type] || 'fas fa-info-circle text-primary';
    
    toast.innerHTML = `
        <div class="toast-header">
            <i class="${iconClass} me-2"></i>
            <strong class="me-auto">A.L.F.R.E.D.</strong>
            <small>now</small>
            <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
        </div>
        <div class="toast-body">
            ${message}
        </div>
    `;
    
    return toast;
}

function setButtonLoading(button, loadingText, originalText = null) {
    if (!originalText) {
        originalText = button.innerHTML;
    }
    
    button.dataset.originalText = originalText;
    button.innerHTML = `<i class="fas fa-spinner fa-spin me-1"></i>${loadingText}`;
    button.disabled = true;
    
    return originalText;
}

function resetButton(button, delay = 0) {
    setTimeout(() => {
        const originalText = button.dataset.originalText;
        if (originalText) {
            button.innerHTML = originalText;
            button.disabled = false;
            delete button.dataset.originalText;
        }
    }, delay);
}

function formatTime(timestamp) {
    return new Date(timestamp).toLocaleTimeString();
}

function formatDateTime(timestamp) {
    const date = new Date(timestamp);
    return `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;
}

function getRelativeTime(timestamp) {
    const now = new Date();
    const time = new Date(timestamp);
    const diffMs = now - time;
    const diffSecs = Math.floor(diffMs / 1000);
    const diffMins = Math.floor(diffSecs / 60);
    const diffHours = Math.floor(diffMins / 60);
    
    if (diffSecs < 60) {
        return 'just now';
    } else if (diffMins < 60) {
        return `${diffMins}m ago`;
    } else if (diffHours < 24) {
        return `${diffHours}h ago`;
    } else {
        return formatDateTime(timestamp);
    }
}

// API functions
async function apiCall(url, options = {}) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), config.apiTimeout);
    
    try {
        const response = await fetch(url, {
            ...options,
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return await response.json();
    } catch (error) {
        clearTimeout(timeoutId);
        if (error.name === 'AbortError') {
            throw new Error('Request timeout');
        }
        throw error;
    }
}

async function discoverAgents() {
    try {
        const data = await apiCall('/api/discover', { method: 'POST' });
        showToast('Agent discovery initiated successfully', 'success');
        return data;
    } catch (error) {
        showToast(`Discovery failed: ${error.message}`, 'error');
        throw error;
    }
}

async function healthCheckAgents() {
    try {
        const data = await apiCall('/api/health-check', { method: 'POST' });
        showToast('Health check completed', 'success');
        return data;
    } catch (error) {
        showToast(`Health check failed: ${error.message}`, 'error');
        throw error;
    }
}

async function getAgentStatus() {
    try {
        const data = await apiCall('/api/agents');
        return data.agents;
    } catch (error) {
        console.error('Failed to get agent status:', error);
        return [];
    }
}

// Auto-refresh functionality
let refreshTimer = null;

function startAutoRefresh(callback, interval = config.refreshInterval) {
    stopAutoRefresh();
    refreshTimer = setInterval(callback, interval);
}

function stopAutoRefresh() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
    }
}

// Page-specific functionality
function initializeDashboard() {
    // Auto-refresh agents on dashboard
    startAutoRefresh(async () => {
        try {
            const agents = await getAgentStatus();
            updateAgentsTable(agents);
            updateAgentStats(agents);
        } catch (error) {
            console.error('Auto-refresh failed:', error);
        }
    });
}

function updateAgentsTable(agents) {
    const tbody = document.getElementById('agents-table');
    if (!tbody) return;
    
    tbody.innerHTML = agents.map(agent => `
        <tr>
            <td><strong>${agent.name}</strong></td>
            <td>
                <i class="fab fa-${agent.os_type === 'Windows' ? 'windows' : 'linux'} me-1"></i>
                ${agent.os_type}
            </td>
            <td><code>${agent.host}:${agent.port}</code></td>
            <td>
                <span class="badge bg-${agent.is_healthy ? 'success' : 'danger'}">
                    <i class="fas fa-${agent.is_healthy ? 'check-circle' : 'times-circle'} me-1"></i>
                    ${agent.is_healthy ? 'Healthy' : 'Unhealthy'}
                </span>
            </td>
            <td>
                <small class="text-muted" title="${formatDateTime(agent.last_seen)}">
                    ${getRelativeTime(agent.last_seen)}
                </small>
            </td>
        </tr>
    `).join('');
}

function updateAgentStats(agents) {
    const totalCount = agents.length;
    const healthyCount = agents.filter(agent => agent.is_healthy).length;
    const unhealthyCount = totalCount - healthyCount;
    
    // Update stat cards
    const totalElement = document.querySelector('.card.bg-primary .card-body h2');
    const healthyElement = document.querySelector('.card.bg-success .card-body h2');
    const unhealthyElement = document.querySelector('.card.bg-warning .card-body h2, .card.bg-secondary .card-body h2');
    
    if (totalElement) totalElement.textContent = totalCount;
    if (healthyElement) healthyElement.textContent = healthyCount;
    if (unhealthyElement) unhealthyElement.textContent = unhealthyCount;
    
    // Update unhealthy card color
    const unhealthyCard = document.querySelector('.card.bg-warning, .card.bg-secondary');
    if (unhealthyCard) {
        unhealthyCard.className = unhealthyCard.className
            .replace('bg-warning', unhealthyCount > 0 ? 'bg-warning' : 'bg-secondary')
            .replace('bg-secondary', unhealthyCount > 0 ? 'bg-warning' : 'bg-secondary');
    }
}

// Command execution helpers
function setQuickCommand(command) {
    const commandInput = document.getElementById('command');
    if (commandInput) {
        commandInput.value = command;
        commandInput.focus();
    }
}

function clearCommand() {
    const commandInput = document.getElementById('command');
    if (commandInput) {
        commandInput.value = '';
        commandInput.focus();
    }
}

// Initialize page-specific functionality when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Check which page we're on and initialize accordingly
    const currentPage = window.location.pathname;
    
    if (currentPage === '/' || currentPage === '/dashboard') {
        initializeDashboard();
    }
    
    // Global keyboard shortcuts
    document.addEventListener('keydown', function(event) {
        // Ctrl/Cmd + K to focus search or command input
        if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
            event.preventDefault();
            const commandInput = document.getElementById('command') || 
                               document.querySelector('input[type="search"]');
            if (commandInput) {
                commandInput.focus();
                commandInput.select();
            }
        }
        
        // Escape to clear focused input
        if (event.key === 'Escape') {
            const activeElement = document.activeElement;
            if (activeElement && (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA')) {
                activeElement.blur();
            }
        }
    });
});

// Clean up on page unload
window.addEventListener('beforeunload', function() {
    stopAutoRefresh();
});

// Global error handler
window.addEventListener('error', function(event) {
    console.error('Global error:', event.error);
    showToast('An unexpected error occurred', 'error');
});

// Export functions for global use
window.ALFREDWebInterface = {
    showToast,
    discoverAgents,
    healthCheckAgents,
    getAgentStatus,
    setQuickCommand,
    clearCommand,
    setButtonLoading,
    resetButton
};