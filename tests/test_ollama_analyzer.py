"""Tests for ollama_analyzer.py."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import ollama_analyzer as oa


# ---------------------------------------------------------------------------
# log_prompt
# ---------------------------------------------------------------------------

class TestLogPrompt:
    def test_creates_log_entry(self, tmp_path: Path) -> None:
        log_file = tmp_path / "prompts.log"
        with patch.object(oa, "PROMPT_LOG_FILE", log_file):
            oa.log_prompt("test_task", "hello world", "gpt-4o")

        assert log_file.exists()
        entry = json.loads(log_file.read_text(encoding="utf-8").strip())
        assert entry["task"] == "test_task"
        assert entry["model"] == "gpt-4o"
        assert entry["prompt_length"] == len("hello world")

    def test_appends_multiple_entries(self, tmp_path: Path) -> None:
        log_file = tmp_path / "prompts.log"
        with patch.object(oa, "PROMPT_LOG_FILE", log_file):
            oa.log_prompt("task1", "prompt 1", "model-a")
            oa.log_prompt("task2", "prompt 2", "model-b")

        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2

    def test_does_not_raise_on_write_error(self, tmp_path: Path) -> None:
        # If the log directory can't be created, log_prompt should swallow the error
        bad_path = Path("/nonexistent/deeply/nested/dir/log.jsonl")
        with patch.object(oa, "PROMPT_LOG_FILE", bad_path):
            # Should not raise
            oa.log_prompt("task", "prompt", "model")

    def test_prompt_preview_truncated(self, tmp_path: Path) -> None:
        log_file = tmp_path / "prompts.log"
        long_prompt = "x" * 500
        with patch.object(oa, "PROMPT_LOG_FILE", log_file):
            oa.log_prompt("task", long_prompt, "model")

        entry = json.loads(log_file.read_text(encoding="utf-8").strip())
        assert len(entry["prompt_preview"]) <= 200


# ---------------------------------------------------------------------------
# OllamaClient
# ---------------------------------------------------------------------------

class TestOllamaClient:
    def test_default_url_and_model(self) -> None:
        client = oa.OllamaClient()
        assert "localhost" in client.base_url
        assert client.model == "gpt-oss:20b"
        assert client.provider == "ollama"

    def test_health_check_true_when_200(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("requests.get", return_value=mock_resp):
            client = oa.OllamaClient()
            assert client.health_check() is True

    def test_health_check_false_when_non_200(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        with patch("requests.get", return_value=mock_resp):
            client = oa.OllamaClient()
            assert client.health_check() is False

    def test_health_check_false_on_exception(self) -> None:
        with patch("requests.get", side_effect=Exception("connection refused")):
            client = oa.OllamaClient()
            assert client.health_check() is False

    def test_list_models_returns_names(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "models": [{"name": "llama3"}, {"name": "mistral"}]
        }
        with patch("requests.get", return_value=mock_resp):
            client = oa.OllamaClient()
            models = client.list_models()
        assert models == ["llama3", "mistral"]

    def test_list_models_empty_on_exception(self) -> None:
        with patch("requests.get", side_effect=Exception("connection error")):
            client = oa.OllamaClient()
            assert client.list_models() == []

    def test_generate_returns_response_text(self, tmp_path: Path) -> None:
        log_file = tmp_path / "prompts.log"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": "Hello there!"}
        with patch("requests.post", return_value=mock_resp):
            with patch.object(oa, "PROMPT_LOG_FILE", log_file):
                client = oa.OllamaClient()
                result = client.generate("Say hello")
        assert result == "Hello there!"

    def test_generate_returns_none_on_exception(self, tmp_path: Path) -> None:
        log_file = tmp_path / "prompts.log"
        with patch("requests.post", side_effect=Exception("server error")):
            with patch.object(oa, "PROMPT_LOG_FILE", log_file):
                client = oa.OllamaClient()
                result = client.generate("Say hello")
        assert result is None

    def test_chat_returns_content(self, tmp_path: Path) -> None:
        log_file = tmp_path / "prompts.log"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"message": {"content": "Chat response"}}
        messages = [{"role": "user", "content": "Hello"}]
        with patch("requests.post", return_value=mock_resp):
            with patch.object(oa, "PROMPT_LOG_FILE", log_file):
                client = oa.OllamaClient()
                result = client.chat(messages)
        assert result == "Chat response"

    def test_chat_returns_none_on_exception(self, tmp_path: Path) -> None:
        log_file = tmp_path / "prompts.log"
        with patch("requests.post", side_effect=Exception("error")):
            with patch.object(oa, "PROMPT_LOG_FILE", log_file):
                client = oa.OllamaClient()
                result = client.chat([{"role": "user", "content": "Hi"}])
        assert result is None


# ---------------------------------------------------------------------------
# GitHubModelsClient
# ---------------------------------------------------------------------------

class TestGitHubModelsClient:
    def test_is_configured_with_token(self) -> None:
        client = oa.GitHubModelsClient(token="test-token-123")
        assert client.is_configured() is True

    def test_is_not_configured_without_token(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            # Ensure no env var is set
            for key in ("GITHUB_MODELS_TOKEN", "GITHUB_TOKEN"):
                os.environ.pop(key, None)
            client = oa.GitHubModelsClient(token=None)
            assert client.is_configured() is False

    def test_provider_is_github_models(self) -> None:
        client = oa.GitHubModelsClient(token="tok")
        assert client.provider == "github-models"

    def test_chat_returns_none_without_token(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            for key in ("GITHUB_MODELS_TOKEN", "GITHUB_TOKEN"):
                os.environ.pop(key, None)
            client = oa.GitHubModelsClient(token=None)
            result = client.chat([{"role": "user", "content": "Hello"}])
        assert result is None

    def test_chat_returns_content(self, tmp_path: Path) -> None:
        log_file = tmp_path / "prompts.log"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "GitHub response"}}]
        }
        messages = [{"role": "user", "content": "Hello"}]
        with patch("requests.post", return_value=mock_resp):
            with patch.object(oa, "PROMPT_LOG_FILE", log_file):
                client = oa.GitHubModelsClient(token="test-token")
                result = client.chat(messages)
        assert result == "GitHub response"

    def test_chat_returns_none_on_exception(self, tmp_path: Path) -> None:
        log_file = tmp_path / "prompts.log"
        with patch("requests.post", side_effect=Exception("API error")):
            with patch.object(oa, "PROMPT_LOG_FILE", log_file):
                client = oa.GitHubModelsClient(token="test-token")
                result = client.chat([{"role": "user", "content": "Hi"}])
        assert result is None

    def test_chat_empty_choices_returns_none(self, tmp_path: Path) -> None:
        log_file = tmp_path / "prompts.log"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": []}
        messages = [{"role": "user", "content": "Hello"}]
        with patch("requests.post", return_value=mock_resp):
            with patch.object(oa, "PROMPT_LOG_FILE", log_file):
                client = oa.GitHubModelsClient(token="test-token")
                result = client.chat(messages)
        assert result is None


# ---------------------------------------------------------------------------
# analyze_record
# ---------------------------------------------------------------------------

class TestAnalyzeRecord:
    def _mock_client(self, response: str = "mock output") -> MagicMock:
        client = MagicMock()
        client.provider = "ollama"
        client.generate.return_value = response
        return client

    def test_summarize_task_calls_generate(self) -> None:
        client = self._mock_client("A summary.")
        record = {"AGENCY": "NASA", "SUBJECT": "Cloud Platform", "DESC": "Build a cloud."}
        result = oa.analyze_record(client, record, task="summarize")
        assert result == "A summary."
        client.generate.assert_called_once()

    def test_extract_tech_task(self) -> None:
        client = self._mock_client("Python, Docker, Kubernetes")
        record = {"SUBJECT": "DevOps Contract", "DESC": "DevOps pipeline."}
        result = oa.analyze_record(client, record, task="extract_tech")
        assert result == "Python, Docker, Kubernetes"

    def test_classify_task(self) -> None:
        client = self._mock_client("ICT/Software Development")
        record = {"SUBJECT": "Web App", "DESC": "Build a web application."}
        result = oa.analyze_record(client, record, task="classify")
        assert "ICT" in result or result == "ICT/Software Development"

    def test_assess_relevance_task(self) -> None:
        client = self._mock_client("8 - Good match for accessibility work.")
        record = {"SUBJECT": "508 Compliance", "DESC": "Accessibility testing."}
        result = oa.analyze_record(client, record, task="assess_relevance")
        assert result is not None

    def test_unknown_task_returns_none(self) -> None:
        client = self._mock_client()
        result = oa.analyze_record(client, {}, task="unknown_task")
        assert result is None

    def test_github_models_client_uses_chat(self, tmp_path: Path) -> None:
        log_file = tmp_path / "prompts.log"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "GitHub summary"}}]
        }
        record = {"AGENCY": "HHS", "SUBJECT": "Portal", "DESC": "Health portal."}
        with patch("requests.post", return_value=mock_resp):
            with patch.object(oa, "PROMPT_LOG_FILE", log_file):
                client = oa.GitHubModelsClient(token="tok")
                result = oa.analyze_record(client, record, task="summarize")
        assert result == "GitHub summary"
