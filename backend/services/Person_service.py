"""Business logic for people management."""

import logging

from repositories.Person_repository import PersonRepository
from repositories.Assignment_repository import AssignmentRepository

logger = logging.getLogger(__name__)


class PersonService:
    """Encapsulates business logic for creating and querying people."""

    def __init__(self, conn) -> None:
        self.conn = conn
        self.people = PersonRepository(conn)
        self.assignments = AssignmentRepository(conn)

    def create_person(self, data: dict) -> dict:
        """
        Validates and creates a new person record.

        Args:
            data: Person fields from the request body.

        Returns:
            dict: Created person record.

        Raises:
            ValueError: If required fields are missing or email is already in use.
        """
        if not data.get("name", "").strip():
            raise ValueError("name is required")
        if not data.get("email", "").strip():
            raise ValueError("email is required")

        existing = self.people.find_by_email(data["email"].lower().strip())
        if existing:
            raise ValueError(f"A person with email {data['email']} already exists")

        data["email"] = data["email"].lower().strip()
        return self.people.create(data)

    def get_person_allocation(self, person_id: str) -> dict:
        """
        Returns a person's allocation details with overallocation flag.

        Args:
            person_id: UUID string.

        Returns:
            dict: Person record with allocated_hours_per_week, is_overallocated,
                  and project_assignments list.

        Raises:
            ValueError: If the person does not exist.
        """
        person = self.people.find_with_allocation(person_id)
        if not person:
            raise ValueError(f"Person not found: {person_id}")

        project_assignments = self.assignments.find_all(person_id=person_id)
        person["project_assignments"] = project_assignments
        return person

    def get_all_with_allocation(self) -> list[dict]:
        """
        Returns all active people enriched with their total allocated hours and overallocation flag.

        Returns:
            list[dict]: People records with allocation summary.
        """
        people = self.people.find_all()
        result = []
        for person in people:
            total_hours = self.assignments.get_person_total_hours(person["id"])
            person["allocated_hours_per_week"] = total_hours
            person["is_overallocated"] = total_hours > person["weekly_hours_capacity"]
            result.append(person)
        return result
