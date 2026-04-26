"""SQLite historian for Phase 2 simulation telemetry."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.messages.message_generator import select_top_messages


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
        usage_count REAL,
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
    """Open a configured SQLite connection for historian operations.

    @return: SQLite connection with row access by column name and foreign keys enabled.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database() -> None:
    """Create or migrate the historian schema required by the backend.

    @return: None.
    """
    with _connect() as connection:
        _migrate_legacy_schema(connection)
        for statement in CREATE_STATEMENTS:
            connection.execute(statement)
        connection.commit()


def _migrate_legacy_schema(connection: sqlite3.Connection) -> None:
    """Apply lightweight migrations for older local historian databases.

    @param connection: Open SQLite connection inside the initialization transaction.
    @return: None.
    """
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

    if "telemetry_records" in existing_tables:
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(telemetry_records)"
            ).fetchall()
        }
        if "usage_count" not in columns:
            connection.execute(
                "ALTER TABLE telemetry_records ADD COLUMN usage_count REAL"
            )
            connection.execute(
                """
                UPDATE telemetry_records
                SET usage_count = step_index * COALESCE(
                    (
                        SELECT usage_step
                        FROM runs
                        WHERE runs.run_id = telemetry_records.run_id
                    ),
                    1.0
                )
                """
            )


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
    """Replace existing data for a run and create fresh run metadata.

    @param run_id: Unique run identifier.
    @param scenario_id: Scenario identifier associated with the run.
    @param created_at: ISO-8601 timestamp for run creation.
    @param description: Optional human-readable run description.
    @param selected_component: Component selected for prediction and UI focus.
    @param total_usages: Configured total usage count for the run.
    @param usage_step: Configured visible timeline interval.
    @param config: Full simulation configuration persisted for reloads.
    @return: None.
    """
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
    usage_count: float,
    timestamp: str,
    drivers: dict,
    phase1_output: dict,
) -> int:
    """Persist one simulation step and all related component details.

    @param run_id: Run identifier for the telemetry record.
    @param scenario_id: Scenario identifier for the telemetry record.
    @param step_index: Timeline index of the step.
    @param usage_count: Accumulated usage represented by the step.
    @param timestamp: ISO-8601 timestamp for the step.
    @param drivers: Operating drivers applied to the step.
    @param phase1_output: Raw Phase 1 output to store and decompose.
    @return: Generated telemetry record identifier.
    """
    with _connect() as connection:
        record_id = _insert_simulation_step(
            connection=connection,
            run_id=run_id,
            scenario_id=scenario_id,
            step_index=step_index,
            usage_count=usage_count,
            timestamp=timestamp,
            drivers=drivers,
            phase1_output=phase1_output,
        )
        connection.commit()
    return record_id


def save_simulation_steps(steps: list[dict]) -> list[int]:
    """Persist a batch of simulation steps in one transaction.

    @param steps: Ordered step dictionaries containing telemetry and Phase 1 output.
    @return: Generated telemetry record identifiers in insertion order.
    """
    if not steps:
        return []

    record_ids = []
    with _connect() as connection:
        for step in steps:
            record_ids.append(
                _insert_simulation_step(
                    connection=connection,
                    run_id=step["run_id"],
                    scenario_id=step["scenario_id"],
                    step_index=step["step_index"],
                    usage_count=step["usage_count"],
                    timestamp=step["timestamp"],
                    drivers=step["drivers"],
                    phase1_output=step["phase1_output"],
                )
            )
        connection.commit()
    return record_ids


