"""
LLM layer â€” OpenRouter via OpenAI-compatible interface, with a model
fallback chain. Every agent brain is built through this module so
outages/rate-limits degrade gracefully instead of stalling runs.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Dict, List, Optional

from ..config import Config

logger = logging.getLogger('firstbreath.llm')

# Sensible free-tier fallbacks on OpenRouter (verified live Aug 2026)
DEFAULT_FALLBACKS = [
    "z-ai/glm-5.2:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
]


def get_fallback_models() -> List[str]:
    raw = os.environ.get("LLM_FALLBACK_MODELS", "") or ",".join(DEFAULT_FALLBACKS)
    models = [m.strip() for m in raw.split(",") if m.strip()]
    return models


def build_chat_model(temperature: float = 0.5, model: Optional[str] = None):
    """
    Build the primary ChatOpenAI pointed at OpenRouter.
    Raises if no API key â€” callers must fall back to rule brains.
    """
    from langchain_openai import ChatOpenAI

    api_key = Config.LLM_API_KEY
    if not api_key:
        raise RuntimeError("LLM_API_KEY not configured")

    return ChatOpenAI(
        model=model or Config.LLM_MODEL_NAME,
        api_key=api_key,
        base_url=Config.LLM_BASE_URL,
        temperature=temperature,
        default_headers={
            "HTTP-Referer": "https://first-breath.vercel.app",
            "X-Title": "FirstBreath",
        },
        timeout=60,
        max_retries=1,
    )


class BrainRouter:
    """
    Tries primary then fallbacks; exposes `invoke_structured(schema, messages)`.
    If every model fails, callers use their deterministic fallback brain.
    """

    def __init__(self, temperature: float = 0.5):
        self.temperature = temperature
        self._chain: List = []
        self._names: List[str] = []
        self._cooldown: Dict[str, float] = {}   # model -> epoch until which it's skipped

    def _ensure_chain(self) -> bool:
        if self._chain:
            return True
        names = [Config.LLM_MODEL_NAME] + [m for m in get_fallback_models()
                                           if m != Config.LLM_MODEL_NAME]
        for name in names:
            try:
                m = build_chat_model(temperature=self.temperature, model=name)
                self._chain.append(m)
                self._names.append(name)
            except Exception as e:
                logger.warning(f"model {name} unavailable: {e}")
        return bool(self._chain)

    def invoke_structured(self, schema, messages):
        """
        Returns (structured_obj | None, model_name_used).
        None means all models failed â†’ caller falls back to rule brain.

        Uses manual JSON extraction instead of provider-native structured
        output â€” works uniformly across any OpenRouter model.
        """
        import re
        import time
        from langchain_core.messages import SystemMessage, HumanMessage

        if not self._ensure_chain():
            return None, None

        schema_hint = _schema_hint(schema)
        instruction = (
            f"\n\nRESPONSE FORMAT â€” respond with ONLY a single JSON object, "
            f"no markdown fences, no commentary, matching exactly:\n{schema_hint}"
        )

        for i, model in enumerate(self._chain):
            if self._cooldown.get(self._names[i], 0) > time.time():
                continue
            for attempt in range(2):
                try:
                    msgs = list(messages)
                    if attempt == 0:
                        msgs[-1] = HumanMessage(content=msgs[-1].content + instruction) \
                            if isinstance(msgs[-1], HumanMessage) else msgs[-1]
                    else:
                        msgs.append(HumanMessage(content=(
                            f"Your previous reply was not valid JSON for this schema. "
                            f"Try again. Respond with ONLY the JSON object:\n{schema_hint}")))

                    t0 = time.time()
                    resp = model.invoke(msgs)
                    dt = time.time() - t0

                    obj = _extract_json(resp.content)
                    if obj is None:
                        logger.warning(f"{self._names[i]} attempt {attempt+1}: no JSON found")
                        continue
                    result = _coerce_decision_list(obj)
                    if result is None:
                        logger.warning(f"{self._names[i]} attempt {attempt+1}: "
                                       f"no valid decisions in output")
                        continue
                    logger.info(f"brain ok: {self._names[i]} in {dt:.1f}s")
                    return result, self._names[i]
                except Exception as e:
                    msg = str(e)[:140]
                    logger.warning(f"brain {self._names[i]} attempt {attempt+1}: {msg}")
                    if "429" in msg or "rate" in msg.lower():
                        # circuit breaker: stop burning this model for 90s
                        self._cooldown[self._names[i]] = time.time() + 90
                        break
                    continue
        return None, None


def _coerce_decision_list(obj: dict):
    """
    Tolerant conversion of arbitrary model JSON into a DecisionList.
    Maps kind aliases, drops unparseable decisions individually.
    """
    from ..world.actions import (
        DispatchAmbulance, PreAlertHospital, PrepareOt, RerouteAmbulance,
        RequestBlood, PageStaff, UpdateTraffic, Escalate, NoOp, DecisionList,
    )
    kind_aliases = {
        "dispatch": "dispatch_ambulance", "dispatch_ambulance": "dispatch_ambulance",
        "send_ambulance": "dispatch_ambulance", "assign": "dispatch_ambulance",
        "pre_alert": "pre_alert_hospital", "pre_alert_hospital": "pre_alert_hospital",
        "alert_hospital": "pre_alert_hospital", "notify_hospital": "pre_alert_hospital",
        "prepare_ot": "prepare_ot", "reserve_ot": "prepare_ot", "ot_prep": "prepare_ot",
        "reroute": "reroute_ambulance", "reroute_ambulance": "reroute_ambulance",
        "request_blood": "request_blood", "blood_request": "request_blood",
        "page_staff": "page_staff", "page": "page_staff", "page_doctor": "page_staff",
        "update_traffic": "update_traffic", "traffic_update": "update_traffic",
        "escalate": "escalate", "noop": "noop", "no_op": "noop", "none": "noop",
        "do_nothing": "noop", "wait": "noop",
    }
    classes = {
        "dispatch_ambulance": DispatchAmbulance,
        "pre_alert_hospital": PreAlertHospital,
        "prepare_ot": PrepareOt,
        "reroute_ambulance": RerouteAmbulance,
        "request_blood": RequestBlood,
        "page_staff": PageStaff,
        "update_traffic": UpdateTraffic,
        "escalate": Escalate,
        "noop": NoOp,
    }

    actions = []
    for raw in (obj.get("decisions") or []):
        if not isinstance(raw, dict):
            continue
        kind = kind_aliases.get(str(raw.get("kind", "")).strip().lower())
        cls = classes.get(kind)
        if cls is None:
            continue
        data = {k: v for k, v in raw.items() if k != "kind"}
        # common field aliasing
        if "ambulance" in data and "ambulance_id" not in data:
            data["ambulance_id"] = data.pop("ambulance")
        if "hospital" in data and "hospital_id" not in data:
            data["hospital_id"] = data.pop("hospital")
        try:
            actions.append(cls(**data))
        except Exception as e:
            logging.getLogger('firstbreath.llm').warning(
                f"dropping malformed decision ({kind}): {str(e)[:100]}")

    return DecisionList(
        decisions=actions,
        radio_messages=[str(m) for m in (obj.get("radio_messages")
                                         or obj.get("radio") or []) if m],
        reasoning_summary=str(obj.get("reasoning_summary")
                              or obj.get("reasoning") or ""),
    )


def _extract_json(text: str) -> Optional[dict]:
    """Pull the first balanced JSON object out of arbitrary model output."""
    if not text:
        return None
    # strip fences if present
    text = re.sub(r"```(?:json)?", "", text).strip()
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start:idx + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    return None
    return None


def _schema_hint(schema) -> str:
    """Compact JSON-schema example from a Pydantic model."""
    props = {}
    for name, field in schema.model_fields.items():
        if name == "decisions":
            props[name] = [{
                "kind": "dispatch_ambulance | pre_alert_hospital | prepare_ot | "
                        "reroute_ambulance | request_blood | page_staff | "
                        "update_traffic | escalate | noop",
                "...action fields": "as per the doctrine above",
            }]
        elif name == "radio_messages":
            props[name] = ["short radio line"]
        else:
            props[name] = "string"
    return json.dumps(props, indent=1)

