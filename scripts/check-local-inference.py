"""Generate a real local reply and a proposal without credentials or repository writes."""

import asyncio

from backend.app.schemas.bot_changes import BotChangeProposal
from backend.app.services.bots.provider import generate_text


async def main() -> None:
    model = "ollama/qwen2.5-coder:0.5b"
    answer = await generate_text(
        model, "Reply briefly.", [{"role": "user", "content": "Explain a Git branch in one sentence."}]
    )
    if not answer.strip():
        raise ValueError("Local chat did not return an answer")
    print("Real local chat without an API key: OK")
    proposal = await generate_text(
        model,
        "Return only the requested JSON proposal. Do not add other files.",
        [{"role": "user", "content": (
            "Propose creating docs/local-inference.md with one sentence explaining that "
            "local inference needs no OpenAI key. Include summary and files; each file "
            "has path, action=create, and content."
        )}],
        output_schema=BotChangeProposal.model_json_schema(),
    )
    parsed = BotChangeProposal.model_validate_json(proposal)
    if not parsed.files:
        raise ValueError("Local proposal has no files")
    print("Real schema-constrained local proposal: OK; no files applied")


if __name__ == "__main__":
    asyncio.run(main())
