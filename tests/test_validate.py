"""Tests for validate module."""

from __future__ import annotations

import tempfile
from pathlib import Path

import yaml

from validate.client import OllamaClient
from validate.fetcher import fetch_page_text
from validate.prompt import SYSTEM_PROMPT, build_user_prompt
from validate.validator import apply_results


class TestFetcher:
    """Tests for fetcher module."""

    def test_fetch_linkedin_blocked(self) -> None:
        """LinkedIn URLs should be marked as blocked."""
        url = "https://www.linkedin.com/posts/test"
        text, status = fetch_page_text(url)
        assert status == "blocked"
        assert text == ""

    def test_fetch_invalid_url(self) -> None:
        """Invalid URLs should return error status."""
        url = "https://invalid-domain-that-does-not-exist-12345.com/path"
        text, status = fetch_page_text(url)
        assert status == "error"
        assert text == ""


class TestPrompt:
    """Tests for prompt module."""

    def test_system_prompt_exists(self) -> None:
        """System prompt should be defined."""
        assert SYSTEM_PROMPT
        assert "expert" in SYSTEM_PROMPT.lower()
        assert "reviewer" in SYSTEM_PROMPT.lower()

    def test_build_user_prompt(self) -> None:
        """User prompt should include all entry metadata."""
        entry = {
            "conference": "CVPR",
            "year": 2026,
            "role": "Reviewer",
            "url": "https://example.com/call",
            "label": "Main",
        }
        content = "We are recruiting reviewers for CVPR 2026"

        prompt = build_user_prompt(entry, content)

        assert "CVPR 2026" in prompt
        assert "Reviewer" in prompt
        assert "Main" in prompt
        assert "https://example.com/call" in prompt
        assert "We are recruiting reviewers" in prompt
        assert "answer" in prompt
        assert "reason" in prompt


class TestOllamaClient:
    """Tests for Ollama client."""

    def test_client_initialization(self) -> None:
        """Client should initialize with config dict."""
        config = {
            "ssh_tunnel": {"enabled": False},
            "ollama": {
                "host": "http://localhost:11434",
                "model": "qwen2.5:7b",
                "keep_alive": "30m",
                "options": {},
            },
            "validation": {"retry_count": 2, "retry_delay_seconds": 5},
        }
        client = OllamaClient(config)
        assert client._host == "http://localhost:11434"
        assert client._model == "qwen2.5:7b"

    def test_health_check_unavailable(self) -> None:
        """Health check should return False if service unavailable."""
        config = {
            "ssh_tunnel": {"enabled": False},
            "ollama": {
                "host": "http://localhost:19999",
                "model": "qwen2.5:7b",
                "keep_alive": "30m",
                "options": {},
            },
            "validation": {"retry_count": 0, "retry_delay_seconds": 0},
        }
        client = OllamaClient(config)
        result = client.health_check()
        assert result is False


class TestValidationResults:
    """Tests for apply_results function."""

    def test_apply_results_with_invalid(self) -> None:
        """apply_results should move invalid entries to rejected_urls.yaml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            calls_path = Path(tmpdir) / "calls.yaml"
            rejected_path = Path(tmpdir) / "rejected_urls.yaml"

            initial_calls = {
                "calls": [
                    {
                        "url": "https://example.com/valid",
                        "conference": "CVPR",
                        "year": 2026,
                        "role": "Reviewer",
                        "date": "2026-02-20",
                        "confirmed": False,
                    },
                    {
                        "url": "https://example.com/invalid",
                        "conference": "ICCV",
                        "year": 2026,
                        "role": "PC",
                        "date": "2026-02-20",
                        "confirmed": False,
                    },
                ]
            }

            with open(calls_path, "w") as f:
                yaml.dump(initial_calls, f)

            results = [
                {
                    "url": "https://example.com/valid",
                    "status": "valid",
                    "reason": "Explicitly invites reviewer nominations",
                },
                {
                    "url": "https://example.com/invalid",
                    "status": "invalid",
                    "reason": "Not a reviewer call",
                },
            ]

            valid_count, invalid_count = apply_results(
                results, str(calls_path), str(rejected_path)
            )

            assert valid_count == 1
            assert invalid_count == 1

            with open(calls_path) as f:
                updated_calls = yaml.safe_load(f)

            assert len(updated_calls["calls"]) == 1
            assert updated_calls["calls"][0]["url"] == "https://example.com/valid"
            assert updated_calls["calls"][0]["confirmed"] is True

            assert rejected_path.exists()
            with open(rejected_path) as f:
                rejected = yaml.safe_load(f)

            assert len(rejected["rejected_urls"]) == 1
            assert rejected["rejected_urls"][0]["url"] == "https://example.com/invalid"
