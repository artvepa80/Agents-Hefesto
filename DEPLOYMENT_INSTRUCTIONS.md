# Hefesto Deployment Instructions

## Quick Deploy to GitHub

### Step 1: Initialize Repository (Already Done)

```bash
cd /tmp/hefesto-standalone
git init
git remote add origin https://github.com/artvepa80/Agents-Hefesto.git
```

### Step 2: Add All Files

```bash
git add .
```

### Step 3: Commit

```bash
git commit -m "feat: Initial release v3.5.0 - Hefesto AI Code Quality Guardian

- Phase 0 (Free): Enhanced validation, feedback loop, budget control
- Phase 1 (Pro): Semantic analysis with ML embeddings
- 209 tests (96% passing)
- Dual license (MIT + Commercial)
- pip-installable package
- CLI interface
- Complete documentation

Ready for PyPI publication and commercial use."
```

### Step 4: Push to GitHub

```bash
git branch -M main
git push -u origin main
```

---

## Publish to PyPI

### Prerequisites

1. PyPI account: https://pypi.org/account/register/
2. API token: https://pypi.org/manage/account/token/

### Build Package

```bash
# Install build tools
pip install build twine

# Build distribution
python -m build

# This creates:
# - dist/hefesto-3.5.0.tar.gz
# - dist/hefesto-3.5.0-py3-none-any.whl
```

### Upload to PyPI

```bash
# Test on TestPyPI first (recommended)
twine upload --repository testpypi dist/*

# Then upload to real PyPI
twine upload dist/*
```

### Verify Publication

```bash
# Install from PyPI
pip install hefesto

# Test
hefesto --version
# Expected: 3.5.0
```

---

## Deploy to Cloud Run

### Prerequisites

- Google Cloud Project
- Cloud Run API enabled
- gcloud CLI installed

### Step 1: Create Dockerfile

Already included in repository.

### Step 2: Deploy

```bash
gcloud run deploy hefesto \
  --source . \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300s \
  --set-env-vars GEMINI_API_KEY=$GEMINI_API_KEY
```

### Step 3: Get URL

```bash
gcloud run services describe hefesto \
  --region us-central1 \
  --format 'value(status.url)'
```

---

## Configure Stripe

### Step 1: Create Product

1. Go to: https://dashboard.stripe.com/products
2. Click "Add Product"
3. Name: "Hefesto Pro"
4. Price: $99/month (recurring)
5. Save product

### Step 2: Create Payment Link

1. Go to "Payment Links"
2. Create link for Hefesto Pro
3. Copy link URL
4. Update README.md with actual link

### Step 3: Webhook Setup

For license validation:

1. Go to: https://dashboard.stripe.com/webhooks
2. Add endpoint: https://your-hefesto.run.app/webhooks/stripe
3. Subscribe to events:
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
4. Copy webhook secret
5. Set: `export STRIPE_WEBHOOK_SECRET='whsec_...'`

---

## Update Documentation Links

After Stripe setup, update these files with actual links:

1. **README.md** - Replace `https://buy.stripe.com/hefesto-pro`
2. **LICENSE** - Add actual Stripe payment link
3. **hefesto/llm/license_validator.py** - Update purchase URL
4. **docs/STRIPE_SETUP.md** - Add actual links

---

## Release Checklist

### Before Release

- [ ] All tests passing (`pytest`)
- [ ] Linters clean (`black .`, `isort .`, `mypy hefesto/`)
- [ ] Version updated in `hefesto/__version__.py`
- [ ] CHANGELOG.md updated
- [ ] README.md reviewed
- [ ] LICENSE files in place
- [ ] Stripe product created
- [ ] Payment link working

### Release Process

```bash
# Tag release
git tag -a v3.5.0 -m "Release v3.5.0 - Phase 0 + Phase 1"
git push origin v3.5.0

# Build and publish
python -m build
twine upload dist/*

# Announce
# - GitHub Releases
# - Twitter/LinkedIn
# - Email to beta users
```

### Post-Release

- [ ] Monitor PyPI downloads
- [ ] Watch GitHub issues
- [ ] Track Stripe subscriptions
- [ ] Respond to support emails
- [ ] Update documentation as needed

---

## Monitoring

### PyPI Stats

- Downloads: https://pypistats.org/packages/hefesto
- Package page: https://pypi.org/project/hefesto/

### GitHub Stats

- Stars: https://github.com/artvepa80/Agents-Hefesto/stargazers
- Forks: https://github.com/artvepa80/Agents-Hefesto/network/members
- Issues: https://github.com/artvepa80/Agents-Hefesto/issues

### Stripe Stats

- Dashboard: https://dashboard.stripe.com
- Subscriptions: MRR, churn rate, customer count
- Revenue: Track monthly recurring revenue

---

## Marketing

### Launch Checklist

- [ ] GitHub README polished
- [ ] PyPI description compelling
- [ ] Demo video created
- [ ] Blog post written
- [ ] HackerNews post prepared
- [ ] Reddit r/Python post
- [ ] Twitter announcement
- [ ] LinkedIn post
- [ ] ProductHunt launch

### Target Metrics (First 3 Months)

- PyPI downloads: 1,000+
- GitHub stars: 100+
- Pro customers: 10+ ($990/month MRR)
- Free users: 500+

---

## Support Setup

### Email

- support@narapa.com - General support
- sales@narapa.com - License sales
- security@narapa.com - Security issues

### GitHub

- Issues: Bug reports
- Discussions: Feature requests, questions
- Wiki: Extended documentation

### Community

- Discord server (optional)
- Slack workspace (Pro customers)

---

**Ready to launch!** 🚀

Contact: sales@narapa.com for questions.

