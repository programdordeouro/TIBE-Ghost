import os
from openai import OpenAI

_KEY = os.getenv("OPENROUTER_API_KEY", "")
MODEL = "z-ai/glm-4.5-air"

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=_KEY,
    default_headers={"HTTP-Referer": "https://bilion-rouge.vercel.app"},
)

def chat(system: str, messages: list, max_tokens: int = 500) -> str:
    msgs = [{"role": "system", "content": system}] + messages
    r = client.chat.completions.create(
        model=MODEL,
        messages=msgs,
        max_tokens=max_tokens,
    )
    return (r.choices[0].message.content or "").strip()
