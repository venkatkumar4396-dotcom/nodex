"""Quick test for Kimi API connectivity."""
import asyncio
import sys

sys.path.insert(0, "src")

async def test():
    import agentflow.logging_config  # noqa — configures structlog
    from agentflow.core.llm.client import complete
    from agentflow.core.llm.structured import complete_structured
    from pydantic import BaseModel

    print("=" * 60)
    print("  AgentFlow — Kimi API Connectivity Test")
    print("=" * 60)

    # Test 1: Basic completion
    print("\n[1/2] Testing basic completion with moonshot-v1-8k...")
    try:
        resp = await complete(
            messages=[{"role": "user", "content": "Say hello in 5 words or less."}],
            model="moonshot/moonshot-v1-8k",
            max_tokens=30,
        )
        print(f"  [OK] Response: {resp.content.strip()}")
        print(f"  Tokens: {resp.total_tokens}, Cost: ${resp.cost_usd:.6f}")
    except Exception as e:  # noqa: BLE001
        print(f"  [FAIL] Basic completion failed: {e}")
        return

    # Test 2: Structured output
    print("\n[2/2] Testing structured JSON output with moonshot-v1-32k...")
    class TestOutput(BaseModel):
        message: str
        status: str

    try:
        result, resp2 = await complete_structured(
            messages=[{"role": "user", "content": "Return a greeting message."}],
            output_model=TestOutput,
            model="moonshot/moonshot-v1-32k",
        )
        print(f"  [OK] Parsed: message={result.message!r}, status={result.status!r}")
        print(f"  Tokens: {resp2.total_tokens}")
    except Exception as e:  # noqa: BLE001
        print(f"  [FAIL] Structured output failed: {e}")
        return

    print("\n" + "=" * 60)
    print("  [OK] ALL TESTS PASSED - Kimi API is working!")
    print("=" * 60)
    print("\nRun the demo:")
    print("  python -m agentflow.scripts.run_demo")
    print()

asyncio.run(test())
