"""D0 连接自检：验证 SDK 版本、API key，列出可用 Agent 与模型。"""
import asyncio

import sciencepal
from sciencepal import SciencePal

from common import get_config


async def main() -> None:
    api_key, base_url = get_config()
    print(f"SDK version : {sciencepal.__version__}")
    print(f"Base URL    : {base_url}")
    print(f"API key     : {api_key[:8]}...{api_key[-4:]}（已脱敏）")
    print("-" * 60)

    async with SciencePal(api_key=api_key, base_url=base_url, timeout=60) as client:
        # 1) 可用 Agent
        print("【可用 Agent】")
        try:
            agents, pagination = await client.agents.list(page=1, limit=100)
            for a in agents:
                print(f"  - {getattr(a, 'name', '?'):20s} id={getattr(a, 'id', '?')}")
            print(f"  页数: {getattr(pagination, 'pages', '?')}")
        except Exception as e:
            print(f"  列出 Agent 失败: {type(e).__name__}: {e}")

        print("-" * 60)
        # 2) 可用模型
        print("【可选模型】")
        try:
            models = await client.models.list()
            for m in models:
                mid = m.get("id", "?") if isinstance(m, dict) else getattr(m, "id", "?")
                name = m.get("display_name", "") if isinstance(m, dict) else getattr(m, "display_name", "")
                print(f"  - {mid:32s} {name}")
        except Exception as e:
            print(f"  列出模型失败: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
