"""
SimulationConfigGenerator — generates VahanAI dispatch simulation parameters.

Analyzes available units and city conditions to predict:
1. Success probability
2. Where the response chain will fail
3. What intervention to take
"""

import json
import time
from dataclasses import asdict
from typing import Any, Callable, Dict, List, Optional

import httpx

from ...config import Config
from ...utils.logger import get_logger
from ..neo4j_entity_reader import EntityNode
from .models import (
    UnitConfig,
    CityCondition,
    DistressSignal,
    SimulationParameters,
)
from .prompts import (
    UNIT_CONFIG_SYSTEM_PROMPT,
    DISPATCH_SYSTEM_PROMPT,
    build_unit_config_prompt,
    build_dispatch_prompt,
)

logger = get_logger('mirofish.simulation_config')


class SimulationConfigGenerator:
    """
    VahanAI dispatch simulation configuration generator.

    Focus: Given a distress signal, available units, and city conditions,
    predict where the response will fail and what intervention to take.
    """

    MAX_CONTEXT_LENGTH = 30000

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model_name = model_name or Config.LLM_MODEL_NAME

        if not self.api_key:
            raise ValueError("LLM_API_KEY is not configured")

        self.client = None  # Will use httpx instead

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_config(
        self,
        simulation_id: str,
        project_id: str,
        graph_id: str,
        simulation_requirement: str,
        document_text: str,
        entities: List[EntityNode],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> SimulationParameters:
        """
        Generate dispatch simulation configuration.

        Analyzes available units and generates:
        1. Unit configurations (availability, location, dependencies)
        2. Dispatch analysis (bottleneck + intervention)

        Args:
            simulation_id: Simulation ID.
            project_id: Project ID.
            graph_id: Graph ID.
            simulation_requirement: Emergency scenario description.
            document_text: Raw document content (optional context).
            entities: Available units from hospital graph.
            progress_callback: Progress callback.

        Returns:
            SimulationParameters with dispatch analysis.
        """
        logger.info(
            f"Generating dispatch config: simulation_id={simulation_id}, units={len(entities)}"
        )

        def report_progress(step: int, total: int, message: str) -> None:
            if progress_callback:
                progress_callback(step, total, message)
            logger.info(f"[{step}/{total}] {message}")

        report_progress(1, 3, "Analyzing available units...")

        # Step 1: Generate unit configurations
        unit_configs = self._generate_unit_configs(entities, simulation_requirement)

        report_progress(2, 3, "Running dispatch analysis...")

        # Step 2: Generate dispatch analysis (bottleneck + intervention)
        dispatch_analysis = self._generate_dispatch_analysis(
            simulation_requirement=simulation_requirement,
            unit_configs=unit_configs,
        )

        # Parse dispatch signal from requirement or use defaults
        distress_signal = self._parse_distress_signal(simulation_requirement)

        # Default city condition (can be updated from live feeds)
        city_condition = CityCondition()

        params = SimulationParameters(
            simulation_id=simulation_id,
            project_id=project_id,
            graph_id=graph_id,
            simulation_requirement=simulation_requirement,
            unit_configs=unit_configs,
            city_condition=city_condition,
            distress_signal=distress_signal,
            llm_model=self.model_name,
            llm_base_url=self.base_url,
        )

        report_progress(3, 3, "Configuration complete")

        logger.info(
            f"Dispatch config complete: {len(unit_configs)} units analyzed, "
            f"bottleneck={dispatch_analysis.get('bottleneck', 'unknown')}"
        )
        return params

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _call_llm_with_retry(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        """Call the LLM with retry logic."""
        max_attempts = 3
        last_error = None

        for attempt in range(max_attempts):
            try:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01",
                }

                body = {
                    "model": self.model_name,
                    "max_tokens": 4096,
                    "messages": [
                        {"role": "user", "content": f"{system_prompt}\n\n{prompt}"}
                    ],
                    "temperature": 0.3,  # Lower temp for more consistent JSON
                }

                with httpx.Client(timeout=120.0) as client:
                    response = client.post(
                        f"{self.base_url}/messages",
                        headers=headers,
                        json=body
                    )

                if response.status_code != 200:
                    raise RuntimeError(f"API error {response.status_code}: {response.text}")

                data = response.json()
                content = ""
                for block in data.get("content", []):
                    if block.get("type") == "text":
                        content = block.get("text", "")
                        break

                if not content:
                    raise ValueError("Empty response from LLM")

                return json.loads(content)

            except Exception as e:
                logger.warning(f"LLM call failed (attempt {attempt + 1}): {str(e)[:80]}")
                last_error = e
                time.sleep(2 * (attempt + 1))

        raise last_error or Exception("LLM call failed after all retries")

    def _generate_unit_configs(
        self,
        entities: List[EntityNode],
        simulation_requirement: str,
    ) -> List[UnitConfig]:
        """Analyze available units for dispatch simulation."""
        entity_list = []
        for i, e in enumerate(entities):
            entity_list.append({
                "agent_id": i,
                "entity_name": e.name,
                "entity_type": e.get_entity_type() or "Unknown",
                "description": e.description or "",
            })

        prompt = build_unit_config_prompt(simulation_requirement, entity_list)

        try:
            result = self._call_llm_with_retry(prompt, UNIT_CONFIG_SYSTEM_PROMPT)
            llm_units = result.get("units", [])
        except Exception as e:
            logger.warning(f"LLM unit analysis failed: {e}; using defaults")
            llm_units = []

        configs = []
        for i, entity in enumerate(entities):
            cfg = next((u for u in llm_units if u.get("agent_id") == i), {})

            configs.append(UnitConfig(
                agent_id=i,
                entity_uuid=entity.uuid,
                entity_name=entity.name,
                entity_type=entity.get_entity_type() or "Unknown",
                is_available=cfg.get("is_available", True),
                current_location=cfg.get("current_location", ""),
                distance_km=cfg.get("distance_km", 0.0),
                response_time_min=cfg.get("response_time_min", 10),
                prep_time_min=cfg.get("prep_time_min", 0),
                requires=cfg.get("requires", []),
                provides=cfg.get("provides", []),
                criticality=cfg.get("criticality", 0.5),
            ))

        return configs

    def _generate_dispatch_analysis(
        self,
        simulation_requirement: str,
        unit_configs: List[UnitConfig],
    ) -> Dict[str, Any]:
        """Run dispatch analysis to find bottleneck and intervention."""
        # Parse distress signal from requirement
        distress_signal = self._parse_distress_signal(simulation_requirement)

        # Convert units to dicts
        available_units = [asdict(u) for u in unit_configs]

        # Default city condition
        city_condition = asdict(CityCondition())

        prompt = build_dispatch_prompt(distress_signal, available_units, city_condition)

        try:
            return self._call_llm_with_retry(prompt, DISPATCH_SYSTEM_PROMPT)
        except Exception as e:
            logger.warning(f"LLM dispatch analysis failed: {e}; using defaults")
            return {
                "success_probability": 50,
                "bottleneck": "unknown",
                "bottleneck_unit": "multiple",
                "intervention": {
                    "action": "Review manually",
                    "trigger": "now",
                    "time_saved_min": 0,
                    "survival_impact": "Medium"
                }
            }

    def _parse_distress_signal(self, simulation_requirement: str) -> Dict[str, Any]:
        """Parse distress signal from simulation requirement."""
        # Default values
        signal = {
            "signal_type": "B",  # 108 call by default
            "severity": 8,
            "time_window_min": 20,
            "location": "Unknown",
            "patient_condition": "Emergency",
            "needs_ambulance": True,
            "needs_blood": False,
            "blood_type": "",
            "needs_ot": False,
            "needs_specialist": "",
        }

        req_lower = simulation_requirement.lower()

        # Detect signal type
        if "firstbreath" in req_lower or "ctg" in req_lower:
            signal["signal_type"] = "A"
        elif "nurse" in req_lower or "manual" in req_lower:
            signal["signal_type"] = "C"
        elif "mass" in req_lower or "casualty" in req_lower:
            signal["signal_type"] = "D"

        # Detect severity
        for level in [str(i) for i in range(10, 0, -1)]:
            if f"severity {level}" in req_lower or f"/{level}" in req_lower:
                signal["severity"] = int(level)
                break

        # Detect needs
        if "blood" in req_lower:
            signal["needs_blood"] = True
            # Try to extract blood type
            for bt in ["o-negative", "o-negative", "a-positive", "a-negative", "b-positive", "b-negative", "ab-positive", "ab-negative"]:
                if bt in req_lower:
                    signal["blood_type"] = bt
                    break

        if "ot" in req_lower or "theater" in req_lower or "surgery" in req_lower:
            signal["needs_ot"] = True

        # Detect specialist
        specialists = ["cardiologist", "neurosurgeon", "orthopedic", "pediatric", "anesthesiologist"]
        for spec in specialists:
            if spec in req_lower:
                signal["needs_specialist"] = spec
                break

        return signal
from dataclasses import asdict
