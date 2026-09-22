"""
Ollama Connection Manager -- Single source of truth for LLM connectivity.

Provides:
  1. check_ollama() -- test if Ollama is reachable
  2. get_client()   -- get a configured ollama.Client instance
  3. call_ollama()  -- call LLM with retry + timeout + failsafe

All modules MUST use this instead of importing ollama directly.
"""

import time
from typing import Optional
import ollama
from utils.config_loader import load_config, AppConfig
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Module-level cache for the client
_client: Optional[ollama.Client] = None
_config: Optional[AppConfig] = None


def _get_config() -> AppConfig:
    """Get or load config (cached)."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def get_client(config: Optional[AppConfig] = None) -> ollama.Client:
    """
    Get a configured Ollama client with explicit host.
    Caches the client for reuse.
    """
    global _client
    if _client is not None and config is None:
        return _client

    cfg = config or _get_config()
    host = cfg.llm.base_url

    # Create client with explicit host (fixes Windows connection issues)
    _client = ollama.Client(host=host)
    return _client


def check_ollama(config: Optional[AppConfig] = None) -> dict:
    """
    Check if Ollama is reachable and the configured model is available.

    Returns:
        dict with keys:
          - connected: bool
          - models: list of model names (if connected)
          - model_available: bool (if the configured model is present)
          - error: str (if connection failed)
    """
    cfg = config or _get_config()
    result = {
        "connected": False,
        "models": [],
        "model_available": False,
        "configured_model": cfg.llm.model,
        "host": cfg.llm.base_url,
        "error": None,
    }

    try:
        client = get_client(cfg)
        models_response = client.list()
        model_names = [m.model for m in models_response.models]
        result["connected"] = True
        result["models"] = model_names

        # Check if configured model is available
        configured = cfg.llm.model.lower()
        result["model_available"] = any(
            configured in m.lower() or m.lower().startswith(configured.split(":")[0])
            for m in model_names
        )

        if result["model_available"]:
            logger.info(
                f"Ollama connected | host={cfg.llm.base_url} | "
                f"model={cfg.llm.model} | {len(model_names)} models available"
            )
        else:
            logger.warning(
                f"Ollama connected but model '{cfg.llm.model}' not found. "
                f"Available: {', '.join(model_names[:5])}"
            )

    except Exception as e:
        result["error"] = str(e)
        logger.warning(f"Ollama unavailable at {cfg.llm.base_url}: {e}")

    return result


def call_ollama(
    messages: list,
    task: str = "LLM",
    attempt: int = 1,
    config: Optional[AppConfig] = None,
) -> str:
    """
    Call Ollama with retry, timeout, and proper error handling.

    Args:
        messages: Chat messages (OpenAI format)
        task: Task name for logging
        attempt: Current attempt number
        config: Optional config override

    Returns:
        LLM response content string

    Raises:
        RuntimeError: If all retries fail
    """
    cfg = config or _get_config()
    client = get_client(cfg)
    model = cfg.llm.model
    timeout = cfg.llm.timeout
    max_retries = cfg.llm.max_retries
    temperature = cfg.llm.temperature

    last_error = None

    for retry in range(max_retries):
        current_attempt = attempt + retry
        logger.info(
            f"[{task}] Calling Ollama (attempt {current_attempt}, "
            f"model={model}, timeout={timeout}s)..."
        )

        try:
            import threading

            result_container = {}

            def _run():
                try:
                    result_container["response"] = client.chat(
                        model=model,
                        messages=messages,
                        options={
                            "temperature": temperature,
                            "top_p": cfg.llm.top_p,
                            "seed": cfg.llm.seed,
                            "num_predict": 4096,
                        },
                    )
                except Exception as e:
                    result_container["error"] = e

            start = time.time()
            thread = threading.Thread(target=_run, daemon=True)
            thread.start()
            thread.join(timeout=timeout)

            if thread.is_alive():
                last_error = f"{task} timed out after {timeout}s"
                logger.error(f"[{task}] LLM timeout on attempt {current_attempt}")
                if retry < max_retries - 1:
                    wait = 2 ** retry
                    logger.info(f"[{task}] Retrying in {wait}s...")
                    time.sleep(wait)
                continue

            if "error" in result_container:
                last_error = str(result_container["error"])
                logger.error(f"[{task}] LLM error on attempt {current_attempt}: {last_error}")
                if retry < max_retries - 1:
                    wait = 2 ** retry
                    logger.info(f"[{task}] Retrying in {wait}s...")
                    time.sleep(wait)
                continue

            # Success
            elapsed = time.time() - start
            content = result_container["response"]["message"]["content"]
            logger.info(
                f"[{task}] Response received | "
                f"time={elapsed:.1f}s | chars={len(content)} | attempt={current_attempt}"
            )
            return content

        except Exception as e:
            last_error = str(e)
            logger.error(f"[{task}] Unexpected error on attempt {current_attempt}: {e}")
            if retry < max_retries - 1:
                wait = 2 ** retry
                logger.info(f"[{task}] Retrying in {wait}s...")
                time.sleep(wait)

    raise RuntimeError(
        f"{task} failed after {max_retries} attempts. "
        f"Last error: {last_error}"
    )
