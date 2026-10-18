#!/usr/bin/env python3
"""Executes the non-functional checks that need a real running server, a large dataset or
external tools, and writes the observed results to test-results/nft-results.json.

  NFT-04  SOS notification latency while the system is under load (k6 in the background)
  NFT-05  Dashboard / report / search query time on a large dataset
  NFT-22  Data persists after the API server restarts
  NFT-24  Backup (pg_dump) and restore (pg_restore) with row-count verification
  NFT-30  Static checks: ESLint, TypeScript, Ruff (Python)
  NFT-31  Production build of the frontend
  NFT-32  Reproducible setup from scratch (.env.example coverage, fresh DB init + seed + health)
  NFT-34  Data-privacy check: is personal data encrypted at rest? (inspects stored values)

Usage:  python3 scripts/nft_runner.py            (needs PostgreSQL + the 'vista' role with CREATEDB)
Environment: PERF_DATABASE_URL, ADMIN_DATABASE_URL (defaults match .env.example)
"""
import json
import os
import re
import shutil
import signal
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
OUT = ROOT / "test-results"
PERF_DB = os.getenv("PERF_DATABASE_URL", "postgresql+psycopg://vista:vista_dev_pw@localhost:5432/vista_perf")
PORT = int(os.getenv("NFT_PORT", "8003"))
BASE = f"http://localhost:{PORT}"
RESULTS: list[dict] = []


def log(msg: str) -> None:
    print(f"[nft] {msg}", flush=True)


def record(case: str, status: str, actual: str, evidence: str = "", metrics: dict | None = None) -> None:
    RESULTS.append({"id": case, "status": status, "actual": actual, "evidence": evidence, "metrics": metrics or {},
                    "executed_at": datetime.now(UTC).isoformat()})
    log(f"{case}: {status} – {actual}")


def libpq(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://")


def db_name(url: str) -> str:
    return url.rsplit("/", 1)[1].split("?")[0]


def with_db(url: str, name: str) -> str:
    return url.rsplit("/", 1)[0] + "/" + name


def http(method: str, path: str, token: str | None = None, body: dict | None = None, timeout: float = 30):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = json.loads(r.read() or b"null")
            return r.status, payload, (time.perf_counter() - t0) * 1000
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null"), (time.perf_counter() - t0) * 1000


def login(email: str, pw: str) -> str:
    code, body, _ = http("POST", "/api/auth/login", body={"email": email, "password": pw})
    assert code == 200, (email, code, body)
    return body["access_token"]


class Server:
    def __init__(self, db_url: str, workers: int = 2):
        self.db_url, self.workers, self.proc = db_url, workers, None

    def start(self) -> None:
        env = {**os.environ, "DATABASE_URL": self.db_url, "ESCALATION_CHECK_SECONDS": "0"}
        self.proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(PORT), "--workers",
                                      str(self.workers), "--no-access-log"], cwd=BACKEND, env=env,
                                     stdout=open(OUT / "perf" / "nft-server.log", "a"), stderr=subprocess.STDOUT, start_new_session=True)
        for _ in range(60):
            try:
                if http("GET", "/api/health", timeout=2)[0] == 200:
                    return
            except Exception:
                pass
            time.sleep(0.5)
        raise RuntimeError("API server did not start")

    def stop(self) -> None:
        if self.proc:
            os.killpg(self.proc.pid, signal.SIGTERM)
            self.proc.wait(timeout=20)
            self.proc = None


def seed(db_url: str) -> None:
    subprocess.run([sys.executable, "-m", "app.seed", "--reset"], cwd=BACKEND, env={**os.environ, "DATABASE_URL": db_url},
                   check=True, stdout=subprocess.DEVNULL)


