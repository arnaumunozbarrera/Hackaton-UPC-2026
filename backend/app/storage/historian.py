"""SQLite historian for Phase 2 simulation telemetry."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parents[2] / "storage" / "historian.sqlite"


CREATE_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS runs (
        run_id TEXT PRIMARY KEY,
        scenario_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        description TEXT,
        selected_component TEXT,
        total_usages REAL,
        usage_step REAL,
        config_json TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS telemetry_records (
        record_id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        scenario_id TEXT NOT NULL,
        step_index INTEGER NOT NULL,
        timestamp TEXT NOT NULL,
        raw_phase1_output TEXT NOT NULL,
        FOREIGN KEY (run_id) REFERENCES runs(run_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS driver_values (
        record_id INTEGER PRIMARY KEY,
        operational_load REAL NOT NULL,
        contamination REAL NOT NULL,
        humidity REAL NOT NULL,
        temperature_stress REAL NOT NULL,
        maintenance_level REAL NOT NULL,
        FOREIGN KEY (record_id) REFERENCES telemetry_records(record_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS component_states (
        record_id INTEGER NOT NULL,
        component_id TEXT NOT NULL,
        subsystem TEXT NOT NULL,
        health_index REAL NOT NULL,
        status TEXT NOT NULL,
        PRIMARY KEY (record_id, component_id),
        FOREIGN KEY (record_id) REFERENCES telemetry_records(record_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS component_damage (
        record_id INTEGER NOT NULL,
        component_id TEXT NOT NULL,
        damage_name TEXT NOT NULL,
        damage_value REAL NOT NULL,
        PRIMARY KEY (record_id, component_id, damage_name),
        FOREIGN KEY (record_id, component_id) REFERENCES component_states(record_id, component_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS component_metrics (
        record_id INTEGER NOT NULL,
        component_id TEXT NOT NULL,
        metric_name TEXT NOT NULL,
        metric_value REAL NOT NULL,
        PRIMARY KEY (record_id, component_id, metric_name),
        FOREIGN KEY (record_id, component_id) REFERENCES component_states(record_id, component_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS component_alerts (
        record_id INTEGER NOT NULL,
        component_id TEXT NOT NULL,
        alert_index INTEGER NOT NULL,
        alert_value TEXT NOT NULL,
        PRIMARY KEY (record_id, component_id, alert_index),
        FOREIGN KEY (record_id, component_id) REFERENCES component_states(record_id, component_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        component_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        prediction_json TEXT NOT NULL,
        FOREIGN KEY (run_id) REFERENCES runs(run_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        component_id TEXT,
        timestamp TEXT NOT NULL,
        severity TEXT NOT NULL,
        title TEXT NOT NULL,
        body TEXT NOT NULL,
        evidence_json TEXT NOT NULL,
        FOREIGN KEY (run_id) REFERENCES runs(run_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_telemetry_run_timestamp
    ON telemetry_records(run_id, timestamp)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_component_states_component
    ON component_states(component_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_component_states_status
    ON component_states(status)
    """,
]


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database() -> None:
    with _connect() as connection:
        _migrate_legacy_schema(connection)
        for statement in CREATE_STATEMENTS:
            connection.execute(statement)
        connection.commit()


def _migrate_legacy_schema(connection: sqlite3.Connection) -> None:
    existing_tables = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }

    if "simulation_runs" in existing_tables or "simulation_points" in existing_tables:
        connection.execute("DROP TABLE IF EXISTS messages")
        connection.execute("DROP TABLE IF EXISTS predictions")
        connection.execute("DROP TABLE IF EXISTS simulation_points")
        connection.execute("DROP TABLE IF EXISTS simulation_runs")


