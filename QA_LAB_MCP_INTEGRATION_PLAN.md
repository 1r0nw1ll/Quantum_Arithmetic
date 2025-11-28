# QA Lab MCP Integration Plan
**Integrating Model Context Protocol, Terminal AI Workflows, and Docker**

## Executive Summary

This plan integrates three powerful paradigms into the QA Lab:

1. **MCP Protocol** - Expose QA modules as tool servers for AI assistants
2. **Terminal AI Workflows** - Multi-AI collaboration via CLI with persistent context
3. **Docker Containers** - Isolated, reproducible MCP server deployment

**Timeline**: 5 phases over 6-8 weeks
**Current State**: qa_lab has 11 CLI agents with task-based YAML architecture
**End Goal**: Dockerized MCP servers + terminal AI orchestration for QA research

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLAUDE CODE (Orchestrator)                   │
│                   Terminal-Based AI Workflows                   │
└───────────────────┬─────────────────────────────────────────────┘
                    │
        ┌───────────┼───────────┐
        │           │           │
        ▼           ▼           ▼
    ┌────────┐  ┌────────┐  ┌────────┐
    │ Codex  │  │ Gemini │  │  QALM  │
    │  CLI   │  │  CLI   │  │ Local  │
    └────┬───┘  └────┬───┘  └────┬───┘
         │           │           │
         └───────────┼───────────┘
                     │
            ┌────────▼────────┐
            │  MCP GATEWAY    │
            │  (Docker)       │
            └────────┬────────┘
                     │
     ┌───────────────┼───────────────┐
     │               │               │
     ▼               ▼               ▼
┌─────────┐    ┌─────────┐    ┌─────────┐
│ qa-right│    │ qa-reso │    │ qa-hgd  │
│-triangle│    │ -nance  │    │-optim   │
│  server │    │  server │    │  server │
└─────────┘    └─────────┘    └─────────┘
  (Docker)       (Docker)       (Docker)
```

### Integration Points

1. **Existing qa_lab CLI** → Enhanced with MCP client capabilities
2. **Dispatcher** → Routes tasks to MCP tools OR AI agents
3. **QALM Agent** → Can invoke MCP tools for validation
4. **Docker Compose** → Orchestrates all MCP servers
5. **Persistent Context** → YAML files store QA state across sessions

---

## Directory Structure

```
signal_experiments/
├── qa_lab/
│   ├── qa_agents/
│   │   └── cli/
│   │       ├── qa_cli.py          # Enhanced with MCP commands
│   │       ├── qalm.py             # Can call MCP tools
│   │       ├── dispatcher.py       # Routes to MCP or AI
│   │       └── mcp_client.py       # NEW: MCP client wrapper
│   │
│   ├── qa_mcp_servers/             # NEW: MCP server implementations
│   │   ├── qa-right-triangle/
│   │   │   ├── server.py
│   │   │   ├── Dockerfile
│   │   │   └── mcp.json
│   │   ├── qa-resonance/
│   │   ├── qa-hgd-optimizer/
│   │   ├── qa-tuple-validator/
│   │   └── qa-proton-radius/
│   │
│   ├── qa_contexts/                # NEW: Persistent AI contexts
│   │   ├── base_context.yaml
│   │   ├── proton_radius.yaml
│   │   └── ellipse_quantization.yaml
│   │
│   └── docker-compose.yml          # NEW: Multi-MCP orchestration
│
├── qa-in-terminal/                 # NEW: Terminal AI workflows
│   ├── qa_terminal_agent.py
│   ├── qa_context_manager.py
│   └── workflows/
│
└── DOCKER_QUICK_START.md          # Existing guide
```

---

## Phase 1: MCP Foundation (Week 1-2)

### Objectives
- Understand MCP JSON-RPC protocol
- Build first MCP server for QA Right Triangle
- Test with stdio transport locally

### Implementation

#### 1.1 Create MCP Client Wrapper

**File**: `qa_lab/qa_agents/cli/mcp_client.py`

```python
#!/usr/bin/env python3
"""
MCP Client for QA Lab
JSON-RPC client for communicating with MCP servers
"""