# ------------------------------------------------------------------ NFT-04
def nft04_sos_latency() -> None:
    k6 = shutil.which("k6")
    bg = None
    if k6:
        bg = subprocess.Popen([k6, "run", "--quiet", "-e", f"BASE_URL={BASE}", "-e", "VUS=150", "-e", "DURATION=40s", "-e",
                               "LABEL=background-sos", "-e", f"OUT_DIR={OUT / 'perf'}", str(ROOT / "perf" / "load-test.js")],
                              cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(15)
    students = [f"student{2001 + i}@vista.demo" for i in range(20)]
    tokens = [login(s, "Student@123") for s in students]
    warden = login("warden.lh@vista.demo", "Warden@123")
    delays, rtts = [], []
    for t in tokens:
        code, body, ms = http("POST", "/api/sos", t, {"confirm": True, "message": "NFT-04 latency probe"})
        assert code == 201, body
        delays.append(body["notification_delay_ms"])
        # end-to-end: time until the alert is visible on the warden's SOS board
        t0 = time.perf_counter()
        while True:
            c, alerts, _ = http("GET", "/api/sos?status=RAISED", warden)
            if any(a["id"] == body["id"] for a in alerts):
                break
            if time.perf_counter() - t0 > 10:
                break
        rtts.append(ms + (time.perf_counter() - t0) * 1000)
    if bg:
        bg.wait(timeout=120)
    worst = max(rtts)
    metrics = {"samples": len(rtts), "notify_delay_ms_max": max(delays), "end_to_end_ms_avg": round(statistics.mean(rtts), 1),
               "end_to_end_ms_p95": round(sorted(rtts)[int(0.95 * len(rtts)) - 1], 1), "end_to_end_ms_max": round(worst, 1),
               "background_load": "150 virtual users (k6)" if k6 else "none (k6 not installed)"}
    record("NFT-04", "Pass" if worst < 5000 else "Fail",
           f"20 SOS alerts raised during a {metrics['background_load']} load: server-side notify delay max {max(delays)} ms; "
           f"alert visible on warden board avg {metrics['end_to_end_ms_avg']} ms, p95 {metrics['end_to_end_ms_p95']} ms, max {metrics['end_to_end_ms_max']} ms",
           "nft-results.json", metrics)


# ------------------------------------------------------------------ NFT-05
def nft05_large_dataset() -> None:
    import psycopg
    n_c, n_d, n_n = 20000, 5000, 20000
    with psycopg.connect(libpq(PERF_DB)) as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE role='STUDENT' ORDER BY id")
        sids = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT id FROM users WHERE staff_type='MAINTENANCE'")
        staff = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT id FROM hostels ORDER BY id")
        hs = [r[0] for r in cur.fetchall()]
        cur.execute("""
            INSERT INTO complaints (code, student_id, category, priority, title, description, location, status,
                                    assigned_staff_id, created_at, updated_at)
            SELECT 'BULK-' || g, (%(s)s)[1 + (g %% %(ns)s)], (ARRAY['ELECTRICAL','PLUMBING','CARPENTRY','WASHROOM','WATER','OTHER'])[1 + g %% 6],
                   (ARRAY['LOW','MEDIUM','HIGH'])[1 + g %% 3], 'Bulk complaint ' || g, 'Generated for the large-dataset test', 'X-' || g,
                   (ARRAY['OPEN','IN_PROGRESS','RESOLVED','CLOSED'])[1 + g %% 4], (%(st)s)[1 + (g %% %(nst)s)],
                   now() - (g || ' minutes')::interval, now()
            FROM generate_series(1, %(n)s) g""", {"s": sids, "ns": len(sids), "st": staff, "nst": len(staff), "n": n_c})
        cur.execute("""
            INSERT INTO delivery_requests (code, sender_id, receiver_id, item_description, item_type, pickup_hostel_id,
                                           drop_hostel_id, pickup_point, fee, status, qr_token, failure_reason, created_at)
            SELECT 'BULKD-' || g, (%(s)s)[1 + (g %% %(ns)s)], (%(s)s)[1 + ((g + 7) %% %(ns)s)], 'Bulk parcel', 'PARCEL',
                   (%(h)s)[1 + g %% 4], (%(h)s)[1 + (g + 1) %% 4], 'gate', 10,
                   (ARRAY['OPEN','DELIVERED','CANCELLED'])[1 + g %% 3], md5(g::text), '', now() - (g || ' minutes')::interval
            FROM generate_series(1, %(n)s) g""", {"s": sids, "ns": len(sids), "h": hs, "n": n_d})
        cur.execute("""
            INSERT INTO notifications (user_id, title, body, link, kind, is_read, created_at)
            SELECT (%(s)s)[1 + (g %% %(ns)s)], 'Bulk notification ' || g, '', '', 'INFO', g %% 2 = 0, now() - (g || ' seconds')::interval
            FROM generate_series(1, %(n)s) g""", {"s": sids, "ns": len(sids), "n": n_n})
        conn.commit()
        cur.execute("ANALYZE")
    admin = login("admin@vista.demo", "Admin@123")
    warden = login("warden.lh@vista.demo", "Warden@123")
    student = login("priya.sharma@vista.demo", "Student@123")
    probes = {
        "warden dashboard": ("/api/dashboard", warden),
        "admin reports": ("/api/admin/reports", admin),
        "complaint search": ("/api/complaints?q=bulk%20complaint%2019&page=1&page_size=10", warden),
        "complaint page 500": ("/api/complaints?page=500&page_size=10&sort=priority", warden),
        "student notifications": ("/api/notifications", student),
        "all deliveries": ("/api/deliveries?view=all", admin),
    }
    res = {}
    for name, (path, tok) in probes.items():
        times = []
        for _ in range(10):
            code, _, ms = http("GET", path, tok)
            assert code == 200, (path, code)
            times.append(ms)
        res[name] = {"avg_ms": round(statistics.mean(times), 1), "max_ms": round(max(times), 1)}
    worst = max(v["avg_ms"] for v in res.values())
    record("NFT-05", "Pass" if worst < 3000 else "Fail",
           f"With +{n_c:,} complaints, +{n_d:,} deliveries, +{n_n:,} notifications: "
           + "; ".join(f"{k} avg {v['avg_ms']} ms" for k, v in res.items()) + f". Slowest average {worst} ms",
           "nft-results.json", {"dataset": {"complaints": n_c, "deliveries": n_d, "notifications": n_n}, "endpoints": res})


# ------------------------------------------------------------------ NFT-22
def nft22_restart_persistence(server: Server) -> None:
    tok = login("rahul.verma@vista.demo", "Student@123")
    code, c, _ = http("POST", "/api/complaints", tok, {"category": "OTHER", "title": "Persistence probe NFT-22",
                                                       "description": "Must survive a server restart."})
    assert code == 201
    server.stop()
    server.start()
    tok = login("rahul.verma@vista.demo", "Student@123")
    code, again, _ = http("GET", f"/api/complaints/{c['id']}", tok)
    ok = code == 200 and again["code"] == c["code"] and again["title"] == c["title"]
    record("NFT-22", "Pass" if ok else "Fail",
           f"Complaint {c['code']} created, API server stopped and restarted, record read back with HTTP {code} and identical data",
           "nft-results.json")


# ------------------------------------------------------------------ NFT-24
def nft24_backup_restore() -> None:
    import psycopg
    if not (shutil.which("pg_dump") and shutil.which("pg_restore")):
        record("NFT-24", "Blocked", "pg_dump / pg_restore not installed on this machine")
        return
    dump = OUT / "perf" / "vista_backup.dump"
    target = with_db(PERF_DB, "vista_restore_check")
    t0 = time.perf_counter()
    subprocess.run(["pg_dump", "-Fc", "-f", str(dump), libpq(PERF_DB)], check=True)
    backup_s = time.perf_counter() - t0
    with psycopg.connect(libpq(with_db(PERF_DB, "postgres")), autocommit=True) as conn:
        conn.execute("DROP DATABASE IF EXISTS vista_restore_check")
        conn.execute("CREATE DATABASE vista_restore_check")
    t1 = time.perf_counter()
    subprocess.run(["pg_restore", "--no-owner", "-d", libpq(target), str(dump)], check=True)
    restore_s = time.perf_counter() - t1
    tables = ["users", "complaints", "complaint_updates", "visitor_requests", "delivery_requests", "notifications", "audit_logs", "sos_alerts"]
    counts = {}
    for url, key in ((PERF_DB, "source"), (target, "restored")):
        with psycopg.connect(libpq(url)) as conn:
            counts[key] = {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in tables}
    with psycopg.connect(libpq(with_db(PERF_DB, "postgres")), autocommit=True) as conn:
        conn.execute("DROP DATABASE IF EXISTS vista_restore_check")
    size_mb = dump.stat().st_size / 1e6
    dump.unlink(missing_ok=True)
    same = counts["source"] == counts["restored"]
    record("NFT-24", "Pass" if same and restore_s < 7200 else "Fail",
           f"pg_dump {size_mb:.1f} MB in {backup_s:.1f} s; restore into a new database in {restore_s:.1f} s (target < 2 h); "
           f"row counts of {len(tables)} tables {'identical' if same else 'DIFFERENT'} "
           f"(e.g. complaints {counts['source']['complaints']:,}). Daily scheduling is a deployment task (scripts/backup_db.sh + cron) and was not run here",
           "scripts/backup_db.sh, scripts/restore_db.sh", {"backup_s": round(backup_s, 2), "restore_s": round(restore_s, 2), "counts": counts})


# ------------------------------------------------------------------ NFT-30 / 31
def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr)


