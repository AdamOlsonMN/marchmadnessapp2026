"""Run schema validation on loaded Kaggle + optional enrichment data."""

from pathlib import Path

from mm.data.kaggle_loader import DEFAULT_RAW_DIR, load_all
from mm.data.sports_reference import (
    validate_massey_schema,
    validate_results_schema,
    validate_seeds_schema,
    validate_teams_schema,
)


def run_validation(raw_dir: Path = DEFAULT_RAW_DIR) -> list[str]:
    """Load all available data and run schema validators. Returns list of error messages."""
    errors = []
    data = load_all(raw_dir)

    if "teams" in data:
        errors.extend(validate_teams_schema(data["teams"]))
    if "seeds" in data:
        errors.extend(validate_seeds_schema(data["seeds"]))
    if "regular" in data:
        errors.extend(validate_results_schema(data["regular"], "regular"))
    if "tourney" in data:
        errors.extend(validate_results_schema(data["tourney"], "tourney"))
    if "massey" in data:
        errors.extend(validate_massey_schema(data["massey"]))

    return errors


def main() -> None:
    import sys
    raw = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_RAW_DIR
    errs = run_validation(raw)
    if errs:
        for e in errs:
            print(e)
        sys.exit(1)
    print("Schema validation passed.")


if __name__ == "__main__":
    main()