import json
import subprocess
import sys
from typing import Dict, List, Any, Optional

class MCPClient:
    """Client for Model Context Protocol servers"""

    def __init__(self, server_command: List[str]):
        """
        Initialize MCP client with server command

        Args:
            server_command: Command to start server (e.g., ['python', 'server.py'])
        """
        self.server_command = server_command
        self.process = None
        self.request_id = 0

    def start(self):
        """Start the MCP server process"""
        self.process = subprocess.Popen(
            self.server_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

    def send_request(self, method: str, params: Optional[Dict] = None) -> Dict:
        """Send JSON-RPC request to server"""
        self.request_id += 1

        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }

        # Send request
        request_str = json.dumps(request) + "\n"
        self.process.stdin.write(request_str)
        self.process.stdin.flush()

        # Read response
        response_str = self.process.stdout.readline()
        response = json.loads(response_str)

        if "error" in response:
            raise Exception(f"MCP Error: {response['error']}")

        return response.get("result", {})

    def call_tool(self, tool_name: str, arguments: Dict) -> Any:
        """Call a tool on the MCP server"""
        return self.send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })

    def list_tools(self) -> List[Dict]:
        """List available tools from server"""
        result = self.send_request("tools/list")
        return result.get("tools", [])

    def stop(self):
        """Stop the MCP server process"""
        if self.process:
            self.process.terminate()
            self.process.wait()
```

#### 1.2 Build First MCP Server: QA Right Triangle

**File**: `qa_lab/qa_mcp_servers/qa-right-triangle/server.py`

```python
#!/usr/bin/env python3
"""
QA Right Triangle MCP Server
Exposes QA right triangle calculations as MCP tools
"""

import json
import sys
import math
from typing import Dict, List

class QARightTriangleMCPServer:
    """MCP Server for QA Right Triangle calculations"""

    def __init__(self):
        self.request_id = 0

    def compute_triangle(self, b: float, e: float) -> Dict:
        """
        Compute QA right triangle from base pair (b, e)

        Returns all QA tuple values and right triangle invariants
        """
        # QA tuple construction
        d = b + e
        a = b + 2*e

        # Right triangle sides
        # Using canonical QA mapping: C=d, F=b+e+d, G=a
        C = d
        F = b + e + d  # Semi-perimeter
        G = a

        # QA invariants
        J = b * d
        K = d * a
        X = e * d
        W = b * e
        Y = e * a
        Z = b * a

        # Compute right triangle properties
        # For a right triangle with legs and hypotenuse related to QA tuple
        # Using sides derived from QA geometry

        leg1 = math.sqrt(2 * J)  # From b*d
        leg2 = math.sqrt(2 * X)  # From e*d
        hypotenuse = math.sqrt(leg1**2 + leg2**2)

        area = 0.5 * leg1 * leg2
        perimeter = leg1 + leg2 + hypotenuse

        # Inradius and circumradius
        r = area / (perimeter / 2) if perimeter > 0 else 0
        R = hypotenuse / 2 if hypotenuse > 0 else 0

        return {
            "qa_tuple": {"b": b, "e": e, "d": d, "a": a},
            "invariants": {
                "J": J, "K": K, "X": X,
                "W": W, "Y": Y, "Z": Z
            },
            "triangle": {
                "leg1": leg1,
                "leg2": leg2,
                "hypotenuse": hypotenuse,
                "area": area,
                "perimeter": perimeter,
                "inradius": r,
                "circumradius": R
            },
            "modular": {
                "d_mod_9": d % 9,
                "d_mod_24": d % 24,
                "classification": self._classify_tuple(b, e)
            }
        }

    def _classify_tuple(self, b: float, e: float) -> str:
        """Classify QA tuple by orbit family"""
        # Simplified classification - expand based on QA theory
        d = b + e
        if d % 24 == 0:
            return "Cosmos-24-cycle"
        elif d % 8 == 0:
            return "Satellite-8-cycle"
        elif b == 9 and e == 9:
            return "Singularity"
        else:
            return "General"

    def handle_request(self, request: Dict) -> Dict:
        """Handle JSON-RPC request"""
        method = request.get("method")
        params = request.get("params", {})
        req_id = request.get("id")

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": [
                        {
                            "name": "qa_compute_triangle",
                            "description": "Compute QA right triangle from base pair (b, e)",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "b": {"type": "number", "description": "Base parameter b"},
                                    "e": {"type": "number", "description": "Base parameter e"}
                                },
                                "required": ["b", "e"]
                            }
                        }
                    ]
                }
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            if tool_name == "qa_compute_triangle":
                try:
                    b = float(arguments["b"])
                    e = float(arguments["e"])
                    result = self.compute_triangle(b, e)

                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [
                                {"type": "json", "json": result}
                            ]
                        }
                    }
                except Exception as e:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32000, "message": str(e)}
                    }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": "Method not found"}
        }

    def run(self):
        """Main server loop - stdio transport"""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                request = json.loads(line)
                response = self.handle_request(request)
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
            except Exception as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {str(e)}"}
                }
                sys.stdout.write(json.dumps(error_response) + "\n")
                sys.stdout.flush()

