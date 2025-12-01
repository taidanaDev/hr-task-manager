import heapq
from datetime import datetime
from collections import defaultdict, deque
from typing import List, Tuple, Dict, Any

class TaskPriorityQueue:

    DEFAULT_MAP = {'high': 0, 'medium': 1, 'low': 2}

    def __init__(self):
        self._heap = []
        self._counter = 0

    def _normalize_priority_str(self, p):
        if p is None:
            return ''
        try:
            # if Enum-like with .value
            if hasattr(p, 'value'):
                return str(p.value).lower()
        except Exception:
            pass
        return str(p).lower()

    def _compute_priority(self, task, priority_fn):
        # If caller provided a priority function, try to use it.
        if priority_fn and callable(priority_fn):
            try:
                # pass the raw priority string/value to priority_fn
                raw = task.priority
                # If Enum-like, extract .value
                raw_val = raw.value if hasattr(raw, 'value') else raw
                return int(priority_fn(raw_val))
            except Exception:
                # fall back to default mapping on error
                pass

        # Default mapping
        pstr = self._normalize_priority_str(getattr(task, 'priority', None))
        return self.DEFAULT_MAP.get(pstr, 1)

    def push(self, task, priority_fn=None):
        """
        Push a task. Optionally pass priority_fn (e.g. your priority_value function).
        """
        pr = self._compute_priority(task, priority_fn)

        # tie-breaker 1: created_at (older first). unify to timestamp
        created_at = getattr(task, 'created_at', None)
        try:
            if created_at is None:
                created_ts = 0
            elif isinstance(created_at, str):
                # ISO string fallback
                created_ts = int(datetime.fromisoformat(created_at).timestamp())
            else:
                created_ts = int(created_at.timestamp())
        except Exception:
            created_ts = getattr(task, 'id', 0) or 0

        # tie-breaker 2: task id
        task_id = getattr(task, 'id', 0) or 0

        self._counter += 1
        heapq.heappush(self._heap, (pr, created_ts, task_id, self._counter, task))

    def pop(self):
        if not self._heap:
            return None
        return heapq.heappop(self._heap)[-1]

    def is_empty(self):
        return len(self._heap) == 0

    def __len__(self):
        return len(self._heap)

    def peek(self):
        return None if not self._heap else self._heap[0][-1]

# Topological Sort and Readiness Checking for Tasks with Dependencies

class TaskGraph:
    def __init__(self, pending_tasks: List[Any], dependencies: List[Any]):
        self.task_map: Dict[int, Any] = {t.id: t for t in pending_tasks}
        self.adj: Dict[int, List[int]] = defaultdict(list)
        self.in_degree: Dict[int, int] = {tid: 0 for tid in self.task_map.keys()}

        self._build_graph(dependencies)

    def _iter_deps(self, dependencies):
        """Yield (prereq_id, dependent_id) for various dependency representations."""
        for d in (dependencies or []):
            if d is None:
                continue
            if isinstance(d, (list, tuple)) and len(d) >= 2:
                yield int(d[0]), int(d[1])
            elif isinstance(d, dict) and 'prereq_id' in d and 'dependent_id' in d:
                yield int(d['prereq_id']), int(d['dependent_id'])
            else:
                try:
                    yield int(getattr(d, 'prereq_id')), int(getattr(d, 'dependent_id'))
                except Exception:
                    continue

    def _build_graph(self, dependencies):
        for prereq_id, dependent_id in self._iter_deps(dependencies):
            if prereq_id in self.task_map and dependent_id in self.task_map:
                self.adj[prereq_id].append(dependent_id)
                self.in_degree[dependent_id] = self.in_degree.get(dependent_id, 0) + 1
                if prereq_id not in self.in_degree:
                    self.in_degree[prereq_id] = 0

    def topological_sort(self) -> List[int] | None:
        in_deg = dict(self.in_degree)
        q = deque([tid for tid, deg in in_deg.items() if deg == 0])
        order = []

        while q:
            node = q.popleft()
            order.append(node)
            for neigh in self.adj.get(node, []):
                in_deg[neigh] -= 1
                if in_deg[neigh] == 0:
                    q.append(neigh)

        if len(order) == len(self.task_map):
            return order
        return None

    def get_ready_tasks(self) -> List[Any]:
        ready_ids = [tid for tid, deg in self.in_degree.items() if deg == 0]
        return [self.task_map[tid] for tid in ready_ids if tid in self.task_map]

    def decrement_in_degree(self, task_id: int) -> List[int]:
        became_ready = []
        for dep in self.adj.get(task_id, []):
            if dep in self.in_degree:
                self.in_degree[dep] -= 1
                if self.in_degree[dep] == 0:
                    became_ready.append(dep)
        return became_ready

    def add_dependency(self, prereq_id: int, dependent_id: int) -> bool:
        if prereq_id in self.task_map and dependent_id in self.task_map:
            self.adj[prereq_id].append(dependent_id)
            self.in_degree[dependent_id] = self.in_degree.get(dependent_id, 0) + 1
            return True
        return False


# Greedy Assignment Algorithm 

def find_best_assignee(candidates, max_workload):
    if not candidates:
        return None

    workload_heap = []

    for employee in candidates:
        heapq.heappush(workload_heap, (employee.workload, employee.id, employee))

    best_assignee_tuple = heapq.heappop(workload_heap)
    
    return best_assignee_tuple[2]
