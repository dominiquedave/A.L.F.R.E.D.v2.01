# Cross-Machine Agent Discovery Setup

The coordinator now supports multiple methods to discover agents running on different machines.

## Discovery Methods

### 1. Broadcast Discovery (Default)
- **How it works**: Coordinator sends UDP broadcast, agents respond automatically
- **Best for**: Same network segment (LAN/Wi-Fi)
- **Setup**: No configuration needed, works out of the box
- **Environment**: `AGENT_USE_BROADCAST=true` (default)

### 2. Manual Host List
- **How it works**: Specify exact IP:port combinations
- **Best for**: Known agent locations, cross-network setups
- **Setup**: Set environment variable or config file
- **Environment**: `AGENT_DISCOVERY_HOSTS=192.168.1.10:5001,192.168.1.11:5002`

### 3. Network Scanning
- **How it works**: Scans local subnet for agents
- **Best for**: Large local networks
- **Setup**: Enable scanning mode
- **Environment**: `AGENT_SCAN_NETWORK=true`

### 4. Predefined Network Configs
- **How it works**: Use saved network configurations
- **Best for**: Multiple environments (home/office/lab)
- **Setup**: Edit `coordinator/agent_discovery.json`
- **Environment**: `AGENT_NETWORK_CONFIG=office_network`

## Setup Examples

### Example 1: Windows Desktop + Linux VM
```bash
# On Windows (coordinator):
set AGENT_DISCOVERY_HOSTS=10.0.2.15:5001,localhost:5002

# On Linux VM (agent):
python agent/core/agent.py vm-agent 5001

# On Windows (agent):
python agent/core/agent.py windows-agent 5002
```

### Example 2: Multiple Office Computers
Edit `coordinator/agent_discovery.json`:
```json
{
    "network_configs": {
        "office_network": {
            "hosts": [
                "192.168.1.10:5001",
                "192.168.1.11:5001", 
                "192.168.1.12:5001"
            ]
        }
    }
}
```

Then run:
```bash
set AGENT_NETWORK_CONFIG=office_network
python coordinator/main.py
```

### Example 3: Auto-Discovery on Same Network
```bash
# Default mode - agents will be found automatically via broadcast
python coordinator/main.py
```

## Troubleshooting

### Agents Not Found
1. **Check firewall**: Ensure UDP port 5099 and HTTP ports (5001, 5002) are open
2. **Verify network**: Use `ping` to test connectivity between machines
3. **Check logs**: Enable debug logging to see discovery attempts
4. **Test manually**: Try `curl http://AGENT_IP:5001/capabilities`

### Broadcast Not Working
- Some networks block UDP broadcast
- Use manual host list instead: `AGENT_DISCOVERY_HOSTS=ip1:port1,ip2:port2`

### Cross-Subnet Discovery
- Broadcast doesn't work across subnets
- Use manual hosts or network scanning with specific IP ranges

## Configuration Precedence
1. Manual `host_range` parameter (highest priority)
2. `AGENT_DISCOVERY_HOSTS` environment variable
3. `AGENT_NETWORK_CONFIG` predefined network
4. Discovery settings from config file
5. Default localhost discovery (lowest priority)

## Port Requirements
- **Agent HTTP**: 5001, 5002, 5003 (configurable)
- **Broadcast Discovery**: UDP 5099
- **Direction**: Coordinator → Agent (outbound from coordinator)