def _insert_simulation_step(
    connection: sqlite3.Connection,
    run_id: str,
    scenario_id: str,
    step_index: int,
    usage_count: float,
    timestamp: str,
    drivers: dict,
    phase1_output: dict,
) -> int:
    """Insert one telemetry record and decompose nested component data.

    @param connection: Open SQLite connection owned by the caller transaction.
    @param run_id: Run identifier for the telemetry record.
    @param scenario_id: Scenario identifier for the telemetry record.
    @param step_index: Timeline index of the step.
    @param usage_count: Accumulated usage represented by the step.
    @param timestamp: ISO-8601 timestamp for the step.
    @param drivers: Operating drivers applied to the step.
    @param phase1_output: Raw Phase 1 output to store and decompose.
    @return: Generated telemetry record identifier.
    """
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO telemetry_records (
            run_id,
            scenario_id,
            step_index,
            usage_count,
            timestamp,
            raw_phase1_output
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            scenario_id,
            step_index,
            float(usage_count),
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
    """Persist one prediction result for a component.

    @param run_id: Run identifier that owns the prediction.
    @param component_id: Component identifier used for prediction lookup.
    @param created_at: ISO-8601 timestamp when the prediction was created.
    @param prediction: Prediction payload to serialize.
    @return: None.
    """
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
    """Persist ranked runtime messages for a run.

    @param run_id: Run identifier that owns the messages.
    @param messages: Candidate runtime messages generated from the timeline.
    @return: None.
    """
    messages = select_top_messages(messages)
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
    """List stored simulation runs with persisted configuration metadata.

    @return: Runs ordered from newest to oldest.
    """
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
    """Reconstruct component states for one telemetry record from normalized tables.

    @param connection: Open SQLite connection used for read queries.
    @param record_id: Telemetry record identifier.
    @return: Component map with health, damage, metrics, and alerts.
    """
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
    """Load run metadata needed for timeline reconstruction.

    @param connection: Open SQLite connection used for read queries.
    @param run_id: Run identifier to resolve.
    @return: Metadata dictionary, or None when the run is unknown.
    """
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
    """Reconstruct the full stored timeline for a run.

    @param run_id: Run identifier to retrieve.
    @return: Ordered timeline records with drivers and reconstructed components.
    """
    with _connect() as connection:
        run_metadata = _get_run_metadata(connection, run_id)
        if run_metadata is None:
            return []

        rows = connection.execute(
            """
            SELECT record_id, run_id, scenario_id, step_index, usage_count, timestamp
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
                    "usage_count": round(
                        float(row["usage_count"])
                        if row["usage_count"] is not None
                        else float(row["step_index"]) * usage_step,
                        6,
                    ),
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
    """Reconstruct the stored history for a single component.

    @param run_id: Run identifier to retrieve.
    @param component_id: Component identifier to filter.
    @return: Ordered component-specific timeline records.
    """
    with _connect() as connection:
        run_metadata = _get_run_metadata(connection, run_id)
        if run_metadata is None:
            return []

        rows = connection.execute(
            """
            SELECT
                telemetry_records.record_id,
                telemetry_records.run_id,
                telemetry_records.scenario_id,
                telemetry_records.step_index,
                telemetry_records.usage_count,
                telemetry_records.timestamp,
                driver_values.operational_load,
                driver_values.contamination,
                driver_values.humidity,
                driver_values.temperature_stress,
                driver_values.maintenance_level,
                component_states.subsystem,
                component_states.health_index,
                component_states.status
            FROM telemetry_records
            JOIN driver_values
                ON driver_values.record_id = telemetry_records.record_id
            JOIN component_states
                ON component_states.record_id = telemetry_records.record_id
                AND component_states.component_id = ?
            WHERE telemetry_records.run_id = ?
            ORDER BY telemetry_records.step_index ASC
            """,
            (component_id, run_id),
        ).fetchall()

        timeline = []
        usage_step = float(run_metadata["usage_step"] or 1.0)
        for row in rows:
            metric_rows = connection.execute(
                """
                SELECT metric_name, metric_value
                FROM component_metrics
                WHERE record_id = ? AND component_id = ?
                ORDER BY metric_name ASC
                """,
                (row["record_id"], component_id),
            ).fetchall()
            damage_rows = connection.execute(
                """
                SELECT damage_name, damage_value
                FROM component_damage
                WHERE record_id = ? AND component_id = ?
                ORDER BY damage_name ASC
                """,
                (row["record_id"], component_id),
            ).fetchall()

            usage_count = (
                float(row["usage_count"])
                if row["usage_count"] is not None
                else float(row["step_index"]) * usage_step
            )
            timeline.append(
                {
                    "run_id": row["run_id"],
                    "scenario_id": row["scenario_id"],
                    "step_index": row["step_index"],
                    "usage_count": round(usage_count, 6),
                    "timestamp": row["timestamp"],
                    "drivers": {
                        "operational_load": float(row["operational_load"]),
                        "contamination": float(row["contamination"]),
                        "humidity": float(row["humidity"]),
                        "temperature_stress": float(row["temperature_stress"]),
                        "maintenance_level": float(row["maintenance_level"]),
                    },
                    "components": {
                        component_id: {
                            "component": component_id,
                            "subsystem": row["subsystem"],
                            "health_index": float(row["health_index"]),
                            "status": row["status"],
                            "damage": {
                                damage_row["damage_name"]: float(
                                    damage_row["damage_value"]
                                )
                                for damage_row in damage_rows
                            },
                            "metrics": {
                                metric_row["metric_name"]: float(
                                    metric_row["metric_value"]
                                )
                                for metric_row in metric_rows
                            },
                            "alerts": [],
                        }
                    },
                }
            )

    return timeline


def get_recent_history(scenario_name: str, window_steps: int) -> list[dict]:
    """Load the latest stored records for a scenario in chronological order.

    @param scenario_name: Scenario identifier used by the agent historian adapter.
    @param window_steps: Maximum number of recent records to return.
    @return: Recent timeline records ordered oldest to newest.
    """
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT
                telemetry_records.record_id,
                telemetry_records.run_id,
                telemetry_records.scenario_id,
                telemetry_records.step_index,
                telemetry_records.usage_count,
                telemetry_records.timestamp,
                runs.usage_step
            FROM telemetry_records
            JOIN runs ON runs.run_id = telemetry_records.run_id
            WHERE telemetry_records.scenario_id = ?
            ORDER BY telemetry_records.timestamp DESC, telemetry_records.step_index DESC
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
                    "usage_count": round(
                        float(row["usage_count"])
                        if row["usage_count"] is not None
                        else float(row["step_index"])
                        * float(row["usage_step"] or 1.0),
                        6,
                    ),
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
    """Return the raw persisted Phase 1 output for a specific timeline step.

    @param run_id: Run identifier to retrieve.
    @param step_index: Step index within the run timeline.
    @return: Raw Phase 1 output, or None when the record does not exist.
    """
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
    """Load and rank persisted runtime messages for a run.

    @param run_id: Run identifier that owns the messages.
    @return: Ranked messages suitable for the dashboard.
    """
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

    messages = [
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
    return select_top_messages(messages)


def get_latest_prediction(run_id: str, component_id: str) -> dict | None:
    """Load the most recent prediction for a component in a run.

    @param run_id: Run identifier that owns the prediction.
    @param component_id: Component identifier used for prediction lookup.
    @return: Prediction payload, or None when no prediction is stored.
    """
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
    """Delete all historian data while preserving the schema.

    @return: None.
    """
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
