import json
import sqlite3
from pathlib import Path
from typing import Any


class SQLiteHistorian:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)

    def list_runs(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT run_id, scenario_id, created_at, description, selected_component, total_usages, usage_step, config_json
                FROM runs
                ORDER BY created_at DESC
                """
            ).fetchall()

        return [
            {
                "run_id": row["run_id"],
                "scenario_id": row["scenario_id"],
                "created_at": row["created_at"],
                "description": row["description"],
                "selected_component": row["selected_component"],
                "total_usages": row["total_usages"],
                "usage_step": row["usage_step"],
                "config": json.loads(row["config_json"] or "{}"),
            }
            for row in rows
        ]

    def list_scenarios(self) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT scenario_id
                FROM runs
                ORDER BY scenario_id ASC
                """
            ).fetchall()

        return [row["scenario_id"] for row in rows]

    def get_latest_run(self) -> dict[str, Any] | None:
        runs = self.list_runs()
        return runs[0] if runs else None

    def get_latest_run_id_for_scenario(self, scenario_id: str) -> str:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT run_id
                FROM runs
                WHERE scenario_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (scenario_id,),
            ).fetchone()

        if row is None:
            raise ValueError(f"No run found for scenario_id={scenario_id}")

        return row["run_id"]

    def resolve_run_id(self, run_or_scenario_id: str) -> str:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT run_id
                FROM runs
                WHERE run_id = ?
                LIMIT 1
                """,
                (run_or_scenario_id,),
            ).fetchone()

        if row is not None:
            return row["run_id"]

        return self.get_latest_run_id_for_scenario(run_or_scenario_id)

    def get_run_id(self, run_or_scenario_id: str) -> str:
        return self.resolve_run_id(run_or_scenario_id)

    def get_latest_record(self, run_or_scenario_id: str) -> dict[str, Any]:
        run_id = self.resolve_run_id(run_or_scenario_id)

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT record_id, run_id, scenario_id, step_index, usage_count, timestamp
                FROM telemetry_records
                WHERE run_id = ?
                ORDER BY step_index DESC
                LIMIT 1
                """,
                (run_id,),
            ).fetchone()

            if row is None:
                raise ValueError(f"No telemetry records found for run_id={run_id}")

            return self._build_record(connection, row)

    def get_recent_history(self, run_or_scenario_id: str, window_steps: int | None = None) -> list[dict[str, Any]]:
        run_id = self.resolve_run_id(run_or_scenario_id)

        with self._connect() as connection:
            if window_steps is None:
                rows = connection.execute(
                    """
                    SELECT record_id, run_id, scenario_id, step_index, usage_count, timestamp
                    FROM telemetry_records
                    WHERE run_id = ?
                    ORDER BY step_index ASC
                    """,
                    (run_id,),
                ).fetchall()
            else:
                if window_steps <= 0:
                    raise ValueError("window_steps must be positive")

                rows = connection.execute(
                    """
                    SELECT record_id, run_id, scenario_id, step_index, usage_count, timestamp
                    FROM telemetry_records
                    WHERE run_id = ?
                    ORDER BY step_index DESC
                    LIMIT ?
                    """,
                    (run_id, window_steps),
                ).fetchall()
                rows = list(reversed(rows))

            return [
                self._build_record(connection, row)
                for row in rows
            ]

    def get_component_history(
        self,
        run_or_scenario_id: str,
        component_id: str,
        window_steps: int | None = None,
    ) -> list[dict[str, Any]]:
        history = self.get_recent_history(run_or_scenario_id, window_steps)

        return [
            record
            for record in history
            if component_id in record.get("components", {})
        ]

    def _connect(self) -> sqlite3.Connection:
        if not self.db_path.exists():
            raise FileNotFoundError(f"SQLite historian not found: {self.db_path}")

        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _build_record(self, connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
        driver_row = connection.execute(
            """
            SELECT operational_load, contamination, humidity, temperature_stress, maintenance_level
            FROM driver_values
            WHERE record_id = ?
            """,
            (row["record_id"],),
        ).fetchone()

        if driver_row is None:
            raise ValueError(f"Missing driver values for record_id={row['record_id']}")

        return {
            "run_id": row["run_id"],
            "scenario_id": row["scenario_id"],
            "step_index": row["step_index"],
            "usage_count": float(row["usage_count"]) if row["usage_count"] is not None else float(row["step_index"]),
            "timestamp": row["timestamp"],
            "drivers": {
                "operational_load": float(driver_row["operational_load"]),
                "contamination": float(driver_row["contamination"]),
                "humidity": float(driver_row["humidity"]),
                "temperature_stress": float(driver_row["temperature_stress"]),
                "maintenance_level": float(driver_row["maintenance_level"]),
            },
            "components": self._build_components(connection, row["record_id"]),
        }

    def _build_components(self, connection: sqlite3.Connection, record_id: int) -> dict[str, Any]:
        state_rows = connection.execute(
            """
            SELECT component_id, subsystem, health_index, status
            FROM component_states
            WHERE record_id = ?
            ORDER BY component_id ASC
            """,
            (record_id,),
        ).fetchall()

        components = {}

        for state_row in state_rows:
            component_id = state_row["component_id"]

            components[component_id] = {
                "component": component_id,
                "subsystem": state_row["subsystem"],
                "health_index": float(state_row["health_index"]),
                "status": state_row["status"],
                "damage": self._get_component_damage(connection, record_id, component_id),
                "metrics": self._get_component_metrics(connection, record_id, component_id),
                "alerts": self._get_component_alerts(connection, record_id, component_id),
            }

        return components

    def _get_component_damage(
        self,
        connection: sqlite3.Connection,
        record_id: int,
        component_id: str,
    ) -> dict[str, float]:
        rows = connection.execute(
            """
            SELECT damage_name, damage_value
            FROM component_damage
            WHERE record_id = ? AND component_id = ?
            ORDER BY damage_name ASC
            """,
            (record_id, component_id),
        ).fetchall()

        return {
            row["damage_name"]: float(row["damage_value"])
            for row in rows
        }

    def _get_component_metrics(
        self,
        connection: sqlite3.Connection,
        record_id: int,
        component_id: str,
    ) -> dict[str, float]:
        rows = connection.execute(
            """
            SELECT metric_name, metric_value
            FROM component_metrics
            WHERE record_id = ? AND component_id = ?
            ORDER BY metric_name ASC
            """,
            (record_id, component_id),
        ).fetchall()

        return {
            row["metric_name"]: float(row["metric_value"])
            for row in rows
        }

    def _get_component_alerts(
        self,
        connection: sqlite3.Connection,
        record_id: int,
        component_id: str,
    ) -> list[Any]:
        rows = connection.execute(
            """
            SELECT alert_value
            FROM component_alerts
            WHERE record_id = ? AND component_id = ?
            ORDER BY alert_index ASC
            """,
            (record_id, component_id),
        ).fetchall()

        return [
            self._deserialize_alert(row["alert_value"])
            for row in rows
        ]

    def _deserialize_alert(self, value: str) -> Any:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value