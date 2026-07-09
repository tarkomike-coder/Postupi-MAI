from __future__ import annotations

import argparse

from .database import init_db, session_scope
from .services.importer import import_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description="MAI admissions worker")
    parser.add_argument("command", choices=["import"])
    args = parser.parse_args()
    init_db()
    if args.command == "import":
        with session_scope() as db:
            snapshot = import_snapshot(db)
            print(
                f"snapshot id={snapshot.id} status={snapshot.status} "
                f"groups={snapshot.groups_count} rows={snapshot.rows_count}"
            )


if __name__ == "__main__":
    main()
