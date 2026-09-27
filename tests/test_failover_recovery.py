import json
import subprocess
import unittest
from pathlib import Path


DEPLOYMENT_DIR = Path(__file__).resolve().parents[1]


def resolved_compose_configuration() -> dict:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            str(DEPLOYMENT_DIR / ".env.example"),
            "-f",
            str(DEPLOYMENT_DIR / "docker-compose.yml"),
            "config",
            "--format",
            "json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


class FailoverRecoveryConfigurationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.configuration = resolved_compose_configuration()

    def test_FR_01_application_service_has_automatic_restart_recovery(self) -> None:
        service = self.configuration["services"]["main-backend"]

        self.assertEqual("unless-stopped", service["restart"])
        self.assertIn("debtlens-network", service["networks"])

    def test_FR_02_analysis_service_has_automatic_restart_recovery(self) -> None:
        service = self.configuration["services"]["analysis-service"]

        self.assertEqual("unless-stopped", service["restart"])
        self.assertIn("debtlens-network", service["networks"])


if __name__ == "__main__":
    unittest.main()
