"""
Automatic Delay Compensation System for Movingo.

Detects train delays on Stockholm C → Bålsta and Stockholm C → Uppsala routes,
determines compensation eligibility, and helps submit claims to the correct operator.

Usage:
    python main.py poll         - Check for new delays
    python main.py status       - Show all pending claims
    python main.py claim        - Prepare and submit claims for pending delays
    python main.py claim --auto - Auto-open claim forms in browser
    python main.py history      - Show all logged delays
"""

import sys

from delay_monitor import poll_delays, get_pending_claims, load_delay_log, mark_claimed
from claim_submitter import prepare_claim, save_claim, print_claim_summary, open_claim_form
from compensation_rules import check_compensation


def cmd_poll():
    """Poll Trafikverket for new delays."""
    print("\nPolling Trafikverket for delays on monitored routes...\n")
    new_delays = poll_delays()

    if new_delays:
        print(f"Found {len(new_delays)} new qualifying delay(s):\n")
        for d in new_delays:
            if d["canceled"]:
                status = "CANCELED"
            else:
                status = f"+{d['delay_minutes']} min delay"
            print(f"  {d['route']} | Train {d['train_id']} | {d['scheduled_time'][:16]} | {status}")
    else:
        print("No new qualifying delays found.")

    pending = get_pending_claims()
    print(f"\nTotal pending claims: {len(pending)}")
    if pending:
        print("Run 'python main.py claim' to prepare and submit claims.")


def cmd_status():
    """Show pending claims."""
    pending = get_pending_claims()
    if not pending:
        print("\nNo pending claims. Run 'python main.py poll' to check for delays.")
        return

    print(f"\n{'=' * 80}")
    print(f"  PENDING CLAIMS ({len(pending)})")
    print(f"{'=' * 80}\n")

    for i, d in enumerate(pending, 1):
        comp = check_compensation(
            d["from_station"], d["to_station"],
            d["train_id"], d["delay_minutes"]
        )
        status = "CANCELED" if d["canceled"] else f"+{d['delay_minutes']} min"
        eligible = "YES" if comp.eligible else "NO"

        print(f"  [{i}] {d['route']} | Train {d['train_id']} | {d['scheduled_time'][:16]} | {status}")
        print(f"      Operator: {comp.operator} | Eligible: {eligible} | Refund: {comp.refund_percentage}%")
        print(f"      Claim URL: {comp.claim_url}")
        print()


def cmd_claim(auto_open=False):
    """Prepare and submit claims for pending delays."""
    pending = get_pending_claims()
    if not pending:
        print("\nNo pending claims.")
        return

    print(f"\n{'=' * 80}")
    print(f"  PROCESSING {len(pending)} PENDING CLAIM(S)")
    print(f"{'=' * 80}")

    for i, d in enumerate(pending, 1):
        print(f"\n{'─' * 80}")
        print(f"  Claim {i}/{len(pending)}")
        print(f"{'─' * 80}\n")

        claim = prepare_claim(d)

        if claim is None:
            print(f"  Train {d['train_id']} on {d['scheduled_time'][:10]}: Not eligible for compensation.")
            continue

        print_claim_summary(claim)
        print()

        # Save claim record
        filepath = save_claim(claim)
        print(f"  Saved to: {filepath}")

        if auto_open:
            print(f"\n  Opening claim form in browser...")
            open_claim_form(claim)
            print(f"  Fill in your personal details and submit.")
            response = input("\n  Mark as claimed? [y/N]: ").strip().lower()
            if response == "y":
                mark_claimed(d["train_id"], d["scheduled_time"])
                print("  Marked as claimed.")
        else:
            print(f"\n  To submit this claim:")
            print(f"  1. Go to: {claim.claim_url}")
            print(f"  2. Enter travel date: {claim.travel_date}")
            print(f"  3. Enter train number: {claim.train_id}")
            print(f"  4. Describe: {claim.delay_minutes} min delay, {claim.route_name}")
            print(f"  5. Ticket type: Movingo")

            response = input("\n  Mark as claimed? [y/N]: ").strip().lower()
            if response == "y":
                mark_claimed(d["train_id"], d["scheduled_time"])
                print("  Marked as claimed.")

    print(f"\n{'=' * 80}")


def cmd_history():
    """Show all logged delays."""
    log = load_delay_log()
    delays = log.get("delays", [])

    if not delays:
        print("\nNo delays logged yet. Run 'python main.py poll' first.")
        return

    print(f"\n{'=' * 90}")
    print(f"  ALL LOGGED DELAYS ({len(delays)} total)")
    print(f"{'=' * 90}\n")

    print(f"  {'Date':<12} {'Train':>6} {'Route':<28} {'Delay':>9} {'Status':<10}")
    print(f"  {'─'*12} {'─'*6} {'─'*28} {'─'*9} {'─'*10}")

    for d in sorted(delays, key=lambda x: x["scheduled_time"], reverse=True):
        date = d["scheduled_time"][:10]
        train = d["train_id"]
        route = d["route"]
        delay = "CANCEL" if d["canceled"] else f"+{d['delay_minutes']}min"
        status = d.get("claim_status", "?")
        print(f"  {date:<12} {train:>6} {route:<28} {delay:>9} {status:<10}")

    print()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    command = sys.argv[1].lower()

    if command == "poll":
        cmd_poll()
    elif command == "status":
        cmd_status()
    elif command == "claim":
        auto = "--auto" in sys.argv
        cmd_claim(auto_open=auto)
    elif command == "history":
        cmd_history()
    else:
        print(f"Unknown command: {command}")
        print(__doc__)


if __name__ == "__main__":
    main()
