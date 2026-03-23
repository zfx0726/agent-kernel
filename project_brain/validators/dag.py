from __future__ import annotations

from collections import defaultdict, deque

from project_brain.repository import BrainRepository, ValidationError


# Validate task graph structure so execution commands never reason over a broken DAG.
def check_dag(repo: BrainRepository) -> list[ValidationError]:
    errors: list[ValidationError] = []
    tasks = {task.frontmatter["task_id"]: task for task in repo.load_tasks()}
    indegree = {task_id: 0 for task_id in tasks}
    graph: dict[str, list[str]] = defaultdict(list)
    for task_id, task in tasks.items():
        for dep in task.frontmatter.get("dependencies", []):
            if dep not in tasks:
                errors.append(ValidationError(task.rel_path, f"dependency {dep} does not exist as a task"))
                continue
            graph[dep].append(task_id)
            indegree[task_id] += 1
    queue = deque([node for node, degree in indegree.items() if degree == 0])
    visited = 0
    while queue:
        node = queue.popleft()
        visited += 1
        for child in graph[node]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if visited != len(tasks):
        cycle_nodes = sorted(task_id for task_id, degree in indegree.items() if degree > 0)
        errors.append(ValidationError("vault/01_execution/tasks", f"dependency cycle detected involving {cycle_nodes}"))
    dependents = {dep for task in tasks.values() for dep in task.frontmatter.get("dependencies", [])}
    roots = [task_id for task_id, task in tasks.items() if not task.frontmatter.get("dependencies")]
    if not roots:
        errors.append(ValidationError("vault/01_execution/tasks", "no root tasks found"))
    for task_id, task in tasks.items():
        if task.frontmatter.get("status") in {"proposed", "ready", "in_progress", "blocked", "review"}:
            continue
        if task_id not in dependents and task.frontmatter.get("status") not in {"complete", "cancelled"}:
            errors.append(ValidationError(task.rel_path, "orphan task is neither terminal nor referenced by plan"))
    return errors
