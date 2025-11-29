#!/usr/bin/env python3
"""
QA Swarm Communication Protocol
Defines inter-agent communication using QA tuples for cooperative multimodal processing
"""

from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import time
import json


class MessageType(Enum):
    """Types of messages in QA swarm protocol"""
    QA_TUPLE_SHARE = "qa_tuple_share"      # Share QA tuple with other agents
    AGENT_DISCOVERY = "agent_discovery"    # Discover available agents
    TASK_DELEGATION = "task_delegation"    # Delegate subtask to specific agent
    RESULT_AGGREGATION = "result_agg"      # Aggregate results from multiple agents
    COORDINATION_REQUEST = "coord_req"     # Request coordination for multimodal task
    STATUS_UPDATE = "status_update"        # Agent status and capability updates


class AgentCapability(Enum):
    """Agent capabilities in the swarm"""
    VISION_PROCESSING = "vision"
    LIDAR_PROCESSING = "lidar"
    SPECTRAL_PROCESSING = "spectral"
    AUDIO_PROCESSING = "audio"
    COORDINATION = "coordination"
    DATA_COLLECTION = "data_collection"


@dataclass
class QATuple:
    """QA tuple with closure constraints"""
    b: float
    e: float
    d: float  # Must equal b + e
    a: float  # Must equal e + d

    def __post_init__(self):
        """Validate closure constraints"""
        if abs(self.d - (self.b + self.e)) > 1e-6:
            raise ValueError(f"QA constraint violation: d={self.d} != b+e={self.b + self.e}")
        if abs(self.a - (self.e + self.d)) > 1e-6:
            raise ValueError(f"QA constraint violation: a={self.a} != e+d={self.e + self.d}")

    def to_dict(self) -> Dict[str, float]:
        return {"b": self.b, "e": self.e, "d": self.d, "a": self.a}

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> 'QATuple':
        return cls(b=data["b"], e=data["e"], d=data["d"], a=data["a"])


@dataclass
class SwarmMessage:
    """Message format for QA swarm communication"""
    message_id: str
    message_type: MessageType
    sender_agent: str
    target_agent: Optional[str]  # None for broadcast
    timestamp: float
    payload: Dict[str, Any]
    qa_context: Optional[QATuple] = None  # QA tuple context
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "message_id": self.message_id,
            "message_type": self.message_type.value,
            "sender_agent": self.sender_agent,
            "target_agent": self.target_agent,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "metadata": self.metadata
        }
        if self.qa_context:
            result["qa_context"] = self.qa_context.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SwarmMessage':
        qa_context = None
        if "qa_context" in data:
            qa_context = QATuple.from_dict(data["qa_context"])

        return cls(
            message_id=data["message_id"],
            message_type=MessageType(data["message_type"]),
            sender_agent=data["sender_agent"],
            target_agent=data.get("target_agent"),
            timestamp=data["timestamp"],
            payload=data["payload"],
            qa_context=qa_context,
            metadata=data.get("metadata", {})
        )


