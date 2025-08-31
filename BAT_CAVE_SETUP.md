# 🦇 A.L.F.R.E.D. Bat Cave Console Setup

Welcome to the darkness, master. Your digital domain awaits your command.

## 🌙 Overview

The A.L.F.R.E.D. system now features a dark, atmospheric **Bat Cave Console** - a gothic-themed web interface that transforms your distributed agent system into a commanding digital fortress.

### ✨ Features

- **🦇 Bat Cave Web Interface**: Dark, gothic web UI with animated bat silhouettes
- **🎤 Enhanced Voice Interface**: Terminal-based voice control with atmospheric styling
- **🌙 Dual Mode Operation**: Run voice-only, web-only, or hybrid mode
- **⚡ Real-time Updates**: WebSocket-powered live agent status updates
- **🏰 Command Center**: Execute commands across your agent network
- **👥 Colony Management**: Monitor and manage your digital bat colony

## 🛠️ Installation

### Prerequisites
```bash
# Ensure you have Python 3.8+
python --version

# Install existing dependencies first
pip install -r requirements.txt  # Your existing requirements
```

### Web Interface Dependencies
```bash
# Install bat cave web interface requirements
pip install -r requirements-web.txt
```

### Manual Installation
```bash
pip install fastapi uvicorn[standard] jinja2 websockets aiofiles
```

## 🚀 Quick Start

### 1. Web Interface Only (Recommended for new users)
```bash
cd /home/ddominique/A.L.F.R.E.D.v2.01/coordinator
python main.py --mode web --web-port 8000
```

Open your browser to: **http://localhost:8000**

### 2. Voice Interface Only (Original mode)
```bash
python main.py --mode voice
```

### 3. Hybrid Mode (Both interfaces)
```bash
python main.py --mode hybrid --web-port 8000
```

## 🦇 Bat Cave Console Features

### Web Interface
- **Dashboard**: Colony status overview with health monitoring
- **Command Terminal**: Execute commands with real-time feedback
- **Agent Management**: View and monitor your digital bat colony
- **Real-time Updates**: WebSocket-powered live status updates
- **Atmospheric Effects**: Animated bats, particle systems, and gothic styling

### Enhanced Voice Interface
- **Bat-themed ASCII art startup**
- **Colored terminal output with atmospheric messaging**
- **Enhanced command feedback with gothic styling**
- **Improved status displays and colony monitoring**

## 🎨 Theme Customization

### Color Palette
- **Primary**: Deep midnight black (`#0B0B0B`)
- **Secondary**: Dark purple (`#2D1B69`)
- **Accent**: Electric purple (`#6A0DAD`)
- **Highlight**: Silver/white (`#C0C0C0`)
- **Success**: Dark green (`#006400`)
- **Error**: Dark red (`#8B0000`)

### Fonts
- **Gothic**: Creepster (headings)
- **Technical**: Orbitron (interface)
- **Horror**: Nosifer (special effects)

## 🔧 Configuration

### Environment Variables
```bash
# Disable ANSI colors for voice interface (if needed)
export NO_ANSI=1

# Standard A.L.F.R.E.D. configuration
export OPENAI_API_KEY="your-openrouter-key"
export AGENT_DISCOVERY_HOSTS="localhost:5001,localhost:5002"
```

### Command Line Options
```bash
# Interface modes
--mode voice          # Voice interface only
--mode web            # Web interface only
--mode hybrid         # Both interfaces (default)

# Web server configuration
--web-port 8000       # Web server port (default: 8000)
--host 0.0.0.0        # Bind address (default: 0.0.0.0)
```

## 🌐 Web Interface Usage

### Dashboard
1. **Agent Status**: Monitor your digital bat colony health
2. **Command Terminal**: Execute commands with syntax highlighting
3. **Real-time Updates**: Live agent status and command results

### Voice Commands (Web + Voice Mode)
- `"status"` or `"agents"` - Display colony status
- `"exit"` or `"quit"` - Shutdown gracefully
- Any system command - Execute on available agents

### Keyboard Shortcuts
- **Escape**: Focus command input
- **Ctrl+Shift+D**: Trigger agent discovery
- **Ctrl+C**: Graceful shutdown (voice mode)

## 🔍 Agent Discovery

The system will automatically discover agents using:
1. **UDP Broadcast**: Scan network for responsive agents
2. **Manual Configuration**: Use environment variables
3. **Network Scanning**: Scan local network ranges

## 🐛 Troubleshooting

### Common Issues

**Web interface won't start:**
```bash
# Check if port is in use
netstat -an | grep :8000

# Try different port
python main.py --mode web --web-port 8080
```

**Voice synthesis fails:**
```bash
# Install audio dependencies (Linux)
sudo apt-get install espeak espeak-data libespeak1 libespeak-dev
sudo apt-get install portaudio19-dev python3-pyaudio

# Install audio dependencies (macOS)
brew install portaudio
```

**No agents discovered:**
```bash
# Check agent discovery configuration
export AGENT_DISCOVERY_HOSTS="localhost:5001"
# Or check agent_discovery.json file
```

### Debug Mode
```bash
# Enable detailed logging
python main.py --mode hybrid 2>&1 | tee bat_cave.log
```

## 🎭 Atmospheric Features

### Web Interface
- **Animated Bats**: Flying bat silhouettes across the interface
- **Gothic Typography**: Horror and sci-fi themed fonts
- **Particle Systems**: Floating atmospheric particles
- **Screen Effects**: Subtle screen flicker and glow effects
- **Dynamic Backgrounds**: Gradient cave-like backgrounds

### Voice Interface
- **ASCII Art**: Dramatic startup banner
- **Colored Output**: Atmospheric terminal styling
- **Themed Messages**: Gothic and bat-themed system messages
- **Status Displays**: Enhanced visual agent status reports

## 📁 File Structure

```
coordinator/
├── main.py                 # Enhanced main entry point
├── web/                    # Bat Cave web interface
│   ├── __init__.py
│   ├── interface.py        # Web interface logic
│   ├── templates/
│   │   ├── base.html       # Base template with bat theme
│   │   └── dashboard.html  # Main dashboard
│   └── static/
│       ├── css/
│       │   └── bat-theme.css      # Gothic styling
│       └── js/
│           └── bat-console.js     # Interactive features
└── voice/
    └── interface.py        # Enhanced voice interface
```

## 🦇 Welcome to the Darkness

Your A.L.F.R.E.D. system has been transformed into a commanding digital fortress. The Bat Cave Console awaits your commands, master.

*"In the darkness, we find power. In the shadows, we command our digital empire."*

---

### Support
For issues with the Bat Cave Console, check the logs or create an issue with your system configuration.

🦇 **The night is yours to command.**
