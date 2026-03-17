"""
report_agent package.

Implements ReACT-pattern simulation report generation using LangChain + Zep.

Public API:
    ReportAgent         — main report generation agent
    ReportManager       — report persistence and retrieval
    Report              — complete report data model
    ReportOutline       — report outline
    ReportSection       — individual report section
    ReportStatus        — report generation status enum
    ReportLogger        — structured JSONL action logger
    ReportConsoleLogger — plain-text console logger
"""

from .models import ReportStatus, ReportSection, ReportOutline, Report
from .loggers import ReportLogger, ReportConsoleLogger
from .manager import ReportManager
from .service import ReportAgent

__all__ = [
    "ReportAgent",
    "ReportManager",
    "Report",
    "ReportOutline",
    "ReportSection",
    "ReportStatus",
    "ReportLogger",
    "ReportConsoleLogger",
]
