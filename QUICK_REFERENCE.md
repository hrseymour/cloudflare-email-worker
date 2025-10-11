# Quick Reference

**Note:** This file was created by generate_repo.sh.
For the complete quick reference, see the QUICK_REFERENCE.md 
artifact in the Claude conversation.

## Essential Commands

```bash
# Deploy
wrangler deploy

# Watch logs
wrangler tail email-worker --format pretty

# View emails (with venv active and .env loaded)
python3 view_failed_emails.py --stats
python3 view_failed_emails.py --recent 10
```

## Setup .env

```bash
cp .env.example .env
# Edit with your R2 credentials
set -a; source .env; set +a
```

See full QUICK_REFERENCE.md for all commands and tips.
