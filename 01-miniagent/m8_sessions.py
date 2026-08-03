"""Claude Agent SDK session resume and fork exercise (live/paid when run)."""

import asyncio

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query


async def run_and_get_session(prompt: str, options: ClaudeAgentOptions) -> str:
    """Run one turn and return its session identifier."""
    session_id = ""
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            session_id = message.session_id
            print(message.result)
    if not session_id:
        raise RuntimeError("The SDK returned no session ID")
    return session_id


async def main() -> None:
    base = await run_and_get_session(
        "Design two refund-policy options and list their tradeoffs. Do not choose yet.",
        ClaudeAgentOptions(max_turns=3, max_budget_usd=0.30),
    )
    print(f"base session: {base}")

    # Resume the original state but fork before pursuing a divergent option.
    forked = await run_and_get_session(
        "Pursue the customer-friendly option and write acceptance criteria.",
        ClaudeAgentOptions(
            resume=base,
            fork_session=True,
            max_turns=3,
            max_budget_usd=0.30,
        ),
    )
    print(f"forked session: {forked}")


if __name__ == "__main__":
    asyncio.run(main())
