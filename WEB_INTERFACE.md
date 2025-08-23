# A.L.F.R.E.D. Web Interface

A modern web dashboard for monitoring and controlling your A.L.F.R.E.D. distributed system.

## ✨ Features

- **📊 Real-time Dashboard**: Monitor agent status, health, and system metrics
- **🤖 Agent Management**: View agent details, capabilities, and connection status  
- **⚡ Command Execution**: Execute commands via web interface with natural language parsing
- **📈 Auto-refresh**: Real-time updates every 15 seconds
- **🔄 Agent Discovery**: Manual and automatic agent discovery
- **📱 Responsive Design**: Works on desktop, tablet, and mobile devices

## 🚀 Quick Start

### Option 1: Standalone Web Interface
```bash
python start_web.py
```

### Option 2: Via Main Coordinator
```bash
# Web interface only
python coordinator/main.py --interface web

# Web interface on custom port
python coordinator/main.py --interface web --web-port 9000

# Both voice and web interfaces
python coordinator/main.py --interface both
```

## 📋 Requirements

Install required dependencies:
```bash
pip install fastapi uvicorn jinja2 python-multipart
```

Or install all project dependencies:
```bash
pip install -r requirements.txt
```

## 🌐 Web Interface URLs

Once running, access the interface at:

- **Dashboard**: http://localhost:8000
- **Agents**: http://localhost:8000/agents  
- **Command Execution**: http://localhost:8000/command
- **API Endpoints**: http://localhost:8000/api/*

## 🖥️ Pages

### Dashboard (`/`)
- System overview with agent counts and health status
- Recently executed commands history
- Quick action buttons for discovery and health checks
- Auto-refreshing agent status table

### Agents (`/agents`)  
- Detailed view of all discovered agents
- Agent capabilities, permissions, and system information
- Individual agent health check and connectivity testing
- Agent discovery and management controls

### Command Execution (`/command`)
- Execute commands using natural language or direct shell commands
- Quick command buttons for common operations
- Real-time command result display
- Command history and agent routing information

## 🔧 API Endpoints

The web interface exposes several API endpoints for programmatic access:

- `GET /api/agents` - Get current agent status
- `POST /api/discover` - Trigger agent discovery
- `POST /api/health-check` - Force health check on all agents

## ⚙️ Configuration

The web interface inherits configuration from the main A.L.F.R.E.D. system:

- **Agent Discovery**: Configured via `coordinator/agent_discovery.json`
- **Environment Variables**: `AGENT_DISCOVERY_HOSTS`, `AGENT_USE_BROADCAST`, etc.
- **Web Port**: Default 8000, customizable via `--web-port` argument

## 🎨 Customization

### Themes
The interface supports both light and dark themes automatically based on system preferences.

### Refresh Intervals
- Agent status: 15 seconds
- Health checks: 30 seconds  
- Discovery: 5 minutes

These can be customized in `web/static/script.js`.

## 🧪 Testing

Run the test suite to verify your installation:
```bash
python test_web_interface.py
```

This will check:
- ✅ All required imports
- ✅ Directory structure
- ✅ Template files
- ✅ Static assets  
- ✅ Coordinator initialization

## 🔧 Troubleshooting

### Common Issues

**"Module not found" errors**
```bash
pip install fastapi uvicorn jinja2 python-multipart
```

**Web interface won't start**
- Check if port 8000 is already in use
- Try a different port: `--web-port 9000`
- Verify all dependencies are installed

**No agents discovered**
- Check agent discovery configuration
- Ensure agents are running and accessible
- Use the "Discover Agents" button in the web interface

**Template not found errors**  
- Verify the `coordinator/web/` directory structure exists
- Check that all HTML templates are present

### Port Conflicts

If port 8000 is in use, specify a different port:
```bash
python start_web.py --port 9000
# or
python coordinator/main.py --interface web --web-port 9000
```

## 🔒 Security Notes

- The web interface runs on `0.0.0.0` by default (accessible from network)
- No authentication is currently implemented
- Command execution follows the same security restrictions as the CLI
- Dangerous commands are automatically blocked

## 🤝 Integration

The web interface integrates seamlessly with existing A.L.F.R.E.D. components:
- Uses the same `Coordinator` class for agent management
- Shares agent discovery configuration
- Compatible with voice interface (can run simultaneously)
- Leverages existing command parsing and security features

## 📝 Development

### File Structure
```
coordinator/
├── web_interface.py          # Main FastAPI application
├── web/
│   ├── templates/           # Jinja2 HTML templates
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   ├── agents.html
│   │   ├── command.html
│   │   └── result.html
│   └── static/             # CSS, JS, and assets
│       ├── style.css
│       └── script.js
start_web.py                # Standalone launcher
test_web_interface.py       # Test suite
```

### Adding New Features

1. Add new routes in `WebInterface._setup_routes()`
2. Create corresponding HTML templates
3. Update navigation in `base.html`
4. Add any required static assets
5. Test with `test_web_interface.py`

---

🎉 **Enjoy your new A.L.F.R.E.D. web interface!**