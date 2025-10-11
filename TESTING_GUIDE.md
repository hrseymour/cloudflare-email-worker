# Testing Guide for Email Worker

This guide helps you test the email worker before routing live email through it.

## Pre-Deployment Tests (Before `wrangler deploy`)

### 1. Syntax Check

```bash
# Check JavaScript syntax
node --check worker.js
```

**Expected:** No output means syntax is valid ✅

### 2. Configuration Review

```bash
# View email configuration
head -30 worker.js

# Check R2 bucket name
grep bucket_name wrangler.toml
```

**Verify:**
- Email addresses are correct
- `forwardTo` addresses are correct
- `enabled: true` for addresses you want to use
- Bucket name matches: `failed-emails`

### 3. R2 Bucket Exists

```bash
wrangler r2 bucket list
```

**Expected:** Should show `failed-emails` bucket

### 4. Python Script Works

```bash
source .venv/bin/activate
set -a; source .env; set +a
python3 view_failed_emails.py --stats
```

**Expected:** Shows email statistics (0 for each if no failures yet)

## Post-Deployment Tests (After `wrangler deploy`)

### 5. Verify Deployment

```bash
# Check deployment succeeded
wrangler deployments list --name email-worker
```

**Expected:** Recent deployment with status "Complete"

### 6. Start Log Monitoring

```bash
# Watch logs in real-time (keep this running)
wrangler tail email-worker --format pretty
```

Keep this terminal open while testing!

## Live Email Tests

### Strategy A: Test with Non-Critical Email (Safest)

If you have a test email address like `test@harlanseymour.com`:

#### Step 1: Add Test Configuration

Edit `worker.js`:
```javascript
const EMAIL_CONFIG = {
  'harlan@harlanseymour.com': {
    forwardTo: 'hrseymour@gmail.com',
    enabled: false  // ← Keep your real one disabled for now
  },
  'test@harlanseymour.com': {  // ← Add test address
    forwardTo: 'your-test-email@gmail.com',
    enabled: true
  }
};
```

#### Step 2: Redeploy

```bash
wrangler deploy
```

#### Step 3: Configure Routing (Test Address Only)

1. Go to Cloudflare Dashboard
2. Email → Email Routing → Routes
3. Configure `test@harlanseymour.com` → Send to Worker → `email-worker`

#### Step 4: Send Test Email

Send an email to `test@harlanseymour.com`

#### Step 5: Watch Logs

In your `wrangler tail` terminal, you should see:

**Success:**
```
✓ Successfully forwarded email from sender@example.com to your-test-email@gmail.com 
  (recipient: test@harlanseymour.com)
```

**Failure (intentional test):**
```
✗ Failed to forward email from sender@example.com to your-test-email@gmail.com
  Reason: [error message]
✓ Stored failed email in R2: test@harlanseymour.com/2024-10-10T...json
```

#### Step 6: Verify Captured Email (If Failed)

```bash
python3 view_failed_emails.py --email test@harlanseymour.com
```

#### Step 7: Enable Real Email (When Ready)

Once testing looks good:

1. Edit `worker.js`:
```javascript
'harlan@harlanseymour.com': {
  forwardTo: 'hrseymour@gmail.com',
  enabled: true  // ← Enable it
},
'test@harlanseymour.com': {
  forwardTo: 'your-test-email@gmail.com',
  enabled: false  // ← Disable test
}
```

2. Deploy: `wrangler deploy`
3. Configure routing for `harlan@harlanseymour.com`

### Strategy B: Quick Production Test (No Test Email Available)

If you don't have a test email address:

#### Step 1: Deploy Worker

```bash
wrangler deploy
```

#### Step 2: Start Monitoring

```bash
wrangler tail email-worker --format pretty
```

#### Step 3: Configure Routing (One Email Only)

Configure routing for just `harlan@harlanseymour.com` (keep others direct)

#### Step 4: Send Test Email to Yourself

Send yourself an email at `harlan@harlanseymour.com`

#### Step 5: Check Results

**Option 1:** Check Gmail - did you receive it? ✅

**Option 2:** Check logs - successful forward? ✅

**Option 3:** If failed - check R2:
```bash
python3 view_failed_emails.py --recent 1
```

#### Step 6: Revert Immediately If Issues

If something's wrong:
1. Dashboard → Email Routing → Routes
2. Change `harlan@harlanseymour.com` back to "Send to an email"
3. Direct forwarding restored immediately

## Expected Log Messages

### Successful Forward

```
✓ Successfully forwarded email from alice@example.com to hrseymour@gmail.com 
  (recipient: harlan@harlanseymour.com)
```

### Failed Forward (Captured)

```
✗ Failed to forward email from bob@example.com to hrseymour@gmail.com. 
  Reason: SMTP error: 550 5.7.1 Rate limit exceeded

✓ Stored failed email in R2: harlan@harlanseymour.com/2024-10-10T12-30-45-123Z_from_bob@example.com.json
```

### Email Not Configured

```
✗ No configuration found for recipient: unknown@harlanseymour.com
```

### Email Disabled

```
✗ Email routing disabled for: test@harlanseymour.com
```

## Troubleshooting

### Email Not Forwarding

**Check:**
1. Is email address in `EMAIL_CONFIG`?
2. Is `enabled: true`?
3. Is routing configured to use worker?
4. Are logs showing errors?

**Fix:**
```bash
# View configuration
grep -A 10 "EMAIL_CONFIG" worker.js

# Check routing in dashboard
# Email → Email Routing → Routes
```

### Worker Not Receiving Emails

**Check:**
1. Is Email Routing enabled for your domain?
2. Is route pointing to `email-worker`?
3. Did deployment succeed?

**Fix:**
```bash
# Check deployment
wrangler deployments list --name email-worker

# Redeploy if needed
wrangler deploy
```

### R2 Storage Not Working

**Check:**
1. Does bucket exist?
2. Is bucket name correct in `wrangler.toml`?
3. Are logs showing storage errors?

**Fix:**
```bash
# Check bucket
wrangler r2 bucket list

# Verify configuration
grep bucket_name wrangler.toml
```

## Emergency Revert

If anything goes wrong and you need to quickly restore direct forwarding:

### Method 1: Dashboard (Fastest)

1. Go to Cloudflare Dashboard
2. Email → Email Routing → Routes
3. Find your email address
4. Change action to "Send to an email"
5. Select your Gmail address
6. Save

**Result:** Direct forwarding restored immediately. Worker still deployed but not being called.

### Method 2: Delete Worker (Nuclear Option)

```bash
wrangler delete email-worker
```

**Result:** Worker completely removed. Email routing will fail until reconfigured.

## Success Checklist

Before considering testing complete:

- [ ] Worker deploys without errors
- [ ] Can see worker in deployments list
- [ ] Test email forwards successfully
- [ ] Logs show successful forward message
- [ ] Test email arrives in Gmail
- [ ] (Optional) Trigger a failure and verify R2 capture
- [ ] (Optional) View captured email with Python script
- [ ] Know how to revert routing if needed

## Next Steps After Testing

Once testing is successful:

1. ✅ Configure routing for all desired email addresses
2. ✅ Monitor logs occasionally: `wrangler tail email-worker`
3. ✅ Check for failed emails periodically: `python3 view_failed_emails.py --stats`
4. ✅ Set up automatic .env loading in venv (optional)
5. ✅ Document any custom configurations you made

---

**Remember:** The worker is just code sitting in Cloudflare. It only runs when email routing sends emails to it. You can always revert routing back to direct forwarding with zero consequences!