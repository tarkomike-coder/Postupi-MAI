from __future__ import annotations

import argparse

from .database import init_db, session_scope
from .services.bauman_importer import import_bauman_snapshot
from .services.importer import import_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description="Admissions data worker")
    parser.add_argument("command", choices=["import", "import-mai", "import-bauman", "import-all"])
    args = parser.parse_args()
    init_db()
    if args.command in ("import", "import-mai", "import-all"):
        with session_scope() as db:
            snapshot = import_snapshot(db)
            print(
                f"mai snapshot id={snapshot.id} status={snapshot.status} "
                f"groups={snapshot.groups_count} rows={snapshot.rows_count}"
            )
    if args.command in ("import-bauman", "import-all"):
        with session_scope() as db:
            snapshot = import_bauman_snapshot(db)
            print(
                f"bauman snapshot id={snapshot.id} status={snapshot.status} "
                f"groups={snapshot.groups_count} rows={snapshot.rows_count}"
            )


if __name__ == "__main__":
    main()