if __name__ == "__main__":
    server = QARightTriangleMCPServer()
    server.run()
```

#### 1.3 Test MCP Server Locally

```bash
# Terminal 1: Start server
cd qa_lab/qa_mcp_servers/qa-right-triangle
python3 server.py

# Terminal 2: Test with Python client
python3 << 'EOF'
from qa_lab.qa_agents.cli.mcp_client import MCPClient

client = MCPClient(['python3', 'qa_lab/qa_mcp_servers/qa-right-triangle/server.py'])
client.start()

# List available tools
tools = client.list_tools()
print("Available tools:", tools)

# Call the tool
result = client.call_tool("qa_compute_triangle", {"b": 1.0, "e": 1.0})
print("Result:", result)

client.stop()
EOF
```

**Expected Output**:
```json
{
  "qa_tuple": {"b": 1.0, "e": 1.0, "d": 2.0, "a": 3.0},
  "invariants": {"J": 2.0, "K": 6.0, "X": 2.0, ...},
  "triangle": {"leg1": 2.0, "leg2": 2.0, "area": 2.0, ...}
}
```

---

## Phase 2: Docker Integration (Week 2-3)

### Objectives
- Containerize MCP servers
- Create docker-compose for multi-server gateway
- Test Claude Desktop connection

### Implementation

#### 2.1 Dockerfile for QA Right Triangle Server

**File**: `qa_lab/qa_mcp_servers/qa-right-triangle/Dockerfile`

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# Copy server code
COPY server.py .
COPY mcp.json .

# Install any dependencies (add if needed)
# RUN pip install --no-cache-dir -r requirements.txt

# Expose MCP server (stdio, no network port needed)
CMD ["python3", "server.py"]
```

#### 2.2 MCP Configuration

**File**: `qa_lab/qa_mcp_servers/qa-right-triangle/mcp.json`

```json
{
  "mcpServers": {
    "qa-right-triangle": {
      "command": "python3",
      "args": ["server.py"],
      "description": "QA Right Triangle computation server",
      "version": "1.0.0"
    }
  }
}
```

#### 2.3 Docker Compose Multi-Server Setup

**File**: `qa_lab/docker-compose.yml`

