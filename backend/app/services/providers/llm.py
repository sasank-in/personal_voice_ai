import openai
from openai import AsyncOpenAI

from app.services.providers.base import ProviderError

STAGE = "generating_text"


class OpenAICompatibleLLM:
    """Groq uses Chat Completions; xAI asks new integrations to use Responses."""

    def __init__(
        self,
        provider: str,
        api_key: str | None,
        base_url: str,
        model: str,
        timeout_seconds: float,
        max_output_tokens: int = 2048,
    ) -> None:
        if not api_key:
            raise ProviderError(
                "provider_not_configured", "The LLM API key is not configured.", stage="configuration"
            )
        self._provider = provider
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout_seconds)

    async def generate(self, system_prompt: str, messages: list[dict[str, str]]) -> str:
        try:
            content = await self._request(system_prompt, messages)
        except openai.AuthenticationError as exc:
            raise ProviderError(
                "provider_auth_failed", "The LLM provider rejected the configured key.", stage=STAGE, status_code=401
            ) from exc
        except openai.RateLimitError as exc:
            raise ProviderError(
                "provider_rate_limited", "The LLM provider is rate limited.", stage=STAGE, retryable=True, status_code=429
            ) from exc
        except (openai.APITimeoutError, openai.APIConnectionError, openai.InternalServerError) as exc:
            raise ProviderError(
                "provider_unavailable", "The LLM provider is unavailable.", stage=STAGE, retryable=True
            ) from exc
        except openai.APIError as exc:
            raise ProviderError("llm_request_failed", "The LLM request failed.", stage=STAGE) from exc

        if not content or not content.strip():
            raise ProviderError("empty_llm_response", "The LLM returned an empty response.", stage=STAGE, retryable=True)
        return content.strip()

    async def _request(self, system_prompt: str, messages: list[dict[str, str]]) -> str | None:
        if self._provider == "xai":
            response = await self._client.responses.create(
                model=self._model,
                instructions=system_prompt,
                input=messages,
                store=False,
                max_output_tokens=self._max_output_tokens,
            )
            return response.output_text

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": system_prompt}, *messages],
            max_completion_tokens=self._max_output_tokens,
        )
        return response.choices[0].message.content
