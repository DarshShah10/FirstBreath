"""Zep graph memory updater and manager — batches agent activities into the Zep knowledge graph."""

import time
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime
from queue import Queue, Empty

from zep_cloud.client import Zep

from ...config import Config
from ...utils.logger import get_logger
from .activity import AgentActivity

logger = get_logger('mirofish.zep_graph_memory_updater')


class ZepGraphMemoryUpdater:
    """
    Zep Graph Memory Updater.

    Monitors the simulation's action log files and streams new agent activities
    into the Zep knowledge graph in real time. Activities are grouped by platform
    and sent in batches of BATCH_SIZE.

    All meaningful actions are forwarded to Zep; action_args carries full context:
    - post content for likes/dislikes
    - original post content for reposts/quotes
    - username for follows/mutes
    - comment content for comment likes/dislikes
    """

    # Number of activities to accumulate per platform before sending a batch
    BATCH_SIZE = 5

    # Platform display names for log messages
    PLATFORM_DISPLAY_NAMES = {
        'twitter': 'World 1',
        'reddit': 'World 2',
    }

    # Minimum interval between sends (seconds) to avoid throttling
    SEND_INTERVAL = 0.5

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds

    def __init__(self, graph_id: str, api_key: Optional[str] = None):
        """
        Initialise the updater.

        Args:
            graph_id: Zep graph ID.
            api_key: Zep API key (optional; read from Config if omitted).
        """
        self.graph_id = graph_id
        self.api_key = api_key or Config.ZEP_API_KEY

        if not self.api_key:
            raise ValueError("ZEP_API_KEY is not configured")

        self.client = Zep(api_key=self.api_key)

        # Activity queue
        self._activity_queue: Queue = Queue()

        # Per-platform activity buffers — each platform accumulates to BATCH_SIZE before sending
        self._platform_buffers: Dict[str, List[AgentActivity]] = {
            'twitter': [],
            'reddit': [],
        }
        self._buffer_lock = threading.Lock()

        # Control flags
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None

        # Statistics
        self._total_activities = 0   # total activities enqueued
        self._total_sent = 0         # batches successfully sent to Zep
        self._total_items_sent = 0   # individual activities successfully sent to Zep
        self._failed_count = 0       # batches that failed to send
        self._skipped_count = 0      # activities filtered out (DO_NOTHING)

        logger.info(f"ZepGraphMemoryUpdater initialised: graph_id={graph_id}, batch_size={self.BATCH_SIZE}")

    def _get_platform_display_name(self, platform: str) -> str:
        """Return the display name for the given platform."""
        return self.PLATFORM_DISPLAY_NAMES.get(platform.lower(), platform)

    def start(self):
        """Start the background worker thread."""
        if self._running:
            return

        self._running = True
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name=f"ZepMemoryUpdater-{self.graph_id[:8]}"
        )
        self._worker_thread.start()
        logger.info(f"ZepGraphMemoryUpdater started: graph_id={self.graph_id}")

    def stop(self):
        """Stop the background worker thread and flush remaining activities."""
        self._running = False

        # Flush any remaining activities before stopping
        self._flush_remaining()

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=10)

        logger.info(
            f"ZepGraphMemoryUpdater stopped: graph_id={self.graph_id}, "
            f"total_activities={self._total_activities}, "
            f"batches_sent={self._total_sent}, "
            f"items_sent={self._total_items_sent}, "
            f"failed={self._failed_count}, "
            f"skipped={self._skipped_count}"
        )

    def add_activity(self, activity: AgentActivity):
        """
        Add a single agent activity to the processing queue.

        All meaningful actions are enqueued, including:
        - CREATE_POST, CREATE_COMMENT, QUOTE_POST
        - SEARCH_POSTS, SEARCH_USER
        - LIKE_POST, DISLIKE_POST, REPOST, FOLLOW, MUTE
        - LIKE_COMMENT, DISLIKE_COMMENT

        action_args should carry full context (post content, usernames, etc.).

        Args:
            activity: Agent activity record.
        """
        # Skip DO_NOTHING actions
        if activity.action_type == "DO_NOTHING":
            self._skipped_count += 1
            return

        self._activity_queue.put(activity)
        self._total_activities += 1
        logger.debug(f"Enqueued activity for Zep: {activity.agent_name} - {activity.action_type}")

    def add_activity_from_dict(self, data: Dict[str, Any], platform: str):
        """
        Build and enqueue an AgentActivity from a raw dict (parsed from actions.jsonl).

        Args:
            data: Dict parsed from the actions log file.
            platform: Platform name (twitter/reddit).
        """
        # Skip entries that describe events rather than actions
        if "event_type" in data:
            return

        activity = AgentActivity(
            platform=platform,
            agent_id=data.get("agent_id", 0),
            agent_name=data.get("agent_name", ""),
            action_type=data.get("action_type", ""),
            action_args=data.get("action_args", {}),
            round_num=data.get("round", 0),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
        )

        self.add_activity(activity)

    def _worker_loop(self):
        """Background worker loop — batches activities per platform and sends to Zep."""
        while self._running or not self._activity_queue.empty():
            try:
                # Try to dequeue an activity (1-second timeout)
                try:
                    activity = self._activity_queue.get(timeout=1)

                    # Buffer the activity under its platform
                    platform = activity.platform.lower()
                    with self._buffer_lock:
                        if platform not in self._platform_buffers:
                            self._platform_buffers[platform] = []
                        self._platform_buffers[platform].append(activity)

                        # Check whether the platform buffer has reached the batch threshold
                        if len(self._platform_buffers[platform]) >= self.BATCH_SIZE:
                            batch = self._platform_buffers[platform][:self.BATCH_SIZE]
                            self._platform_buffers[platform] = self._platform_buffers[platform][self.BATCH_SIZE:]
                            # Release the lock before sending to avoid holding it during I/O
                            self._send_batch_activities(batch, platform)
                            # Rate-limit sends
                            time.sleep(self.SEND_INTERVAL)

                except Empty:
                    pass

            except Exception as e:
                logger.error(f"Worker loop exception: {e}")
                time.sleep(1)

    def _send_batch_activities(self, activities: List[AgentActivity], platform: str):
        """
        Send a batch of activities to the Zep graph as a single combined text episode.

        Args:
            activities: List of agent activities to send.
            platform: Platform name (used for logging).
        """
        if not activities:
            return

        # Combine multiple activities into one text block, separated by newlines
        episode_texts = [activity.to_episode_text() for activity in activities]
        combined_text = "\n".join(episode_texts)

        # Send with retry
        for attempt in range(self.MAX_RETRIES):
            try:
                self.client.graph.add(
                    graph_id=self.graph_id,
                    type="text",
                    data=combined_text
                )

                self._total_sent += 1
                self._total_items_sent += len(activities)
                display_name = self._get_platform_display_name(platform)
                logger.info(
                    f"Sent batch of {len(activities)} {display_name} activities "
                    f"to graph {self.graph_id}"
                )
                logger.debug(f"Batch preview: {combined_text[:200]}...")
                return

            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(
                        f"Batch send to Zep failed (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}"
                    )
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                else:
                    logger.error(
                        f"Batch send to Zep failed after {self.MAX_RETRIES} attempts: {e}"
                    )
                    self._failed_count += 1

    def _flush_remaining(self):
        """Drain the queue and buffers, sending all remaining activities regardless of batch size."""
        # First drain any remaining items from the queue into the buffers
        while not self._activity_queue.empty():
            try:
                activity = self._activity_queue.get_nowait()
                platform = activity.platform.lower()
                with self._buffer_lock:
                    if platform not in self._platform_buffers:
                        self._platform_buffers[platform] = []
                    self._platform_buffers[platform].append(activity)
            except Empty:
                break

        # Then send whatever remains in each platform buffer (even if under BATCH_SIZE)
        with self._buffer_lock:
            for platform, buffer in self._platform_buffers.items():
                if buffer:
                    display_name = self._get_platform_display_name(platform)
                    logger.info(
                        f"Flushing {len(buffer)} remaining {display_name} activities"
                    )
                    self._send_batch_activities(buffer, platform)
            # Clear all buffers
            for platform in self._platform_buffers:
                self._platform_buffers[platform] = []

    def get_stats(self) -> Dict[str, Any]:
        """Return current statistics for this updater."""
        with self._buffer_lock:
            buffer_sizes = {p: len(b) for p, b in self._platform_buffers.items()}

        return {
            "graph_id": self.graph_id,
            "batch_size": self.BATCH_SIZE,
            "total_activities": self._total_activities,  # activities enqueued
            "batches_sent": self._total_sent,            # batches successfully sent
            "items_sent": self._total_items_sent,        # individual activities sent
            "failed_count": self._failed_count,          # batches that failed
            "skipped_count": self._skipped_count,        # DO_NOTHING activities skipped
            "queue_size": self._activity_queue.qsize(),
            "buffer_sizes": buffer_sizes,                # per-platform buffer occupancy
            "running": self._running,
        }


