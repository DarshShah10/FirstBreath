"""
Legacy Intervention Recommender - Kept for backward compatibility.

This module provides the original InterventionRecommendation classes
and functions for backward compatibility with existing code.
"""

from .actionable_intervention_recommender import (
    InterventionType,
    InterventionPriority,
    ActionStep,
    ActionableRecommendation,
    BottleneckSeverity,
    BottleneckAnalysis,
    ContactInfo,
    ResourceStatus,
    ResponseChainStatus,
    InterventionScenario,
    OutcomeProjection,
    ActionableResponseAnalysis,
    ActionableInterventionRecommender,
    generate_actionable_report,
    ReportFormat
)

# Re-export for backward compatibility
__all__ = [
    # Legacy classes
    'InterventionType',
    'InterventionPriority',
    'BottleneckAnalysis',
    # Legacy function
    'generate_intervention_report',
    # New classes
    'ActionStep',
    'ActionableRecommendation',
    'BottleneckSeverity',
    'ContactInfo',
    'ResourceStatus',
    'ResponseChainStatus',
    'InterventionScenario',
    'OutcomeProjection',
    'ActionableResponseAnalysis',
    # New classes and functions
    'ActionableInterventionRecommender',
    'generate_actionable_report',
    'ReportFormat'
]
