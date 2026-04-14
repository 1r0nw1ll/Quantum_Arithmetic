"""
Auto-refactor: normalize formatting for qa_collab_bus.py
"""

#!/usr/bin/env python3
"""
QA Collaboration Bus - Real-time agent coordination system
Uses ZeroMQ for lightweight, fast message passing without a broker
"""

import json
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Any, Optional, Callable
from collections import defaultdict
import queue

try:
    import zmq
    ZMQ_AVAILABLE = True
except ImportError:
    ZMQ_AVAILABLE = False
    print("⚠️  ZeroMQ not available. Install with: pip install pyzmq")


class CollaborationBus:
    """Real-time message bus for agent collaboration"""

    def __init__(self,
                 pub_port: int = 5555,
                 router_port: int = 5556,
                 state_port: int = 5557,
                 base_dir: Optional[Path] = None):
        """
        Initialize collaboration bus

        Args:
            pub_port: Port for pub/sub events
            router_port: Port for request/response
            state_port: Port for shared state
            base_dir: Base directory for logs
        """
        if not ZMQ_AVAILABLE:
            raise RuntimeError("ZeroMQ required for collaboration bus")

        self.pub_port = pub_port
        self.router_port = router_port
        self.state_port = state_port
        self.base_dir = base_dir or Path(__file__).parent.parent.parent
        self.logs_dir = self.base_dir / "logs"
        self.logs_dir.mkdir(exist_ok=True)
        self.event_log_path = self.logs_dir / "collab_events.jsonl"
        self._event_log_lock = threading.Lock()

        # ZMQ context and sockets
        self.context = zmq.Context()
        self.pub_socket = None
        self.router_socket = None
        self.state_socket = None

        # Agent registry
        self.agents: Dict[str, Dict] = {}  # agent_id -> {name, status, last_heartbeat, ...}
        self.subscriptions: Dict[str, Set[str]] = defaultdict(set)  # topic -> {agent_ids}

        # Shared state
        self.shared_state: Dict[str, Any] = {}

        # Message history (for debugging)
        self.message_history: List[Dict] = []
        self.max_history = 1000

        # Control
        self.running = False
        self.threads: List[threading.Thread] = []

    def start(self):
        """Start the collaboration bus"""
        if not ZMQ_AVAILABLE:
            print("❌ Cannot start bus: ZeroMQ not available")
            return

        print("🚀 Starting QA Collaboration Bus...")

        # Initialize sockets
        self.pub_socket = self.context.socket(zmq.PUB)
        self.pub_socket.bind(f"tcp://*:{self.pub_port}")

        self.router_socket = self.context.socket(zmq.ROUTER)
        self.router_socket.bind(f"tcp://*:{self.router_port}")

        self.state_socket = self.context.socket(zmq.REP)
        self.state_socket.bind(f"tcp://*:{self.state_port}")

        self.running = True

        # Start worker threads
        self.threads = [
            threading.Thread(target=self._router_worker, daemon=True),
            threading.Thread(target=self._state_worker, daemon=True),
            threading.Thread(target=self._heartbeat_monitor, daemon=True),
        ]

        for thread in self.threads:
            thread.start()

        print(f"✅ Bus running:")
        print(f"   • PUB/SUB: tcp://localhost:{self.pub_port}")
        print(f"   • ROUTER:  tcp://localhost:{self.router_port}")
        print(f"   • STATE:   tcp://localhost:{self.state_port}")

    def stop(self):
        """Stop the collaboration bus"""
        print("🛑 Stopping QA Collaboration Bus...")
        self.running = False

        # Give threads time to finish
        time.sleep(0.5)

        # Close sockets
        if self.pub_socket:
            self.pub_socket.close()
        if self.router_socket:
            self.router_socket.close()
        if self.state_socket:
            self.state_socket.close()

        self.context.term()
        print("✅ Bus stopped")

    def _router_worker(self):
        """Handle request/response messages"""
        while self.running:
            try:
                # Non-blocking receive with timeout
                if self.router_socket.poll(100):
                    identity, empty, message = self.router_socket.recv_multipart()

                    try:
                        data = json.loads(message.decode('utf-8'))
                        # Identity can be binary, use hex representation
                        identity_str = identity.hex() if isinstance(identity, bytes) else str(identity)
                        response = self._handle_request(data, identity_str)

                        self.router_socket.send_multipart([
                            identity,
                            b'',
                            json.dumps(response).encode('utf-8')
                        ])
                    except Exception as e:
                        error_response = {
                            "status": "error",
                            "error": str(e),
                            "timestamp": datetime.now().isoformat()
                        }
                        self.router_socket.send_multipart([
                            identity,
                            b'',
                            json.dumps(error_response).encode('utf-8')
                        ])

            except Exception as e:
                if self.running:
                    print(f"⚠️  Router error: {e}")

    def _state_worker(self):
        """Handle shared state requests"""
        while self.running:
            try:
                if self.state_socket.poll(100):
                    message = self.state_socket.recv_string()

                    try:
                        data = json.loads(message)
                        response = self._handle_state_request(data)
                        self.state_socket.send_string(json.dumps(response))
                    except Exception as e:
                        error_response = {
                            "status": "error",
                            "error": str(e)
                        }
                        self.state_socket.send_string(json.dumps(error_response))

            except Exception as e:
                if self.running:
                    print(f"⚠️  State error: {e}")

    def _heartbeat_monitor(self):
        """Monitor agent heartbeats and clean up stale agents"""
        while self.running:
            try:
                now = time.time()
                stale_agents = []

                for agent_id, info in self.agents.items():
                    last_beat = info.get('last_heartbeat', 0)
                    if now - last_beat > 30:  # 30 second timeout
                        stale_agents.append(agent_id)

                for agent_id in stale_agents:
                    self._unregister_agent(agent_id)
                    print(f"⚠️  Agent timeout: {agent_id}")

                time.sleep(5)  # Check every 5 seconds

            except Exception as e:
                if self.running:
                    print(f"⚠️  Heartbeat monitor error: {e}")

    def _handle_request(self, data: Dict, identity: str) -> Dict:
        """Handle incoming requests from agents"""
        action = data.get('action')

        if action == 'register':
            return self._register_agent(data, identity)
        elif action == 'unregister':
            return self._unregister_agent(data.get('agent_id'))
        elif action == 'heartbeat':
            return self._heartbeat(data.get('agent_id'))
        elif action == 'subscribe':
            return self._subscribe(data.get('agent_id'), data.get('topic'))
        elif action == 'unsubscribe':
            return self._unsubscribe(data.get('agent_id'), data.get('topic'))
        elif action == 'publish':
            return self._publish_event(data)
        elif action == 'query_agents':
            return self._query_agents(data.get('filters', {}))
        else:
            return {"status": "error", "error": f"Unknown action: {action}"}

    def _handle_state_request(self, data: Dict) -> Dict:
        """Handle shared state operations"""
        action = data.get('action')

        if action == 'get':
            key = data.get('key')
            return {
                "status": "ok",
                "value": self.shared_state.get(key),
                "exists": key in self.shared_state
            }
        elif action == 'set':
            key = data.get('key')
            value = data.get('value')
            self.shared_state[key] = value

            # Broadcast state change
            self._broadcast_event('state_changed', {
                'key': key,
                'value': value,
                'timestamp': datetime.now().isoformat()
            })

            return {"status": "ok"}
        elif action == 'delete':
            key = data.get('key')
            if key in self.shared_state:
                del self.shared_state[key]
            return {"status": "ok"}
        elif action == 'keys':
            return {
                "status": "ok",
                "keys": list(self.shared_state.keys())
            }
        else:
            return {"status": "error", "error": f"Unknown state action: {action}"}

    def _register_agent(self, data: Dict, identity: str) -> Dict:
        """Register a new agent"""
        agent_id = data.get('agent_id') or identity
        agent_name = data.get('name', 'unknown')

        self.agents[agent_id] = {
            'id': agent_id,
            'name': agent_name,
            'status': 'active',
            'registered_at': datetime.now().isoformat(),
            'last_heartbeat': time.time(),
            'metadata': data.get('metadata', {})
        }

        # Broadcast registration
        self._broadcast_event('agent_registered', {
            'agent_id': agent_id,
            'name': agent_name,
            'timestamp': datetime.now().isoformat()
        })

        print(f"✅ Agent registered: {agent_name} ({agent_id})")

        return {
            "status": "ok",
            "agent_id": agent_id,
            "message": f"Agent {agent_name} registered successfully"
        }

    def _unregister_agent(self, agent_id: str) -> Dict:
        """Unregister an agent"""
        if agent_id in self.agents:
            agent_name = self.agents[agent_id].get('name', agent_id)
            del self.agents[agent_id]

            # Remove from subscriptions
            for topic, subscribers in self.subscriptions.items():
                subscribers.discard(agent_id)

            # Broadcast unregistration
            self._broadcast_event('agent_unregistered', {
                'agent_id': agent_id,
                'name': agent_name,
                'timestamp': datetime.now().isoformat()
            })

            print(f"👋 Agent unregistered: {agent_name} ({agent_id})")

        return {"status": "ok"}

    def _heartbeat(self, agent_id: str) -> Dict:
        """Update agent heartbeat"""
        if agent_id in self.agents:
            self.agents[agent_id]['last_heartbeat'] = time.time()
            return {"status": "ok"}
        else:
            return {"status": "error", "error": "Agent not registered"}

    def _subscribe(self, agent_id: str, topic: str) -> Dict:
        """Subscribe agent to topic"""
        self.subscriptions[topic].add(agent_id)
        return {
            "status": "ok",
            "message": f"Subscribed to {topic}"
        }

    def _unsubscribe(self, agent_id: str, topic: str) -> Dict:
        """Unsubscribe agent from topic"""
        self.subscriptions[topic].discard(agent_id)
        return {
            "status": "ok",
            "message": f"Unsubscribed from {topic}"
        }

    def _publish_event(self, data: Dict) -> Dict:
        """Publish event to subscribers"""
        topic = data.get('topic', 'general')
        payload = data.get('payload', {})

        self._broadcast_event(topic, payload)

        return {
            "status": "ok",
            "subscribers": len(self.subscriptions.get(topic, set()))
        }

    def _broadcast_event(self, topic: str, payload: Dict):
        """Broadcast event on pub socket"""
        if self.pub_socket:
            message = {
                'topic': topic,
                'payload': payload,
                'timestamp': datetime.now().isoformat()
            }

            # Add to history
            self.message_history.append(message)
            if len(self.message_history) > self.max_history:
                self.message_history.pop(0)

            self._append_event_log(message)

            # Send on ZMQ
            self.pub_socket.send_string(
                f"{topic} {json.dumps(message)}"
            )

    def _append_event_log(self, message: Dict) -> None:
        """Persist broadcast events so MCP read_events reflects live ZMQ traffic."""
        try:
            line = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
            with self._event_log_lock:
                with self.event_log_path.open("a", encoding="utf-8") as handle:
                    handle.write(line + "\n")
        except Exception as e:
            if self.running:
                print(f"⚠️  Event log write error: {e}")

    def _query_agents(self, filters: Dict) -> Dict:
        """Query registered agents"""
        results = []

        for agent_id, info in self.agents.items():
            match = True

            # Apply filters
            for key, value in filters.items():
                if info.get(key) != value:
                    match = False
                    break

            if match:
                results.append(info)

        return {
            "status": "ok",
            "agents": results,
            "count": len(results)
        }

    def get_status(self) -> Dict:
        """Get bus status"""
        return {
            "running": self.running,
            "agents": len(self.agents),
            "topics": len(self.subscriptions),
            "state_keys": len(self.shared_state),
            "message_history": len(self.message_history),
            "agents_list": list(self.agents.values())
        }


def main():
    """Run collaboration bus as standalone service"""
    import signal

    bus = CollaborationBus()

    def signal_handler(sig, frame):
        bus.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    bus.start()

    print("\n📊 Collaboration Bus Status:")
    print("   Press Ctrl+C to stop\n")

    try:
        while bus.running:
            time.sleep(1)

            # Print status every 10 seconds
            if int(time.time()) % 10 == 0:
                status = bus.get_status()
                print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                      f"Agents: {status['agents']} | "
                      f"Topics: {status['topics']} | "
                      f"State: {status['state_keys']} keys")

    except KeyboardInterrupt:
        pass

    bus.stop()


if __name__ == "__main__":
    main()
