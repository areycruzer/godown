import os
import asyncio
import threading
from queue import Queue
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from app.config import get_settings

async def _call_web_search_mcp(query: str, num_results: int = 5) -> dict:
    settings = get_settings()
    api_key = settings.exa_api_key or os.environ.get("EXA_API_KEY", "")
    if not api_key:
        return {
            "query": query,
            "error": "EXA_API_KEY is not configured. Please set it in your .env file.",
            "ok": False
        }
    
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "exa-mcp-server"],
        env={**os.environ, "EXA_API_KEY": api_key}
    )

    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                result = await session.call_tool(
                    "web_search_exa",
                    arguments={"query": query, "numResults": num_results}
                )
                
                text_content = ""
                if hasattr(result, "content") and result.content:
                    for block in result.content:
                        if hasattr(block, "text"):
                            text_content += block.text + "\n"
                        elif isinstance(block, dict) and "text" in block:
                            text_content += block["text"] + "\n"
                
                return {
                    "query": query,
                    "results": text_content.strip() or str(result),
                    "ok": True
                }
    except Exception as e:
        return {
            "query": query,
            "error": str(e),
            "ok": False
        }

def web_search_mcp(query: str, num_results: int = 5) -> dict:
    coro = _call_web_search_mcp(query, num_results)
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    if loop.is_running():
        q = Queue()
        def worker():
            try:
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                res = new_loop.run_until_complete(coro)
                q.put((True, res))
            except Exception as ex:
                q.put((False, ex))
        t = threading.Thread(target=worker)
        t.start()
        t.join()
        ok, val = q.get()
        if ok:
            return val
        raise val
    else:
        return loop.run_until_complete(coro)
