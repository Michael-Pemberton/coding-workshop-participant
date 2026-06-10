from repositories.project_repository import ProjectRepository
from repositories.deliverable_repository import DeliverableRepository
from repositories.budget_repository import BudgetRepository


class ProjectService:
    def __init__(self):
        self.repo = ProjectRepository()
        self.deliverable_repo = DeliverableRepository()
        self.budget_repo = BudgetRepository()

    def get_all(self, active_only: bool = True):
        return self.repo.find_all(active_only=active_only)

    def get_by_id(self, project_id: str):
        project = self.repo.find_by_id(project_id)
        if not project:
            return None
        # Enrich with deliverables and budget
        project["deliverables"] = self.deliverable_repo.find_all(project_id=project_id)
        project["budget"] = self.budget_repo.find_by_project(project_id)
        return project

    def create(self, data: dict):
        # Check unique project code
        if self.repo.find_by_code(data["project_code"]):
            raise ValueError(f"Project code '{data['project_code']}' already exists")
        project = self.repo.create(data)
        # Auto-create a budget record for the project
        self.budget_repo.create({
            "project_id": project["id"],
            "planned_amount": data.get("planned_budget", 0),
            "consumed_amount": 0,
        })
        return project

    def update(self, project_id: str, data: dict):
        existing = self.repo.find_by_id(project_id)
        if not existing:
            return None
        updated = self.repo.update(project_id, data)
        # Recalculate health after update
        self._recalculate_health(project_id)
        return updated

    def delete(self, project_id: str) -> bool:
        return self.repo.delete(project_id)

    def get_dashboard_stats(self) -> dict:
        stats = self.repo.get_dashboard_stats()
        health = self.repo.get_health_distribution()
        stats["health_distribution"] = {h["health_status"]: h["count"] for h in health}
        return stats

    def _recalculate_health(self, project_id: str):
        """
        Business rule:
        GREEN  - on schedule, budget healthy, no blocked deliverables
        AMBER  - slight delay, moderate budget concern
        RED    - major delay, budget overrun, or critical deliverable blocked
        """
        project = self.repo.find_by_id(project_id)
        if not project:
            return

        deliverables = self.deliverable_repo.find_all(project_id=project_id)
        budget = self.budget_repo.find_by_project(project_id)

        has_blocked = any(d["status"] == "BLOCKED" for d in deliverables)

        budget_ratio = 0.0
        if budget and budget["planned_amount"] and budget["planned_amount"] > 0:
            budget_ratio = float(budget["consumed_amount"]) / float(budget["planned_amount"])

        avg_completion = 0.0
        if deliverables:
            avg_completion = sum(d["completion_percentage"] for d in deliverables) / len(deliverables)

        # Determine health
        if has_blocked or budget_ratio > 1.0:
            health = "RED"
        elif budget_ratio > 0.85 or avg_completion < 40:
            health = "AMBER"
        else:
            health = "GREEN"

        self.repo.update(project_id, {"health_status": health})

    def add_dependency(self, parent_id: str, child_id: str):
        if not self.repo.find_by_id(parent_id) or not self.repo.find_by_id(child_id):
            raise ValueError("One or both projects not found")
        with __import__("utils.database", fromlist=["db_cursor"]).db_cursor() as cur:
            cur.execute(
                """
                INSERT INTO project_dependencies (parent_project_id, child_project_id)
                VALUES (%s, %s)
                RETURNING *
                """,
                (parent_id, child_id),
            )
            return dict(cur.fetchone())

    def get_project_dependencies(self, project_id: str = None):
        from utils.database import db_cursor
        with db_cursor() as cur:
            query = """
                SELECT pd.*,
                    parent.title AS parent_title, parent.project_code AS parent_code,
                    child.title AS child_title, child.project_code AS child_code
                FROM project_dependencies pd
                JOIN projects parent ON pd.parent_project_id = parent.id
                JOIN projects child ON pd.child_project_id = child.id
                WHERE TRUE
            """
            params = []
            if project_id:
                query += " AND (pd.parent_project_id = %s OR pd.child_project_id = %s)"
                params.extend([project_id, project_id])
            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]

    def remove_dependency(self, dependency_id: str) -> bool:
        from utils.database import db_cursor
        with db_cursor() as cur:
            cur.execute(
                "DELETE FROM project_dependencies WHERE id = %s",
                (dependency_id,),
            )
            return cur.rowcount > 0