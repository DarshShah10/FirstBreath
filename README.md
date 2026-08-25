# FirstBreath

Multi-agent emergency response simulation for the Golden Hour.

FirstBreath simulates the complete hospital-city response to a medical emergency —
dispatcher, ambulances, and hospital as AI agents (LangGraph) making real decisions
under time pressure, on top of an honest deterministic world model that tracks every
minute, kilometer, bed, and blood unit. Every run ends with a grounded mission
briefing: what happened, where the response chain strained, and what intervention
would change the outcome.

> Under active development — see the phase plan in this repo's history.

## Architecture

```
Scenario input (structured form / uploaded document)
        |
        v
LangGraph agent runtime      Dispatcher / Ambulance / Hospital agents
  structured actions  -----> World model (deterministic physics:
  radio chatter  --------->     clock, roads/ETAs, OTs, blood inventory)
                                     |
                                Event log (Supabase Postgres)
                                     |
                          Report + Debrief agents (grounded in log)
```

## Repository layout

| Path | What it is |
|---|---|
| `backend/` | Flask API + simulation engine + (upcoming) LangGraph agent runtime |
| `dashboard/` | React TypeScript frontend |
| `backend/config/emergency_resources.yaml` | City resource registry (hospitals, ambulances, routes) |

## Quick start

### Backend

```bash
cd backend
uv sync            # or: pip install -r requirements.txt
cp ../.env.example ../.env   # then fill in your keys
uv run python run.py
```

API served at `http://localhost:5001` (`/api/v1`, `/api/emergency`, `/health`).

### Dashboard

```bash
cd dashboard
npm install
npm run dev
```

## Environment variables

See `.env.example`. Requires:

- `LLM_API_KEY` — OpenRouter (or any OpenAI-compatible endpoint)
- `SUPABASE_URL` + `SUPABASE_SECRET_KEY` — database

## Deployment

- Backend: Render / Railway via the included `Dockerfile`
- Dashboard: Vercel (`dashboard/vercel.json`)
- Database: Supabase Postgres (`supabase/migrations/`)

## License

AGPL-3.0
