import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import doctor


class DoctorTests(unittest.TestCase):
    def test_threshold_status(self):
        self.assertEqual(doctor.threshold_status(50, 80, 90), "healthy")
        self.assertEqual(doctor.threshold_status(85, 80, 90), "warning")
        self.assertEqual(doctor.threshold_status(95, 80, 90), "critical")

    def test_duration_label(self):
        self.assertEqual(doctor.duration_label(90), "1m")
        self.assertEqual(doctor.duration_label(90061), "1d 1h")

    def test_failed_units_can_be_ignored(self):
        output = "run-p123.service loaded failed failed transient\nnginx.service loaded failed failed nginx"
        with patch.object(doctor, "run", return_value=(0, output)):
            result = doctor.failed_unit_check({"ignoreFailedUnits": ["run-*.service"]})
        self.assertEqual(result["status"], "critical")
        self.assertEqual(result["units"], ["nginx.service"])

    def test_atomic_write_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "status.json"
            doctor.atomic_write(path, {"overall": "healthy"})
            self.assertEqual(json.loads(path.read_text()), {"overall": "healthy"})


if __name__ == "__main__":
    unittest.main()

