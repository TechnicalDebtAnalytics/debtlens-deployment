import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = ROOT / "Deployment"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def service_environment(compose: str, service: str) -> set[str]:
    match = re.search(
        rf"(?ms)^  {re.escape(service)}:\s*$\n(.*?)(?=^  [a-zA-Z0-9_-]+:\s*$|^networks:\s*$|\Z)",
        compose,
    )
    if not match:
        raise AssertionError(f"Compose service not found: {service}")
    return set(re.findall(r"(?m)^\s+-\s+([A-Z][A-Z0-9_]*)=", match.group(1)))


def spring_property_environment_names(yaml_text: str) -> set[str]:
    stack: list[tuple[int, str]] = []
    names: set[str] = set()
    for line in yaml_text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.match(r"^(\s*)([A-Za-z0-9_-]+):", line)
        if not match:
            continue
        indent = len(match.group(1))
        key = match.group(2)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        stack.append((indent, key))
        canonical = "_".join(part for _, part in stack).replace("-", "_").upper()
        names.add(canonical)
    return names


def dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in read(path).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


class DeploymentConfigurationTest(unittest.TestCase):
    def test_cfg_02_deployment_variables_are_consumed_by_services(self):
        compose = read(DEPLOYMENT / "docker-compose.yml")
        configurations = {
            "main-backend": read(ROOT / "Application_service_Spring_Boot/src/main/resources/application.yaml"),
            "analysis-service": read(ROOT / "Analysis_Service_Spring_Boot/src/main/resources/application.yaml"),
            "ml-service": read(ROOT / "ML_service_FastAPI/app/config/settings.py"),
        }

        missing: list[str] = []
        for service, configuration in configurations.items():
            declared = service_environment(compose, service)
            if service == "ml-service":
                consumed = set(re.findall(r'os\.getenv\("([A-Z][A-Z0-9_]*)"', configuration))
            else:
                consumed = spring_property_environment_names(configuration)
                consumed.update(re.findall(r"\$\{([A-Z][A-Z0-9_]*)", configuration))
            missing.extend(f"{service}:{name}" for name in sorted(declared - consumed))

        self.assertEqual(
            [],
            missing,
            "Deployment variables declared but not consumed by the corresponding service: "
            + ", ".join(missing),
        )

    def test_cfg_03_rabbitmq_queue_names_are_consistent(self):
        constant_pattern = re.compile(
            r'public\s+static\s+final\s+String\s+(\w+)\s*=\s*"([^"]+)"'
        )
        application_constants = dict(
            constant_pattern.findall(
                read(
                    ROOT
                    / "Application_service_Spring_Boot/src/main/java/com/debtlens/backend/config/RabbitMQConfig.java"
                )
            )
        )
        analysis_constants = dict(
            constant_pattern.findall(
                read(
                    ROOT
                    / "Analysis_Service_Spring_Boot/src/main/java/com/debtlens/analysisservice/config/RabbitMQConfig.java"
                )
            )
        )
        settings = read(ROOT / "ML_service_FastAPI/app/config/settings.py")
        ml_defaults = dict(
            re.findall(
                r'(ML_(?:JOB|RESULT)_QUEUE).*?os\.getenv\("\1",\s*"([^"]+)"\)',
                settings,
            )
        )
        deployment_defaults = dotenv(DEPLOYMENT / ".env.example")

        expected = {
            "analysis-job": deployment_defaults["ANALYSIS_JOB_QUEUE"],
            "analysis-result": deployment_defaults["ANALYSIS_RESULT_QUEUE"],
            "ml-job": deployment_defaults["ML_JOB_QUEUE"],
            "ml-result": deployment_defaults["ML_RESULT_QUEUE"],
        }
        actual = {
            "application-analysis-job": application_constants["ANALYSIS_JOB_QUEUE"],
            "analysis-analysis-job": analysis_constants["ANALYSIS_JOB_QUEUE"],
            "application-analysis-result": application_constants["ANALYSIS_RESULT_QUEUE"],
            "analysis-analysis-result": analysis_constants["ANALYSIS_RESULT_QUEUE"],
            "application-ml-job": application_constants["ML_JOB_CREATION_QUEUE"],
            "ml-ml-job": ml_defaults["ML_JOB_QUEUE"],
            "application-ml-result": application_constants["ML_JOB_RESULTS_QUEUE"],
            "ml-ml-result": ml_defaults["ML_RESULT_QUEUE"],
        }
        for name, value in actual.items():
            queue_type = name.split("-", 1)[1]
            self.assertEqual(expected[queue_type], value, f"Queue mismatch for {name}")

    def test_cfg_07_deployment_and_secret_configuration_is_safe_and_consistent(self):
        issues: list[str] = []

        for relative in (
            "Application_service_Spring_Boot/src/main/resources/application.yaml",
            "Analysis_Service_Spring_Boot/src/main/resources/application.yaml",
        ):
            for number, line in enumerate(read(ROOT / relative).splitlines(), start=1):
                stripped = line.strip()
                match = re.match(r"(?:username|password|client-secret):\s*(.+)$", stripped)
                if match and not re.fullmatch(r"\$\{[A-Z][A-Z0-9_]*:?\}", match.group(1)):
                    issues.append(f"tracked credential/default in {relative}:{number}")

        application_yaml = read(
            ROOT / "Application_service_Spring_Boot/src/main/resources/application.yaml"
        )
        datasource_section = re.search(
            r"(?ms)^\s{2}datasource:\s*$\n(.*?)(?=^\s{2}[A-Za-z0-9_-]+:|\Z)",
            application_yaml,
        )
        if datasource_section and "${DB_URL" not in datasource_section.group(1):
            issues.append("Application datasource URL is stored in tracked configuration")

        for project in (
            "Deployment",
            "frontend",
            "Application_service_Spring_Boot",
            "Analysis_Service_Spring_Boot",
            "ML_service_FastAPI",
        ):
            ignore_file = ROOT / project / ".gitignore"
            if not ignore_file.exists() or not re.search(
                r"(?m)^\.env(?:\*|$)", read(ignore_file)
            ):
                issues.append(f"{project} does not explicitly ignore .env files")

        deployment_readme = read(DEPLOYMENT / "README.md").lower()
        claims_automatic_images = "automatic" in deployment_readme and "ghcr.io" in deployment_readme
        if claims_automatic_images:
            for project in (
                "frontend",
                "Application_service_Spring_Boot",
                "Analysis_Service_Spring_Boot",
                "ML_service_FastAPI",
            ):
                if not (ROOT / project / "Dockerfile").exists():
                    issues.append(f"{project} has no Dockerfile required by deployment documentation")
                workflows = ROOT / project / ".github/workflows"
                workflow_text = "\n".join(
                    read(path) for path in workflows.glob("*.y*ml")
                ) if workflows.exists() else ""
                if "docker/build-push-action" not in workflow_text and "docker build" not in workflow_text:
                    issues.append(f"{project} has no documented container image publishing workflow")

        self.assertEqual([], issues, "Configuration findings: " + "; ".join(issues))


if __name__ == "__main__":
    unittest.main()
