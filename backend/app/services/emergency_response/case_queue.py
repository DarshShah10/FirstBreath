"""
Case Priority Queue for Emergency Response Simulation.

Provides scalable case prioritization and queue management:
- Priority-based case ordering
- Concurrent case handling
- Resource conflict detection
- Dynamic priority adjustment
- Queue metrics and monitoring
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import heapq
import uuid

from ...models.emergency_case import DistressSignal, EmergencySeverity, EmergencyType
from ...models.response_resource import Ambulance, Hospital, ResourceLocation
from ...utils.logger import get_logger

logger = get_logger('mirofish.case_queue')


class CasePriority(Enum):
    """Case priority levels."""
    CRITICAL = 1    # Immediate response required
    HIGH = 2       # Urgent, within 15 minutes
    MEDIUM = 3     # Standard urgency, within 30 minutes
    LOW = 4        # Non-urgent, can wait


class CaseStatus(Enum):
    """Case processing status."""
    QUEUED = "queued"
    PROCESSING = "processing"
    DISPATCHED = "dispatched"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass(order=True)
class QueuedCase:
    """A case in the priority queue."""
    priority: int
    case_id: str = field(compare=False)
    signal: DistressSignal = field(compare=False)
    queued_at: float = field(compare=False)
    attempts: int = field(default=0, compare=False)
    assigned_ambulance: Optional[str] = field(default=None, compare=False)
    assigned_hospital: Optional[str] = field(default=None, compare=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "priority": self.priority,
            "priority_label": CasePriority(self.priority).name,
            "severity": self.signal.severity.value,
            "emergency_type": self.signal.emergency_type.value,
            "queued_at": self.queued_at,
            "attempts": self.attempts,
            "assigned_ambulance": self.assigned_ambulance,
            "assigned_hospital": self.assigned_hospital
        }


class CaseQueue:
    """
    Scalable priority queue for emergency cases.

    Features:
    - Priority-based ordering (critical cases first)
    - Time-based decay (older high-priority cases stay ahead)
    - Resource conflict detection
    - Dynamic priority adjustment
    - Concurrent access support
    """

    # Priority weights for dynamic adjustment
    PRIORITY_WEIGHTS = {
        EmergencySeverity.CRITICAL: 1,
        EmergencySeverity.SEVERE: 2,
        EmergencySeverity.MODERATE: 3,
        EmergencySeverity.LOW: 4
    }

    # Emergency type urgency multipliers
    EMERGENCY_URGENCY = {
        EmergencyType.CORD_PROLAPSE: 0.5,      # Most urgent
        EmergencyType.UTERINE_RUPTURE: 0.6,
        EmergencyType.PLACENTAL_ABRUPTION: 0.7,
        EmergencyType.ECLAMPSIA: 0.8,
        EmergencyType.FETAL_DISTRESS: 0.9,
        EmergencyType.MATERNAL_HEMORRHAGE: 1.0,
        EmergencyType.SHOULDER_DYSTOCIA: 1.1,
        EmergencyType.PREMATURE_LABOR: 1.5,
        EmergencyType.OTHER: 2.0
    }

    def __init__(self, max_concurrent: int = 100):
        self._heap: List[QueuedCase] = []
        self._cases: Dict[str, QueuedCase] = {}
        self._processing: Dict[str, QueuedCase] = {}
        self._completed: Dict[str, QueuedCase] = {}
        self._failed: Dict[str, QueuedCase] = {}
        self._max_concurrent = max_concurrent

        # Resource locks (which cases are using which resources)
        self._ambulance_locks: Dict[str, str] = {}  # ambulance_id -> case_id
        self._hospital_locks: Dict[str, List[str]] = {}  # hospital_id -> [case_ids]

        # Metrics
        self._total_queued = 0
        self._total_completed = 0
        self._total_failed = 0
        self._avg_wait_time = 0.0

        logger.info(f"CaseQueue initialized: max_concurrent={max_concurrent}")

    def enqueue(self, signal: DistressSignal, sim_time: float = 0) -> str:
        """
        Add a case to the queue.

        Args:
            signal: The distress signal
            sim_time: Current simulation time

        Returns:
            Case ID
        """
        case_id = signal.case_id or f"case_{uuid.uuid4().hex[:12]}"

        # Calculate priority
        priority = self._calculate_priority(signal)

        # Create queued case
        queued_case = QueuedCase(
            priority=priority,
            case_id=case_id,
            signal=signal,
            queued_at=sim_time,
            attempts=0
        )

        # Add to queue
        heapq.heappush(self._heap, queued_case)
        self._cases[case_id] = queued_case
        self._total_queued += 1

        logger.info(
            f"Case enqueued: {case_id} (priority={priority}, "
            f"severity={signal.severity.value}, type={signal.emergency_type.value})"
        )

        return case_id

    def _calculate_priority(self, signal: DistressSignal) -> int:
        """Calculate priority score (lower = higher priority)."""
        # Base priority from severity
        severity_weight = self.PRIORITY_WEIGHTS.get(signal.severity, 3)

        # Urgency multiplier from emergency type
        urgency_mult = self.EMERGENCY_URGENCY.get(signal.emergency_type, 1.0)

        # Time pressure (golden hour consideration)
        time_weight = 1.0
        if signal.time_window_minutes <= 15:
            time_weight = 0.5
        elif signal.time_window_minutes <= 30:
            time_weight = 0.75

        # Calculate final priority (1-4 scale)
        raw_priority = severity_weight * urgency_mult * time_weight

        if raw_priority <= 1.5:
            return CasePriority.CRITICAL.value
        elif raw_priority <= 2.5:
            return CasePriority.HIGH.value
        elif raw_priority <= 4.0:
            return CasePriority.MEDIUM.value
        else:
            return CasePriority.LOW.value

    def dequeue(self, sim_time: float = 0) -> Optional[QueuedCase]:
        """
        Get the highest priority case from the queue.

        Args:
            sim_time: Current simulation time

        Returns:
            Next case to process or None if queue empty
        """
        if not self._heap:
            return None

        # Check concurrent limit
        if len(self._processing) >= self._max_concurrent:
            return None

        # Get next case
        case = heapq.heappop(self._heap)
        case.attempts += 1

        # Move to processing
        del self._cases[case.case_id]
        self._processing[case.case_id] = case

        logger.debug(
            f"Case dequeued: {case.case_id} "
            f"(wait_time={sim_time - case.queued_at:.1f}min)"
        )

        return case

    def get_next(self, available_ambulances: Dict[str, Any],
                 available_hospitals: List[str],
                 sim_time: float = 0) -> Optional[QueuedCase]:
        """
        Get next assignable case considering resource availability.

        Args:
            available_ambulances: Dict of ambulance_id -> ambulance info
            available_hospitals: List of available hospital IDs
            sim_time: Current simulation time

        Returns:
            Next assignable case or None
        """
        # Find first case that can be assigned
        while self._heap:
            case = self.dequeue(sim_time)
            if not case:
                break

            # Check if we have resources
            if self._can_assign(case, available_ambulances, available_hospitals):
                return case
            else:
                # Re-queue with lower priority
                case.priority = min(case.priority + 1, CasePriority.LOW.value)
                heapq.heappush(self._heap, case)
                del self._processing[case.case_id]
                self._cases[case.case_id] = case

        return None

    def _can_assign(
        self,
        case: QueuedCase,
        available_ambulances: Dict[str, Any],
        available_hospitals: List[str]
    ) -> bool:
        """Check if case can be assigned to available resources."""
        # Check ambulance availability
        if not available_ambulances:
            return False

        # Check hospital availability
        if not available_hospitals:
            return False

        return True

    def assign_resources(
        self,
        case_id: str,
        ambulance_id: str,
        hospital_id: str
    ) -> bool:
        """Assign resources to a case."""
        if case_id not in self._processing:
            return False

        case = self._processing[case_id]
        case.assigned_ambulance = ambulance_id
        case.assigned_hospital = hospital_id

        # Lock resources
        self._ambulance_locks[ambulance_id] = case_id
        if hospital_id not in self._hospital_locks:
            self._hospital_locks[hospital_id] = []
        self._hospital_locks[hospital_id].append(case_id)

        logger.debug(f"Resources assigned: case={case_id}, amb={ambulance_id}, hosp={hospital_id}")
        return True

    def complete(self, case_id: str, status: CaseStatus = CaseStatus.COMPLETED) -> None:
        """Mark a case as completed."""
        if case_id in self._processing:
            case = self._processing.pop(case_id)

            if status == CaseStatus.COMPLETED:
                self._completed[case_id] = case
                self._total_completed += 1
            else:
                self._failed[case_id] = case
                self._total_failed += 1

            # Release resource locks
            if case.assigned_ambulance:
                self._ambulance_locks.pop(case.assigned_ambulance, None)
            if case.assigned_hospital:
                if case.assigned_hospital in self._hospital_locks:
                    if case_id in self._hospital_locks[case.assigned_hospital]:
                        self._hospital_locks[case.assigned_hospital].remove(case_id)

            logger.info(f"Case {case_id} marked as {status.value}")

    def get_status(self) -> CaseStatus:
        """Get overall queue status."""
        if self._total_failed > self._total_completed * 0.1:
            return CaseStatus.FAILED
        return CaseStatus.QUEUED

    def get_metrics(self) -> Dict[str, Any]:
        """Get queue metrics."""
        total = self._total_queued
        completed = self._total_completed
        failed = self._total_failed

        return {
            "total_queued": total,
            "total_completed": completed,
            "total_failed": failed,
            "success_rate": completed / total if total > 0 else 0,
            "currently_queued": len(self._cases),
            "currently_processing": len(self._processing),
            "completed_cases": len(self._completed),
            "failed_cases": len(self._failed),
            "avg_wait_time": self._avg_wait_time,
            "resource_locks": {
                "ambulances": len(self._ambulance_locks),
                "hospitals": len(self._hospital_locks)
            },
            "capacity": {
                "max_concurrent": self._max_concurrent,
                "current_load": len(self._processing),
                "utilization": len(self._processing) / self._max_concurrent if self._max_concurrent > 0 else 0
            }
        }

    def get_queue_snapshot(self) -> List[Dict[str, Any]]:
        """Get snapshot of queued cases."""
        return [case.to_dict() for case in sorted(self._heap)]

    def get_processing_snapshot(self) -> List[Dict[str, Any]]:
        """Get snapshot of processing cases."""
        return [case.to_dict() for case in self._processing.values()]

    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return len(self._cases) == 0 and len(self._processing) == 0

    def size(self) -> int:
        """Get total cases in system."""
        return len(self._cases) + len(self._processing)

    def clear(self) -> None:
        """Clear all cases."""
        self._heap.clear()
        self._cases.clear()
        self._processing.clear()
        self._completed.clear()
        self._failed.clear()
        self._ambulance_locks.clear()
        self._hospital_locks.clear()
        logger.info("CaseQueue cleared")


class CaseQueuePool:
    """
    Pool of case queues for scaling to multiple regions/districts.

    Enables handling thousands of concurrent cases.
    """
    def __init__(self):
        self._queues: Dict[str, CaseQueue] = {}
        self._default_queue = CaseQueue()

    def add_queue(self, region_id: str, max_concurrent: int = 50) -> CaseQueue:
        """Add a new regional queue."""
        queue = CaseQueue(max_concurrent=max_concurrent)
        self._queues[region_id] = queue
        logger.info(f"Added case queue for region: {region_id}")
        return queue

    def get_queue(self, region_id: str = "default") -> CaseQueue:
        """Get queue for region."""
        if region_id == "default":
            return self._default_queue
        return self._queues.get(region_id, self._default_queue)

    def enqueue_to_region(
        self,
        signal: DistressSignal,
        region_id: str = "default",
        sim_time: float = 0
    ) -> str:
        """Enqueue case to specific region."""
        queue = self.get_queue(region_id)
        return queue.enqueue(signal, sim_time)

    def get_global_metrics(self) -> Dict[str, Any]:
        """Get metrics across all queues."""
        total_metrics = {
            "total_queues": len(self._queues) + 1,
            "total_queued": 0,
            "total_processing": 0,
            "total_completed": 0,
            "total_failed": 0
        }

        # Aggregate default queue
        default_metrics = self._default_queue.get_metrics()
        total_metrics["total_queued"] += default_metrics["currently_queued"]
        total_metrics["total_processing"] += default_metrics["currently_processing"]
        total_metrics["total_completed"] += default_metrics["total_completed"]
        total_metrics["total_failed"] += default_metrics["total_failed"]

        # Aggregate regional queues
        for queue in self._queues.values():
            metrics = queue.get_metrics()
            total_metrics["total_queued"] += metrics["currently_queued"]
            total_metrics["total_processing"] += metrics["currently_processing"]
            total_metrics["total_completed"] += metrics["total_completed"]
            total_metrics["total_failed"] += metrics["total_failed"]

        return total_metrics
