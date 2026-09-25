import asyncio
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

async def my_async_tool(x: int) -> int:
    """Multiplies by 2"""
    await asyncio.sleep(0.1)
    return x * 2

def run_test():
    agent = LlmAgent(
        name="test",
        model=LiteLlm(model="gemini-2.5-flash"),
        instruction="Use my_async_tool to double 5.",
        tools=[my_async_tool],
    )
    runner = Runner(agent=agent, app_name="test", session_service=InMemorySessionService())
    
    async def main():
        import os
        from app.config import settings
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
        os.environ["OPENAI_API_BASE"] = settings.openai_api_base
        
        async for event in runner.run_async("u1", "s1", types.Content(role="user", parts=[types.Part(text="double 5")])):
            print(event)
            
    asyncio.run(main())

run_test()
