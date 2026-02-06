# Frontend

React + TypeScript + Vite frontend for the SLM RAG Skill Tracker.

## Setup

1. Install dependencies:
   ```bash
   npm install
   ```

2. Copy `.env.example` to `.env` and set `VITE_API_URL` to your backend URL (default: `http://localhost:8000`).

3. Start the dev server:
   ```bash
   npm run dev
   ```

4. Build for production:
   ```bash
   npm run build
   ```

## Development

The dev server runs on `http://localhost:5173` by default. Vite proxies `/api` and `/auth` requests to the backend (configured in `vite.config.ts`).