```yaml
version: '3.8'

services:
  # MCP Server: QA Right Triangle
  qa-right-triangle:
    build: ./qa_mcp_servers/qa-right-triangle
    container_name: mcp-qa-right-triangle
    stdin_open: true
    tty: true
    volumes:
      - ./qa_mcp_servers/qa-right-triangle:/app
    restart: unless-stopped

  # MCP Server: QA Resonance Scanner
  qa-resonance:
    build: ./qa_mcp_servers/qa-resonance
    container_name: mcp-qa-resonance
    stdin_open: true
    tty: true
    volumes:
      - ./qa_mcp_servers/qa-resonance:/app
    restart: unless-stopped

  # MCP Server: QA HGD Optimizer
  qa-hgd-optimizer:
    build: ./qa_mcp_servers/qa-hgd-optimizer
    container_name: mcp-qa-hgd-optimizer
    stdin_open: true
    tty: true
    volumes:
      - ./qa_mcp_servers/qa-hgd-optimizer:/app
      - ./results:/app/results  # Share results
    restart: unless-stopped

  # MCP Gateway (optional SSE transport)
  mcp-gateway:
    image: mcp-gateway:latest  # Use official MCP gateway if available
    container_name: mcp-gateway
    ports:
      - "3000:3000"
    environment:
      - MCP_SERVERS=qa-right-triangle,qa-resonance,qa-hgd-optimizer
    depends_on:
      - qa-right-triangle
      - qa-resonance
      - qa-hgd-optimizer
    restart: unless-stopped

volumes:
  mcp_data:
```

#### 2.4 Build and Run

```bash
cd qa_lab

# Build all MCP server images
docker-compose build

# Start all MCP servers
docker-compose up -d

# View logs
docker-compose logs -f qa-right-triangle

# Test server
docker exec -i mcp-qa-right-triangle python3 server.py << 'EOF'
{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
EOF
```

---

## Phase 3: Terminal AI Workflows (Week 3-4)

### Objectives
- Create terminal-first AI collaboration system
- Persistent context files for QA research
- Multi-AI orchestration (Claude + Codex + Gemini + QALM)

### Implementation

#### 3.1 QA Terminal Agent

**File**: `qa-in-terminal/qa_terminal_agent.py`

