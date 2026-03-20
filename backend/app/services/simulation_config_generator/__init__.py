"""
simulation_config_generator package.

VahanAI dispatch simulation configuration generator.

Public API:
    SimulationConfigGenerator — main service class
    SimulationParameters      — complete parameter configuration
    UnitConfig               — per-unit configuration
    CityCondition            — city conditions
    DistressSignal           — emergency signal
"""

from .models import (
    UnitConfig,
    CityCondition,
    DistressSignal,
    SimulationParameters,
    # Backward compatibility aliases
    AgentActivityConfig as UnitConfig,
    TimeSimulationConfig as SimulationConfig,
    EventConfig as DistressSignal,
)
from .service import SimulationConfigGenerator

__all__ = [
    "SimulationConfigGenerator",
    "SimulationParameters",
    "UnitConfig",
    "CityCondition",
    "DistressSignal",
]
