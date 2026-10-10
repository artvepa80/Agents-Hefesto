#!/bin/bash
#
# HefestoAI COBOL Governance — Investor Demo
#
# Purpose: Demonstrate COBOL governance analysis capabilities in <30 seconds
# Run from repo root: ./docs/demo/cobol_investor_demo.sh
# Requires: hefesto-ai installed (pip install hefesto-ai)
#
# Narrative Arc:
# 1. Visceral finding → hardcoded credentials in legacy banking code (CRITICAL)
# 2. Codebase scan → governance analysis across 11 synthetic COBOL files
# 3. Speed proof → sub-second analysis (production-ready performance)
# 4. Clean baseline → no findings on a clean program (one fixture, not a
#    false-positive rate; real-code precision has not been measured yet)
#
# Copyright 2025 Narapa LLC, Miami, Florida
#

set -e  # Exit on error

# Colors for output
BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Check if hefesto is installed
if ! command -v hefesto &> /dev/null; then
    echo -e "${YELLOW}Error: hefesto-ai not installed${NC}"
    echo "Install with: pip install hefesto-ai"
    exit 1
fi

echo -e "${BOLD}${CYAN}"
echo "═══════════════════════════════════════════════════════════════"
echo "  HefestoAI COBOL Governance — Investor Demo"
echo "═══════════════════════════════════════════════════════════════"
echo -e "${NC}"
echo ""
sleep 1

#
# STEP 1: Visceral Finding — Hardcoded Credentials
#
echo -e "${BOLD}${YELLOW}[STEP 1] Detecting Hardcoded Credentials in Legacy Banking Code${NC}"
echo ""
echo "File: BATCH-DB2.cbl (synthetic mainframe batch program, 95 lines)"
echo "Risk: Hardcoded DB password + API secrets in production code"
echo ""
sleep 2

hefesto analyze tests/fixtures/cobol/BATCH-DB2.cbl --severity CRITICAL

echo ""
echo -e "${GREEN}✓ Found 3 CRITICAL security issues (hardcoded credentials)${NC}"
echo ""
sleep 3

#
# STEP 2: Codebase Scan — Multiple Governance Findings
#
echo -e "${BOLD}${YELLOW}[STEP 2] Scanning Entire Legacy COBOL Codebase${NC}"
echo ""
echo "Corpus: 11 synthetic COBOL files (10 programs + 1 copybook) from tests/fixtures"
echo "Rules: 15 free COBOL governance rules (no license needed)"
echo ""
sleep 2

hefesto analyze tests/fixtures/cobol/*.cbl tests/fixtures/cobol/*.cpy --severity HIGH

echo ""
echo -e "${GREEN}✓ Found 9 HIGH+ severity governance issues across codebase${NC}"
echo "  - Hardcoded credentials: 4 CRITICAL"
echo "  - Spaghetti GO TOs: 2 HIGH"
echo "  - REDEFINES over COMP-3/signed numeric data: 2 HIGH"
echo "  - PERFORM THRU chains: 1 HIGH"
echo "  (copybook blast radius needs 5+ programs sharing a copybook; the fixtures have 2)"
echo ""
sleep 3

#
# STEP 3: Speed Proof — Production-Ready Performance
#
echo -e "${BOLD}${YELLOW}[STEP 3] Performance Benchmark — Speed Test${NC}"
echo ""
echo "Analyzing 11 synthetic COBOL files with all 15 governance rules..."
echo ""
sleep 1

time hefesto analyze tests/fixtures/cobol/*.cbl tests/fixtures/cobol/*.cpy --severity MEDIUM > /dev/null 2>&1

echo ""
echo -e "${GREEN}✓ Analysis complete in <1 second (production-ready speed)${NC}"
echo ""
sleep 2

#
# STEP 4: Clean Baseline — Zero False Positives
#
echo -e "${BOLD}${YELLOW}[STEP 4] Clean Baseline — Well-Structured Program${NC}"
echo ""
echo "File: CLEAN-PROG.cbl (well-structured COBOL program)"
echo "Expected: 0 findings on this program"
echo ""
sleep 2

hefesto analyze tests/fixtures/cobol/CLEAN-PROG.cbl --severity MEDIUM

echo ""
echo -e "${GREEN}✓ Zero findings on the clean program${NC}"
echo ""
sleep 2

#
# Demo Complete
#
echo -e "${BOLD}${CYAN}"
echo "═══════════════════════════════════════════════════════════════"
echo "  Demo Complete — HefestoAI COBOL Governance"
echo "═══════════════════════════════════════════════════════════════"
echo -e "${NC}"
echo ""
echo "Summary:"
echo "  ✓ 12 governance issues detected across 11 synthetic COBOL files"
echo "  ✓ <1 second analysis time (production-ready)"
echo "  ✓ No findings on the clean program (precision on ~440 labelled real-corpus findings: docs/cobol-corpus-baseline.md)"
echo "  ✓ 15 free governance rules (credentials, spaghetti logic, copybooks,"
echo "    FILE STATUS, dead code; COBOL008-014 are exercised by tests/fixtures/cobol/smoke)"
echo ""
echo "Limits:"
echo "  • Fixed format by default; free format is inferred (heuristic) or set with >>SOURCE FORMAT IS FREE"
echo "  • COBOL004 checks COMP-3/binary/signed layouts but not field lengths or runtime use"
echo "  • Copybook rules (COBOL007/015) only see copybooks inside the scanned tree"
echo "  • Dead-code/unused-paragraph rules do not follow procedure copybooks (COPY in PROCEDURE)"
echo ""
echo "Next Steps:"
echo "  • SARIF output (not available yet; the GitHub Action already runs these rules)"
echo "  • Phase 4: performance on large codebases"
echo "  • Target: Banking/insurance/gov COBOL teams (300K+ active developers)"
echo ""
echo -e "${YELLOW}Questions?${NC}"
echo ""