class ZepGraphMemoryManager:
    """
    Manages multiple Zep graph memory updaters — one per simulation.

    Each simulation can have its own updater instance, identified by simulation_id.
    """

    _updaters: Dict[str, ZepGraphMemoryUpdater] = {}
    _lock = threading.Lock()

    # Guard against duplicate stop_all calls
    _stop_all_done = False

    @classmethod
    def create_updater(cls, simulation_id: str, graph_id: str) -> ZepGraphMemoryUpdater:
        """
        Create and start a graph memory updater for the given simulation.

        If an updater already exists for this simulation_id, it is stopped first.

        Args:
            simulation_id: Simulation ID.
            graph_id: Zep graph ID.

        Returns:
            ZepGraphMemoryUpdater instance.
        """
        with cls._lock:
            # Stop any existing updater for this simulation
            if simulation_id in cls._updaters:
                cls._updaters[simulation_id].stop()

            updater = ZepGraphMemoryUpdater(graph_id)
            updater.start()
            cls._updaters[simulation_id] = updater

            logger.info(
                f"Graph memory updater created: simulation_id={simulation_id}, graph_id={graph_id}"
            )
            return updater

    @classmethod
    def get_updater(cls, simulation_id: str) -> Optional[ZepGraphMemoryUpdater]:
        """Return the updater for the given simulation, or None if not found."""
        return cls._updaters.get(simulation_id)

    @classmethod
    def stop_updater(cls, simulation_id: str):
        """Stop and remove the updater for the given simulation."""
        with cls._lock:
            if simulation_id in cls._updaters:
                cls._updaters[simulation_id].stop()
                del cls._updaters[simulation_id]
                logger.info(f"Graph memory updater stopped: simulation_id={simulation_id}")

    @classmethod
    def stop_all(cls):
        """Stop all active updaters."""
        # Guard against duplicate calls
        if cls._stop_all_done:
            return
        cls._stop_all_done = True

        with cls._lock:
            if cls._updaters:
                for simulation_id, updater in list(cls._updaters.items()):
                    try:
                        updater.stop()
                    except Exception as e:
                        logger.error(
                            f"Failed to stop updater: simulation_id={simulation_id}, error={e}"
                        )
                cls._updaters.clear()
            logger.info("All graph memory updaters stopped")

    @classmethod
    def get_all_stats(cls) -> Dict[str, Dict[str, Any]]:
        """Return statistics for all active updaters."""
        return {
            sim_id: updater.get_stats()
            for sim_id, updater in cls._updaters.items()
        }
