#!/usr/bin/env python3
"""Merge the outputs of every executed test tool into one machine-readable result set.

Inputs (all produced by actually running the suites – see scripts/run_all_tests.sh):
  test-results/pytest-results.json, pytest-actuals.json   backend API / security tests
  test-results/vitest-results.json                        frontend unit tests
  test-results/playwright-results.json                    browser end-to-end tests
  test-results/perf/k6-*.json                             load tests
  test-results/nft-results.json                           non-functional runner
Outputs:
  test-results/test-results.json   per-test and per-case results + summary
  test-results/test-results.xml    JUnit XML (one <testsuite> per tool, plus case-level suites)
"""
import json
import platform
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_catalog import FUNCTIONAL, NONFUNCTIONAL, NOT_RUN  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TR = ROOT / "test-results"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def load(name: str, default=None):
    p = TR / name
    return json.loads(p.read_text()) if p.exists() else default


def version(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout.strip().splitlines()[0]
    except Exception:
        return "not available"


# ------------------------------------------------------------------ gather raw results
def pytest_tests() -> list[dict]:
    d = load("pytest-results.json", {"results": []})
    return [{"tool": "pytest", "id": r["nodeid"], "cases": r["cases"], "status": r["outcome"], "duration_s": r["duration_s"],
             "project": "api", "message": r["message"], "actual": ""} for r in d["results"]]


def vitest_tests() -> list[dict]:
    d = load("vitest-results.json")
    out = []
    if not d:
        return out
    for f in d.get("testResults", []):
        for a in f.get("assertionResults", []):
            out.append({"tool": "vitest", "id": f"{Path(f['name']).name} > {a['fullName']}", "cases": [], "status": a["status"],
                        "duration_s": round((a.get("duration") or 0) / 1000, 3), "project": "jsdom", "message": "; ".join(a.get("failureMessages", []))[:300],
                        "actual": ""})
    return out


def playwright_tests() -> list[dict]:
    d = load("playwright-results.json")
    out = []
    if not d:
        return out

    def walk(suite, prefix=""):
        for sp in suite.get("specs", []):
            for t in sp["tests"]:
                r = t["results"][-1] if t["results"] else {}
                ann = r.get("annotations") or t.get("annotations") or []
                msg = ANSI.sub("", (r.get("error") or {}).get("message", ""))
                status = r.get("status", "skipped")
                if status != "passed" and "Executable doesn't exist" in msg:
                    status = "blocked"
                cases = [a["description"] for a in ann if a["type"] == "case"]
                if not cases and t["projectName"].startswith(("firefox", "webkit")):  # browser never launched
                    cases = ["NFT-27" if t["projectName"].startswith("firefox") else "NFT-28"]
                out.append({"tool": "playwright", "id": f"[{t['projectName']}] {sp['file']} › {sp['title']}",
                            "cases": cases, "status": status,
                            "duration_s": round(r.get("duration", 0) / 1000, 2), "project": t["projectName"],
                            "message": msg.splitlines()[0][:300] if msg else "",
                            "actual": " | ".join(a["description"] for a in ann if a["type"] == "actual")})
        for s in suite.get("suites", []):
            walk(s)

    for s in d.get("suites", []):
        walk(s)
    return out


def k6_runs() -> dict:
    runs = {}
    for p in sorted((TR / "perf").glob("k6-*.json")):
        d = json.loads(p.read_text())
        runs[d["label"]] = d
    return runs


# ------------------------------------------------------------------ evaluate cases
def combine(tests: list[dict]) -> str:
    st = {t["status"] for t in tests}
    if not tests:
        return "Not Run"
    if "failed" in st or "timedOut" in st or "interrupted" in st:
        return "Fail"
    if st == {"blocked"}:
        return "Blocked"
    if st <= {"passed"}:
        return "Pass"
    if "blocked" in st:
        return "Blocked"
    return "Not Run"


def actual_for(case: str, tests: list[dict], api_actuals: dict) -> str:
    parts = []
    api = api_actuals.get(case, [])
    if api:
        parts.append("API: " + "; ".join(dict.fromkeys(api)))
    ui = [t["actual"] for t in tests if t["tool"] == "playwright" and t["actual"]]
    for u in dict.fromkeys(ui):
        parts.append(u if u.startswith("UI:") else "UI: " + u)
    failed = [t for t in tests if t["status"] in ("failed", "timedOut")]
    for f in failed:
        parts.append(f"FAILED {f['id'].split('::')[-1][:60]}: {f['message'][:160]}")
    blocked = [t for t in tests if t["status"] == "blocked"]
    for b in blocked:
        parts.append(f"Not executed – {b['project']}: {b['message'][:140]}")
    return "\n".join(parts) if parts else "No automated result recorded"


def defects_for(case: str, register: list[dict]) -> str:
    ids = [f"{d['id']}{' (fixed)' if d['status'] == 'Fixed' else ''}" for d in register if re.search(rf"\b{case}\b", d["found_by"])]
    return ", ".join(ids)


def main() -> None:
    api_actuals = load("pytest-actuals.json", {})
    nft = {r["id"]: r for r in load("nft-results.json", [])}
    register = json.loads((ROOT / "scripts" / "defect_register.json").read_text())
    tests = pytest_tests() + vitest_tests() + playwright_tests()
    k6 = k6_runs()

    by_case: dict[str, list[dict]] = {}
    for t in tests:
        for c in t["cases"]:
            by_case.setdefault(c, []).append(t)

    functional = []
    for cid, module, desc, pre, steps, data, expected, frs in FUNCTIONAL:
        ts = by_case.get(cid, [])
        tools = sorted({("API (pytest)" if t["tool"] == "pytest" else "UI (Playwright)") for t in ts})
        functional.append({"id": cid, "module": module, "description": desc, "preconditions": pre, "steps": steps, "data": data,
                           "expected": expected, "requirements": frs, "status": combine(ts), "actual": actual_for(cid, ts, api_actuals),
                           "automated_by": tools, "linked_tests": [t["id"] for t in ts], "defects": defects_for(cid, register),
                           "execution": "Executed (automated)" if ts and combine(ts) in ("Pass", "Fail") else "Not executed"})

    def k6_line(label):
        r = k6.get(label)
        if not r:
            return None
        lat = r["latency_ms"]
        return (f"{r['vus']} users, {r['requests']:,} requests, {r['throughput_rps']} req/s, failed {r['http_req_failed_rate'] * 100:.2f} %, "
                f"avg {lat['avg']:.0f} ms, p95 {lat['p(95)']:.0f} ms, max {lat['max']:.0f} ms")

    nonfunctional = []
    for cid, attr, desc, metric, steps, expected, source, req in NONFUNCTIONAL:
        ts = by_case.get(cid, [])
        status, actual, evidence = None, None, ""
        if cid in NOT_RUN:
            status, actual = "Not Run", "Not executed: " + NOT_RUN[cid]
        elif cid == "NFT-01" and "normal-50vus" in k6:
            r = k6["normal-50vus"]
            status = "Pass" if r["latency_ms"]["avg"] < 3000 and r["http_req_failed_rate"] < 0.005 else "Fail"
            actual, evidence = k6_line("normal-50vus"), "k6-normal-50vus.json"
        elif cid == "NFT-02" and "peak-300vus" in k6:
            r = k6["peak-300vus"]
            status = "Pass" if r["latency_ms"]["avg"] < 3000 and r["http_req_failed_rate"] < 0.005 else "Fail"
            actual, evidence = k6_line("peak-300vus") + " (after fix of DEF-03; first run: 0.82 % failed, p99 32 s)", "k6-peak-300vus.json"
        elif cid == "NFT-06" and {"normal-50vus", "peak-300vus"} <= set(k6):
            p50, p300 = k6["normal-50vus"]["latency_ms"]["p(95)"], k6["peak-300vus"]["latency_ms"]["p(95)"]
            mid = k6.get("peak-150vus", {}).get("latency_ms", {}).get("p(95)")
            status = "Pass" if p300 <= 2 * p50 else "Fail"
            actual = (f"p95: {p50:.0f} ms (50 users) → {mid:.0f} ms (150) → {p300:.0f} ms (300) = {p300 / p50:.1f}x; throughput "
                      f"{k6['normal-50vus']['throughput_rps']} → {k6.get('peak-150vus', {}).get('throughput_rps', '?')} → {k6['peak-300vus']['throughput_rps']} req/s. "
                      "CPU-bound on a 2-vCPU host shared with PostgreSQL and the load generator")
            evidence = "k6-*.json"
        elif cid == "NFT-25" and k6:
            main_runs = [r for k, r in k6.items() if k in ("normal-50vus", "peak-150vus", "peak-300vus")]
            reqs = sum(r["requests"] for r in main_runs)
            failed = sum(r["requests"] * r["http_req_failed_rate"] for r in main_runs)
            rate = failed / reqs if reqs else 1
            status = "Pass" if rate < 0.005 else "Fail"
            actual = f"{int(failed)} failed of {reqs:,} requests across {len(main_runs)} load runs = {rate * 100:.3f} %"
            evidence = "k6-*.json"
        elif cid in nft:
            status, actual, evidence = nft[cid]["status"], nft[cid]["actual"], nft[cid]["evidence"]
        elif cid == "NFT-26":
            chrome = [t for t in tests if t["tool"] == "playwright" and t["project"] == "chromium-desktop"]
            status = combine(chrome)
            npass = sum(t["status"] == "passed" for t in chrome)
            actual = f"Chromium {version(['/opt/pw-browsers/chromium-1194/chrome-linux/chrome', '--version']).replace('Chromium ', '') or ''}: {npass}/{len(chrome)} desktop E2E tests passed"
            evidence = "playwright-results.json"
        elif cid in ("NFT-27", "NFT-28"):
            status = combine(ts)
            actual = actual_for(cid, ts, {}) if ts else "Not executed – run with ALL_BROWSERS=1"
            evidence = "playwright-results.json"
        else:
            status = combine(ts)
            actual = actual_for(cid, ts, api_actuals)
            evidence = "pytest-results.json" if any(t["tool"] == "pytest" for t in ts) else "playwright-results.json"
        if status == "Blocked" and not actual.startswith("Not executed"):
            actual = "Not executed (blocked): " + actual
        nonfunctional.append({"id": cid, "attribute": attr, "description": desc, "criteria": metric, "steps": steps, "expected": expected,
                              "target_source": source, "requirements": req, "status": status or "Not Run", "actual": actual or "No result",
                              "evidence": evidence, "defects": defects_for(cid, register), "linked_tests": [t["id"] for t in ts],
                              "execution": "Executed" if status in ("Pass", "Fail") else "Not executed"})

    def summary(rows):
        s = {k: sum(r["status"] == k for r in rows) for k in ("Pass", "Fail", "Blocked", "Not Run")}
        executed = s["Pass"] + s["Fail"]
        return {"total": len(rows), "passed": s["Pass"], "failed": s["Fail"], "blocked": s["Blocked"], "not_run": s["Not Run"],
                "executed": executed, "pass_percentage": round(100 * s["Pass"] / executed, 1) if executed else None}

    tool_summary = {}
    for tool in ("pytest", "vitest", "playwright"):
        ts = [t for t in tests if t["tool"] == tool]
        tool_summary[tool] = {"total": len(ts), "passed": sum(t["status"] == "passed" for t in ts),
                              "failed": sum(t["status"] in ("failed", "timedOut") for t in ts),
                              "blocked": sum(t["status"] == "blocked" for t in ts), "skipped": sum(t["status"] == "skipped" for t in ts)}
    tool_summary["k6"] = {"runs": len(k6), "labels": sorted(k6)}
    tool_summary["nft_runner"] = {"checks": len(nft), "passed": sum(r["status"] == "Pass" for r in nft.values()),
                                  "failed": sum(r["status"] == "Fail" for r in nft.values())}

    env = {
        "os": f"{platform.system()} {platform.release()}", "cpu_count": __import__("os").cpu_count(), "python": platform.python_version(),
        "node": version(["node", "--version"]), "postgresql": version(["psql", "--version"]), "k6": version(["k6", "version"]),
        "chromium": version(["/opt/pw-browsers/chromium-1194/chrome-linux/chrome", "--version"]),
        "note": "All tests executed locally in a cloud Linux container (2 vCPU). The API, PostgreSQL and the load generator share the same machine.",
    }
    out = {
        "project": "VISTA – Smart Hostel & Accommodation Management System",
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": env,
        "definitions": {"executed": "Pass or Fail outcome", "pass_percentage": "passed / executed x 100; N/A if nothing executed",
                        "blocked": "could not run because of the environment", "not_run": "requires resources not available (users, 30-day monitoring)"},
        "summary": {"functional": summary(functional), "nonfunctional": summary(nonfunctional), "tools": tool_summary},
        "functional_cases": functional,
        "nonfunctional_cases": nonfunctional,
        "k6_runs": k6,
        "automated_tests": tests,
        "defects": register,
    }
    (TR / "test-results.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))

    # JUnit XML
    root = ET.Element("testsuites", name="VISTA automated tests", timestamp=out["generated_at"])
    for tool in ("pytest", "vitest", "playwright"):
        ts = [t for t in tests if t["tool"] == tool]
        suite = ET.SubElement(root, "testsuite", name=tool, tests=str(len(ts)),
                              failures=str(sum(t["status"] in ("failed", "timedOut") for t in ts)),
                              skipped=str(sum(t["status"] in ("blocked", "skipped") for t in ts)),
                              time=f"{sum(t['duration_s'] for t in ts):.2f}")
        for t in ts:
            tc = ET.SubElement(suite, "testcase", classname=t["project"], name=t["id"], time=str(t["duration_s"]))
            if t["status"] in ("failed", "timedOut"):
                ET.SubElement(tc, "failure", message=t["message"][:300])
            elif t["status"] in ("blocked", "skipped"):
                ET.SubElement(tc, "skipped", message=t["message"][:300] or t["status"])
            if t["cases"]:
                props = ET.SubElement(tc, "properties")
                for c in t["cases"]:
                    ET.SubElement(props, "property", name="case", value=c)
    for name, rows in (("functional-cases", functional), ("nonfunctional-cases", nonfunctional)):
        suite = ET.SubElement(root, "testsuite", name=name, tests=str(len(rows)), failures=str(sum(r["status"] == "Fail" for r in rows)),
                              skipped=str(sum(r["status"] in ("Blocked", "Not Run") for r in rows)))
        for r in rows:
            tc = ET.SubElement(suite, "testcase", classname=name, name=f"{r['id']} {r['description']}")
            if r["status"] == "Fail":
                ET.SubElement(tc, "failure", message=r["actual"][:500])
            elif r["status"] in ("Blocked", "Not Run"):
                ET.SubElement(tc, "skipped", message=f"{r['status']}: {r['actual'][:400]}")
            else:
                ET.SubElement(tc, "system-out").text = r["actual"]
    ET.indent(root)
    ET.ElementTree(root).write(TR / "test-results.xml", encoding="utf-8", xml_declaration=True)
    f, n = out["summary"]["functional"], out["summary"]["nonfunctional"]
    print(f"Functional: {f}\nNon-functional: {n}\nTools: {json.dumps(tool_summary)}")


if __name__ == "__main__":
    main()
