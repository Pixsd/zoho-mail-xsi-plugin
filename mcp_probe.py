"""Bounded real-stdio smoke test; no Zoho credentials or network needed."""
import asyncio
import json
from pathlib import Path
import sys
import tempfile
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    with tempfile.TemporaryDirectory(prefix='zoho-probe-') as data:
        params = StdioServerParameters(command=sys.executable,
            args=[str(Path(__file__).resolve().with_name('connector.py'))],
            env={'ZOHO_MAIL_DATA_DIR': data})
        async with asyncio.timeout(15):
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    info = await session.initialize()
                    tools = await session.list_tools()
                    await session.send_ping()
                    assert len(tools.tools) == 10
                    print(json.dumps({'server': info.serverInfo.name, 'tools': len(tools.tools), 'ping': 'ok'}))

if __name__ == '__main__':
    asyncio.run(main())
