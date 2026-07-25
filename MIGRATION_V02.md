# Migration from the old demo repository

V0.2 is a replacement, not an overlay. Before committing V0.2, remove these legacy paths if present:

- `app/`
- `src/`
- `scripts/update_and_train.py`
- `tests/test_features.py`
- `tests/test_scoring.py`

From the repository root, run:

```bash
python -m scripts.cleanup_legacy
```

Then copy the V0.2.1 files, commit all deletions and additions, and push.
