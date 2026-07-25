from __future__ import annotations

import json

from ats.db.repository import Repository
from ats.settings import settings


def main() -> int:
    repo = Repository(settings.database_path)
    repo.initialize()
    with repo.connect() as conn:
        rows = conn.execute(
            """SELECT experiment_id,source_type,target_symbol,experiment_name,status,
                      data_version,git_commit,created_at
               FROM experiments ORDER BY created_at DESC LIMIT 10"""
        ).fetchall()
    print(json.dumps([dict(row) for row in rows], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
