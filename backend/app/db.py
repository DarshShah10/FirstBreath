"""
Supabase Postgres data-access layer.

All persistence goes through this module — no direct DB calls elsewhere.
Uses the Supabase REST client when configured; every function degrades
gracefully to a no-op with a warning if Supabase is not configured, so
local development never hard-fails on persistence.
"""

import uuid
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .config import Config

logger = logging.getLogger('firstbreath.db')


class Database:
    """Thin wrapper over the Supabase REST API."""

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            url, key = Config.SUPABASE_URL, Config.SUPABASE_SECRET_KEY
            if not url or not key:
                return None
            try:
                from supabase import create_client
                self._client = create_client(url, key)
            except Exception as e:
                logger.warning(f"Supabase init failed; persistence disabled: {e}")
                self._client = False  # sentinel: failed permanently
        return self._client or None

    @property
    def enabled(self) -> bool:
        return self.client is not None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _insert(self, table: str, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        c = self.client
        if not c:
            return None
        try:
            resp = c.table(table).insert(row).execute()
            data = getattr(resp, 'data', None)
            return data[0] if data else None
        except Exception as e:
            logger.error(f"insert {table} failed: {e}")
            return None

    def _update(self, table: str, match: Dict[str, Any], patch: Dict[str, Any]):
        c = self.client
        if not c:
            return
        try:
            c.table(table).update(patch).match(match).execute()
        except Exception as e:
            logger.error(f"update {table} failed: {e}")

    @staticmethod
    def new_id(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:12]}"

    # ------------------------------------------------------------------
    # Simulations
    # ------------------------------------------------------------------

    def create_simulation(self, meta: Optional[Dict[str, Any]] = None,
                          simulation_id: Optional[str] = None) -> Optional[str]:
        sid = simulation_id or self.new_id('sim')
        row = self._insert('simulations', {
            'id': sid,
            'status': 'created',
            'meta': json.loads(json.dumps(meta or {}, default=str)),
        })
        if not row and not self.enabled:
            return sid  # local dev without Supabase: id still usable
        return sid

    def update_simulation(self, simulation_id: str, status: Optional[str] = None,
                          meta: Optional[Dict[str, Any]] = None):
        patch: Dict[str, Any] = {'updated_at': datetime.utcnow().isoformat()}
        if status is not None:
            patch['status'] = status
        if meta is not None:
            patch['meta'] = json.loads(json.dumps(meta, default=str))
        self._update('simulations', {'id': simulation_id}, patch)

    def get_simulation(self, simulation_id: str) -> Optional[Dict[str, Any]]:
        c = self.client
        if not c:
            return None
        try:
            resp = c.table('simulations').select('*').eq('id', simulation_id).execute()
            rows = getattr(resp, 'data', None)
            return rows[0] if rows else None
        except Exception as e:
            logger.error(f"get_simulation failed: {e}")
            return None

    def list_simulations(self, limit: int = 50) -> List[Dict[str, Any]]:
        c = self.client
        if not c:
            return []
        try:
            resp = (
                c.table('simulations')
                .select('*')
                .order('created_at', desc=True)
                .limit(limit)
                .execute()
            )
            return getattr(resp, 'data', None) or []
        except Exception as e:
            logger.error(f"list_simulations failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Cases
    # ------------------------------------------------------------------

    def upsert_case(self, simulation_id: str, case_id: str,
                    distress_signal: Dict[str, Any],
                    status: str = 'pending') -> Optional[str]:
        self._insert('cases', {
            'id': case_id,
            'simulation_id': simulation_id,
            'distress_signal': json.loads(json.dumps(distress_signal, default=str)),
            'status': status,
        })
        return case_id

    def update_case(self, case_id: str, status: Optional[str] = None,
                    outcome: Optional[Dict[str, Any]] = None):
        patch: Dict[str, Any] = {'updated_at': datetime.utcnow().isoformat()}
        if status is not None:
            patch['status'] = status
        if outcome is not None:
            patch['outcome'] = json.loads(json.dumps(outcome, default=str))
        self._update('cases', {'id': case_id}, patch)

    # ------------------------------------------------------------------
    # Runs
    # ------------------------------------------------------------------

    def start_run(self, simulation_id: str, run_id: Optional[str] = None) -> Optional[str]:
        rid = run_id or self.new_id('run')
        self._insert('runs', {
            'id': rid,
            'simulation_id': simulation_id,
            'status': 'running',
        })
        return rid

    def finish_run(self, run_id: str, status: str,
                   results: Optional[Dict[str, Any]] = None,
                   metrics: Optional[Dict[str, Any]] = None):
        patch: Dict[str, Any] = {
            'status': status,
            'completed_at': datetime.utcnow().isoformat(),
        }
        if results is not None:
            patch['results'] = json.loads(json.dumps(results, default=str))
        if metrics is not None:
            patch['metrics'] = json.loads(json.dumps(metrics, default=str))
        self._update('runs', {'id': run_id}, patch)

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        c = self.client
        if not c:
            return None
        try:
            resp = c.table('runs').select('*').eq('id', run_id).execute()
            rows = getattr(resp, 'data', None)
            return rows[0] if rows else None
        except Exception as e:
            logger.error(f"get_run failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Events (append-only transcript)
    # ------------------------------------------------------------------

    def append_event(self, run_id: str, event_type: str,
                     sim_time: Optional[float] = None,
                     agent_id: Optional[str] = None,
                     agent_type: Optional[str] = None,
                     payload: Optional[Dict[str, Any]] = None):
        c = self.client
        if not c:
            return
        try:
            c.table('events').insert({
                'run_id': run_id,
                'event_type': event_type,
                'sim_time': sim_time,
                'agent_id': agent_id,
                'agent_type': agent_type,
                'payload': json.loads(json.dumps(payload or {}, default=str)),
            }).execute()
        except Exception as e:
            logger.error(f"append_event failed: {e}")

    def get_events(self, run_id: str, limit: int = 1000,
                   after_id: int = 0) -> List[Dict[str, Any]]:
        c = self.client
        if not c:
            return []
        try:
            query = (
                c.table('events')
                .select('*')
                .eq('run_id', run_id)
                .gt('id', after_id)
                .order('id')
                .limit(limit)
            )
            resp = query.execute()
            return getattr(resp, 'data', None) or []
        except Exception as e:
            logger.error(f"get_events failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------

    def save_report(self, run_id: str, report_id: Optional[str],
                    content: Dict[str, Any], markdown: Optional[str] = None,
                    case_id: Optional[str] = None) -> Optional[str]:
        rid = report_id or self.new_id('rpt')
        self._insert('reports', {
            'id': rid,
            'run_id': run_id,
            'case_id': case_id,
            'content': json.loads(json.dumps(content, default=str)),
            'markdown': markdown,
        })
        return rid


# Module-level singleton
db = Database()
