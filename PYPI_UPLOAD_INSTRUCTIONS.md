# PyPI Upload Instructions for Hefesto v4.0.1

## Prerequisites

1. **PyPI Account**: https://pypi.org/account/register/
2. **API Token**: https://pypi.org/manage/account/token/
   - Token name: "hefesto-upload"
   - Scope: Project (hefesto-ai)

## Step 1: Configure Credentials

Create `.pypirc` in home directory:
```bash
cat > ~/.pypirc << 'EOF'
[pypi]
username = __token__
password = pypi-YOUR-API-TOKEN-HERE

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-YOUR-TEST-API-TOKEN-HERE
EOF

chmod 600 ~/.pypirc
```

**IMPORTANT:** Replace `pypi-YOUR-API-TOKEN-HERE` with actual token from PyPI.

## Step 2: Build Distribution

```bash
cd /Users/user/Library/CloudStorage/OneDrive-Personal/Agents-Hefesto

# Clean previous builds
rm -rf dist/ build/ *.egg-info

# Build
python3 -m build

# Verify files
ls -lh dist/
# Should show:
# - hefesto_ai-4.0.1-py3-none-any.whl
# - hefesto-ai-4.0.1.tar.gz
```

## Step 3: Upload to PyPI

### Test Upload (Recommended First)
```bash
python3 -m twine upload --repository testpypi dist/*
```

Verify on Test PyPI: https://test.pypi.org/project/hefesto-ai/

### Production Upload
```bash
python3 -m twine upload dist/*
```

## Step 4: Verify Publication

```bash
# Wait 1-2 minutes for PyPI indexing

# Install from PyPI
pip install hefesto-ai==4.0.1

# Verify
hefesto --version  # Should output: 4.0.1

# Check PyPI page
open https://pypi.org/project/hefesto-ai/
```

## Troubleshooting

### "Invalid credentials"
- Verify token in .pypirc
- Token must start with `pypi-`
- Check token hasn't expired

### "File already exists"
- Version 4.0.1 already uploaded
- Increment version or contact PyPI support

## Post-Upload Checklist

- [ ] Package visible on PyPI
- [ ] `pip install hefesto-ai` works
- [ ] CLI commands functional
- [ ] API server starts
- [ ] Documentation links work
- [ ] GitHub release created (v4.0.1)

## Contact

Questions: arturo@narapa.com