def create_run(
    run_id: str,
    scenario_id: str,
    created_at: str,
    description: str | None = None,
    selected_component: str | None = None,
    total_usages: float | None = None,
    usage_step: float | None = None,
    config: dict | None = None,
) -> None:
    with _connect() as connection:
        connection.execute("DELETE FROM messages WHERE run_id = ?", (run_id,))
        connection.execute("DELETE FROM predictions WHERE run_id = ?", (run_id,))
        connection.execute(
            "DELETE FROM component_alerts WHERE record_id IN (SELECT record_id FROM telemetry_records WHERE run_id = ?)",
            (run_id,),
        )
        connection.execute(
            "DELETE FROM component_metrics WHERE record_id IN (SELECT record_id FROM telemetry_records WHERE run_id = ?)",
            (run_id,),
        )
        connection.execute(
            "DELETE FROM component_damage WHERE record_id IN (SELECT record_id FROM telemetry_records WHERE run_id = ?)",
            (run_id,),
        )
        connection.execute(
            "DELETE FROM component_states WHERE record_id IN (SELECT record_id FROM telemetry_records WHERE run_id = ?)",
            (run_id,),
        )
        connection.execute("DELETE FROM driver_values WHERE record_id IN (SELECT record_id FROM telemetry_records WHERE run_id = ?)", (run_id,))
        connection.execute("DELETE FROM telemetry_records WHERE run_id = ?", (run_id,))
        connection.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
        connection.execute(
            """
            INSERT INTO runs (
                run_id,
                scenario_id,
                created_at,
                description,
                selected_component,
                total_usages,
                usage_step,
                config_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                scenario_id,
                created_at,
                description,
                selected_component,
                total_usages,
                usage_step,
                json.dumps(config or {}),
            ),
        )
        connection.commit()


def save_simulation_step(
    run_id: str,
    scenario_id: str,
    step_index: int,
    timestamp: str,
    drivers: dict,
    phase1_output: dict,
) -> int:
    with _connect() as connection:
        record_id = _insert_simulation_step(
            connection=connection,
            run_id=run_id,
            scenario_id=scenario_id,
            step_index=step_index,
            timestamp=timestamp,
            drivers=drivers,
            phase1_output=phase1_output,
        )
        connection.commit()
    return record_id


def _insert_simulation_step(
    connection: sqlite3.Connection,
    run_id: str,
    scenario_id: str,
    step_index: int,
    timestamp: str,
    drivers: dict,
    phase1_output: dict,
) -> int:
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO telemetry_records (
            run_id,
            scenario_id,
            step_index,
            timestamp,
            raw_phase1_output
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            run_id,
            scenario_id,
            step_index,
            timestamp,
            json.dumps(phase1_output),
        ),
    )
    record_id = cursor.lastrowid

    cursor.execute(
        """
        INSERT INTO driver_values (
            record_id,
            operational_load,
            contamination,
            humidity,
            temperature_stress,
            maintenance_level
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            record_id,
            float(drivers["operational_load"]),
            float(drivers["contamination"]),
            float(drivers["humidity"]),
            float(drivers["temperature_stress"]),
            float(drivers["maintenance_level"]),
        ),
    )

    for component_id, component_data in phase1_output.get("components", {}).items():
        cursor.execute(
            """
            INSERT INTO component_states (
                record_id,
                component_id,
                subsystem,
                health_index,
                status
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                record_id,
                component_id,
                component_data["subsystem"],
                float(component_data["health"]),
                component_data["status"],
            ),
        )

        for damage_name, damage_value in component_data.get("damage", {}).items():
            cursor.execute(
                """
                INSERT INTO component_damage (
                    record_id,
                    component_id,
                    damage_name,
                    damage_value
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    record_id,
                    component_id,
                    damage_name,
                    float(damage_value),
                ),
            )

        for metric_name, metric_value in component_data.get("metrics", {}).items():
            if metric_value is None:
                continue
            cursor.execute(
                """
                INSERT INTO component_metrics (
                    record_id,
                    component_id,
                    metric_name,
                    metric_value
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    record_id,
                    component_id,
                    metric_name,
                    float(metric_value),
                ),
            )

        for alert_index, alert_value in enumerate(component_data.get("alerts", [])):
            serialized_alert = (
                json.dumps(alert_value)
                if isinstance(alert_value, (dict, list))
                else str(alert_value)
            )
            cursor.execute(
                """
                INSERT INTO component_alerts (
                    record_id,
                    component_id,
                    alert_index,
                    alert_value
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    record_id,
                    component_id,
                    alert_index,
                    serialized_alert,
                ),
            )

    return int(record_id)


