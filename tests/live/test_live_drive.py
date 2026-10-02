import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "gdrive-cli"))


@unittest.skipUnless(
    os.environ.get("RUN_LIVE_DRIVE_TESTS") == "1",
    "set RUN_LIVE_DRIVE_TESTS=1 with dedicated-account credentials",
)
class LiveDriveTests(unittest.TestCase):
    def test_list_one_file(self):
        import gdrive_cli

        service = gdrive_cli.drive_service()
        result = gdrive_cli.list_recent_files(service, page_size=1)
        self.assertLessEqual(len(result["files"]), 1)


if __name__ == "__main__":
    unittest.main()
