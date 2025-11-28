"""
Auto-refactor: normalize formatting for qa_collab_api.py
"""

#!/usr/bin/env python3
"""
QA Collaboration REST API
Provides HTTP/REST interface to the collaboration bus
for agents that can't use ZeroMQ or MCP directly
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from flask import Flask, request, jsonify
from flask_cors import CORS

import sys
sys.path.insert(0, str(Path(__file__).parent))

from qa_agent_base import CollaborativeAgent

app = Flask(__name__)
CORS(app)  # Enable CORS for web clients

# Store agents by session ID
agents: Dict[str, CollaborativeAgent] = {}


def get_or_create_agent(agent_name: str, session_id: Optional[str] = None) -> CollaborativeAgent:
    """Get existing agent or create new one"""
    if session_id and session_id in agents:
        return agents[session_id]

    # Create new agent
    agent = CollaborativeAgent(
        name=agent_name,
        auto_connect=True,
        metadata={"type": "rest_api"}
    )

    if session_id:
        agents[session_id] = agent

    return agent


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "active_agents": len(agents),
        "timestamp": datetime.now().isoformat()
    })


@app.route('/agents/register', methods=['POST'])
def register_agent():
    """Register a new agent"""
    data = request.json
    agent_name = data.get('name', 'rest_agent')
    session_id = data.get('session_id')

    try:
        agent = get_or_create_agent(agent_name, session_id)

        return jsonify({
            "status": "ok",
            "agent_id": agent.agent_id,
            "agent_name": agent.name,
            "connected": agent.connected,
            "session_id": session_id
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@app.route('/agents/list', methods=['GET'])
def list_agents():
    """List all agents on the bus"""
    session_id = request.args.get('session_id')

    if not session_id or session_id not in agents:
        return jsonify({
            "status": "error",
            "error": "Invalid session_id"
        }), 400

    agent = agents[session_id]
    all_agents = agent.query_agents()

    return jsonify({
        "status": "ok",
        "agents": all_agents,
        "count": len(all_agents)
    })


@app.route('/broadcast', methods=['POST'])
def broadcast():
    """Broadcast an event"""
    data = request.json
    session_id = data.get('session_id')
    event_type = data.get('event_type')
    event_data = data.get('data', {})

    if not session_id or session_id not in agents:
        return jsonify({
            "status": "error",
            "error": "Invalid session_id"
        }), 400

    if not event_type:
        return jsonify({
            "status": "error",
            "error": "event_type required"
        }), 400

    agent = agents[session_id]
    success = agent.broadcast(event_type, event_data)

    return jsonify({
        "status": "ok" if success else "error",
        "event_type": event_type,
        "broadcasted": success
    })


@app.route('/state/get', methods=['GET'])
def get_state():
    """Get value from shared state"""
    session_id = request.args.get('session_id')
    key = request.args.get('key')

    if not session_id or session_id not in agents:
        return jsonify({
            "status": "error",
            "error": "Invalid session_id"
        }), 400

    if not key:
        return jsonify({
            "status": "error",
            "error": "key required"
        }), 400

    agent = agents[session_id]
    value = agent.get_state(key)

    return jsonify({
        "status": "ok",
        "key": key,
        "value": value
    })


@app.route('/state/set', methods=['POST'])
def set_state():
    """Set value in shared state"""
    data = request.json
    session_id = data.get('session_id')
    key = data.get('key')
    value = data.get('value')

    if not session_id or session_id not in agents:
        return jsonify({
            "status": "error",
            "error": "Invalid session_id"
        }), 400

    if not key:
        return jsonify({
            "status": "error",
            "error": "key required"
        }), 400

    agent = agents[session_id]
    success = agent.set_state(key, value)

    return jsonify({
        "status": "ok" if success else "error",
        "key": key,
        "value": value,
        "updated": success
    })


@app.route('/subscribe', methods=['POST'])
def subscribe():
    """Subscribe to a topic"""
    data = request.json
    session_id = data.get('session_id')
    topic = data.get('topic')

    if not session_id or session_id not in agents:
        return jsonify({
            "status": "error",
            "error": "Invalid session_id"
        }), 400

    if not topic:
        return jsonify({
            "status": "error",
            "error": "topic required"
        }), 400

    agent = agents[session_id]
    agent.subscribe(topic)

    return jsonify({
        "status": "ok",
        "topic": topic,
        "message": f"Subscribed to {topic}"
    })


@app.route('/publish', methods=['POST'])
def publish():
    """Publish event to topic"""
    data = request.json
    session_id = data.get('session_id')
    topic = data.get('topic')
    payload = data.get('payload', {})

    if not session_id or session_id not in agents:
        return jsonify({
            "status": "error",
            "error": "Invalid session_id"
        }), 400

    if not topic:
        return jsonify({
            "status": "error",
            "error": "topic required"
        }), 400

    agent = agents[session_id]
    success = agent.publish(topic, payload)

    return jsonify({
        "status": "ok" if success else "error",
        "topic": topic,
        "published": success
    })


@app.route('/activity/log', methods=['POST'])
def log_activity():
    """Log an activity"""
    data = request.json
    session_id = data.get('session_id')
    action = data.get('action')
    details = data.get('details', {})

    if not session_id or session_id not in agents:
        return jsonify({
            "status": "error",
            "error": "Invalid session_id"
        }), 400

    if not action:
        return jsonify({
            "status": "error",
            "error": "action required"
        }), 400

    agent = agents[session_id]
    agent.log_activity(action, details)

    return jsonify({
        "status": "ok",
        "action": action,
        "logged": True
    })


@app.route('/agents/disconnect', methods=['POST'])
def disconnect_agent():
    """Disconnect an agent"""
    data = request.json
    session_id = data.get('session_id')

    if session_id and session_id in agents:
        agent = agents[session_id]
        agent.disconnect()
        del agents[session_id]

        return jsonify({
            "status": "ok",
            "message": "Agent disconnected"
        })

    return jsonify({
        "status": "error",
        "error": "Invalid session_id"
    }), 400


def main():
    """Run REST API server"""
    import argparse

    parser = argparse.ArgumentParser(description='QA Collaboration REST API')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8080, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')

    args = parser.parse_args()

    print(f"🚀 Starting QA Collaboration REST API on {args.host}:{args.port}")
    print(f"📡 API Documentation:")
    print(f"   POST /agents/register       - Register agent")
    print(f"   GET  /agents/list           - List all agents")
    print(f"   POST /broadcast             - Broadcast event")
    print(f"   GET  /state/get             - Get shared state")
    print(f"   POST /state/set             - Set shared state")
    print(f"   POST /subscribe             - Subscribe to topic")
    print(f"   POST /publish               - Publish to topic")
    print(f"   POST /activity/log          - Log activity")
    print(f"   POST /agents/disconnect     - Disconnect agent")
    print()

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    # Check if Flask is installed
    try:
        import flask
        import flask_cors
    except ImportError:
        print("❌ Flask not installed. Install with:")
        print("   pip install flask flask-cors")
        sys.exit(1)

    main()
