"""
simulation_config_generator package.

Intelligently generates simulation parameters using an LLM.

Public API:
    SimulationConfigGenerator — main service class
    SimulationParameters      — complete parameter configuration
    AgentActivityConfig       — per-agent activity configuration
    TimeSimulationConfig      — time simulation configuration
    EventConfig               — event configuration
    PlatformConfig            — platform-specific configuration
"""

from .models import (
    AgentActivityConfig,
    EventConfig,
    PlatformConfig,
    SimulationParameters,
    TimeSimulationConfig,
)
from .service import SimulationConfigGenerator

__all__ = [
    "SimulationConfigGenerator",
    "SimulationParameters",
    "AgentActivityConfig",
    "TimeSimulationConfig",
    "EventConfig",
    "PlatformConfig",
]
