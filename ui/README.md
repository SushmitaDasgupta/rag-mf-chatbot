# Kotak Mutual Fund FAQ — React UI (Phase 4)

Web frontend based on the Stitch design in [`../stitch_kotak_mutual_fund_faq_assistant/`](../stitch_kotak_mutual_fund_faq_assistant/) (`DESIGN.md`, `code.html`).

**Stack:** React 18 · Vite · TypeScript · Tailwind CSS

## Features (Phase 4)

- Sticky compliance disclaimer
- Welcome state + supported schemes list
- Three example question chips
- Live chat via `POST /api/chat`
- Citation link + last-updated footer on answers
- Refusal / rate-limit styling
- Chat history sidebar with New Chat
- Client-side submit spacing + 429 cooldown

## Run locally

```bash
# Terminal 1 — API
cd ..
source .venv/bin/activate
uvicorn src.api.main:app --reload

# Terminal 2 — UI
cd ui
npm install
npm run dev
```

Open http://localhost:5173

Vite proxies `/api/*` to `http://127.0.0.1:8000`.

## Build

```bash
npm run build
npm run preview
```

## Environment

Copy `ui/.env.example` to `ui/.env` for local overrides.

```env
# Local dev: leave empty to use Vite proxy (/api -> localhost:8000)
VITE_API_BASE_URL=
```

For Vercel production, set `VITE_API_BASE_URL` to your Railway API URL (see [`vercel.env.example`](../vercel.env.example) and [`docs/deployment.md`](../docs/deployment.md) Phase 2).

Production build locally:

```bash
VITE_API_BASE_URL=https://your-api.up.railway.app bash ../scripts/build_ui_production.sh
```

## Design tokens

Dark “Institutional Trust” theme from Stitch `DESIGN.md`: surface `#0b1326`, primary `#adc6ff`, secondary teal citations, amber compliance banner.
