# from backend.app import create_app
# from backend.models import db, User
# import sys

# try:
#     app = create_app()
#     with app.app_context():
#         # List of test emails to delete
#         test_emails = ['test.a@company.local', 'test.b@company.local','she@gmail.com']
        
#         # Delete test user records
#         deleted_users = db.session.query(User).filter(User.email.in_(test_emails)).delete(synchronize_session=False)
        
#         # Optionally, delete tasks related to integration testing
#         from backend.models import Task
#         deleted_tasks = db.session.query(Task).filter(Task.title.like('Integration test task%')).delete(synchronize_session=False)
        
#         db.session.commit()
#         print(f"? Cleanup successful: {deleted_users} users and {deleted_tasks} tasks deleted.")

# except Exception as e:
#     print(f"? ERROR during database cleanup: {e}", file=sys.stderr)
#     sys.exit(1)

# cleanup.py
"""
Database cleanup script: delete tasks regardless of status.

Usage:
    python cleanup.py            # delete integration-test tasks + orphaned tasks
    python cleanup.py --all      # delete ALL Task and TaskDependency rows (irreversible)
    python cleanup.py --dry-run  # show counts but do not delete
"""

import sys
import argparse

from backend.app import create_app
from backend.models import db
from sqlalchemy import exists, or_


def main():
    parser = argparse.ArgumentParser(description="DB cleanup helper (task deletions).")
    parser.add_argument("--all", action="store_true", help="Delete ALL Task and TaskDependency rows (IRREVERSIBLE).")
    parser.add_argument("--dry-run", action="store_true", help="Don't perform deletions; only report counts.")
    args = parser.parse_args()

    try:
        app = create_app()
        with app.app_context():
            # import models within app context
            from backend.models import Task, TaskDependency, User

            # Prepare counters
            deleted_integration_tasks = 0
            deleted_orphan_tasks = 0
            deleted_all_tasks = 0
            deleted_orphan_deps = 0

            if args.all:
                # Count first (for dry-run)
                total_tasks = db.session.query(Task).count()
                total_deps = db.session.query(TaskDependency).count()

                print(f"[INFO] Tasks to delete: {total_tasks}; TaskDependency rows to delete: {total_deps}")

                if args.dry_run:
                    print("[DRY RUN] No deletions performed.")
                    return

                # Delete dependencies first to avoid FK issues (if any)
                deleted_all_deps = db.session.query(TaskDependency).delete(synchronize_session=False)
                deleted_all_tasks = db.session.query(Task).delete(synchronize_session=False)
                db.session.commit()
                print(f"[DONE] Deleted ALL TaskDependency rows: {deleted_all_deps}; ALL Task rows: {deleted_all_tasks}")
                return

            # 1) Delete tasks that match the integration-test title pattern (no status checks)
            deleted_integration_tasks = db.session.query(Task).filter(Task.title.like('Integration test task%')).count()
            print(f"[INFO] Integration-test tasks matching pattern: {deleted_integration_tasks}")
            if not args.dry_run:
                deleted_integration_tasks = db.session.query(Task).filter(Task.title.like('Integration test task%')).delete(synchronize_session=False)

            # 2) Delete orphaned tasks: tasks whose assignee_id OR creator_id refer to no User row
            orphan_filter = or_(
                ~exists().where(User.id == Task.assignee_id),
                ~exists().where(User.id == Task.creator_id)
            )
            deleted_orphan_tasks = db.session.query(Task).filter(orphan_filter).count()
            print(f"[INFO] Orphaned tasks found (assignee/creator missing): {deleted_orphan_tasks}")
            if not args.dry_run:
                deleted_orphan_tasks = db.session.query(Task).filter(orphan_filter).delete(synchronize_session=False)

            # 3) Cleanup TaskDependency rows that reference missing tasks
            #    (prereq_id or dependent_id points to a Task id that doesn't exist)
            dep_orphan_filter = or_(
                ~exists().where(Task.id == TaskDependency.prereq_id),
                ~exists().where(Task.id == TaskDependency.dependent_id)
            )
            deleted_orphan_deps = db.session.query(TaskDependency).filter(dep_orphan_filter).count()
            print(f"[INFO] TaskDependency rows referencing missing tasks: {deleted_orphan_deps}")
            if not args.dry_run:
                deleted_orphan_deps = db.session.query(TaskDependency).filter(dep_orphan_filter).delete(synchronize_session=False)

            if not args.dry_run:
                db.session.commit()

            print(
                f"[RESULT] Deleted integration tasks: {deleted_integration_tasks}; "
                f"deleted orphan tasks: {deleted_orphan_tasks}; "
                f"deleted orphan dependencies: {deleted_orphan_deps}"
            )

    except Exception as e:
        print(f"[ERROR] during database cleanup: {e}", file=sys.stderr)
        try:
            db.session.rollback()
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()

