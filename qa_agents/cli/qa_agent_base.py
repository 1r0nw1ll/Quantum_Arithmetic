"""
Refactored module: qa_agents/cli/qa_agent_base.py
"""

# Auto header added by external refactor
#!/usr/bin/env python3
"""
QA Agent Base Class - Base class for all collaborative agents
Provides real-time communication, state sharing, and event handling
"""

import json
import sys
import time
import threading
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
from collections import defaultdict

try:
    import zmq
    ZMQ_AVAILABLE = True
except ImportError:
    ZMQ_AVAILABLE = False

# QA swarm protocol will be imported dynamically


class CollaborativeAgent:
    """Base class for agents with real-time collaboration capabilities"""

    def __init__(self,
                 name: str,
                 bus_host: str = "localhost",
                 pub_port: int = 5555,
                 router_port: int = 5556,
                 state_port: int = 5557,
                 auto_connect: bool = True,
                 metadata: Optional[Dict] = None):
        """
        Initialize collaborative agent

        Args:
            name: Agent name (e.g., 'scout', 'executor')
            bus_host: Collaboration bus hostname
            pub_port: PUB/SUB port
            router_port: Request/response port
            state_port: Shared state port
            auto_connect: Automatically connect to bus
            metadata: Additional metadata to register
        """
        self.name = name
        self.agent_id = f"{name}_{uuid.uuid4().hex[:8]}"
        self.bus_host = bus_host
        self.pub_port = pub_port
        self.router_port = router_port
        self.state_port = state_port
        self.metadata = metadata or {}

        # ZMQ
        if not ZMQ_AVAILABLE:
            # Log to stderr so this does NOT contaminate the stdio JSON-RPC
            # stream when this class is used from inside an MCP server.
            print(
                f"⚠️  {self.name}: ZeroMQ not available, running in standalone mode",
                file=sys.stderr,
            )
            self.collaborative = False
            self.connected = False
            return

        self.collaborative = True
        self.context = zmq.Context()
        self.req_socket = None
        self.sub_socket = None
        self.state_socket = None

        # Event handlers
        self.event_handlers: Dict[str, List[Callable]] = defaultdict(list)

        # QA Swarm Protocol
        try:
            sys.path.append(str(Path(__file__).parent))
            from qa_swarm_protocol import QASwarmProtocol
            self.swarm_protocol = QASwarmProtocol(name)
            self.swarm_enabled = True
        except ImportError:
            self.swarm_protocol = None
            self.swarm_enabled = False

        # Control
        self.connected = False
        self.running = False
        self.heartbeat_thread = None
        self.listener_thread = None

        if auto_connect:
            self.connect()

    def connect(self):
        """Connect to collaboration bus"""
        if not self.collaborative:
            print(f"ℹ️  {self.name}: Running in standalone mode (no collaboration)")
            return

        try:
            # Request/response socket
            self.req_socket = self.context.socket(zmq.REQ)
            self.req_socket.connect(f"tcp://{self.bus_host}:{self.router_port}")

            # Subscribe socket
            self.sub_socket = self.context.socket(zmq.SUB)
            self.sub_socket.connect(f"tcp://{self.bus_host}:{self.pub_port}")

            # State socket
            self.state_socket = self.context.socket(zmq.REQ)
            self.state_socket.connect(f"tcp://{self.bus_host}:{self.state_port}")

            # Register with bus
            response = self._send_request({
                'action': 'register',
                'agent_id': self.agent_id,
                'name': self.name,
                'metadata': self.metadata
            })

            if response.get('status') == 'ok':
                self.connected = True
                self.running = True

                # Start heartbeat
                self.heartbeat_thread = threading.Thread(target=self._heartbeat_worker, daemon=True)
                self.heartbeat_thread.start()

                # Start event listener
                self.listener_thread = threading.Thread(target=self._event_listener, daemon=True)
                self.listener_thread.start()

                print(
                    f"✅ {self.name} connected to collaboration bus (ID: {self.agent_id})",
                    file=sys.stderr,
                )
            else:
                print(
                    f"❌ {self.name} registration failed: {response.get('error')}",
                    file=sys.stderr,
                )

        except Exception as e:
            print(f"❌ {self.name} connection failed: {e}", file=sys.stderr)
            self.collaborative = False

    def disconnect(self):
        """Disconnect from collaboration bus"""
        if not self.connected:
            return

        self.running = False

        # Unregister
        try:
            self._send_request({
                'action': 'unregister',
                'agent_id': self.agent_id
            })
        except:
            pass

        # Close sockets
        if self.req_socket:
            self.req_socket.close()
        if self.sub_socket:
            self.sub_socket.close()
        if self.state_socket:
            self.state_socket.close()

        self.connected = False
        print(f"👋 {self.name} disconnected", file=sys.stderr)

    def _send_request(self, data: Dict) -> Dict:
        """Send request to bus and wait for response"""
        if not self.req_socket:
            return {"status": "error", "error": "Not connected"}

        try:
            self.req_socket.send_string(json.dumps(data))

            # Poll with timeout (5 seconds)
            if self.req_socket.poll(5000):
                response = self.req_socket.recv_string()
                return json.loads(response)
            else:
                return {"status": "error", "error": "Request timeout"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _heartbeat_worker(self):
        """Send periodic heartbeats to bus"""
        while self.running:
            try:
                # Create a separate socket for heartbeat to avoid blocking main req socket
                heartbeat_socket = self.context.socket(zmq.REQ)
                heartbeat_socket.connect(f"tcp://{self.bus_host}:{self.router_port}")

                heartbeat_socket.send_string(json.dumps({
                    'action': 'heartbeat',
                    'agent_id': self.agent_id
                }))

                # Wait for response with timeout
                if heartbeat_socket.poll(1000):
                    heartbeat_socket.recv_string()

                heartbeat_socket.close()

            except Exception as e:
                if self.running:
                    print(f"⚠️  {self.name} heartbeat error: {e}")

            time.sleep(10)  # Heartbeat every 10 seconds

    def _event_listener(self):
        """Listen for events on subscribed topics"""
        while self.running:
            try:
                if self.sub_socket and self.sub_socket.poll(100):
                    message = self.sub_socket.recv_string()

                    # Parse message: "topic {json}"
                    parts = message.split(' ', 1)
                    if len(parts) == 2:
                        topic, json_data = parts
                        data = json.loads(json_data)

                        # Call registered handlers
                        for handler in self.event_handlers.get(topic, []):
                            try:
                                handler(data)
                            except Exception as e:
                                print(f"⚠️  {self.name} event handler error: {e}")

                        # Also call wildcard handlers
                        for handler in self.event_handlers.get('*', []):
                            try:
                                handler(data)
                            except Exception as e:
                                print(f"⚠️  {self.name} wildcard handler error: {e}")

            except Exception as e:
                if self.running:
                    print(f"⚠️  {self.name} listener error: {e}")

    def subscribe(self, topic: str):
        """Subscribe to topic"""
        if not self.connected:
            return

        # Subscribe on ZMQ socket
        if self.sub_socket:
            self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, topic)

        # Notify bus
        response = self._send_request({
            'action': 'subscribe',
            'agent_id': self.agent_id,
            'topic': topic
        })

        if response.get('status') == 'ok':
            print(f"📡 {self.name} subscribed to: {topic}")

    def unsubscribe(self, topic: str):
        """Unsubscribe from topic"""
        if not self.connected:
            return

        # Unsubscribe on ZMQ socket
        if self.sub_socket:
            self.sub_socket.setsockopt_string(zmq.UNSUBSCRIBE, topic)

        # Notify bus
        self._send_request({
            'action': 'unsubscribe',
            'agent_id': self.agent_id,
            'topic': topic
        })

    def on(self, topic: str, handler: Callable[[Dict], None]):
        """Register event handler for topic"""
        self.event_handlers[topic].append(handler)

    def publish(self, topic: str, payload: Dict):
        """Publish event to topic"""
        if not self.connected:
            return

        response = self._send_request({
            'action': 'publish',
            'topic': topic,
            'payload': payload
        })

        return response.get('status') == 'ok'

    def broadcast(self, event_type: str, data: Dict):
        """Broadcast event (convenience method)"""
        return self.publish(event_type, {
            'agent_id': self.agent_id,
            'agent_name': self.name,
            'event_type': event_type,
            'data': data,
            'timestamp': datetime.now().isoformat()
        })

    def get_state(self, key: str, default: Any = None) -> Any:
        """Get value from shared state"""
        if not self.connected:
            return default

        try:
            self.state_socket.send_string(json.dumps({
                'action': 'get',
                'key': key
            }))

            # Poll with timeout (5 seconds)
            if self.state_socket.poll(5000):
                response_str = self.state_socket.recv_string()
                response = json.loads(response_str)

                if response.get('exists'):
                    return response.get('value')
                else:
                    return default
            else:
                print(f"⚠️  {self.name} get_state timeout for key: {key}")
                return default

        except Exception as e:
            print(f"⚠️  {self.name} get_state error: {e}")
            return default

    def set_state(self, key: str, value: Any) -> bool:
        """Set value in shared state"""
        if not self.connected:
            return False

        try:
            self.state_socket.send_string(json.dumps({
                'action': 'set',
                'key': key,
                'value': value
            }))

            # Poll with timeout (5 seconds)
            if self.state_socket.poll(5000):
                response_str = self.state_socket.recv_string()
                response = json.loads(response_str)

                return response.get('status') == 'ok'
            else:
                print(f"⚠️  {self.name} set_state timeout for key: {key}")
                return False

        except Exception as e:
            print(f"⚠️  {self.name} set_state error: {e}")
            return False

    def query_agents(self, filters: Optional[Dict] = None) -> List[Dict]:
        """Query other registered agents"""
        if not self.connected:
            return []

        response = self._send_request({
            'action': 'query_agents',
            'filters': filters or {}
        })

        if response.get('status') == 'ok':
            return response.get('agents', [])
        else:
            return []

    def log_activity(self, action: str, details: Dict):
        """Log agent activity to shared state"""
        activity = {
            'agent_id': self.agent_id,
            'agent_name': self.name,
            'action': action,
            'details': details,
            'timestamp': datetime.now().isoformat()
        }

        # Broadcast activity event
        self.broadcast('activity', activity)

        # Also store in shared state
        activities_key = f"activities:{self.agent_id}"
        activities = self.get_state(activities_key, [])
        activities.append(activity)

        # Keep last 100 activities
        if len(activities) > 100:
            activities = activities[-100:]

        self.set_state(activities_key, activities)

    def __enter__(self):
        """Context manager entry"""
        if not self.connected:
            self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()

    # QA Swarm Protocol Methods
    def register_swarm_capability(self, capability: str):
        """Register a capability for swarm coordination"""
        if self.swarm_enabled and self.swarm_protocol:
            from .qa_swarm_protocol import AgentCapability
            try:
                cap_enum = AgentCapability(capability.lower())
                self.swarm_protocol.register_capability(cap_enum)
                print(f"🧠 {self.name} registered swarm capability: {capability}")
            except ValueError:
                print(f"⚠️  Unknown capability: {capability}")

    def send_qa_tuple(self, qa_tuple_data: Dict, target_agent: Optional[str] = None):
        """Send QA tuple to other agents"""
        if not self.swarm_enabled or not self.swarm_protocol:
            return

        try:
            from .qa_swarm_protocol import QATuple
            qa_tuple = QATuple.from_dict(qa_tuple_data)
            message = self.swarm_protocol.create_qa_tuple_share(qa_tuple, target_agent=target_agent)
            # In real implementation, send via collaboration bus
            target = target_agent or "all agents"
            print(f"📤 {self.name} sending QA tuple to {target}")
        except Exception as e:
            print(f"❌ Failed to send QA tuple: {e}")

    def request_coordination(self, task_description: str, required_capabilities: List[str]):
        """Request coordination for multimodal task"""
        if not self.swarm_enabled or not self.swarm_protocol:
            return

        try:
            from .qa_swarm_protocol import AgentCapability
            caps = [AgentCapability(cap.lower()) for cap in required_capabilities]
            message = self.swarm_protocol.create_coordination_request(task_description, caps)
            print(f"🤝 {self.name} requesting coordination for: {task_description}")
        except Exception as e:
            print(f"❌ Failed to request coordination: {e}")

    def delegate_task(self, task_description: str, capability: str, target_agent: Optional[str] = None):
        """Delegate task to specific agent or capability"""
        if not self.swarm_enabled or not self.swarm_protocol:
            return

        try:
            from .qa_swarm_protocol import AgentCapability
            cap_enum = AgentCapability(capability.lower())
            message = self.swarm_protocol.create_task_delegation(task_description, cap_enum, target_agent=target_agent)
            target = target_agent or capability
            print(f"🎯 {self.name} delegating task to {target}")
        except Exception as e:
            print(f"❌ Failed to delegate task: {e}")


# Example usage
if __name__ == "__main__":
    # Create a test agent
    agent = CollaborativeAgent("test_agent")

    # Subscribe to events
    agent.subscribe("task_completed")
    agent.subscribe("state_changed")

    # Register event handlers
    def on_task_completed(data):
        print(f"📋 Task completed: {data}")

    def on_state_changed(data):
        print(f"🔄 State changed: {data}")

    agent.on("task_completed", on_task_completed)
    agent.on("state_changed", on_state_changed)

    # Test shared state
    agent.set_state("test_key", "test_value")
    value = agent.get_state("test_key")
    print(f"State value: {value}")

    # Test broadcasting
    agent.broadcast("test_event", {"message": "Hello from test agent!"})

    # Query other agents
    agents = agent.query_agents()
    print(f"Active agents: {len(agents)}")

    # Keep running
    try:
        print("\n✨ Test agent running. Press Ctrl+C to stop\n")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n")

    agent.disconnect()
