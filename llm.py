import os
import time
from openai import OpenAI

_KEY = os.getenv("OPENROUTER_API_KEY", "")
MODEL = "z-ai/glm-4.5-air"

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=_KEY,
    default_headers={"HTTP-Referer": "https://bilion-rouge.vercel.app"},
)

def chat(system: str, messages: list, max_tokens: int = 600) -> str:
    msgs = [{"role": "system", "content": system}] + messages
    for attempt in range(3):
        try:
            r = client.chat.completions.create(
                model=MODEL,
                messages=msgs,
                max_tokens=max_tokens,
            )
            choice = r.choices[0]
            content = choice.message.content

            # GLM reasoning model: content may be null if reasoning consumed all tokens
            if not content:
                # try to grab from reasoning field if present
                raw = getattr(choice.message, "reasoning", None)
                if raw:
                    content = raw
            if content:
                return content.strip()

            # empty response — wait and retry
            time.sleep(1.5 * (attempt + 1))
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(1.5 * (attempt + 1))
    return ""
