"""Base class providing shared Zep client, LLM client, and retry logic."""

import time
from typing import Optional

from zep_cloud.client import Zep

from ...config import Config
from ...utils.logger import get_logger
from ...utils.llm_client import LLMClient

logger = get_logger('mirofish.zep_tools')


class ZepToolsBase:
    """
    Shared base for all ZepTools mixin services.

    Provides the Zep client, LLM client, and exponential-backoff retry logic.
    """

    MAX_RETRIES = 3
    RETRY_DELAY = 2.0

    def __init__(self, api_key: Optional[str] = None, llm_client: Optional[LLMClient] = None):
        self.api_key = api_key or Config.ZEP_API_KEY
        if not self.api_key:
            raise ValueError("ZEP_API_KEY is not configured")

        self.client = Zep(api_key=self.api_key)
        # LLM client used by InsightForge and Interview to call the LLM
        self._llm_client = llm_client
        logger.info("ZepToolsService initialized")

    @property
    def llm(self) -> LLMClient:
        """Lazily initialize the LLM client."""
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client

    def _call_with_retry(self, func, operation_name: str, max_retries: int = None):
        """Execute an API call with exponential-backoff retry logic."""
        max_retries = max_retries or self.MAX_RETRIES
        last_exception = None
        delay = self.RETRY_DELAY

        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Zep {operation_name} attempt {attempt + 1} failed: {str(e)[:100]}, "
                        f"retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    delay *= 2
                else:
                    logger.error(f"Zep {operation_name} failed after {max_retries} attempts: {str(e)}")

        raise last_exception
