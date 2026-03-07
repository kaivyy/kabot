from pathlib import Path

from kabot.core.cost_tracker import CostTracker

sessions_dir = Path("c:/Users/Arvy Kairi/.kabot/sessions")
tracker = CostTracker(sessions_dir)
summary = tracker.get_summary()

print("Cost & Usage Summary:")
print(f"Today: ${summary['today']:.4f}")
print(f"Total: ${summary['total']:.4f}")
print(f"Projected/Mo: ${summary['projected_monthly']:.2f}")
print(f"Token Usage: {summary['token_usage']}")

expected_total = 0.0335
if abs(summary['total'] - expected_total) < 0.0001:
    print("\n✅ Total cost matches expected value!")
else:
    print(f"\n❌ Total cost mismatch! Expected {expected_total}, got {summary['total']}")
