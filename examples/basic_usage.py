"""
Basic Hefesto usage examples.

These examples work with the free tier (Phase 0).
"""

import os


# Example 1: Validate a code suggestion
def example_validate_suggestion():
    """Validate a refactoring suggestion."""
    from hefesto import get_validator

    print("=" * 60)
    print("Example 1: Validate Code Suggestion")
    print("=" * 60)

    validator = get_validator()

    original = "password = 'hardcoded123'"
    suggested = "password = os.environ.get('PASSWORD')"

    result = validator.validate(
        original_code=original, suggested_code=suggested, issue_type="security"
    )

    print(f"\nOriginal:  {original}")
    print(f"Suggested: {suggested}")
    print(f"\nValidation Result:")
    print(f"  ✓ Valid: {result.valid}")
    print(f"  ✓ Confidence: {result.confidence:.2%}")
    print(f"  ✓ Similarity: {result.similarity_score:.2%}")
    print(f"  ✓ Safe to apply: {result.safe_to_apply}")

    if result.issues:
        print(f"\n  Issues found:")
        for issue in result.issues:
            print(f"    - {issue}")


# Example 2: Track suggestion feedback
def example_track_feedback():
    """Track user feedback on suggestions."""
    from hefesto import get_feedback_logger

    print("\n" + "=" * 60)
    print("Example 2: Track Suggestion Feedback")
    print("=" * 60)

    # Requires: GCP_PROJECT_ID environment variable
    if not os.getenv("GCP_PROJECT_ID"):
        print("\n⚠️  Skipped: Set GCP_PROJECT_ID to use BigQuery")
        return

    logger = get_feedback_logger()

    # Log suggestion shown
    suggestion_id = logger.log_suggestion_shown(
        file_path="api/users.py",
        issue_type="security",
        severity="HIGH",
        confidence_score=0.85,
        validation_passed=True,
        similarity_score=0.72,
    )

    print(f"\n✅ Suggestion logged: {suggestion_id}")

    # Later: log user action
    logger.log_user_action(
        suggestion_id=suggestion_id,
        accepted=True,
        applied_successfully=True,
        time_to_apply_seconds=45,
        user_comment="Worked perfectly!",
    )

    print(f"✅ User feedback recorded")

    # Query acceptance rate
    metrics = logger.get_acceptance_rate(issue_type="security", days=30)

    if "error" not in metrics:
        print(f"\n📊 Acceptance Rate (last 30 days):")
        print(f"  Total: {metrics['total']}")
        print(f"  Accepted: {metrics['accepted']}")
        print(f"  Rate: {metrics['acceptance_rate']:.1%}")


# Example 3: Monitor budget
def example_monitor_budget():
    """Monitor LLM API budget."""
    from hefesto import get_budget_tracker

    print("\n" + "=" * 60)
    print("Example 3: Monitor LLM Budget")
    print("=" * 60)

    # Requires: GCP_PROJECT_ID environment variable
    if not os.getenv("GCP_PROJECT_ID"):
        print("\n⚠️  Skipped: Set GCP_PROJECT_ID to use BigQuery")
        return

    tracker = get_budget_tracker(daily_limit_usd=10.0, monthly_limit_usd=200.0)

    # Check if budget available
    available = tracker.check_budget_available(period="today")

    print(f"\n💰 Budget Status:")
    print(f"  Available: {'✅ Yes' if available else '❌ No (exceeded)'}")

    # Get usage summary
    summary = tracker.get_usage_summary(period="today")

    if "error" not in summary:
        print(f"\n📊 Today's Usage:")
        print(f"  Requests: {summary['request_count']}")
        print(f"  Tokens: {summary['total_tokens']:,}")
        print(f"  Cost: ${summary['estimated_cost_usd']:.4f}")
        print(f"  Limit: ${summary.get('daily_limit_usd', 10.0):.2f}")
        print(f"  Remaining: ${summary.get('budget_remaining_usd', 0):.2f}")
        print(f"  Used: {summary.get('budget_utilization_pct', 0):.1f}%")


# Example 4: Calculate costs
def example_calculate_costs():
    """Calculate LLM costs for a request."""
    from hefesto import BudgetTracker

    print("\n" + "=" * 60)
    print("Example 4: Calculate LLM Costs")
    print("=" * 60)

    tracker = BudgetTracker()

    # Example request
    input_tokens = 1500
    output_tokens = 800
    model = "gemini-2.0-flash"

    cost = tracker.calculate_cost(
        input_tokens=input_tokens, output_tokens=output_tokens, model=model
    )

    print(f"\n💵 Cost Calculation:")
    print(f"  Model: {model}")
    print(f"  Input tokens: {input_tokens:,}")
    print(f"  Output tokens: {output_tokens:,}")
    print(f"  Total cost: ${cost:.6f}")

    # At scale
    requests_per_day = 1000
    daily_cost = cost * requests_per_day
    monthly_cost = daily_cost * 30

    print(f"\n📈 At Scale:")
    print(f"  1,000 requests/day: ${daily_cost:.2f}/day = ${monthly_cost:.2f}/month")


if __name__ == "__main__":
    print("🔨 HEFESTO - Basic Usage Examples\n")

    example_validate_suggestion()
    example_track_feedback()
    example_monitor_budget()
    example_calculate_costs()

    print("\n" + "=" * 60)
    print("✅ All examples complete!")
    print("=" * 60)
    print("\n💡 For Pro features (semantic analysis), see:")
    print("   examples/pro_semantic_analysis.py")
    print("\n🛒 Purchase Pro: https://buy.stripe.com/hefesto-pro")