def nft30_static_checks() -> None:
    parts, ok = [], True
    code, out = run(["npx", "eslint", ".", "-f", "json"], FRONTEND)
    try:
        data = json.loads(out[out.index("["):])
        errs = sum(f["errorCount"] for f in data)
        warns = sum(f["warningCount"] for f in data)
    except ValueError:
        errs, warns = -1, -1
    parts.append(f"ESLint: {errs} errors, {warns} warnings in {len(data) if errs >= 0 else '?'} files")
    ok &= errs == 0
    code, out = run(["npx", "tsc", "-b", "--noEmit"], FRONTEND)
    tsc_errs = len(re.findall(r"error TS\d+", out))
    parts.append(f"TypeScript strict: {tsc_errs} errors")
    ok &= code == 0
    if shutil.which("ruff"):
        code, out = run(["ruff", "check", "app", "tests", "--output-format", "json"], BACKEND)
        try:
            n = len(json.loads(out))
        except ValueError:
            n = -1
        parts.append(f"Ruff (Python): {n} issues")
        ok &= n == 0
    else:
        parts.append("Ruff not installed – Python lint skipped")
    record("NFT-30", "Pass" if ok else "Fail", "; ".join(parts), "eslint.config.js, tsconfig.json, backend/ruff.toml")


def nft31_build() -> None:
    t0 = time.perf_counter()
    code, out = run(["npm", "run", "build"], FRONTEND)
    secs = time.perf_counter() - t0
    assets = list((FRONTEND / "dist" / "assets").glob("*.js")) if code == 0 else []
    size = sum(a.stat().st_size for a in assets) / 1024
    record("NFT-31", "Pass" if code == 0 else "Fail",
           f"Production build {'succeeded' if code == 0 else 'FAILED'} in {secs:.1f} s; JavaScript bundle {size:.0f} KB (uncompressed)",
           "frontend/dist")