def save_prediction(run_id: str, component_id: str, created_at: str, prediction: dict) -> None:
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO predictions
            (run_id, component_id, created_at, prediction_json)
            VALUES (?, ?, ?, ?)
            """,
            (run_id, component_id, created_at, json.dumps(prediction)),
        )
        connection.commit()


def save_messages(run_id: str, messages: list[dict]) -> None:
    if not messages:
        return

    with _connect() as connection:
        connection.executemany(
            """
            INSERT INTO messages
            (run_id, component_id, timestamp, severity, title, body, evidence_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id,
                    message.get("component_id"),
                    message["timestamp"],
                    message["severity"],
                    message["title"],
                    message["body"],
                    json.dumps(message["evidence"]),
                )
                for message in messages
            ],
        )
        connection.commit()


def list_runs() -> list[dict]:
    with _connect() as connection:
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


def get_latest_run() -> dict | None:
    runs = list_runs()
    return runs[0] if runs else None


def _deserialize_alert(alert_value: str):
    try:
        return json.loads(alert_value)
    except json.JSONDecodeError:
        return alert_value


def _build_components(connection: sqlite3.Connection, record_id: int) -> dict:
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
        damage_rows = connection.execute(
            """
            SELECT damage_name, damage_value
            FROM component_damage
            WHERE record_id = ? AND component_id = ?
            ORDER BY damage_name ASC
            """,
            (record_id, component_id),
        ).fetchall()
        metric_rows = connection.execute(
            """
            SELECT metric_name, metric_value
            FROM component_metrics
            WHERE record_id = ? AND component_id = ?
            ORDER BY metric_name ASC
            """,
            (record_id, component_id),
        ).fetchall()
        alert_rows = connection.execute(
            """
            SELECT alert_value
            FROM component_alerts
            WHERE record_id = ? AND component_id = ?
            ORDER BY alert_index ASC
            """,
            (record_id, component_id),
        ).fetchall()

        components[component_id] = {
            "component": component_id,
            "subsystem": state_row["subsystem"],
            "health_index": float(state_row["health_index"]),
            "status": state_row["status"],
            "damage": {
                row["damage_name"]: float(row["damage_value"])
                for row in damage_rows
            },
            "metrics": {
                row["metric_name"]: float(row["metric_value"])
                for row in metric_rows
            },
            "alerts": [_deserialize_alert(row["alert_value"]) for row in alert_rows],
        }

    return components


