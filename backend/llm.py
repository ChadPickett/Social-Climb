"""LLM access through the OpenAI-compatible chat API.

DeepSeek, OpenAI, OpenRouter, Groq, Together, Gemini's OpenAI endpoint and a
local Ollama server all speak this format, so switching is a .env change.
"""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod

import httpx

from .config import Settings


class LLMError(RuntimeError):
    pass


def parse_json(text: str) -> dict:
    """Parse a JSON object from model output, tolerating ``` fences or chatter."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
    raise LLMError(f"Model did not return valid JSON: {text[:200]}")


class LLM(ABC):
    @abstractmethod
    def complete_json(self, task: str, system: str, user: str) -> dict:
        """Run one chat turn and return the parsed JSON object. `task` names the agent."""


class OpenAICompatibleLLM(LLM):
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 120):
        if not api_key:
            raise LLMError("No AI key yet. Add your DeepSeek key in Settings.")
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.headers = {"Authorization": f"Bearer {api_key}"}
        self.model = model
        self.timeout = timeout

    def complete_json(self, task: str, system: str, user: str) -> dict:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_object"},
            "temperature": 0.7,
        }
        try:
            resp = httpx.post(self.url, headers=self.headers, json=body, timeout=self.timeout)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            if code in (401, 403):
                raise LLMError("The AI service didn't accept your key. Check the DeepSeek key in Settings.") from exc
            if code == 402:
                raise LLMError("Your AI account is out of credit. Top it up (for DeepSeek: platform.deepseek.com).") from exc
            raise LLMError(f"LLM API returned {exc.response.status_code}: {exc.response.text[:200]}") from exc
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise LLMError(f"LLM request failed ({task}): {exc}") from exc
        return parse_json(content or "")


class MockLLM(LLM):
    """Offline stand-in that returns plausible, deterministic output."""

    def complete_json(self, task: str, system: str, user: str) -> dict:
        payload = json.loads(user)
        topic = payload["topic"]
        words = re.findall(r"[a-z0-9]+", topic.lower())
        if task == "plan":
            base = "".join(words)
            return {
                "hashtags": [base, *words, f"{base}lovers", f"{base}facts"],
                "search_terms": [topic, f"{topic} tips"],
                "rationale": "Mock planner: derived tags from the topic words.",
            }
        stats = payload["stats"]
        return {
            "format": stats.get("best_format") or "carousel",
            "hook": f"3 things nobody tells you about {topic}",
            "caption": f"Here's what most people get wrong about {topic}... (mock draft)",
            "hashtags": [h["tag"] for h in payload.get("top_hashtags", [])][:10],
            "content_outline": ["Hook slide", "Point 1", "Point 2", "Point 3", "Call to action"],
            "visual_direction": "Bold text overlay on high-contrast imagery.",
            "call_to_action": "Save this and share it with a friend who'd love it.",
            "why_it_should_work": "Mirrors the format and timing of top performers (mock).",
            "posting_notes": "Reply to every comment in the first hour.",
        }


def build_llm(settings: Settings) -> LLM:
    if settings.active_llm_provider == "mock":
        return MockLLM()
    return OpenAICompatibleLLM(settings.llm_base_url, settings.llm_api_key, settings.llm_model)
