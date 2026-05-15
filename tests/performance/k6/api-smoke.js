import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.API_BASE_URL || 'http://localhost:8000';

export const options = {
  thresholds: {
    http_req_failed: ['rate<0.05'],
    http_req_duration: ['p(95)<750'],
    checks: ['rate>0.95'],
  },
  scenarios: {
    smoke: {
      executor: 'constant-vus',
      vus: Number(__ENV.K6_VUS || 3),
      duration: __ENV.K6_DURATION || '30s',
    },
  },
};

const endpoints = [
  '/health',
  '/products?limit=20&offset=0&sort_by=sku&sort_order=asc',
  '/forecasts?limit=20&offset=0&sort_by=forecast_period_start&sort_order=asc',
  '/forecast-runs?limit=20&offset=0&sort_by=completed_at&sort_order=desc',
  '/inventory-snapshots?limit=20&offset=0&sort_by=recorded_at&sort_order=desc',
  '/sales?limit=20&offset=0&sort_by=sold_at&sort_order=desc',
  '/inventory-risks?limit=20&offset=0&sort_by=risk_status&sort_order=asc',
  '/notifications?user_id=platform-admin&limit=20&offset=0',
  '/me?user_id=platform-admin',
  '/metrics',
];

export default function () {
  for (const endpoint of endpoints) {
    const response = http.get(`${BASE_URL}${endpoint}`, {
      headers: {
        'X-Correlation-ID': `k6-${__VU}-${__ITER}`,
      },
      tags: { endpoint },
    });

    check(response, {
      [`${endpoint} returns 2xx`]: (r) => r.status >= 200 && r.status < 300,
    });
  }

  sleep(1);
}
