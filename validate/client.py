"""Ollama client with SSH tunnel management."""

from __future__ import annotations

import atexit
import json
import logging
import socket
import subprocess
import time

from json_repair import repair_json
from ollama import Client, ResponseError

logger = logging.getLogger(__name__)

_tunnel_proc: subprocess.Popen | None = None


def _is_port_open(host: str, port: int) -> bool:
    """Check if TCP port accepts connections."""
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


def _ensure_tunnel(config: dict) -> None:
    """Start SSH tunnel if configured.

    :param config: Configuration dictionary
    :raises ConnectionError: If tunnel fails to start
    """
    global _tunnel_proc

    cfg = config.get("ssh_tunnel", {})
    if not cfg.get("enabled", False):
        return

    local_port = cfg.get("local_port", 11434)
    if _is_port_open("localhost", local_port):
        return
    if _tunnel_proc is not None and _tunnel_proc.poll() is None:
        return

    host = cfg["host"]
    port = cfg.get("port", 22)
    user = cfg["username"]
    remote_host = cfg.get("remote_host", "localhost")
    remote_port = cfg.get("remote_port", 11434)

    logger.info("Opening SSH tunnel to %s@%s:%s", user, host, port)
    _tunnel_proc = subprocess.Popen(
        [
            "ssh",
            "-N",
            "-L",
            f"{local_port}:{remote_host}:{remote_port}",
            "-p",
            str(port),
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "ServerAliveInterval=30",
            "-o",
            "ServerAliveCountMax=3",
            f"{user}@{host}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    for _ in range(20):
        if _is_port_open("localhost", local_port):
            break
        if _tunnel_proc.poll() is not None:
            stderr = _tunnel_proc.stderr.read().decode().strip()
            raise ConnectionError(f"SSH tunnel failed: {stderr}")
        time.sleep(0.5)
    else:
        raise ConnectionError("SSH tunnel: port not reachable after 10s")

    logger.info(
        "SSH tunnel active: localhost:%d -> %s:%d", local_port, remote_host, remote_port
    )
    atexit.register(_close_tunnel)


def _close_tunnel() -> None:
    """Terminate the SSH tunnel subprocess."""
    global _tunnel_proc
    if _tunnel_proc is not None and _tunnel_proc.poll() is None:
        _tunnel_proc.terminate()
        _tunnel_proc.wait(timeout=5)
        _tunnel_proc = None


class OllamaClient:
    """Ollama API client with tunnel and retry support."""

    def __init__(self, config: dict) -> None:
        """Initialize Ollama client.

        :param config: Full configuration dictionary
        """
        self._config = config
        ollama_cfg = config["ollama"]
        self._host = ollama_cfg["host"]
        self._model = ollama_cfg["model"]
        self._options = ollama_cfg.get("options", {})
        self._keep_alive = ollama_cfg.get("keep_alive", "30m")
        self._retry_count = config.get("validation", {}).get("retry_count", 2)
        self._retry_delay = config.get("validation", {}).get("retry_delay_seconds", 5)
        self._client: Client | None = None

    def _get_client(self) -> Client:
        """Return Ollama client, starting tunnel if needed."""
        if self._client is None:
            _ensure_tunnel(self._config)
            self._client = Client(host=self._host)
        return self._client

    def _is_model_loaded(self) -> bool:
        """Check if model is already in GPU/RAM."""
        response = self._get_client().ps()
        return any(
            m.model == self._model or m.model.startswith(f"{self._model}:")
            for m in response.models
        )

    def _load_model(self) -> None:
        """Load model into memory if not already loaded."""
        if self._is_model_loaded():
            logger.debug("Model '%s' already loaded", self._model)
            return

        logger.info("Loading model '%s' (keep_alive=%s)", self._model, self._keep_alive)
        t0 = time.time()
        self._get_client().generate(
            model=self._model,
            prompt="",
            keep_alive=self._keep_alive,
        )
        logger.info("Model loaded in %.1fs", time.time() - t0)

    def health_check(self) -> bool:
        """Verify server connectivity and model availability.

        :returns: True if server and model are ready
        """
        try:
            available = [m.model for m in self._get_client().list().models]
        except (ConnectionError, OSError) as e:
            logger.error("Cannot connect to Ollama: %s", e)
            return False

        model_found = any(
            m == self._model or m.startswith(f"{self._model}:") for m in available
        )
        if not model_found:
            logger.error(
                "Model '%s' not found. Available: %s", self._model, ", ".join(available)
            )
            return False

        logger.info("Ollama OK: %d model(s) available", len(available))
        self._load_model()
        return True

    def extract(self, system_prompt: str, user_prompt: str) -> dict | None:
        """Send chat request and return parsed JSON.

        Retries on JSON parse errors and Ollama errors.

        :param system_prompt: System message
        :param user_prompt: User message with data
        :returns: Parsed JSON dict, or None if all attempts fail
        """
        client = self._get_client()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        for attempt in range(1 + self._retry_count):
            try:
                response = client.chat(
                    model=self._model,
                    messages=messages,
                    format="json",
                    options=self._options,
                    keep_alive=self._keep_alive,
                )
                result = json.loads(response.message.content)
                if isinstance(result, dict):
                    return result
                logger.warning("LLM returned %s, expected dict", type(result).__name__)
            except json.JSONDecodeError as e:
                logger.debug("JSON parse error (attempt %d): %s", attempt + 1, e)
                repaired = repair_json(response.message.content, return_objects=True)
                if isinstance(repaired, dict):
                    logger.debug("JSON repaired successfully")
                    return repaired
            except ResponseError as e:
                logger.warning("Ollama error (attempt %d): %s", attempt + 1, e)

            if attempt < self._retry_count:
                time.sleep(self._retry_delay)

        logger.error("All LLM extraction attempts failed")
        return None
