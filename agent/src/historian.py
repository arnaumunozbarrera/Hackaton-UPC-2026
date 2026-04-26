import json
from pathlib import Path


class JsonHistorian:
    def __init__(self, scenarios_dir: Path | str) -> None:
        """Create a JSON-backed historian adapter for synthetic scenarios.

        @param scenarios_dir: Directory containing scenario history JSON files.
        @return: None.
        """
        self.scenarios_dir = Path(scenarios_dir)

    def list_scenarios(self) -> list[str]:
        if not self.scenarios_dir.exists():
            return []

        return sorted(path.stem for path in self.scenarios_dir.glob("*.json"))

    def load_history(self, scenario_name: str) -> list[dict]:
        """Load and validate one scenario history file.

        @param scenario_name: Scenario filename stem to load.
        @return: Non-empty list of historical records.
        @raises FileNotFoundError: If the scenario file is missing.
        @raises ValueError: If the file does not contain a non-empty list.
        """
        path = self.scenarios_dir / f"{scenario_name}.json"

        if not path.exists():
            raise FileNotFoundError(f"Scenario file not found: {path}")

        with path.open("r", encoding="utf-8") as file:
            history = json.load(file)

        if not isinstance(history, list):
            raise ValueError(f"Scenario history must be a list: {path}")

        if not history:
            raise ValueError(f"Scenario history is empty: {path}")

        return history

    def get_run_id(self, scenario_name: str) -> str:
        history = self.load_history(scenario_name)
        return history[-1]["run_id"]

    def get_latest_record(self, scenario_name: str) -> dict:
        history = self.load_history(scenario_name)
        return history[-1]

    def get_recent_history(self, scenario_name: str, window_steps: int | None = None) -> list[dict]:
        """Load full or windowed scenario history in chronological order.

        @param scenario_name: Scenario filename stem to load.
        @param window_steps: Optional number of recent records to return.
        @return: Historical records ordered oldest to newest.
        @raises ValueError: If window_steps is provided and not positive.
        """
        history = self.load_history(scenario_name)

        if window_steps is None:
            return history

        if window_steps <= 0:
            raise ValueError("window_steps must be positive")

        return history[-window_steps:]

    def get_component_history(
        self,
        scenario_name: str,
        component_id: str,
        window_steps: int | None = None,
    ) -> list[dict]:
        """Load recent scenario records containing a specific component.

        @param scenario_name: Scenario filename stem to load.
        @param component_id: Component identifier to filter.
        @param window_steps: Optional number of recent records to inspect.
        @return: Component-specific history records.
        """
        history = self.get_recent_history(scenario_name, window_steps)

        result = []

        for record in history:
            components = record.get("components", {})

            if component_id not in components:
                continue

            result.append(
                {
                    "run_id": record["run_id"],
                    "timestamp": record["timestamp"],
                    "drivers": record["drivers"],
                    "component": components[component_id],
                }
            )

        return result