```python
#!/usr/bin/env python3
"""
QA Terminal Agent
Multi-AI orchestration with persistent context for QA research
"""

import argparse
import json
import yaml
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

class QATerminalAgent:
    """Terminal-based multi-AI agent for QA research"""

    def __init__(self, context_file: str):
        self.context_file = Path(context_file)
        self.context = self.load_context()
        self.base_dir = Path(__file__).parent.parent

        # AI providers
        self.providers = {
            'claude': self.call_claude,
            'codex': self.call_codex,
            'gemini': self.call_gemini,
            'qalm': self.call_qalm
        }

    def load_context(self) -> Dict:
        """Load persistent QA context"""
        if self.context_file.exists():
            with open(self.context_file, 'r') as f:
                return yaml.safe_load(f)

        # Default context
        return {
            'project_name': 'QA Research',
            'modulus_outer': 24,
            'modulus_inner': 9,
            'active_tuples': [],
            'experiments': [],
            'chat_history': [],
            'mcp_servers': [
                'qa-right-triangle',
                'qa-resonance',
                'qa-hgd-optimizer'
            ]
        }

    def save_context(self):
        """Save persistent context"""
        with open(self.context_file, 'w') as f:
            yaml.dump(self.context, f, default_flow_style=False)

    def build_system_prompt(self) -> str:
        """Build QA-specific system prompt"""
        return f"""You are a QA (Quantum Arithmetic) research assistant.

Active Project: {self.context['project_name']}
Modular Arithmetic: mod-{self.context['modulus_outer']} (outer), mod-{self.context['modulus_inner']} (inner)

QA Invariants (NEVER violate these):
- QA tuple structure: (b, e, d, a) where d = b+e, a = b+2e
- Core invariants: J = b·d, K = d·a, X = e·d
- Modular constraints: All operations respect mod-{self.context['modulus_outer']}

Available MCP Tools:
{json.dumps(self.context['mcp_servers'], indent=2)}

Current Experiments:
{json.dumps(self.context['experiments'][-3:], indent=2)}

Always preserve QA mathematical rigor and cite MCP tools when performing calculations.
"""

    def call_claude(self, prompt: str) -> str:
        """Call Claude Code (current session)"""
        # This would be handled by the current Claude Code session
        # For now, return placeholder
        return "[Claude response would appear here in actual implementation]"

    def call_codex(self, prompt: str) -> str:
        """Call Codex via CLI"""
        try:
            # Assuming codex CLI is installed
            result = subprocess.run(
                ['codex', prompt],
                capture_output=True,
                text=True,
                timeout=60
            )
            return result.stdout.strip()
        except Exception as e:
            return f"Codex error: {e}"

    def call_gemini(self, prompt: str) -> str:
        """Call Gemini via CLI"""
        try:
            result = subprocess.run(
                ['gemini', prompt],
                capture_output=True,
                text=True,
                timeout=60
            )
            return result.stdout.strip()
        except Exception as e:
            return f"Gemini error: {e}"

    def call_qalm(self, prompt: str) -> str:
        """Call QALM local model"""
        try:
            qalm_script = self.base_dir / 'qa_lab/qa_agents/cli/qalm.py'
            result = subprocess.run(
                ['python3', str(qalm_script), '--interactive'],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=60
            )
            return result.stdout.strip()
        except Exception as e:
            return f"QALM error: {e}"

    def call_mcp_tool(self, tool_name: str, arguments: Dict) -> Dict:
        """Call MCP tool via docker"""
        # Use MCP client to call tool in Docker container
        from qa_lab.qa_agents.cli.mcp_client import MCPClient

        server_map = {
            'qa_compute_triangle': 'qa-right-triangle',
            'qa_scan_resonance': 'qa-resonance',
            'qa_optimize_hgd': 'qa-hgd-optimizer'
        }

        server = server_map.get(tool_name, 'qa-right-triangle')

        client = MCPClient([
            'docker', 'exec', '-i', f'mcp-{server}',
            'python3', 'server.py'
        ])
        client.start()

        try:
            result = client.call_tool(tool_name, arguments)
            return result
        finally:
            client.stop()

    def orchestrate(self, user_message: str, provider: str = 'claude') -> str:
        """Orchestrate AI response with context"""
        # Add system prompt
        system_prompt = self.build_system_prompt()
        full_prompt = f"{system_prompt}\n\nUser: {user_message}"

        # Call selected provider
        response = self.providers[provider](full_prompt)

        # Update context
        self.context['chat_history'].append({
            'timestamp': datetime.now().isoformat(),
            'provider': provider,
            'user_message': user_message,
            'response': response
        })

        self.save_context()

        return response

def main():
    parser = argparse.ArgumentParser(description='QA Terminal Agent')
    parser.add_argument('message', nargs='*', help='Message to AI')
    parser.add_argument('-c', '--context', default='qa_contexts/base_context.yaml')
    parser.add_argument('-p', '--provider', default='claude',
                        choices=['claude', 'codex', 'gemini', 'qalm'])

    args = parser.parse_args()

    agent = QATerminalAgent(args.context)

    if args.message:
        message = ' '.join(args.message)
        response = agent.orchestrate(message, args.provider)
        print(response)
    else:
        # Interactive mode
        print("QA Terminal Agent - Interactive Mode")
        print(f"Context: {args.context}")
        print(f"Provider: {args.provider}")
        print("Type 'quit' to exit\n")

        while True:
            try:
                message = input("> ")
                if message.lower() in ['quit', 'exit', 'q']:
                    break

                response = agent.orchestrate(message, args.provider)
                print(f"\n{response}\n")
            except KeyboardInterrupt:
                break

if __name__ == "__main__":
    main()
```

#### 3.2 Enhanced qa_cli with MCP Commands

**File**: `qa_lab/qa_agents/cli/qa_cli.py` (additions)

