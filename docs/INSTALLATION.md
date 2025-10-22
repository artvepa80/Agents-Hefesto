# Hefesto Installation Guide

## Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Google Cloud Project (for BigQuery tracking, optional)
- Gemini API key (get from https://aistudio.google.com/app/apikey)

## Installation Methods

### Method 1: PyPI (Recommended)

```bash
# Free version (Phase 0)
pip install hefesto

# Pro version (Phase 1)
pip install hefesto-ai[pro]
```

### Method 2: From Source

```bash
# Clone repository
git clone https://github.com/artvepa80/Agents-Hefesto.git
cd Agents-Hefesto

# Install in development mode
pip install -e .

# Or with Pro features
pip install -e ".[pro]"
```

### Method 3: Docker

```bash
# Pull image
docker pull ghcr.io/artvepa80/hefesto:latest

# Run server
docker run -p 8080:8080 \
  -e GEMINI_API_KEY='your_key' \
  ghcr.io/artvepa80/hefesto:latest
```

## Configuration

### 1. Set API Key

```bash
# Get key from: https://aistudio.google.com/app/apikey
export GEMINI_API_KEY='your_gemini_api_key_here'
```

### 2. Configure GCP (Optional)

For BigQuery tracking and cost monitoring:

```bash
export GCP_PROJECT_ID='your-project-id'
```

### 3. Set Budget Limits (Optional)

```bash
export HEFESTO_DAILY_BUDGET_USD='10.0'
export HEFESTO_MONTHLY_BUDGET_USD='200.0'
```

### 4. Pro License (Phase 1)

```bash
# After purchasing Pro license
export HEFESTO_LICENSE_KEY='hef_your_pro_license_key'
```

## Verify Installation

```bash
# Check version
hefesto --version

# Check installation
hefesto check

# Show configuration
hefesto info
```

## Quick Test

```bash
# Start server
hefesto serve

# In another terminal, test
curl http://localhost:8080/ping

# Expected: {"ok": true, "version": "3.5.0", ...}
```

## Troubleshooting

### ImportError: No module named 'hefesto'

**Solution**:
```bash
pip install --upgrade hefesto
```

### GEMINI_API_KEY not set

**Solution**:
```bash
export GEMINI_API_KEY='your_key'
# Get key: https://aistudio.google.com/app/apikey
```

### Pro features not working

**Solution**:
```bash
# Install Pro dependencies
pip install hefesto-ai[pro]

# Set license key
export HEFESTO_LICENSE_KEY='hef_your_key'

# Verify
hefesto info  # Should show "Pro Features: ✅ Enabled"
```

### BigQuery permission errors

**Solution**:
```bash
# Authenticate with GCP
gcloud auth application-default login

# Or use service account
export GOOGLE_APPLICATION_CREDENTIALS='/path/to/key.json'
```

## Uninstallation

```bash
pip uninstall hefesto
```

## Next Steps

- Read [Quick Start Guide](QUICK_START.md)
- Review [API Reference](API_REFERENCE.md)
- Check [Examples](../examples/)
- Purchase [Pro License](https://buy.stripe.com/hefesto-pro) for advanced features

---

**Support**: support@narapallc.com