class QASwarmProtocol:
    """QA Swarm Communication Protocol Handler"""

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.agent_capabilities: List[AgentCapability] = []
        self.known_agents: Dict[str, List[AgentCapability]] = {}
        self.pending_responses: Dict[str, Dict] = {}
        self.message_history: List[SwarmMessage] = []

    def register_capability(self, capability: AgentCapability):
        """Register agent capability"""
        if capability not in self.agent_capabilities:
            self.agent_capabilities.append(capability)

    def create_qa_tuple_share(self,
                             qa_tuple: QATuple,
                             context: str = "multimodal_processing",
                             target_agent: Optional[str] = None) -> SwarmMessage:
        """Create QA tuple sharing message"""
        return SwarmMessage(
            message_id=f"qa_share_{int(time.time() * 1000)}",
            message_type=MessageType.QA_TUPLE_SHARE,
            sender_agent=self.agent_name,
            target_agent=target_agent,
            timestamp=time.time(),
            payload={
                "context": context,
                "qa_tuple": qa_tuple.to_dict()
            },
            qa_context=qa_tuple
        )

    def create_agent_discovery(self) -> SwarmMessage:
        """Create agent discovery message"""
        return SwarmMessage(
            message_id=f"discovery_{int(time.time() * 1000)}",
            message_type=MessageType.AGENT_DISCOVERY,
            sender_agent=self.agent_name,
            target_agent=None,  # Broadcast
            timestamp=time.time(),
            payload={
                "capabilities": [cap.value for cap in self.agent_capabilities],
                "status": "active"
            }
        )

    def create_task_delegation(self,
                              task_description: str,
                              target_capability: AgentCapability,
                              qa_context: Optional[QATuple] = None,
                              target_agent: Optional[str] = None) -> SwarmMessage:
        """Create task delegation message"""
        return SwarmMessage(
            message_id=f"delegate_{int(time.time() * 1000)}",
            message_type=MessageType.TASK_DELEGATION,
            sender_agent=self.agent_name,
            target_agent=target_agent,
            timestamp=time.time(),
            payload={
                "task_description": task_description,
                "required_capability": target_capability.value,
                "priority": "high"
            },
            qa_context=qa_context
        )

    def create_coordination_request(self,
                                   multimodal_task: str,
                                   required_capabilities: List[AgentCapability],
                                   qa_seed: Optional[QATuple] = None) -> SwarmMessage:
        """Create coordination request for multimodal task"""
        return SwarmMessage(
            message_id=f"coord_{int(time.time() * 1000)}",
            message_type=MessageType.COORDINATION_REQUEST,
            sender_agent=self.agent_name,
            target_agent=None,  # Broadcast to all agents
            timestamp=time.time(),
            payload={
                "multimodal_task": multimodal_task,
                "required_capabilities": [cap.value for cap in required_capabilities],
                "coordination_strategy": "parallel_processing"
            },
            qa_context=qa_seed
        )

    def create_result_aggregation(self,
                                 task_id: str,
                                 partial_results: List[Dict],
                                 final_qa_tuple: QATuple) -> SwarmMessage:
        """Create result aggregation message"""
        return SwarmMessage(
            message_id=f"agg_{int(time.time() * 1000)}",
            message_type=MessageType.RESULT_AGGREGATION,
            sender_agent=self.agent_name,
            target_agent=None,  # Broadcast results
            timestamp=time.time(),
            payload={
                "task_id": task_id,
                "partial_results_count": len(partial_results),
                "aggregated_result": final_qa_tuple.to_dict()
            },
            qa_context=final_qa_tuple
        )

    def handle_incoming_message(self, message: SwarmMessage) -> Optional[SwarmMessage]:
        """
        Handle incoming swarm message and return response if needed

        Returns:
            Response message or None
        """
        self.message_history.append(message)

        if message.message_type == MessageType.AGENT_DISCOVERY:
            # Update known agents
            self.known_agents[message.sender_agent] = [
                AgentCapability(cap) for cap in message.payload.get("capabilities", [])
            ]

            # Respond with our capabilities
            return self.create_agent_discovery()

        elif message.message_type == MessageType.QA_TUPLE_SHARE:
            # Process shared QA tuple
            qa_tuple = message.qa_context
            if qa_tuple:
                print(f"📥 {self.agent_name} received QA tuple from {message.sender_agent}: {qa_tuple}")
                # Agent-specific processing would go here
            return None

        elif message.message_type == MessageType.TASK_DELEGATION:
            # Check if we can handle this task
            required_cap = message.payload.get("required_capability")
            if required_cap and AgentCapability(required_cap) in self.agent_capabilities:
                print(f"🎯 {self.agent_name} accepting delegated task: {message.payload.get('task_description')}")
                # Task acceptance logic would go here
                return SwarmMessage(
                    message_id=f"accept_{message.message_id}",
                    message_type=MessageType.STATUS_UPDATE,
                    sender_agent=self.agent_name,
                    target_agent=message.sender_agent,
                    timestamp=time.time(),
                    payload={"status": "task_accepted", "original_message": message.message_id}
                )
            return None

        elif message.message_type == MessageType.COORDINATION_REQUEST:
            # Check if we can participate in coordination
            required_caps = [AgentCapability(cap) for cap in message.payload.get("required_capabilities", [])]
            if any(cap in self.agent_capabilities for cap in required_caps):
                print(f"🤝 {self.agent_name} joining coordination for: {message.payload.get('multimodal_task')}")
                return SwarmMessage(
                    message_id=f"join_{message.message_id}",
                    message_type=MessageType.STATUS_UPDATE,
                    sender_agent=self.agent_name,
                    target_agent=message.sender_agent,
                    timestamp=time.time(),
                    payload={"status": "coordination_join", "original_message": message.message_id}
                )
            return None

        return None

    def get_agents_with_capability(self, capability: AgentCapability) -> List[str]:
        """Get list of agents with specific capability"""
        return [agent for agent, caps in self.known_agents.items() if capability in caps]

    def broadcast_qa_context(self, qa_tuple: QATuple, context: str = "shared_context"):
        """Broadcast QA tuple to all known agents"""
        message = self.create_qa_tuple_share(qa_tuple, context)
        # In real implementation, this would send via the collaboration bus
        print(f"📡 {self.agent_name} broadcasting QA context: {qa_tuple}")
        return message
