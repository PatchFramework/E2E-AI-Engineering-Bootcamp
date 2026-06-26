from openai import OpenAI

from api.core.config import config

SUPPORTED_PROVIDERS = ["OpenAI"]
def run_llm(provider, model_name, messages, max_tokens=500):
    assert provider in SUPPORTED_PROVIDERS, f"Unsupported provider: {provider}. Only the following providers are supported: {SUPPORTED_PROVIDERS}"
    
    if provider == "OpenAI":
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        return client.chat.completions.create(
            model=model_name,
            messages=messages,
            max_completion_tokens=max_tokens,
            reasoning_effort="minimal"
        ).choices[0].message.content