"""Allow running: python -m src.enrichment.batch_extract"""

import asyncio
from .batch_extract import main

asyncio.run(main())
