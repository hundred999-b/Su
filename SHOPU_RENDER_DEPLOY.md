# ShopU — Render deployment

## Architecture

GitHub is the source repository. Render deploys the Django web service from `main`.

- `shopu-web`: Django + Gunicorn + Mini App
- `shopu-telegram`: persistent worker for the user-facing/main Telegram bot
- Notification bot: outbound-only Telegram API bot used by the notification delivery code
- cron-job.org + GitHub Actions: existing scheduler architecture; unchanged

## Required Telegram variables

Set these in the Render **shopu-web** environment:

- `TELEGRAM_MAIN_BOT_TOKEN`
- `TELEGRAM_MAIN_BOT_USERNAME`
- `TELEGRAM_NOTIFICATION_BOT_TOKEN`

The main bot worker inherits the main bot token and username from the web service.

If `MINIAPP_URL` is empty, the application derives the Mini App URL from Render's public hostname.

## Required database/storage variables

Set the existing ShopU `DATABASE_URL` and Supabase S3 storage variables in Render.

Do not commit secrets.

## Deploy

Push to GitHub `main`, then Render auto-deploys the Blueprint.

Health endpoint: `/health/`
Mini App: `/miniapp/`

The cron setup is intentionally not changed by this deployment.
