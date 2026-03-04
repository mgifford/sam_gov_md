# GitHub Pages Deployment

1. Go to the repository Settings page on GitHub.
2. Open **Pages**.
3. Set **Source** to **Deploy from a branch**.
4. Select branch `main` and folder `/docs`.
5. Save.

After each data refresh, run:

```bash
/Users/mgifford/sam_gov/.venv/bin/python scripts/process_today.py --target-date 2026-03-04 --fallback-latest
```

Then commit and push updates so the dashboard reflects fresh data.
