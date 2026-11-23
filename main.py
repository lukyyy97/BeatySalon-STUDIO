"""Entry point: `python main.py`."""
import asyncio
import contextlib

from bot.app import main

if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt, SystemExit):
        asyncio.run(main())