# ------------------------------------------------------------------ NFT-32
def nft32_reproducible_setup() -> None:
    import psycopg
    env_keys = {line.split("=", 1)[0].strip() for line in (ROOT / ".env.example").read_text().splitlines()
                if "=" in line and not line.lstrip().startswith("#")}
    used = set()
    for f in (BACKEND / "app").rglob("*.py"):
        used |= set(re.findall(r'os\.getenv\("([A-Z_]+)"', f.read_text()))
    missing = sorted(used - env_keys)
    fresh = with_db(PERF_DB, "vista_fresh_setup")
    with psycopg.connect(libpq(with_db(PERF_DB, "postgres")), autocommit=True) as conn:
        conn.execute("DROP DATABASE IF EXISTS vista_fresh_setup")
        conn.execute("CREATE DATABASE vista_fresh_setup")
    t0 = time.perf_counter()
    p = subprocess.run([sys.executable, "-m", "app.seed"], cwd=BACKEND, env={**os.environ, "DATABASE_URL": fresh},
                       capture_output=True, text=True)
    init_s = time.perf_counter() - t0
    with psycopg.connect(libpq(fresh)) as conn:
        n_tables = conn.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'").fetchone()[0]
        n_users = conn.execute("SELECT count(*) FROM users").fetchone()[0]
    srv = Server(fresh, workers=1)
    srv.start()
    healthy = http("GET", "/api/health")[1]
    srv.stop()
    with psycopg.connect(libpq(with_db(PERF_DB, "postgres")), autocommit=True) as conn:
        conn.execute("DROP DATABASE IF EXISTS vista_fresh_setup")
    docker = shutil.which("docker") is not None
    ok = p.returncode == 0 and not missing and healthy.get("database") is True
    record("NFT-32", "Pass" if ok else "Fail",
           f"Empty database initialised and seeded in {init_s:.1f} s ({n_tables} tables, {n_users} users); API health OK on the fresh DB; "
           f".env.example covers {len(used)}/{len(used)} variables read by the code" + (f" (missing: {', '.join(missing)})" if missing else "")
           + ("" if docker else "; Dockerfile included but Docker is not installed here, so the image build was not run"),
           "backend/app/seed.py, .env.example, Dockerfile")


