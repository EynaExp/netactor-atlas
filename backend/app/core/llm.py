from openai import AsyncOpenAI
from typing import List, Dict, Any, Optional
from app.core.config import settings
import json
import asyncio
import logging

logger = logging.getLogger(__name__)

# Hard timeout for a single LLM call — prevents agents hanging forever on
# slow/stuck reasoning models. One retry is attempted before giving up.
LLM_CALL_TIMEOUT = 180  # seconds


class LLMClient:
    def __init__(self, base_url: str = None, api_key: str = None, model: str = None):
        self.base_url = base_url or settings.LLM_BASE_URL
        self.api_key = api_key or settings.LLM_API_KEY
        self.model = model or settings.LLM_MODEL
        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=LLM_CALL_TIMEOUT,
        )

    async def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = None,
        temperature: float = None,
        max_tokens: int = None,
        response_format: dict = None
    ) -> Dict[str, Any]:
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        kwargs = {
            "model": self.model,
            "messages": full_messages,
            "temperature": temperature or settings.DEFAULT_TEMPERATURE,
            "max_tokens": max_tokens or settings.DEFAULT_MAX_TOKENS,
        }
        if response_format:
            kwargs["response_format"] = response_format

        last_err = None
        for attempt in range(2):
            try:
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(**kwargs),
                    timeout=LLM_CALL_TIMEOUT
                )
                message = response.choices[0].message
                content = message.content
                # Reasoning models may return content=None with reasoning filled
                if not content and hasattr(message, 'reasoning') and message.reasoning:
                    content = message.reasoning
                tokens_used = response.usage.total_tokens if response.usage else 0

                return {
                    "content": content or "",
                    "tokens_used": tokens_used,
                    "model": response.model
                }
            except (asyncio.TimeoutError, Exception) as e:
                last_err = e
                logger.warning(f"LLM call attempt {attempt + 1} failed: {type(e).__name__}: {e}")
                if attempt == 0:
                    await asyncio.sleep(2)  # brief pause before retry
        raise RuntimeError(f"LLM call failed after retry: {type(last_err).__name__}: {last_err}")

    async def chat_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        system_prompt: str = None,
        temperature: float = None,
        max_tokens: int = None
    ) -> Dict[str, Any]:
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=full_messages,
            tools=tools,
            tool_choice="auto",
            temperature=temperature or settings.DEFAULT_TEMPERATURE,
            max_tokens=max_tokens or settings.DEFAULT_MAX_TOKENS
        )

        message = response.choices[0].message
        tokens_used = response.usage.total_tokens if response.usage else 0

        return {
            "content": message.content,
            "tool_calls": message.tool_calls,
            "tokens_used": tokens_used,
            "model": response.model
        }

    async def extract_json(self, content: str) -> Any:
        try:
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
                if content.endswith("```"):
                    content = content[:-3]
            return json.loads(content)
        except json.JSONDecodeError:
            return {"raw": content}