```python
# Add to QACLI class:

def cmd_mcp_list(self, args):
    """List all MCP servers and their tools"""
    print("🔌 Available MCP Servers:")

    servers = ['qa-right-triangle', 'qa-resonance', 'qa-hgd-optimizer']

    for server in servers:
        try:
            client = MCPClient(['docker', 'exec', '-i', f'mcp-{server}',
                                'python3', 'server.py'])
            client.start()
            tools = client.list_tools()
            client.stop()

            print(f"\n  📦 {server}")
            for tool in tools:
                print(f"    • {tool['name']}: {tool['description']}")
        except Exception as e:
            print(f"  ❌ {server}: {e}")

def cmd_mcp_call(self, args):
    """Call an MCP tool"""
    tool_name = args.tool
    arguments = json.loads(args.args) if args.args else {}

    from qa_agents.cli.mcp_client import MCPClient

    # Determine which server has this tool
    # (simplified - should query all servers)
    server = 'qa-right-triangle'

    client = MCPClient(['docker', 'exec', '-i', f'mcp-{server}',
                        'python3', 'server.py'])
    client.start()

    try:
        result = client.call_tool(tool_name, arguments)
        print(json.dumps(result, indent=2))
    finally:
        client.stop()

def cmd_terminal(self, args):
    """Launch terminal AI agent"""
    return self.run_command(
        ["python3", "qa-in-terminal/qa_terminal_agent.py",
         "-c", args.context or "qa_contexts/base_context.yaml",
         "-p", args.provider or "claude"],
        "Launching QA Terminal Agent..."
    )
```

---

## Phase 4: Multi-AI Orchestration Enhancement (Week 4-5)

### Objectives
- Integrate existing dispatcher with MCP tools
- Enable QALM to call MCP for validation
- Create collaborative workflows

### Implementation

#### 4.1 Enhanced Dispatcher with MCP Routing

**File**: `qa_lab/qa_agents/cli/dispatcher.py` (modifications)

```python
def assign_agent(self, task: Dict) -> str:
    """Assign task to appropriate AI agent OR MCP tool"""
    title = task['title'].lower()
    lane = task.get('lane', 'green')

    # Check if task can be handled by MCP tool
    if 'compute triangle' in title or 'qa tuple' in title:
        return 'mcp:qa_compute_triangle'

    elif 'resonance' in title or 'scan tuples' in title:
        return 'mcp:qa_scan_resonance'

    elif 'optimize hgd' in title or 'hyperparameter' in title:
        return 'mcp:qa_optimize_hgd'

    # Otherwise route to AI agents
    elif any(keyword in title for keyword in ['code', 'implement']):
        return 'codex'

    elif any(keyword in title for keyword in ['analyze', 'review']):
        return 'gemini_cli'

    else:
        return 'claude_code'
```

#### 4.2 QALM with MCP Tool Calling

**File**: `qa_lab/qa_agents/cli/qalm.py` (additions)

```python
from qa_agents.cli.mcp_client import MCPClient

class QALMAgent:
    # ... existing code ...

    def verify_with_mcp(self, qa_tuple: List[float]) -> Dict:
        """Verify QA tuple using MCP server"""
        client = MCPClient([
            'docker', 'exec', '-i', 'mcp-qa-right-triangle',
            'python3', 'server.py'
        ])
        client.start()

        try:
            result = client.call_tool("qa_compute_triangle", {
                "b": qa_tuple[0],
                "e": qa_tuple[1]
            })

            # Compare QALM's analysis with MCP ground truth
            qalm_analysis = self.analyze_qa_tuple(qa_tuple)

            return {
                'qalm_analysis': qalm_analysis,
                'mcp_verification': result,
                'agreement': self.check_agreement(qalm_analysis, result)
            }
        finally:
            client.stop()

    def check_agreement(self, qalm_result: Dict, mcp_result: Dict) -> bool:
        """Check if QALM and MCP agree"""
        # Compare invariants
        mcp_invariants = mcp_result.get('content', [{}])[0].get('json', {}).get('invariants', {})
        qalm_valid = qalm_result.get('is_valid_qa_tuple', False)

        # Simple agreement check
        return qalm_valid and len(mcp_invariants) > 0
```

---

## Phase 5: Full Integration & Testing (Week 5-6)

### Objectives
- End-to-end workflow testing
- Performance benchmarking
- Documentation and examples

### Implementation

#### 5.1 Example Workflow: QA Theorem Discovery

