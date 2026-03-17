"""
simulation_runner package.

Manages simulation process lifecycle: starting, monitoring, pausing, resuming,
and stopping OASIS social simulations. Tracks per-round progress and agent actions
in real-time.

Public API:
    SimulationRunner    — main runner service (process management, state tracking)
    SimulationRunState  — real-time simulation run state
    RunnerStatus        — runner status enum
    AgentAction         — agent action record
    RoundSummary        — per-round summary
"""

from .models import RunnerStatus, AgentAction, RoundSummary, SimulationRunState
from .service import SimulationRunner

__all__ = [
    "SimulationRunner",
    "SimulationRunState",
    "RunnerStatus",
    "AgentAction",
    "RoundSummary",
]
