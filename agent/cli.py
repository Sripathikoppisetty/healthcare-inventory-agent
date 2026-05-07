"""agent/cli.py — Command-line interface for the inventory agent."""

import sys
import argparse
from dotenv import load_dotenv

load_dotenv()

from data.database import init_db
from agent.core import run_query, stream_query


def interactive_mode():
    """REPL loop for interactive querying."""
    print("=" * 60)
    print("  Healthcare Inventory AI Agent (Groq/llama-3.3-70b)")
    print("  Type 'quit' or 'exit' to stop.")
    print("=" * 60)
    print()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            print("Goodbye.")
            break

        print("\nAgent: ", end="", flush=True)
        try:
            for chunk in stream_query(user_input):
                print(chunk, end="", flush=True)
        except Exception as e:
            print(f"[Error: {e}]")
        print("\n")


def single_query_mode(query: str):
    """Run one query, print the result, and exit."""
    try:
        result = run_query(query)
        print(result)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Healthcare Supply Chain Inventory AI Agent"
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Single query to run (omit for interactive mode)",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Seed the database with demo data before running",
    )
    args = parser.parse_args()

    # Always ensure DB tables exist
    init_db()

    if args.seed:
        print("Seeding database with demo data...")
        from scripts.seed_data import seed
        seed()
        print("Done.\n")

    if args.query:
        single_query_mode(args.query)
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