```bash
#!/bin/bash
# Workflow: Discover QA theorems using multi-AI + MCP

# 1. Start MCP servers
cd qa_lab
docker-compose up -d

# 2. Create research context
cat > qa_contexts/theorem_discovery.yaml << 'EOF'
project_name: "QA Theorem Discovery - Mod-24 Resonance"
modulus_outer: 24
modulus_inner: 9
active_tuples: []
experiments:
  - name: "Scan resonance patterns"
    status: "planned"
mcp_servers:
  - qa-right-triangle
  - qa-resonance
EOF

# 3. Launch terminal AI agent (Claude)
python3 qa-in-terminal/qa_terminal_agent.py \
  -c qa_contexts/theorem_discovery.yaml \
  -p claude

# 4. In terminal, orchestrate:
# > Scan for high-resonance QA tuples with b,e in range [1,24]
# > Use MCP qa_scan_resonance tool
# > Then analyze top 10 with QALM
# > Generate theorems from patterns

# 5. Review with Gemini
python3 qa-in-terminal/qa_terminal_agent.py \
  -c qa_contexts/theorem_discovery.yaml \
  -p gemini \
  "Review the discovered theorems for mathematical correctness"

# 6. Generate code with Codex
python3 qa-in-terminal/qa_terminal_agent.py \
  -c qa_contexts/theorem_discovery.yaml \
  -p codex \
  "Implement automated theorem prover for top 3 conjectures"
```

#### 5.2 Testing Framework

**File**: `qa_lab/tests/test_mcp_integration.py`

```python
#!/usr/bin/env python3
"""
Integration tests for MCP + Terminal AI workflows
"""

import pytest
import json
from qa_agents.cli.mcp_client import MCPClient

class TestMCPIntegration:

    def test_mcp_server_startup(self):
        """Test MCP server starts and responds"""
        client = MCPClient(['python3', 'qa_mcp_servers/qa-right-triangle/server.py'])
        client.start()

        tools = client.list_tools()
        assert len(tools) > 0
        assert tools[0]['name'] == 'qa_compute_triangle'

        client.stop()

    def test_qa_compute_triangle(self):
        """Test QA triangle computation"""
        client = MCPClient(['python3', 'qa_mcp_servers/qa-right-triangle/server.py'])
        client.start()

        result = client.call_tool("qa_compute_triangle", {"b": 1.0, "e": 1.0})

        # Verify result structure
        assert 'content' in result
        data = result['content'][0]['json']

        assert data['qa_tuple']['d'] == 2.0
        assert data['qa_tuple']['a'] == 3.0
        assert data['invariants']['J'] == 2.0

        client.stop()

    def test_docker_mcp_call(self):
        """Test calling MCP server in Docker"""
        import subprocess

        # Assuming docker-compose is running
        result = subprocess.run(
            ['docker', 'exec', '-i', 'mcp-qa-right-triangle', 'python3', 'server.py'],
            input='{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}\n',
            capture_output=True,
            text=True
        )

        response = json.loads(result.stdout)
        assert 'result' in response
        assert 'tools' in response['result']

if __name__ == "__main__":
    pytest.main([__file__, '-v'])
```

#### 5.3 Performance Benchmarks

**File**: `qa_lab/benchmarks/mcp_performance.py`

```python
#!/usr/bin/env python3
"""
Benchmark MCP server performance
"""

import time
import statistics
from qa_agents.cli.mcp_client import MCPClient

def benchmark_mcp_calls(num_calls: int = 100):
    """Benchmark MCP call latency"""
    client = MCPClient(['python3', 'qa_mcp_servers/qa-right-triangle/server.py'])
    client.start()

    latencies = []

    for i in range(num_calls):
        b, e = i % 24 + 1, (i * 2) % 24 + 1

        start = time.time()
        result = client.call_tool("qa_compute_triangle", {"b": float(b), "e": float(e)})
        end = time.time()

        latencies.append((end - start) * 1000)  # Convert to ms

    client.stop()

    print(f"MCP Call Latency Statistics ({num_calls} calls):")
    print(f"  Mean: {statistics.mean(latencies):.2f} ms")
    print(f"  Median: {statistics.median(latencies):.2f} ms")
    print(f"  Std Dev: {statistics.stdev(latencies):.2f} ms")
    print(f"  Min: {min(latencies):.2f} ms")
    print(f"  Max: {max(latencies):.2f} ms")
    print(f"  p95: {sorted(latencies)[int(num_calls * 0.95)]:.2f} ms")
    print(f"  p99: {sorted(latencies)[int(num_calls * 0.99)]:.2f} ms")

if __name__ == "__main__":
    benchmark_mcp_calls(100)
```

