# Stripe License Setup Guide

How to purchase and configure Hefesto Pro license.

## Purchasing Pro License

### Option 1: Stripe Checkout (Recommended)

1. Visit: **https://buy.stripe.com/hefesto-pro**
2. Choose plan:
   - **Individual**: $25/month (Hefesto) or $35/month (OMEGA Founding) or $49/month (OMEGA Pro) (1 user)
   - **Team**: $399/month (5 users)
   - **Enterprise**: Contact sales
3. Complete payment
4. Receive license key via email

### Option 2: Contact Sales

For enterprise licensing, custom terms, or bulk licenses:

**Email**: sales@narapallc.com  
**Subject**: Hefesto Pro License Inquiry

Include:
- Company name
- Number of developers
- Use case
- Any special requirements

---

## Configuring License Key

### Step 1: Set Environment Variable

```bash
export HEFESTO_LICENSE_KEY='hef_1234567890abcdef'
```

### Step 2: Verify License

```bash
hefesto info
```

Expected output:
```
📜 License:
   Tier: PRO
   Pro Features: ✅ Enabled
   Enabled Features:
      • semantic_analysis
      • cicd_feedback
      • duplicate_detection
      • metrics_dashboard
```

### Step 3: Install Pro Dependencies

```bash
pip install hefesto-ai[pro]
```

---

## License Key Format

Valid keys start with:
- `hef_` - Hefesto production keys
- `sk_` - Stripe secret keys (for testing)
- `pk_` - Stripe publishable keys

Example: `hef_live_1234567890abcdef1234567890abcdef`

---

## Environment-Specific Setup

### Development

```bash
# .env file
HEFESTO_LICENSE_KEY=hef_test_1234567890abcdef
HEFESTO_ENV=development
```

### Production

```bash
# Cloud Run / Kubernetes
kubectl create secret generic hefesto-license \
  --from-literal=HEFESTO_LICENSE_KEY='hef_live_...'

# Then reference in deployment
env:
  - name: HEFESTO_LICENSE_KEY
    valueFrom:
      secretKeyRef:
        name: hefesto-license
        key: HEFESTO_LICENSE_KEY
```

### CI/CD

```yaml
# GitHub Actions
env:
  HEFESTO_LICENSE_KEY: ${{ secrets.HEFESTO_LICENSE_KEY }}

# GitLab CI
variables:
  HEFESTO_LICENSE_KEY: $HEFESTO_LICENSE_KEY  # From CI/CD variables
```

---

## Subscription Management

### View Subscription

Visit Stripe Customer Portal:
https://billing.stripe.com/p/login/xxxxx

(Link sent via email after purchase)

### Update Payment Method

1. Log in to Stripe portal
2. Go to "Payment Methods"
3. Add/update card
4. Set as default

### Cancel Subscription

1. Log in to Stripe portal
2. Go to "Subscriptions"
3. Click "Cancel subscription"
4. Confirm cancellation

**Note**: License key remains valid until end of billing period.

---

## Team License Management

### Adding Team Members

Enterprise/Team plans include multiple seats.

**Option 1**: Shared key (simple)
```bash
# All team members use same key
export HEFESTO_LICENSE_KEY='hef_team_...'
```

**Option 2**: Individual keys (coming in v3.6)
```bash
# Each developer gets unique key
export HEFESTO_LICENSE_KEY='hef_user_alice_...'
```

---

## Troubleshooting

### License not recognized

**Symptom**:
```
LicenseError: Phase 1 requires Pro license
```

**Solutions**:
1. Check key is set: `echo $HEFESTO_LICENSE_KEY`
2. Verify key format starts with `hef_`, `sk_`, or `pk_`
3. Check subscription active in Stripe portal
4. Restart application after setting key

### Features still locked

**Symptom**:
```python
from hefesto.llm.semantic_analyzer import get_semantic_analyzer
# ImportError: No module named 'sentence_transformers'
```

**Solution**:
```bash
pip install hefesto-ai[pro]  # Install Pro dependencies
```

### License expired

**Symptom**:
```
LicenseError: License expired
```

**Solution**:
1. Check Stripe portal for payment issues
2. Update payment method
3. Contact support@narapallc.com if needed

---

## Pricing

| Plan | Monthly | Users | Features |
|------|---------|-------|----------|
| **Free** | $0 | ∞ | Phase 0 only |
| **Hefesto Professional** | $25 | 5 | Code Quality AI |
| **OMEGA Founding Members** | $35 | 10 | Complete Suite (limited to 50 teams) |
| **OMEGA Professional** | $49 | 15 | Complete DevOps AI Suite |
| **Enterprise** | Custom | Custom | SLA + Support + Custom integrations |

**Note:** Annual pricing discontinued. Contact sales for custom annual contracts.

---

## Support

### Free Tier
- GitHub Issues
- Community support
- 48-hour response time

### Pro Tier
- Priority email support (support@narapallc.com)
- 24-hour response time
- Direct Slack channel (Enterprise)

### Enterprise
- Dedicated account manager
- Custom SLA
- Phone support
- On-site training (additional fee)

---

## FAQ

**Q: Can I try Pro before buying?**  
A: Yes! Email sales@narapallc.com for 14-day trial key.

**Q: What happens if I cancel?**  
A: License valid until end of billing period, then Pro features disabled.

**Q: Can I transfer license?**  
A: Enterprise licenses can be transferred. Contact sales@narapallc.com

**Q: Refund policy?**  
A: 30-day money-back guarantee, no questions asked.

**Q: Educational discount?**  
A: 50% off for students/educators. Email edu@narapallc.com with proof.

---

**Questions?** sales@narapallc.com

