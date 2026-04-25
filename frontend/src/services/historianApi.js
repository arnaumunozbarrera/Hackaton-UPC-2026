import initSqlJs from 'sql.js';
import wasmUrl from 'sql.js/dist/sql-wasm.wasm?url';

const DB_STORAGE_KEY = 'digital_twin_sqlite_db_v2';
let dbPromise = null;

function uint8ToBase64(bytes) {
  let binary = '';
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode.apply(null, chunk);
  }
  return btoa(binary);
}

function base64ToUint8(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

function persistDatabase(db) {
  const exported = db.export();
  localStorage.setItem(DB_STORAGE_KEY, uint8ToBase64(exported));
}

function createSchema(db) {
  db.run(`
    CREATE TABLE IF NOT EXISTS runs (
      run_id TEXT PRIMARY KEY,
      created_at TEXT NOT NULL,
      component_id TEXT NOT NULL,
      config_json TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS timeline_points (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      run_id TEXT NOT NULL,
      component_id TEXT NOT NULL,
      timestamp TEXT NOT NULL,
      t_hours REAL NOT NULL,
      health REAL NOT NULL,
      damage REAL NOT NULL,
      status TEXT NOT NULL,
      drivers_json TEXT NOT NULL,
      raw_json TEXT NOT NULL,
      FOREIGN KEY(run_id) REFERENCES runs(run_id)
    );

    CREATE TABLE IF NOT EXISTS model_snapshots (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      created_at TEXT NOT NULL,
      model_state_json TEXT NOT NULL
    );
  `);
}

async function getDb() {
  if (dbPromise) return dbPromise;

  dbPromise = initSqlJs({ locateFile: () => wasmUrl }).then((SQL) => {
    const stored = localStorage.getItem(DB_STORAGE_KEY);
    const db = stored ? new SQL.Database(base64ToUint8(stored)) : new SQL.Database();
    createSchema(db);
    persistDatabase(db);
    return db;
  });

  return dbPromise;
}

export async function createRun({ componentId, config }) {
  const db = await getDb();
  const runId = `run_${new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 14)}_${Math.random().toString(16).slice(2, 8)}`;

  db.run(
    'INSERT INTO runs (run_id, created_at, component_id, config_json) VALUES (?, ?, ?, ?)',
    [runId, new Date().toISOString(), componentId, JSON.stringify(config)]
  );
  persistDatabase(db);

  return runId;
}

export async function saveTimelinePoint(point) {
  const db = await getDb();
  db.run(
    `INSERT INTO timeline_points
      (run_id, component_id, timestamp, t_hours, health, damage, status, drivers_json, raw_json)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    [
      point.run_id,
      point.component_id,
      point.timestamp,
      point.t,
      point.health,
      point.damage,
      point.status,
      JSON.stringify(point.drivers),
      JSON.stringify(point)
    ]
  );
  persistDatabase(db);
}

export async function saveModelSnapshot(modelState) {
  const db = await getDb();
  db.run(
    'INSERT INTO model_snapshots (created_at, model_state_json) VALUES (?, ?)',
    [new Date().toISOString(), JSON.stringify(modelState)]
  );
  persistDatabase(db);
}

export async function getRunTimeline(runId, componentId) {
  const db = await getDb();
  const result = db.exec(
    `SELECT raw_json FROM timeline_points
     WHERE run_id = '${runId}' AND component_id = '${componentId}'
     ORDER BY t_hours ASC`
  );

  if (!result.length) return [];
  return result[0].values.map(([rawJson]) => JSON.parse(rawJson));
}

export async function getHistorianSummary() {
  const db = await getDb();
  const runsResult = db.exec('SELECT COUNT(*) AS count FROM runs');
  const pointsResult = db.exec('SELECT COUNT(*) AS count FROM timeline_points');
  const lastRunResult = db.exec('SELECT run_id, component_id, created_at FROM runs ORDER BY created_at DESC LIMIT 1');

  return {
    runs: runsResult[0]?.values[0]?.[0] || 0,
    points: pointsResult[0]?.values[0]?.[0] || 0,
    lastRun: lastRunResult[0]?.values[0]
      ? {
          run_id: lastRunResult[0].values[0][0],
          component_id: lastRunResult[0].values[0][1],
          created_at: lastRunResult[0].values[0][2]
        }
      : null
  };
}

export async function resetHistorian() {
  localStorage.removeItem(DB_STORAGE_KEY);
  dbPromise = null;
  await getDb();
}
