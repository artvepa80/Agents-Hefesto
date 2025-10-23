# 📋 Analysis Rules Reference

**Complete documentation of all 22+ code quality checks in Hefesto.**

---

## Table of Contents

1. [Complexity Issues](#1-complexity-issues)
2. [Security Vulnerabilities](#2-security-vulnerabilities)
3. [Code Smells](#3-code-smells)
4. [Best Practices](#4-best-practices)
5. [Severity Guidelines](#5-severity-guidelines)

---

## 1. Complexity Issues

### 1.1 High Cyclomatic Complexity

**Rule ID:** `COMPLEXITY_001`

**Description:** Functions with too many decision points become hard to understand, test, and maintain.

**Detection Logic:**
- Counts decision points: `if`, `while`, `for`, `and`, `or`, `elif`, `except`, `with`
- Each decision point adds +1 to complexity score

**Severity Levels:**
- **MEDIUM:** Complexity 6-10
- **HIGH:** Complexity 11-20
- **CRITICAL:** Complexity 21+

**Example - BAD (Complexity = 15):**

```python
def process_order(order, user, payment, shipping):
    if not order:
        return None

    if user.is_authenticated:
        if user.has_credit:
            if order.total > 0:
                if payment.is_valid:
                    if payment.amount >= order.total:
                        if shipping.is_available:
                            if shipping.address:
                                if shipping.address.is_valid:
                                    if order.items:
                                        if all(item.in_stock for item in order.items):
                                            # Process order
                                            return True
    return False
```

**Example - GOOD (Complexity = 4):**

```python
def process_order(order, user, payment, shipping):
    # Early returns reduce nesting
    if not order or not order.items:
        return False

    if not _validate_user(user):
        return False

    if not _validate_payment(payment, order.total):
        return False

    if not _validate_shipping(shipping):
        return False

    return _complete_order(order)

def _validate_user(user):
    return user.is_authenticated and user.has_credit

def _validate_payment(payment, total):
    return payment.is_valid and payment.amount >= total

def _validate_shipping(shipping):
    return (shipping.is_available and
            shipping.address and
            shipping.address.is_valid)
```

**Why It Matters:**
- Hard to test (need 2^n test cases for n decision points)
- Higher bug probability
- Difficult to understand and modify
- Code review takes longer

**Refactoring Strategies:**
1. Extract complex conditions into helper functions
2. Use early returns to reduce nesting
3. Replace nested conditionals with guard clauses
4. Consider strategy pattern for complex branching

---

## 2. Security Vulnerabilities

### 2.1 Hardcoded Secrets

**Rule ID:** `SECURITY_001`

**Severity:** CRITICAL

**Description:** API keys, passwords, tokens hardcoded in source code.

**Detection Patterns:**
```python
# Detects patterns like:
api_key = "sk-proj-..."      # OpenAI API keys
API_KEY = "AIza..."          # Google API keys
password = "secret123"       # Passwords
token = "ghp_..."            # GitHub tokens
AWS_ACCESS_KEY = "AKIA..."  # AWS credentials
```

**Example - BAD:**

```python
# ❌ CRITICAL: Secret exposed in code
STRIPE_API_KEY = "sk_live_51H1234567890"
OPENAI_API_KEY = "sk-proj-abcdef123456"
DATABASE_URL = "postgresql://user:password@localhost/db"
```

**Example - GOOD:**

```python
# ✅ Load from environment
import os
from dotenv import load_dotenv

load_dotenv()

STRIPE_API_KEY = os.getenv("STRIPE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

# Validate that secrets are loaded
if not STRIPE_API_KEY:
    raise ValueError("STRIPE_API_KEY not found in environment")
```

**Why It Matters:**
- Secrets leaked to version control
- Anyone with repo access can steal credentials
- Difficult to rotate compromised keys
- Compliance violations (PCI, SOC2, etc.)

---

### 2.2 SQL Injection Risk

**Rule ID:** `SECURITY_002`

**Severity:** CRITICAL

**Description:** Dynamic SQL queries vulnerable to SQL injection attacks.

**Example - BAD:**

```python
# ❌ CRITICAL: SQL injection vulnerability
def get_user(username):
    query = f"SELECT * FROM users WHERE username = '{username}'"
    return db.execute(query)

# Attacker input: "admin' OR '1'='1"
# Resulting query: SELECT * FROM users WHERE username = 'admin' OR '1'='1'
# Returns all users!
```

**Example - GOOD:**

```python
# ✅ Use parameterized queries
def get_user(username):
    query = "SELECT * FROM users WHERE username = ?"
    return db.execute(query, (username,))

# OR with ORM
def get_user(username):
    return User.objects.filter(username=username).first()
```

**Why It Matters:**
- Full database compromise possible
- Data theft and manipulation
- Authentication bypass
- OWASP Top 10 vulnerability

---

### 2.3 Dangerous eval() Usage

**Rule ID:** `SECURITY_003`

**Severity:** CRITICAL

**Description:** Using `eval()` or `exec()` with untrusted input allows arbitrary code execution.

**Example - BAD:**

```python
# ❌ CRITICAL: Code injection vulnerability
def calculate(expression):
    result = eval(expression)  # User can execute ANY Python code!
    return result

# Attacker input: "__import__('os').system('rm -rf /')"
# System compromised!
```

**Example - GOOD:**

```python
# ✅ Use safe alternatives
import ast
import operator

OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}

def calculate(expression):
    tree = ast.parse(expression, mode='eval')
    # Validate that expression only contains safe operations
    return _eval_node(tree.body)

# OR use a safe expression library
from simpleeval import simple_eval
result = simple_eval(expression, functions={"abs": abs, "min": min})
```

**Why It Matters:**
- Complete system compromise
- Remote code execution (RCE)
- Data theft and destruction
- OWASP Top 10 vulnerability

---

### 2.4 Unsafe Deserialization (pickle)

**Rule ID:** `SECURITY_004`

**Severity:** HIGH

**Description:** `pickle.load()` can execute arbitrary code during deserialization.

**Example - BAD:**

```python
# ❌ HIGH: Pickle can execute code
import pickle

def load_data(filename):
    with open(filename, 'rb') as f:
        return pickle.load(f)  # Can execute arbitrary code!
```

**Example - GOOD:**

```python
# ✅ Use safe serialization formats
import json

def load_data(filename):
    with open(filename, 'r') as f:
        return json.load(f)

# OR for complex objects
import jsonpickle

def load_data(filename):
    with open(filename, 'r') as f:
        return jsonpickle.decode(f.read())
```

**Why It Matters:**
- Code execution via malicious pickle files
- Hard to detect malicious payloads
- No safe way to unpickle untrusted data

---

### 2.5 Assert in Production

**Rule ID:** `SECURITY_005`

**Severity:** MEDIUM

**Description:** `assert` statements are removed when Python runs in optimized mode (`-O` flag).

**Example - BAD:**

```python
# ❌ MEDIUM: Assert removed in production
def process_payment(amount, user):
    assert user.is_authenticated, "User must be authenticated"
    assert amount > 0, "Amount must be positive"
    # Process payment

# When running with `python -O app.py`:
# - Asserts are completely removed
# - No validation happens!
```

**Example - GOOD:**

```python
# ✅ Use explicit validation
def process_payment(amount, user):
    if not user.is_authenticated:
        raise ValueError("User must be authenticated")
    if amount <= 0:
        raise ValueError("Amount must be positive")
    # Process payment
```

**Why It Matters:**
- Security checks bypassed in production
- Silent failures and unexpected behavior
- Cannot rely on asserts for validation

---

### 2.6 Bare Except Clause

**Rule ID:** `SECURITY_006`

**Severity:** MEDIUM

**Description:** Catching all exceptions can hide bugs and security issues.

**Example - BAD:**

```python
# ❌ MEDIUM: Hides all errors including KeyboardInterrupt
def process_data(data):
    try:
        result = dangerous_operation(data)
        return result
    except:  # Catches EVERYTHING
        return None

# Problems:
# - Hides KeyboardInterrupt (can't stop program)
# - Hides SystemExit (can't exit cleanly)
# - Hides actual bugs
```

**Example - GOOD:**

```python
# ✅ Catch specific exceptions
def process_data(data):
    try:
        result = dangerous_operation(data)
        return result
    except ValueError as e:
        logger.error(f"Invalid data: {e}")
        return None
    except IOError as e:
        logger.error(f"IO error: {e}")
        raise
```

**Why It Matters:**
- Security errors silently swallowed
- Debugging nightmares
- Masks underlying issues
- Program can't be interrupted

---

## 3. Code Smells

### 3.1 Long Function

**Rule ID:** `SMELL_001`

**Severity:** MEDIUM (>50 lines), HIGH (>100 lines)

**Description:** Functions should do one thing. Long functions do too many things.

**Example - BAD:**

```python
# ❌ MEDIUM: 78 lines, does everything
def process_user_registration(email, password, name, address, phone,
                             payment_method, subscription_tier, referral_code):
    # Validate email (10 lines)
    if not email or '@' not in email:
        # ... validation logic
        pass

    # Validate password (15 lines)
    if len(password) < 8:
        # ... validation logic
        pass

    # Create user (10 lines)
    user = User()
    # ... user creation

    # Send welcome email (10 lines)
    # ... email sending

    # Process payment (15 lines)
    # ... payment processing

    # Apply referral code (10 lines)
    # ... referral logic

    # Log analytics (8 lines)
    # ... analytics

    return user
```

**Example - GOOD:**

```python
# ✅ Each function has single responsibility
def process_user_registration(email, password, name, address, phone,
                             payment_method, subscription_tier, referral_code):
    # Validate
    _validate_email(email)
    _validate_password(password)

    # Create user
    user = _create_user(email, password, name, address, phone)

    # Setup subscription
    _setup_subscription(user, payment_method, subscription_tier)

    # Apply benefits
    if referral_code:
        _apply_referral(user, referral_code)

    # Notify
    _send_welcome_email(user)
    _log_registration(user)

    return user
```

**Why It Matters:**
- Hard to understand
- Hard to test
- Hard to reuse
- High chance of bugs

---

### 3.2 Long Parameter List

**Rule ID:** `SMELL_002`

**Severity:** LOW (6-7 params), MEDIUM (8-10 params), HIGH (>10 params)

**Description:** Functions with many parameters are hard to call and maintain.

**Example - BAD:**

```python
# ❌ HIGH: 11 parameters
def create_order(user_id, product_id, quantity, price, tax, shipping_cost,
                discount_code, shipping_address, billing_address,
                payment_method, notes):
    pass
```

**Example - GOOD:**

```python
# ✅ Use data classes or dictionaries
from dataclasses import dataclass

@dataclass
class OrderDetails:
    user_id: str
    product_id: str
    quantity: int
    price: float

@dataclass
class PricingInfo:
    tax: float
    shipping_cost: float
    discount_code: Optional[str]

@dataclass
class DeliveryInfo:
    shipping_address: str
    billing_address: str
    payment_method: str
    notes: Optional[str]

def create_order(details: OrderDetails, pricing: PricingInfo,
                delivery: DeliveryInfo):
    pass
```

**Why It Matters:**
- Easy to mix up parameter order
- Difficult to extend
- Hard to read at call sites
- Testing becomes complex

---

### 3.3 Deep Nesting

**Rule ID:** `SMELL_003`

**Severity:** LOW (4 levels), MEDIUM (5 levels), HIGH (6+ levels)

**Description:** Deep nesting makes code hard to follow and reason about.

**Example - BAD:**

```python
# ❌ HIGH: 6 levels of nesting
def process(data):
    if data:
        if data.is_valid:
            if data.user:
                if data.user.is_active:
                    if data.user.has_permission:
                        if data.user.subscription.is_active:
                            # Finally do something
                            return process_data(data)
    return None
```

**Example - GOOD:**

```python
# ✅ Use guard clauses
def process(data):
    # Guard clauses at the top
    if not data:
        return None
    if not data.is_valid:
        return None
    if not data.user or not data.user.is_active:
        return None
    if not data.user.has_permission:
        return None
    if not data.user.subscription.is_active:
        return None

    # Happy path at the end with no nesting
    return process_data(data)
```

**Why It Matters:**
- Cognitive load increases exponentially
- Hard to track state at each level
- Error handling becomes complex
- Testing requires many nested conditions

---

### 3.4 Magic Numbers

**Rule ID:** `SMELL_004`

**Severity:** LOW

**Description:** Numbers without clear meaning reduce code readability.

**Example - BAD:**

```python
# ❌ LOW: What do these numbers mean?
def calculate_price(base_price):
    if base_price > 100:
        return base_price * 0.85
    elif base_price > 50:
        return base_price * 0.90
    return base_price * 0.95
```

**Example - GOOD:**

```python
# ✅ Named constants explain intent
BULK_DISCOUNT_THRESHOLD = 100
BULK_DISCOUNT_RATE = 0.85

STANDARD_DISCOUNT_THRESHOLD = 50
STANDARD_DISCOUNT_RATE = 0.90

MINIMUM_DISCOUNT_RATE = 0.95

def calculate_price(base_price):
    if base_price > BULK_DISCOUNT_THRESHOLD:
        return base_price * BULK_DISCOUNT_RATE
    elif base_price > STANDARD_DISCOUNT_THRESHOLD:
        return base_price * STANDARD_DISCOUNT_RATE
    return base_price * MINIMUM_DISCOUNT_RATE
```

**Why It Matters:**
- Reduces readability
- Hard to maintain (change in multiple places)
- No context for why number was chosen
- Can't search for usage

---

### 3.5 Duplicate Code

**Rule ID:** `SMELL_005`

**Severity:** MEDIUM

**Description:** Identical or very similar code in multiple places.

**Example - BAD:**

```python
# ❌ MEDIUM: Duplicated validation logic
def create_user(email, password):
    if not email or '@' not in email:
        raise ValueError("Invalid email")
    if len(password) < 8:
        raise ValueError("Password too short")
    # Create user...

def update_user(user_id, email, password):
    if not email or '@' not in email:
        raise ValueError("Invalid email")
    if len(password) < 8:
        raise ValueError("Password too short")
    # Update user...
```

**Example - GOOD:**

```python
# ✅ Extract common logic
def validate_email(email):
    if not email or '@' not in email:
        raise ValueError("Invalid email")

def validate_password(password):
    if len(password) < 8:
        raise ValueError("Password too short")

def create_user(email, password):
    validate_email(email)
    validate_password(password)
    # Create user...

def update_user(user_id, email, password):
    validate_email(email)
    validate_password(password)
    # Update user...
```

**Why It Matters:**
- Bug fixes needed in multiple places
- Inconsistent behavior over time
- Increases codebase size
- Makes refactoring harder

---

### 3.6 God Class

**Rule ID:** `SMELL_006`

**Severity:** HIGH

**Description:** Classes with too many responsibilities (>500 lines).

**Example - BAD:**

```python
# ❌ HIGH: 800 lines, does everything
class UserManager:
    def create_user(self): pass
    def update_user(self): pass
    def delete_user(self): pass
    def send_email(self): pass
    def send_sms(self): pass
    def process_payment(self): pass
    def refund_payment(self): pass
    def generate_report(self): pass
    def export_csv(self): pass
    def import_csv(self): pass
    def validate_email(self): pass
    def hash_password(self): pass
    def check_permissions(self): pass
    # ... 50 more methods
```

**Example - GOOD:**

```python
# ✅ Split into focused classes
class UserRepository:
    def create(self, user): pass
    def update(self, user): pass
    def delete(self, user_id): pass

class NotificationService:
    def send_email(self, to, subject, body): pass
    def send_sms(self, to, message): pass

class PaymentProcessor:
    def process_payment(self, amount, method): pass
    def refund_payment(self, transaction_id): pass

class UserValidator:
    def validate_email(self, email): pass
    def validate_password(self, password): pass
```

**Why It Matters:**
- Violates Single Responsibility Principle
- Hard to test
- Changes affect many areas
- Difficult to reuse

---

### 3.7 Incomplete TODOs/FIXMEs

**Rule ID:** `SMELL_007`

**Severity:** LOW

**Description:** Unfinished work or known issues left in code.

**Example - BAD:**

```python
# ❌ LOW: Vague TODOs without context
def process_payment(amount):
    # TODO: Fix this
    result = legacy_process(amount)

    # FIXME: Sometimes fails
    save_to_db(result)

    # TODO: Optimize
    return result
```

**Example - GOOD:**

```python
# ✅ Clear, actionable TODOs with context
def process_payment(amount):
    # TODO(john, 2025-02-01): Replace with new Stripe API v3
    # Current implementation uses deprecated v2 API
    # Ticket: JIRA-1234
    result = legacy_process(amount)

    # FIXME(sarah, 2025-02-15): Fails when amount > 10000
    # Add validation or split into multiple transactions
    # Ticket: JIRA-1235
    save_to_db(result)

    return result
```

**Why It Matters:**
- Incomplete work accumulates
- No accountability
- Can't prioritize fixes
- Indicates potential bugs

---

### 3.8 Commented-Out Code

**Rule ID:** `SMELL_008`

**Severity:** LOW

**Description:** Dead code left as comments clutters the codebase.

**Example - BAD:**

```python
# ❌ LOW: Commented code confuses readers
def calculate_total(items):
    total = sum(item.price for item in items)

    # Old calculation method
    # total = 0
    # for item in items:
    #     total += item.price
    #     if item.discount:
    #         total -= item.discount

    return total
```

**Example - GOOD:**

```python
# ✅ Remove dead code, use version control
def calculate_total(items):
    # Calculate base total
    total = sum(item.price for item in items)

    # Apply discounts
    total -= sum(item.discount for item in items if item.discount)

    return total

# If you need old code, check git history:
# git log -p -- file.py
```

**Why It Matters:**
- Clutters codebase
- Confuses readers (is it important?)
- Version control already tracks history
- Can't tell if it should be used

---

## 4. Best Practices

### 4.1 Missing Docstrings

**Rule ID:** `PRACTICE_001`

**Severity:** LOW

**Description:** Public functions and classes should have docstrings.

**Example - BAD:**

```python
# ❌ LOW: No documentation
def calculate_discount(price, tier, referral):
    if tier == "premium":
        discount = 0.20
    elif tier == "standard":
        discount = 0.10
    else:
        discount = 0.05

    if referral:
        discount += 0.05

    return price * (1 - discount)
```

**Example - GOOD:**

```python
# ✅ Clear documentation
def calculate_discount(price: float, tier: str, referral: bool) -> float:
    """Calculate final price after applying tier and referral discounts.

    Args:
        price: Base price before discounts
        tier: Customer tier ("premium", "standard", or "basic")
        referral: Whether customer used a referral code

    Returns:
        Final price after all discounts applied

    Examples:
        >>> calculate_discount(100.0, "premium", True)
        75.0  # 20% tier + 5% referral = 25% total
    """
    if tier == "premium":
        discount = 0.20
    elif tier == "standard":
        discount = 0.10
    else:
        discount = 0.05

    if referral:
        discount += 0.05

    return price * (1 - discount)
```

**Why It Matters:**
- Helps other developers understand code
- Auto-generates API documentation
- Makes code more maintainable
- Clarifies intent and edge cases

---

### 4.2 Poor Variable Naming

**Rule ID:** `PRACTICE_002`

**Severity:** LOW

**Description:** Single-letter or unclear variable names reduce readability.

**Example - BAD:**

```python
# ❌ LOW: Unclear names
def f(x, y, z):
    a = x * y
    b = a * z
    c = b * 0.08
    d = b + c
    return d
```

**Example - GOOD:**

```python
# ✅ Descriptive names
def calculate_order_total(item_price, quantity, tax_rate):
    subtotal = item_price * quantity
    taxable_amount = subtotal * tax_rate
    tax = taxable_amount * 0.08
    total = subtotal + tax
    return total
```

**Why It Matters:**
- Code reads like a story
- No need for comments
- Easier to spot bugs
- Reduces cognitive load

---

### 4.3 PEP 8 Violations

**Rule ID:** `PRACTICE_003`

**Severity:** LOW

**Description:** Python code should follow PEP 8 style guidelines.

**Common Issues:**
- Lines >100 characters
- Missing whitespace around operators
- Incorrect indentation
- Wrong naming conventions

**Example - BAD:**

```python
# ❌ LOW: Multiple PEP 8 violations
def calculateTotal(ItemPrice,Quantity):
    Total=ItemPrice*Quantity # No spaces around operators
    if Total>100:return Total*0.9 # Multiple statements on one line
    else:return Total
```

**Example - GOOD:**

```python
# ✅ Follows PEP 8
def calculate_total(item_price, quantity):
    """Calculate total with bulk discount."""
    total = item_price * quantity

    # Apply bulk discount for orders >100
    if total > 100:
        return total * 0.9

    return total
```

**Why It Matters:**
- Consistency across team
- Easier to read
- Industry standard
- Tool compatibility

---

## 5. Severity Guidelines

### Severity Levels Explained

| Severity | When to Use | Action Required | Blocks Pre-Push |
|----------|-------------|-----------------|-----------------|
| **CRITICAL** | Security vulnerability, data loss risk | **Fix immediately** | ✅ Yes |
| **HIGH** | Major code quality issue, high complexity | **Fix before merge** | ✅ Yes |
| **MEDIUM** | Code smell, maintainability issue | **Fix soon** | ❌ No |
| **LOW** | Minor style issue, missing docs | **Fix when convenient** | ❌ No |

### Decision Tree

```
Is it a security vulnerability?
├─ Yes → CRITICAL
│
Is it high complexity (>20) or god class (>500)?
├─ Yes → HIGH
│
Does it significantly hurt maintainability?
├─ Yes → MEDIUM
│
Is it a minor style or documentation issue?
└─ Yes → LOW
```

### Examples by Severity

**CRITICAL:**
- Hardcoded API keys
- SQL injection vulnerability
- eval() with user input
- Exposed passwords in code

**HIGH:**
- Cyclomatic complexity >20
- God class >500 lines
- Unsafe pickle usage
- Critical logic without tests

**MEDIUM:**
- Long functions (50-100 lines)
- 8+ function parameters
- Deep nesting (5+ levels)
- Duplicate code blocks
- No error handling

**LOW:**
- Missing docstrings
- Poor variable names (x, y, z)
- Magic numbers
- TODOs without context
- PEP 8 violations

---

## 📊 Quick Reference

### All Rules Summary

| ID | Rule | Severity | Analyzer |
|----|------|----------|----------|
| COMPLEXITY_001 | High Cyclomatic Complexity | MEDIUM-CRITICAL | Complexity |
| SECURITY_001 | Hardcoded Secrets | CRITICAL | Security |
| SECURITY_002 | SQL Injection | CRITICAL | Security |
| SECURITY_003 | eval() Usage | CRITICAL | Security |
| SECURITY_004 | Unsafe Pickle | HIGH | Security |
| SECURITY_005 | Assert in Production | MEDIUM | Security |
| SECURITY_006 | Bare Except | MEDIUM | Security |
| SMELL_001 | Long Function | MEDIUM-HIGH | Code Smells |
| SMELL_002 | Long Parameter List | LOW-HIGH | Code Smells |
| SMELL_003 | Deep Nesting | LOW-HIGH | Code Smells |
| SMELL_004 | Magic Numbers | LOW | Code Smells |
| SMELL_005 | Duplicate Code | MEDIUM | Code Smells |
| SMELL_006 | God Class | HIGH | Code Smells |
| SMELL_007 | Incomplete TODOs | LOW | Code Smells |
| SMELL_008 | Commented Code | LOW | Code Smells |
| PRACTICE_001 | Missing Docstrings | LOW | Best Practices |
| PRACTICE_002 | Poor Variable Names | LOW | Best Practices |
| PRACTICE_003 | PEP 8 Violations | LOW | Best Practices |

**Total: 18 core rules + additional pattern variations = 22+ checks**

---

## 🔧 Customizing Rules

### Adjusting Severity Thresholds

```python
from hefesto.core.analyzer_engine import AnalyzerEngine

# Only show HIGH and CRITICAL issues
engine = AnalyzerEngine(severity_threshold="HIGH")

# Show everything including LOW
engine = AnalyzerEngine(severity_threshold="LOW")
```

### Disabling Specific Analyzers

```python
from hefesto.analyzers import (
    ComplexityAnalyzer,
    SecurityAnalyzer,
    # Don't import what you don't want
)

engine = AnalyzerEngine()
engine.register_analyzer(ComplexityAnalyzer())
engine.register_analyzer(SecurityAnalyzer())
# Skipped: CodeSmellAnalyzer, BestPracticesAnalyzer
```

### Inline Suppressions

```python
# hefesto: ignore
API_KEY = "sk-test-123"  # Test key, not real

# Or suppress specific rules (future feature)
def long_function():  # hefesto: ignore SMELL_001
    pass
```

---

## 📚 Related Documentation

- **[Getting Started](GETTING_STARTED.md)** - Quick tutorial
- **[Integration Guide](INTEGRATION.md)** - Phase 0+1 architecture
- **[CLI Reference](CLI_REFERENCE.md)** - All commands
- **[API Reference](API_REFERENCE.md)** - SDK usage

---

<div align="center">

**Questions?** Check the [FAQ](FAQ.md) or [open an issue](https://github.com/artvepa80/Agents-Hefesto/issues).

**Built with ❤️ by [Narapa LLC](https://narapallc.com)**

</div>
