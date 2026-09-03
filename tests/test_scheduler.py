import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from apps.web.scheduler import CloudSchedulerSync


class _Response(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *_): return None


class CloudSchedulerSyncTests(unittest.TestCase):
    def test_updates_cron_and_resumes_a_paused_job(self):
        replies = [
            _Response(b'{"access_token":"token"}'), _Response(b'{"state":"PAUSED"}'),
            _Response(b'{"access_token":"token"}'), _Response(b'{"state":"PAUSED"}'),
            _Response(b'{"access_token":"token"}'), _Response(b'{"state":"ENABLED"}'),
        ]
        with patch("apps.web.scheduler.urlopen", side_effect=replies) as opener:
            result = CloudSchedulerSync("dev-project", "us-central1", "janus-ingestion-daily")({"time": "07:30", "enabled": True})

        self.assertEqual((result["schedule"], result["state"]), ("30 7 * * *", "ENABLED"))
        api_requests = [call.args[0] for call in opener.call_args_list if "cloudscheduler.googleapis.com" in call.args[0].full_url]
        self.assertEqual([request.method for request in api_requests], ["GET", "PATCH", "POST"])
        self.assertTrue(api_requests[-1].full_url.endswith(":resume"))

    def test_pauses_an_enabled_job(self):
        replies = [
            _Response(b'{"access_token":"token"}'), _Response(b'{"state":"ENABLED"}'),
            _Response(b'{"access_token":"token"}'), _Response(b'{"state":"ENABLED"}'),
            _Response(b'{"access_token":"token"}'), _Response(b'{"state":"PAUSED"}'),
        ]
        with patch("apps.web.scheduler.urlopen", side_effect=replies):
            result = CloudSchedulerSync("dev-project", "us-central1", "janus-ingestion-daily")({"time": "08:05", "enabled": False})

        self.assertEqual((result["schedule"], result["state"]), ("5 8 * * *", "PAUSED"))


if __name__ == "__main__":
    unittest.main()
