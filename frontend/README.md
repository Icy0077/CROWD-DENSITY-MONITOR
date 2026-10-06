# CloudCrowd Analytics frontend

A React + Vite dashboard that reads the latest telemetry from the configured API endpoint.

## Run locally

```bash
npm install
npm run dev
```

Copy `.env.example` to `.env.local` and set `VITE_API_BASE_URL` to the API Gateway base URL. Do not put credentials or secrets in frontend environment variables. The dashboard requests `GET /telemetry/latest`, polls every 5 seconds without overlapping requests, and displays an API error when live telemetry is unavailable. Failed polls preserve the last API response and mark it stale; no telemetry fallback is used.
