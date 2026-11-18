# StratAI Deploy Checklist

## Database Migrations

```
cd backend && python scripts/add_reference_docs.py
```

This script is idempotent — safe to re-run on every deploy.

## Important

- Do NOT commit stratai.db — it contains runtime data.
- Schema changes are applied via scripts in backend/scripts/. Run them before starting the server.
- Future: migrate to Alembic when deploy pipeline is formalized.
