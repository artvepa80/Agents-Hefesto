#!/bin/bash
# End-to-end testing script for Hefesto
# Tests all critical paths before launch

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}🧪 HEFESTO E2E TESTING SUITE${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}\n"

PASSED=0
FAILED=0

# Function to test a command
test_command() {
    local test_name=$1
    local command=$2
    local expected_in_output=$3
    
    echo -e "\n${YELLOW}Testing: ${test_name}${NC}"
    echo "Command: ${command}"
    
    if output=$(eval "$command" 2>&1); then
        if [[ -z "$expected_in_output" ]] || echo "$output" | grep -q "$expected_in_output"; then
            echo -e "${GREEN}✅ PASSED${NC}"
            ((PASSED++))
            return 0
        else
            echo -e "${RED}❌ FAILED - Expected output not found: ${expected_in_output}${NC}"
            echo "Output: $output"
            ((FAILED++))
            return 1
        fi
    else
        echo -e "${RED}❌ FAILED - Command returned error${NC}"
        echo "Error: $output"
        ((FAILED++))
        return 1
    fi
}

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}PHASE 1: Installation & Setup${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

test_command \
    "Local installation" \
    "pip install -e . > /dev/null 2>&1 && echo 'installed'" \
    "installed"

test_command \
    "CLI available" \
    "hefesto --help" \
    "Usage:"

test_command \
    "Config directory creation" \
    "python -c 'from hefesto.config.config_manager import ConfigManager; c = ConfigManager(); print(\"config_ok\")'" \
    "config_ok"

echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}PHASE 2: Free Tier Testing${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Clear any existing license
python -c "from hefesto.config.config_manager import ConfigManager; c = ConfigManager(); c.clear_license()" 2>/dev/null || true

test_command \
    "Default to free tier" \
    "hefesto status" \
    "Free"

test_command \
    "Free tier limits shown" \
    "hefesto status" \
    "Repositories: 1"

test_command \
    "Free tier LOC limit" \
    "hefesto status" \
    "50,000"

echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}PHASE 3: License Key Validation${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

test_command \
    "Reject invalid key format (too short)" \
    "hefesto activate INVALID 2>&1" \
    "Invalid license key format"

test_command \
    "Reject invalid key format (wrong prefix)" \
    "hefesto activate ABCD-1234-5678-9ABC-DEF0-1234 2>&1" \
    "Invalid license key format"

test_command \
    "Accept valid key format" \
    "hefesto activate HFST-1234-5678-9ABC-DEF0-1234" \
    "License activated successfully"

echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}PHASE 4: Professional Tier Testing${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

test_command \
    "Show Professional tier after activation" \
    "hefesto status" \
    "Professional"

test_command \
    "Show Pro tier limits (25 repos)" \
    "hefesto status" \
    "Repositories: 25"

test_command \
    "Show Pro tier limits (500K LOC)" \
    "hefesto status" \
    "500,000"

test_command \
    "Show Pro tier limits (unlimited runs)" \
    "hefesto status" \
    "Unlimited"

test_command \
    "Show Pro features available" \
    "hefesto status" \
    "ML semantic code analysis"

echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}PHASE 5: License Management${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

test_command \
    "Deactivate license" \
    "echo 'y' | hefesto deactivate" \
    "License deactivated"

test_command \
    "Revert to free tier after deactivation" \
    "hefesto status" \
    "Free"

# Reactivate for remaining tests
hefesto activate HFST-1234-5678-9ABC-DEF0-1234 > /dev/null 2>&1

echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}PHASE 6: Feature Gating${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

test_command \
    "FeatureGate imports correctly" \
    "python -c 'from hefesto.licensing import FeatureGate; print(\"imported\")'" \
    "imported"

test_command \
    "Get current tier programmatically" \
    "python -c 'from hefesto.licensing import FeatureGate; print(FeatureGate.get_current_tier())'" \
    "professional"

test_command \
    "Check feature access for Pro user" \
    "python -c 'from hefesto.licensing import FeatureGate; has_access, msg = FeatureGate.check_feature_access(\"ml_semantic_analysis\"); print(\"has_access\" if has_access else \"denied\")'" \
    "has_access"

# Test with free tier
echo 'y' | hefesto deactivate > /dev/null 2>&1

test_command \
    "Deny Pro features for Free tier" \
    "python -c 'from hefesto.licensing import FeatureGate; has_access, msg = FeatureGate.check_feature_access(\"ml_semantic_analysis\"); print(\"denied\" if not has_access else \"has_access\")'" \
    "denied"

# Restore Pro tier
hefesto activate HFST-1234-5678-9ABC-DEF0-1234 > /dev/null 2>&1

echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}PHASE 7: Stripe Configuration${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

test_command \
    "Stripe config loads correctly" \
    "python -c 'from hefesto.config.stripe_config import STRIPE_CONFIG; print(\"loaded\" if STRIPE_CONFIG else \"failed\")'" \
    "loaded"

test_command \
    "Stripe products configured" \
    "python -c 'from hefesto.config.stripe_config import STRIPE_CONFIG; print(\"configured\" if \"products\" in STRIPE_CONFIG else \"missing\")'" \
    "configured"

test_command \
    "Stripe payment links configured" \
    "python -c 'from hefesto.config.stripe_config import STRIPE_CONFIG; print(\"configured\" if \"payment_links\" in STRIPE_CONFIG else \"missing\")'" \
    "configured"

test_command \
    "Founding member coupon configured" \
    "python -c 'from hefesto.config.stripe_config import STRIPE_CONFIG; print(\"configured\" if STRIPE_CONFIG[\"coupons\"][\"founding_member\"][\"discount_percent\"] == 40 else \"wrong\")'" \
    "configured"

echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}PHASE 8: License Key Generation${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

test_command \
    "Generate valid license key" \
    "python -c 'from hefesto.licensing import LicenseKeyGenerator; key = LicenseKeyGenerator.generate(\"test@example.com\", \"professional\", \"sub_test123\", True); print(\"generated\" if key.startswith(\"HFST-\") else \"invalid\")'" \
    "generated"

test_command \
    "Validate correct key format" \
    "python -c 'from hefesto.licensing import LicenseKeyGenerator; print(\"valid\" if LicenseKeyGenerator.validate_format(\"HFST-1234-5678-9ABC-DEF0-1234\") else \"invalid\")'" \
    "valid"

test_command \
    "Reject incorrect key format" \
    "python -c 'from hefesto.licensing import LicenseKeyGenerator; print(\"invalid\" if not LicenseKeyGenerator.validate_format(\"INVALID-KEY\") else \"valid\")'" \
    "invalid"

echo -e "\n${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}TEST RESULTS${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"

echo -e "\n${GREEN}✅ Passed: ${PASSED}${NC}"
echo -e "${RED}❌ Failed: ${FAILED}${NC}"

if [ $FAILED -eq 0 ]; then
    echo -e "\n${GREEN}🎉 ALL TESTS PASSED! System is ready for launch! 🚀${NC}\n"
    exit 0
else
    echo -e "\n${RED}⚠️  Some tests failed. Please fix issues before launching.${NC}\n"
    exit 1
fi