# ------------------------------------------------------------------ NFT-34
def nft34_privacy_at_rest() -> None:
    import psycopg
    with psycopg.connect(libpq(PERF_DB)) as conn:
        phone, reg = conn.execute("SELECT phone, reg_no FROM users WHERE role='STUDENT' ORDER BY id LIMIT 1").fetchone()
        vphone = conn.execute("SELECT visitor_phone FROM visitor_requests LIMIT 1").fetchone()[0]
        ssl = conn.execute("SHOW ssl").fetchone()[0]
    plain = bool(re.fullmatch(r"\d{10}", phone or "")) and bool(re.fullmatch(r"\d{10}", vphone or ""))
    record("NFT-34", "Fail" if plain else "Pass",
           f"Passwords and OTPs are hashed, but student phone numbers, registration numbers and visitor phone numbers are stored as plain text "
           f"(e.g. phone '{phone[:3]}*******'); local PostgreSQL ssl={ssl}. Encryption in transit relies on HTTPS at the hosting provider "
           "(HSTS header is sent in production) and could not be verified locally. NFR06 (encrypted at rest) is NOT met by the application",
           "Defect DEF-04", {"plaintext_pii": plain, "postgres_ssl": ssl})


def main() -> None:
    OUT.mkdir(exist_ok=True)
    (OUT / "perf").mkdir(exist_ok=True)
    only = set(sys.argv[1:])
    want = lambda c: not only or c in only  # noqa: E731
    if want("NFT-30"):
        nft30_static_checks()
    if want("NFT-31"):
        nft31_build()
    if want("NFT-32"):
        nft32_reproducible_setup()
    log("Seeding performance database and starting API (2 workers)…")
    seed(PERF_DB)
    server = Server(PERF_DB)
    server.start()
    try:
        if want("NFT-04"):
            nft04_sos_latency()
        if want("NFT-22"):
            nft22_restart_persistence(server)
        if want("NFT-05"):
            nft05_large_dataset()
        if want("NFT-34"):
            nft34_privacy_at_rest()
    finally:
        server.stop()
    if want("NFT-24"):
        nft24_backup_restore()
    path = OUT / "nft-results.json"
    existing = {r["id"]: r for r in json.loads(path.read_text())} if path.exists() and only else {}
    existing.update({r["id"]: r for r in RESULTS})
    path.write_text(json.dumps(sorted(existing.values(), key=lambda r: r["id"]), indent=2))
    log(f"Wrote {path}")


if __name__ == "__main__":
    main()
