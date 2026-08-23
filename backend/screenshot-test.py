import asyncio
import os
import sys

# Ensure Python can import modules from current directory
sys.path.insert(0, os.path.abspath("."))

from app.core.config import settings
from app.recon.services.screenshot_service import ScreenshotService

# 🛠️ OVERRIDE STORAGE PATH for local testing (Saves to ./test_screenshots instead of /app)
settings.RECON_SCREENSHOT_STORAGE_PATH = os.path.abspath("./test_screenshots")


class DummyTarget:
    target_type = "URL"
    host = "ict-integrators.com"
    raw = "https://ict-integrators.com"


async def test_capture():
    service = ScreenshotService()
    target = DummyTarget()

    print(f"Attempting to capture screenshot for {target.raw}...")
    result = await service.capture(target)

    print("\n--- Service Result Payload ---")
    print(result)

    if result.get("captured"):
        screenshot_id = result["screenshot_id"]
        file_path = os.path.join(
            settings.RECON_SCREENSHOT_STORAGE_PATH, f"{screenshot_id}.png"
        )

        print("\n--- Disk Check ---")
        if os.path.exists(file_path):
            size_kb = os.path.getsize(file_path) / 1024
            print(f" SUCCESS! Screenshot captured.")
            print(f" File Location: {file_path}")
            print(f" File Size: {size_kb:.2f} KB")
        else:
            print(f" FAILED: Result says captured, but file missing at {file_path}")
    else:
        print(f"\n FAILED: {result.get('error')}")


if __name__ == "__main__":
    asyncio.run(test_capture())