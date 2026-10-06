# CloudCrowd Analytics frontend

A React + Vite dashboard that reads the latest telemetry from the configured API endpoint and falls back to schema-shaped mock data when the API is unavailable.

## Run locally

```bash
npm install
npm run dev
```

Copy `.env.example` to `.env.local` and set `VITE_API_BASE_URL` to the API Gateway base URL. Do not put credentials or secrets in frontend environment variables.
