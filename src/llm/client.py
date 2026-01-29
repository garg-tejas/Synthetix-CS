"""
LLM client wrapper for ModelScope API inference.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import List, Optional

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    import requests
except ImportError:
    requests = None

# Load .env file if it exists
if load_dotenv is not None:
    project_root = Path(__file__).resolve().parents[2]
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)


DEFAULT_MODELSCOPE_MODEL = os.getenv("MODELSCOPE_MODEL", "zai-org/GLM-4.7-Flash")


class ModelScopeClient:
    """Wrapper around ModelScope API for cloud inference."""

    def __init__(
        self,
        model_name: str = DEFAULT_MODELSCOPE_MODEL,
        api_token: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        if requests is None:
            raise ImportError("requests not installed. Install with: uv pip install requests")

        self.model_name = model_name
        self.api_token = api_token or os.getenv("MODELSCOPE_API_TOKEN")
        if not self.api_token:
            raise ValueError(
                "ModelScope API token required. Set MODELSCOPE_API_TOKEN environment variable "
                "or get token from https://modelscope.cn/my/myaccesstoken"
            )

        self.base_url = base_url or os.getenv(
            "MODELSCOPE_API_URL",
            "https://api.modelscope.cn/v1/chat/completions"
        )
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    def generate_single(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        top_p: float = 0.9,
        stop: Optional[List[str]] = None,
    ) -> str:
        """Generate text for a single prompt."""
        results = self.generate([prompt], max_tokens, temperature, top_p, stop)
        return results[0] if results else ""

    def generate(
        self,
        prompts: List[str],
        max_tokens: int = 2048,
        temperature: float = 0.7,
        top_p: float = 0.9,
        stop: Optional[List[str]] = None,
    ) -> List[str]:
        """Generate text for a batch of prompts."""
        results = []
        for prompt in prompts:
            try:
                messages = [{"role": "user", "content": prompt}]

                payload = {
                    "model": self.model_name,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "top_p": top_p,
                }

                if stop:
                    payload["stop"] = stop

                response = requests.post(
                    self.base_url,
                    headers=self.headers,
                    json=payload,
                    timeout=120,
                )
                response.raise_for_status()

                data = response.json()
                if "choices" in data and len(data["choices"]) > 0:
                    generated_text = data["choices"][0]["message"]["content"]
                    results.append(generated_text.strip())
                else:
                    print(f"Warning: Unexpected response format: {data}")
                    results.append("")

                time.sleep(0.5)

            except requests.exceptions.RequestException as e:
                print(f"Error calling ModelScope API: {e}")
                if hasattr(e, "response") and e.response is not None:
                    print(f"Response: {e.response.text}")
                results.append("")
                time.sleep(2)

        return results


def create_client(
    model_name: Optional[str] = None,
    modelscope_token: Optional[str] = None,
) -> ModelScopeClient:
    """Factory function to create a ModelScope API client."""
    if model_name is None:
        model_name = os.getenv("MODELSCOPE_MODEL", DEFAULT_MODELSCOPE_MODEL)
    return ModelScopeClient(model_name=model_name, api_token=modelscope_token)
