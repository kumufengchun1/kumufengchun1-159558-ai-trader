"""Remove files from pre-V0.2 demo layouts before migration."""
from pathlib import Path

LEGACY_PATHS = (
    Path("app"),
    Path("src"),
    Path("scripts/update_and_train.py"),
    Path("tests/test_features.py"),
    Path("tests/test_scoring.py"),
)


def main() -> int:
    import shutil

    for path in LEGACY_PATHS:
        if path.is_dir():
            shutil.rmtree(path)
            print(f"removed directory: {path}")
        elif path.exists():
            path.unlink()
            print(f"removed file: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
