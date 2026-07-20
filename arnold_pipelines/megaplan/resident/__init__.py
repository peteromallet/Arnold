"""Resident Discord orchestration package boundary for Megaplan.

This package is intentionally split between reusable resident runtime seams
and Megaplan-specific profile/tool/cloud adapters. Implementation-heavy store,
schema, scheduler, and Discord wiring live behind those seams.
"""

from .agent_loop import (
    AgentLoopError,
    AgentRequest,
    AgentResponse,
    AgentRunner,
    CodexCliAgentRunner,
    DispatchProtocol,
    FakeAgentRunner,
    FakeAgentStep,
    FakeToolCall,
    OpenAICompatibleAgentRunner,
)
from .auth import (
    AuthorizationDecision,
    AuthorizationDenialRecord,
    AuthorizationSubject,
    ConfirmationDecision,
    ConfirmationManager,
    ConfirmationRequest,
    ResidentAuthorizer,
    StoreBackedConfirmationManager,
)
from .coalescing import AsyncBurstCoalescer, BurstBatch
from .config import ResidentConfig
from .discord import DiscordDeliveryTarget, DiscordInboundMessage, DiscordOutboundSink, ResidentDiscordService
from .profile import MegaplanResidentProfile
from .runtime import EmitProtocol, InboundEvent, OutboundMessage, ResidentRuntime
from .scheduler import (
    ResidentJobHandlers,
    SchedulerRunResult,
    ScheduledJobWorker,
    StoreScheduledJobBackend,
    make_store_scheduler,
)
from .tool_registry import ToolRegistry, ToolRegistration

__all__ = [
    "AgentLoopError",
    "AgentRequest",
    "AgentResponse",
    "AgentRunner",
    "AsyncBurstCoalescer",
    "AuthorizationDecision",
    "AuthorizationDenialRecord",
    "AuthorizationSubject",
    "BurstBatch",
    "ConfirmationDecision",
    "ConfirmationManager",
    "ConfirmationRequest",
    "CodexCliAgentRunner",
    "DiscordDeliveryTarget",
    "DiscordInboundMessage",
    "DiscordOutboundSink",
    "DispatchProtocol",
    "EmitProtocol",
    "FakeAgentRunner",
    "FakeAgentStep",
    "FakeToolCall",
    "OpenAICompatibleAgentRunner",
    "MegaplanResidentProfile",
    "InboundEvent",
    "OutboundMessage",
    "ResidentAuthorizer",
    "ResidentConfig",
    "ResidentDiscordService",
    "ResidentJobHandlers",
    "ResidentRuntime",
    "SchedulerRunResult",
    "ScheduledJobWorker",
    "StoreScheduledJobBackend",
    "StoreBackedConfirmationManager",
    "ToolRegistry",
    "ToolRegistration",
    "make_store_scheduler",
]
