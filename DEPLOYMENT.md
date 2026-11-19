# Deployment Checklist

Backend → Render (free tier). Frontend → Vercel (free tier). Database → Neon Postgres (free tier).

## 1. Neon (database)

- [ ] Create a free-tier Neon project.
- [ ] Copy its connection string (`postgres://...`).
- [ ] Paste it into Render's `DATABASE_URL` env var (step 2) — never commit it to the repo.

## 2. Render (backend)

- [ ] Connect this repo to a new Render **Web Service**, or run `render.yaml` as a Blueprint.
- [ ] Root Directory: `backend`
- [ ] Build command: `pip install -r requirements.txt`
- [ ] Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- [ ] In the Render dashboard, set every env var listed in `render.yaml` with `sync: false`. At minimum:
  - `DATABASE_URL` — the Neon connection string from step 1
  - `JWT_SECRET_KEY` — generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"` (the code falls back to an **insecure default** if this is left unset — do not skip it)
  - `CONNECTOR_ENCRYPTION_KEY` — generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` (the app raises an error at runtime if this is unset)
  - `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
  - `TAVILY_API_KEY`
  - At least one LLM key: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `MISTRAL_API_KEY`, or `QWEN_API_KEY`
  - `CORS_ORIGINS` — leave as a placeholder for now; comes back in step 4
- [ ] Deploy and confirm the service boots (check the Render logs for `Application startup complete`).

**Note:** PDF export returns `503` on Render by design — there's no LibreOffice binary on this host. DOCX and PPTX export are unaffected.

## 3. Vercel (frontend)

- [ ] Connect this repo to a new Vercel project.
- [ ] Root Directory: `frontend`
- [ ] Framework: Next.js (auto-detected; `frontend/vercel.json` just confirms it)
- [ ] Set `NEXT_PUBLIC_API_URL` in the Vercel dashboard's env vars (Production + Preview) to the Render backend's URL, e.g. `https://stratai-backend.onrender.com`. This is a **build-time** variable for Next.js — set it before the first deploy, or redeploy after setting it.
- [ ] Deploy.

## 4. Close the loop: CORS

- [ ] Once Vercel gives you the production domain, go back to Render → `CORS_ORIGINS` and set it to that exact URL (e.g. `https://your-app.vercel.app`). Vercel preview URLs (`https://*.vercel.app`) are already covered by a regex in `backend/main.py`, so only the production domain needs to be listed explicitly.
- [ ] Redeploy the Render service for the new `CORS_ORIGINS` value to take effect.

## 5. Google OAuth

- [ ] In Google Cloud Console → your OAuth client:
  - Add the Vercel production domain to **Authorized JavaScript origins** (e.g. `https://your-app.vercel.app`).
  - Add the corresponding callback URL to **Authorized redirect URIs**.
- [ ] If you use Vercel preview deployments for Google sign-in too, add those preview domains as well (Google doesn't support wildcard origins).

## 6. Smoke test

- [ ] Visit the Vercel URL, sign in, and confirm it reaches the Render backend (no CORS errors in the browser console).
- [ ] Run through brand setup once to confirm `TAVILY_API_KEY` and the LLM key are working end-to-end.
- [ ] Export a report as DOCX and PPTX; confirm the branded logo renders (it's read from the database, not the filesystem, so it survives Render's free-tier spin-down/restarts).