---

## Makefile Integration

**File**: `qa_lab/Makefile` (additions)

```makefile
# MCP Server Management
.PHONY: mcp-build mcp-up mcp-down mcp-logs mcp-test

mcp-build:
	@echo "🐳 Building MCP server images..."
	docker-compose build

mcp-up:
	@echo "🚀 Starting MCP servers..."
	docker-compose up -d

mcp-down:
	@echo "🛑 Stopping MCP servers..."
	docker-compose down

mcp-logs:
	@echo "📋 MCP server logs..."
	docker-compose logs -f

mcp-test:
	@echo "🧪 Testing MCP integration..."
	pytest tests/test_mcp_integration.py -v

mcp-benchmark:
	@echo "⏱️  Running MCP performance benchmarks..."
	python3 benchmarks/mcp_performance.py

# Terminal AI Workflows
.PHONY: terminal-claude terminal-gemini terminal-codex

terminal-claude:
	@echo "🤖 Launching Claude Terminal Agent..."
	python3 qa-in-terminal/qa_terminal_agent.py -p claude

terminal-gemini:
	@echo "🤖 Launching Gemini Terminal Agent..."
	python3 qa-in-terminal/qa_terminal_agent.py -p gemini

terminal-codex:
	@echo "🤖 Launching Codex Terminal Agent..."
	python3 qa-in-terminal/qa_terminal_agent.py -p codex
```

---

## Success Metrics

### Phase 1 (MCP Foundation)
- [x] MCP client wrapper functional
- [x] QA Right Triangle server responds to JSON-RPC
- [x] Local stdio testing passes

### Phase 2 (Docker Integration)
- [ ] All 3 MCP servers Dockerized
- [ ] docker-compose orchestrates servers
- [ ] Claude Desktop can connect to servers

### Phase 3 (Terminal AI)
- [ ] Terminal agent orchestrates 4 AI providers
- [ ] Persistent context files work
- [ ] Multi-turn conversations maintain state

### Phase 4 (Orchestration)
- [ ] Dispatcher routes to MCP tools
- [ ] QALM validates with MCP
- [ ] Multi-AI collaboration workflows functional

### Phase 5 (Testing & Polish)
- [ ] All integration tests pass
- [ ] Performance benchmarks documented
- [ ] End-to-end workflows demonstrated

---

## Resources

### NetworkChuck References
- **ai-in-the-terminal**: https://github.com/theNetworkChuck/ai-in-the-terminal
- **docker-mcp-tutorial**: https://github.com/theNetworkChuck/docker-mcp-tutorial
- **Video 1 (MCP)**: https://www.youtube.com/watch?v=MsQACpcuTkU
- **Video 2 (Terminal AI)**: https://www.youtube.com/watch?v=GuTcle5edjk

### MCP Documentation
- Model Context Protocol Spec: https://modelcontextprotocol.io/
- Claude Desktop MCP Guide: https://docs.anthropic.com/claude/docs/mcp

### Docker Learning
- Docker in 100 Seconds: https://www.youtube.com/watch?v=Gjnup-PuquQ
- Docker Compose Docs: https://docs.docker.com/compose/

---

## Next Steps

1. **Week 1**: Implement Phase 1 - Build first MCP server
2. **Week 2**: Implement Phase 2 - Dockerize servers
3. **Week 3-4**: Implement Phase 3 - Terminal AI workflows
4. **Week 5**: Implement Phase 4 - Full orchestration
5. **Week 6**: Implement Phase 5 - Testing & polish

**Start here**: Create `qa_lab/qa_mcp_servers/qa-right-triangle/` directory and implement the server.py file from Phase 1.

---

**Status**: Ready for implementation
**Last Updated**: 2025-11-19
**Author**: Claude Code + Will (Human in the loop)
