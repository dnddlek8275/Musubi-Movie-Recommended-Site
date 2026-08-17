import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


AI_ROOT = Path(__file__).resolve().parents[1]
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))

from ops.warm_llm_slots import wait_until_ready, warm_slot


class WarmLlmSlotsTests(unittest.TestCase):
    @patch("ops.warm_llm_slots.urllib.request.urlopen")
    def test_warm_slot_uses_current_general_prompt_and_one_token(self, urlopen):
        response = Mock(status=200)
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b"{}"
        urlopen.return_value = response

        result = warm_slot(0, "http://llama:8081", 10)

        request = urlopen.call_args.args[0]
        payload = __import__("json").loads(request.data)
        self.assertEqual(payload["max_tokens"], 1)
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertIn("무무", payload["messages"][0]["content"])
        self.assertEqual(result["status"], "ok")

    @patch("ops.warm_llm_slots.urllib.request.urlopen")
    def test_ready_health_succeeds(self, urlopen):
        response = Mock(status=200)
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        urlopen.return_value = response
        wait_until_ready("http://llama:8081", 1)
        urlopen.assert_called_once_with("http://llama:8081/health", timeout=2)


if __name__ == "__main__":
    unittest.main()
