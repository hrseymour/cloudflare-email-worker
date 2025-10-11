# Cloudflare Email Worker with R2 Backup

Capture and review emails that Gmail rejects when forwarded through Cloudflare Email Routing.

## The Problem

Cloudflare Email Routing is great for forwarding custom domain emails to Gmail, but when Gmail's spam filters or rate limiters reject an email, it's gone forever. Cloudflare doesn't store rejected emails, leaving you blind to potentially important messages.

## The Solution

This Worker sits between Cloudflare Email Routing and Gmail:
- ✅ Successful forwards work exactly as before
- ✅ Failed forwards are captured with complete content to R2 storage
- ✅ Review failed emails anytime with the included Python script
- ✅ See the full message body, not just headers
- ✅ Understand why Gmail rejected each email

Stop losing emails to spam filters. Start capturing them instead.

## Quick Start

1. Install dependencies (Node.js 22, Wrangler, Python 3.10+)
2. Create R2 bucket: `wrangler r2 bucket create failed-emails`
3. Set up R2 credentials in `.env` (see .env.example)
4. Install Python deps: `pip install -r requirements.txt` (in venv)
5. Configure emails in `worker.js`
6. Deploy: `wrangler deploy`
7. Test (see TESTING.md)
8. Configure email routing in Cloudflare Dashboard

## Key Files

- `worker.js` - Email worker code
- `view_failed_emails.py` - Python script to view emails (uses boto3)
- `.env.example` - Template for R2 credentials
- `TESTING.md` - Complete testing guide
- `QUICK_REFERENCE.md` - Command cheat sheet

## R2 Credentials Setup

See `.env.example` for detailed instructions on creating R2 API tokens.

```bash
cp .env.example .env
# Edit .env with your credentials
set -a; source .env; set +a
```

## Basic Usage

```bash
# Deploy worker
wrangler deploy

# Watch logs
wrangler tail email-worker --format pretty

# View failed emails
source .venv/bin/activate
python3 view_failed_emails.py --stats
```

## Documentation

- `TESTING_GUIDE.md` - How to test before going live
- `QUICK_REFERENCE.md` - All commands in one place
- `TROUBLESHOOTING.md` - Common issues
- `.env.example` - R2 setup instructions

## License

MIT License - see LICENSE file
