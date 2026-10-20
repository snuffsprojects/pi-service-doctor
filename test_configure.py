import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import configure


class ConfigureTests(unittest.TestCase):
    def test_discovery_adds_active_known_units(self):
        with patch.object(configure, "unit_exists", return_value=True), patch.object(configure, "unit_active", side_effect=lambda name: name in {"nginx", "logrotate.timer"}):
            result = configure.discover()
        self.assertEqual([item["name"] for item in result["services"]], ["nginx"])
        self.assertEqual([item["name"] for item in result["timers"]], ["logrotate.timer"])
        self.assertEqual(result["ports"][0]["port"], 80)
        self.assertEqual(result["urls"][0]["url"], "http://127.0.0.1/")

    def test_discovery_without_web_server_has_no_web_checks(self):
        with patch.object(configure, "unit_exists", return_value=False):
            result = configure.discover()
        self.assertEqual(result["ports"], [])
        self.assertEqual(result["urls"], [])


if __name__ == "__main__":
    unittest.main()
