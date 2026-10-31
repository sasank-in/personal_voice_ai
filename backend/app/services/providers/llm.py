import openai
from openai import AsyncOpenAI

from app.services.providers.base import GeneratedText, ProviderError
from app.services.providers.openai_common import map_openai_error, response_usage

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

    async def generate(self, system_prompt: str, messages: list[dict[str, str]]) -> GeneratedText:
        try:
            result = await self._request(system_prompt, messages)
        except openai.APIError as exc:
            raise map_openai_error(exc, STAGE, "LLM provider", "llm_request_failed", "The LLM request failed.") from exc

        if not result.text or not result.text.strip():
            raise ProviderError(
                "empty_llm_response",
                "The LLM returned an empty response.",
                stage=STAGE,
                retryable=True,
                request_id=result.usage.request_id,
            )
        return GeneratedText(result.text.strip(), result.usage)

    async def _request(self, system_prompt: str, messages: list[dict[str, str]]) -> GeneratedText:
        if self._provider == "xai":
            response = await self._client.responses.create(
                model=self._model,
                instructions=system_prompt,
                input=messages,
                store=False,
                max_output_tokens=self._max_output_tokens,
            )
            tokens = response.usage
            return GeneratedText(
                response.output_text,
                response_usage(
                    response,
                    tokens.input_tokens if tokens else None,
                    tokens.output_tokens if tokens else None,
                ),
            )

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": system_prompt}, *messages],
            max_completion_tokens=self._max_output_tokens,
        )
        tokens = response.usage
        return GeneratedText(
            response.choices[0].message.content,
            response_usage(
                response,
                tokens.prompt_tokens if tokens else None,
                tokens.completion_tokens if tokens else None,
            ),
        )
