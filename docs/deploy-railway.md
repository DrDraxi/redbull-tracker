# Deploying the API to Railway

## One-time setup

1. Install the CLI and log in:
   ```bash
   npm i -g @railway/cli
   railway login
   ```

2. Create a new project linked to this repo:
   ```bash
   railway init
   railway link
   ```

3. Add a volume mounted at `/data`:
   - In the Railway dashboard → Service → Volumes → "Add Volume" → mount path `/data`.
   - (CLI equivalent: `railway volume add --mount-path /data`)

4. Set environment variables. Generate strong secrets:
   ```bash
   railway variables set \
     API_TOKEN=$(openssl rand -hex 32) \
     COOKIE_SECRET=$(openssl rand -hex 32) \
     ANTHROPIC_API_KEY=sk-ant-...
   ```

5. Deploy:
   ```bash
   railway up
   ```

6. (Optional) Add a custom domain:
   - Dashboard → Service → Settings → Networking → "Custom Domain"
   - Railway provides HTTPS via Let's Encrypt automatically.

## Verifying the deploy

```bash
RAILWAY_URL=$(railway domain)   # or copy from dashboard
curl "$RAILWAY_URL/api/v1/health"
# → {"ok": true, "db": "ok"}
```

Set the widget env vars locally:

```powershell
$env:REDBULL_API_URL = "https://your-railway-app.up.railway.app"
$env:REDBULL_API_TOKEN = "<the API_TOKEN you set above>"
```

Then launch the widget:

```powershell
dotnet run --project apps/widget/RedBullTracker.csproj -p:Platform=x64
```

## Updating env vars later

```bash
railway variables set API_TOKEN=<new-token>
```

The service restarts automatically.

## Backups

Railway volumes aren't backed up automatically. For periodic SQLite backups:

```bash
railway volume export <volume-id> -o ./backup-$(date +%F).tar.gz
```

For automated backups, consider adding a `litestream` sidecar later (out of scope for the initial launch).

## Troubleshooting

- **Health check fails** — check that the volume is mounted at `/data` and that all three env vars are set. The API refuses to start if `API_TOKEN` or `COOKIE_SECRET` is missing.
- **Receipt upload returns 500** — `ANTHROPIC_API_KEY` is missing or invalid. Set it via `railway variables set`.
- **Widget can't connect** — verify `REDBULL_API_URL` includes `https://` and matches the Railway-assigned hostname exactly.
