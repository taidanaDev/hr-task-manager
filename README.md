# HR Task Assignment and Prioritization Management System

This web application was built as a final project for CpE 411, Data Structures and Algorithms. It helps HR teams assign work, prioritize urgent tasks, and track employee workloads and task progress in one place.

## Features

- Administrators manage user accounts and reporting relationships. Administrators and managers can create, assign, reassign, and batch-schedule tasks.
- Tasks can have high, medium, or low priority, due dates, and dependencies. Workload summaries help managers see how work is distributed.
- Employees can view assigned tasks, start and complete work, and receive assignment notifications.

## Data structures and algorithms

| Technique | How the system uses it |
| --- | --- |
| Min-heap priority queue | Picks the highest-priority task that is ready to schedule. Older creation timestamps come first at the same priority, with task ID as a final tie-breaker. |
| Directed graph and Kahn's topological sort | Stores prerequisites in adjacency lists and counts incoming edges in a dictionary. A deque processes tasks with zero incoming edges to find a valid ordering and detect cycles. |
| Greedy workload assignment | Selects the candidate with the lowest current workload for each automatic assignment. Employee ID breaks ties. |
| N-ary tree and depth-first search | Represents reporting relationships. A stack-based depth-first search finds the employees in a manager's subtree. |

Batch scheduling combines these techniques. The scheduler puts tasks with no pending prerequisites into the priority queue, assigns the next task to the least-loaded employee in scope, then adds any dependent tasks that have become ready to schedule.

## Tech stack

- Python, Flask, Flask-SQLAlchemy, SQLite, and JWT-based authentication
- HTML, CSS, and JavaScript for the role-based dashboards

## Local setup

1. From the project root, create a Python 3.11 virtual environment and install the dependencies. These commands use PowerShell. Flask-Cors is imported by the app and installed alongside the dependencies in `requirements.txt`.

   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt Flask-Cors
   ```

2. Create a `.env` file in the project root with the following settings. Generate a random value for `SECRET_KEY` with `python -c "import secrets; print(secrets.token_hex(32))"`.

   ```dotenv
   DATABASE_URL=sqlite:///hr_task_manager.db
   SECRET_KEY=replace-with-your-generated-secret
   ```

3. Initialize the SQLite database and create a local administrator. Open the Flask shell with the following command.

   ```powershell
   .\.venv\Scripts\python.exe -m flask --app backend.app shell
   ```

   ```python
   from getpass import getpass
   from backend.models import RoleEnum, db
   from backend.seeds import add_user

   db.create_all()
   add_user(db.session, "Local Admin", input("Admin email: "), getpass("Admin password: "), role=RoleEnum.ADMIN)
   db.session.commit()
   exit()
   ```

4. Start the development server and open [http://127.0.0.1:5000](http://127.0.0.1:5000). Sign in with the administrator credentials you created, then add managers and employees from the admin dashboard.

   ```powershell
   .\.venv\Scripts\python.exe -m flask --app backend.app run
   ```