def _get_run_metadata(connection: sqlite3.Connection, run_id: str) -> dict | None:
    row = connection.execute(
        """
        SELECT run_id, scenario_id, created_at, description, selected_component, total_usages, usage_step
        FROM runs
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def get_run_timeline(run_id: str) -> list[dict]:
    with _connect() as connection:
        run_metadata = _get_run_metadata(connection, run_id)
        if run_metadata is None:
            return []

        rows = connection.execute(
            """
            SELECT record_id, run_id, scenario_id, step_index, timestamp
            FROM telemetry_records
            WHERE run_id = ?
            ORDER BY step_index ASC
            """,
            (run_id,),
        ).fetchall()

        timeline = []
        usage_step = float(run_metadata["usage_step"] or 1.0)
        for row in rows:
            driver_row = connection.execute(
                """
                SELECT operational_load, contamination, humidity, temperature_stress, maintenance_level
                FROM driver_values
                WHERE record_id = ?
                """,
                (row["record_id"],),
            ).fetchone()
            if driver_row is None:
                continue

            timeline.append(
                {
                    "run_id": row["run_id"],
                    "scenario_id": row["scenario_id"],
                    "step_index": row["step_index"],
                    "usage_count": round(float(row["step_index"]) * usage_step, 6),
                    "timestamp": row["timestamp"],
                    "drivers": {
                        "operational_load": float(driver_row["operational_load"]),
                        "contamination": float(driver_row["contamination"]),
                        "humidity": float(driver_row["humidity"]),
                        "temperature_stress": float(driver_row["temperature_stress"]),
                        "maintenance_level": float(driver_row["maintenance_level"]),
                    },
                    "components": _build_components(connection, row["record_id"]),
                }
            )

    return timeline


def get_component_history(run_id: str, component_id: str) -> list[dict]:
    return [
        point
        for point in get_run_timeline(run_id)
        if component_id in point.get("components", {})
    ]


def get_recent_history(scenario_name: str, window_steps: int) -> list[dict]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT record_id, run_id, scenario_id, timestamp
            FROM telemetry_records
            WHERE scenario_id = ?
            ORDER BY timestamp DESC, step_index DESC
            LIMIT ?
            """,
            (scenario_name, window_steps),
        ).fetchall()

        history = []
        for row in reversed(rows):
            driver_row = connection.execute(
                """
                SELECT operational_load, contamination, humidity, temperature_stress, maintenance_level
                FROM driver_values
                WHERE record_id = ?
                """,
                (row["record_id"],),
            ).fetchone()
            if driver_row is None:
                continue

            history.append(
                {
                    "run_id": row["run_id"],
                    "scenario_id": row["scenario_id"],
                    "timestamp": row["timestamp"],
                    "drivers": {
                        "operational_load": float(driver_row["operational_load"]),
                        "contamination": float(driver_row["contamination"]),
                        "humidity": float(driver_row["humidity"]),
                        "temperature_stress": float(driver_row["temperature_stress"]),
                        "maintenance_level": float(driver_row["maintenance_level"]),
                    },
                    "components": _build_components(connection, row["record_id"]),
                }
            )

    return history


def get_raw_phase1_output(run_id: str, step_index: int) -> dict | None:
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT raw_phase1_output
            FROM telemetry_records
            WHERE run_id = ? AND step_index = ?
            """,
            (run_id, step_index),
        ).fetchone()
    return json.loads(row["raw_phase1_output"]) if row else None


def get_messages(run_id: str) -> list[dict]:
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT id, run_id, component_id, timestamp, severity, title, body, evidence_json
            FROM messages
            WHERE run_id = ?
            ORDER BY timestamp ASC, id ASC
            """,
            (run_id,),
        ).fetchall()

    return [
        {
            "id": f"msg_{row['id']}",
            "run_id": row["run_id"],
            "component_id": row["component_id"],
            "timestamp": row["timestamp"],
            "severity": row["severity"],
            "title": row["title"],
            "body": row["body"],
            "evidence": json.loads(row["evidence_json"]),
        }
        for row in rows
    ]


def get_latest_prediction(run_id: str, component_id: str) -> dict | None:
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT prediction_json
            FROM predictions
            WHERE run_id = ? AND component_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (run_id, component_id),
        ).fetchone()
    return json.loads(row["prediction_json"]) if row else None


def clear_database() -> None:
    with _connect() as connection:
        connection.execute("DELETE FROM messages")
        connection.execute("DELETE FROM predictions")
        connection.execute("DELETE FROM component_alerts")
        connection.execute("DELETE FROM component_metrics")
        connection.execute("DELETE FROM component_damage")
        connection.execute("DELETE FROM component_states")
        connection.execute("DELETE FROM driver_values")
        connection.execute("DELETE FROM telemetry_records")
        connection.execute("DELETE FROM runs")
        connection.commit()
