"""
LLM client wrapper for ModelScope API using OpenAI SDK.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Iterator, List, Optional

import random
from dotenv import load_dotenv
from openai import OpenAI

# Load .env file if it exists
if load_dotenv is not None:
    project_root = Path(__file__).resolve().parents[2]
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)


DEFAULT_MODELSCOPE_MODEL = os.getenv("MODELSCOPE_MODEL", "deepseek-ai/DeepSeek-R1-0528")
DEFAULT_BASE_URL = "https://api-inference.modelscope.ai/v1"


class ModelScopeClient:
    """Wrapper around ModelScope API using OpenAI SDK."""

    def __init__(
        self,
        model_name: str = DEFAULT_MODELSCOPE_MODEL,
        api_token: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        if OpenAI is None:
            raise ImportError("openai not installed. Install with: uv pip install openai")

        self.model_name = model_name
        self.api_token = api_token or os.getenv("MODELSCOPE_API_TOKEN")
        if not self.api_token:
            raise ValueError(
                "ModelScope API token required. Set MODELSCOPE_API_TOKEN environment variable "
                "or get token from https://modelscope.cn/my/myaccesstoken"
            )

        self.base_url = base_url or os.getenv("MODELSCOPE_API_URL", DEFAULT_BASE_URL)
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_token,
        )

    def generate_single(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        top_p: float = 0.9,
        stop: Optional[List[str]] = None,
        max_retries: int = 3,
    ) -> str:
        """Generate text for a single prompt."""
        results = self.generate([prompt], max_tokens, temperature, top_p, stop, max_retries)
        return results[0] if results else ""

    def generate(
        self,
        prompts: List[str],
        max_tokens: int = 2048,
        temperature: float = 0.7,
        top_p: float = 0.9,
        stop: Optional[List[str]] = None,
        max_retries: int = 3,
    ) -> List[str]:
        """Generate text for a batch of prompts with rate limiting."""
        results = []
        for i, prompt in enumerate(prompts):
            retry_count = 0
            while retry_count < max_retries:
                try:
                    response = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=max_tokens,
                        temperature=temperature,
                        top_p=top_p,
                        stop=stop,
                    )

                    if response.choices and len(response.choices) > 0:
                        generated_text = response.choices[0].message.content or ""
                        if not generated_text.strip():
                            print(f"Warning: Empty content in response for prompt {i+1}")
                        results.append(generated_text.strip())
                    else:
                        print(f"Warning: Empty response from ModelScope API for prompt {i+1}")
                        results.append("")

                    # Rate limiting: delay between requests to avoid concurrency limits
                    if i < len(prompts) - 1:
                        delay = 2.0 + random.uniform(0, 1.0)
                        time.sleep(delay)
                    
                    break

                except Exception as e:
                    error_str = str(e)
                    # Check for rate limit errors
                    if "429" in error_str or "concurrency" in error_str.lower() or "1302" in error_str:
                        retry_count += 1
                        if retry_count >= max_retries:
                            print(f"Rate limit exceeded after {max_retries} retries. Skipping this prompt.")
                            results.append("")
                            # Longer delay before continuing to next prompt
                            time.sleep(10 + random.uniform(0, 5))
                            break
                        # Exponential backoff with jitter for concurrency limits
                        backoff = (2 ** retry_count) * 3 + random.uniform(0, 3)
                        print(f"Rate limit hit (429/concurrency). Retrying in {backoff:.1f}s (attempt {retry_count}/{max_retries})...")
                        time.sleep(backoff)
                    else:
                        print(f"Error calling ModelScope API: {e}")
                        results.append("")
                        time.sleep(2)
                        break

        return results

    def stream(
        self,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        top_p: float = 0.9,
        stop: Optional[List[str]] = None,
    ) -> Iterator[str]:
        """Stream text generation for a single prompt."""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                stop=stop,
                stream=True,
            )

            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            print(f"Error streaming from ModelScope API: {e}")
            yield ""


def create_client(
    model_name: Optional[str] = None,
    modelscope_token: Optional[str] = None,
) -> ModelScopeClient:
    """Factory function to create a ModelScope API client."""
    if model_name is None:
        model_name = os.getenv("MODELSCOPE_MODEL", DEFAULT_MODELSCOPE_MODEL)
    return ModelScopeClient(model_name=model_name, api_token=modelscope_token)
