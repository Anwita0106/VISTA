// k6 load test for the VISTA API (NFT-01, NFT-02, NFT-06, NFT-25).
// Usage: k6 run -e BASE_URL=http://localhost:8000 -e VUS=50 -e DURATION=60s -e LABEL=normal perf/load-test.js
import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

const BASE = __ENV.BASE_URL || "http://localhost:8000";
const VUS = Number(__ENV.VUS || 50);
const DURATION = __ENV.DURATION || "60s";
const LABEL = __ENV.LABEL || `vus${VUS}`;
const OUT = __ENV.OUT_DIR || "test-results/perf";

const readLatency = new Trend("vista_read_latency", true);
const writeLatency = new Trend("vista_write_latency", true);
const businessErrors = new Rate("vista_errors");

export const options = {
  scenarios: {
    hostel_peak: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "10s", target: VUS },
        { duration: DURATION, target: VUS },
        { duration: "5s", target: 0 },
      ],
      gracefulRampDown: "5s",
    },
  },
  thresholds: {
    // Project targets derived from NFR02 (avg < 3 s) and NFR08 (errors < 0.5 %)
    http_req_duration: ["avg<3000"],
    vista_errors: ["rate<0.005"],
  },
  summaryTrendStats: ["avg", "min", "med", "p(90)", "p(95)", "p(99)", "max"],
};

const STUDENTS = [
  "priya.sharma", "ananya.iyer", "rahul.verma", "arjun.nair", "kavya.reddy", "sneha.das", "vikram.singh", "meera.pillai",
];

export function setup() {
  const tokens = [];
  for (const s of STUDENTS) {
    const r = http.post(`${BASE}/api/auth/login`, JSON.stringify({ email: `${s}@vista.demo`, password: "Student@123" }), {
      headers: { "Content-Type": "application/json" },
    });
    if (r.status === 200) tokens.push(r.json("access_token"));
  }
  const w = http.post(`${BASE}/api/auth/login`, JSON.stringify({ email: "warden.lh@vista.demo", password: "Warden@123" }), {
    headers: { "Content-Type": "application/json" },
  });
  return { tokens, warden: w.json("access_token") };
}

function get(path, token) {
  const r = http.get(`${BASE}${path}`, { headers: { Authorization: `Bearer ${token}` }, tags: { name: path.split("?")[0] } });
  readLatency.add(r.timings.duration);
  businessErrors.add(r.status !== 200);
  check(r, { [`GET ${path.split("?")[0]} 200`]: (x) => x.status === 200 });
}

export default function (data) {
  const token = data.tokens[(__VU + __ITER) % data.tokens.length];
  const roll = Math.random();
  if (roll < 0.8) {
    // typical student session: dashboard, notices, complaints, notifications
    get("/api/dashboard", token);
    get("/api/notices", token);
    get("/api/complaints?page=1&page_size=10", token);
    get("/api/notifications", token);
  } else if (roll < 0.9) {
    const r = http.post(
      `${BASE}/api/complaints`,
      JSON.stringify({ category: "OTHER", title: `Load test item ${__VU}-${__ITER}`, description: "Created by the k6 load test script." }),
      { headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }, tags: { name: "/api/complaints (POST)" } },
    );
    writeLatency.add(r.timings.duration);
    businessErrors.add(r.status !== 201);
    check(r, { "POST complaint 201": (x) => x.status === 201 });
  } else {
    get("/api/visitors?status=PENDING", data.warden);
    get("/api/sos", data.warden);
  }
  sleep(1);
}

export function handleSummary(data) {
  const m = data.metrics;
  const out = {
    label: LABEL,
    vus: VUS,
    duration: DURATION,
    requests: m.http_reqs.values.count,
    throughput_rps: Number(m.http_reqs.values.rate.toFixed(2)),
    http_req_failed_rate: m.http_req_failed.values.rate,
    business_error_rate: m.vista_errors ? m.vista_errors.values.rate : null,
    latency_ms: m.http_req_duration.values,
    read_latency_ms: m.vista_read_latency ? m.vista_read_latency.values : null,
    write_latency_ms: m.vista_write_latency ? m.vista_write_latency.values : null,
    checks_passed: m.checks.values.passes,
    checks_failed: m.checks.values.fails,
    thresholds_ok: Object.fromEntries(Object.entries(data.metrics).filter(([, v]) => v.thresholds).map(([k, v]) => [k, Object.values(v.thresholds).every((t) => t.ok)])),
  };
  return { [`${OUT}/k6-${LABEL}.json`]: JSON.stringify(out, null, 2), stdout: JSON.stringify(out, null, 2) + "\n" };
}
