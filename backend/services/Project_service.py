"""Business logic for project management."""

import logging
from datetime import date
from typing import Optional

from repositories.Project_repository import ProjectRepository
from repositories.Assignment_repository import AssignmentRepository
from repositories.Deliverable_repository import DeliverableRepository
from repositories.Budget_repository import BudgetRepository

logger = logging.getLogger(__name__)


class ProjectService:
    """
    Encapsulates all business logic related to projects.

    Delegates persistence to repository classes and enforces rules such as
    health auto-calculation and dependency validation.
    """

    def __init__(self, conn) -> None:
        self.conn = conn
        self.projects = ProjectRepository(conn)
        self.assignments = AssignmentRepository(conn)
        self.deliverables = DeliverableRepository(conn)
        self.budgets = BudgetRepository(conn)

    def calculate_health(self, project: dict) -> str:
        """
        Derives the RAG health status from project dates and budget consumption.

        Rules:
        - RED: end_date has passed OR budget_consumed > budget_planned (when planned > 0)
        - AMBER: end_date within 7 days OR budget_consumed > 80% of budget_planned
        - GREEN: otherwise

        Args:
            project: Project record dict with end_date, budget_planned, budget_consumed.

        Returns:
            str: 'red', 'amber', or 'green'.
        """
        today = date.today()
        end_date = project.get("end_date")
        budget_planned = float(project.get("budget_planned") or 0)
        budget_consumed = float(project.get("budget_consumed") or 0)

        if end_date:
            if isinstance(end_date, str):
                end_date = date.fromisoformat(end_date[:10])
            days_remaining = (end_date - today).days
            if days_remaining < 0:
                return "red"
            if days_remaining <= 7:
                return "amber"

        if budget_planned > 0:
            ratio = budget_consumed / budget_planned
            if ratio > 1.0:
                return "red"
            if ratio > 0.8:
                return "amber"

        return "green"

    def create_project(self, data: dict, created_by: Optional[str] = None) -> dict:
        """
        Validates and creates a new project.

        Args:
            data: Project fields from the request body.
            created_by: UUID of the creating user.

        Returns:
            dict: Created project record.

        Raises:
            ValueError: If required fields are missing or dependencies are invalid.
        """
        if not data.get("title", "").strip():
            raise ValueError("title is required")

        data["health"] = self.calculate_health(data)

        dep_ids = data.get("dependency_ids") or []
        for dep_id in dep_ids:
            if not self.projects.find_by_id(dep_id):
                raise ValueError(f"Dependency project not found: {dep_id}")

        if created_by:
            data["created_by"] = created_by

        return self.projects.create(data)

    def update_project(self, project_id: str, data: dict) -> Optional[dict]:
        """
        Updates a project and recalculates health automatically.

        Args:
            project_id: UUID of the project to update.
            data: Fields to update.

        Returns:
            dict | None: Updated record or None if not found.
        """
        existing = self.projects.find_by_id(project_id)
        if not existing:
            return None

        merged = {**existing, **data}
        data["health"] = self.calculate_health(merged)

        dep_ids = data.get("dependency_ids") or []
        for dep_id in dep_ids:
            if dep_id == project_id:
                raise ValueError("A project cannot depend on itself")
            if not self.projects.find_by_id(dep_id):
                raise ValueError(f"Dependency project not found: {dep_id}")

        return self.projects.update(project_id, data)

    def get_project_with_details(self, project_id: str) -> Optional[dict]:
        """
        Returns a project enriched with counts of assignments, deliverables, and budget totals.

        Args:
            project_id: UUID string.

        Returns:
            dict | None: Project record with summary fields appended.
        """
        project = self.projects.find_by_id(project_id)
        if not project:
            return None

        assignments = self.assignments.find_all(project_id=project_id)
        deliverables = self.deliverables.find_all(project_id=project_id)
        budget_totals = self.budgets.get_project_totals(project_id)

        project["assignment_count"] = len(assignments)
        project["deliverable_count"] = len(deliverables)
        project["budget_total_planned"] = budget_totals["total_planned"]
        project["budget_total_consumed"] = budget_totals["total_consumed"]
        return project
