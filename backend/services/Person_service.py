from repositories.person_repository import PersonRepository
from repositories.assignment_repository import AssignmentRepository


class PersonService:
    def __init__(self):
        self.repo = PersonRepository()
        self.assignment_repo = AssignmentRepository()

    def get_all(self, active_only: bool = True):
        people = self.repo.find_all(active_only=active_only)
        # Annotate allocation status
        for person in people:
            alloc = int(person.get("total_allocated_hours", 0))
            cap = int(person.get("weekly_capacity_hours", 40))
            person["allocation_status"] = "OVER" if alloc > cap else "OK"
            person["allocation_percentage"] = round((alloc / cap * 100) if cap > 0 else 0, 1)
        return people

    def get_by_id(self, person_id: str):
        person = self.repo.find_by_id(person_id)
        if not person:
            return None
        person["assignments"] = self.assignment_repo.find_all(person_id=person_id)
        alloc = int(person.get("total_allocated_hours", 0))
        cap = int(person.get("weekly_capacity_hours", 40))
        person["allocation_status"] = "OVER" if alloc > cap else "OK"
        return person

    def create(self, data: dict):
        if self.repo.find_by_email(data["email"]):
            raise ValueError(f"Person with email '{data['email']}' already exists")
        return self.repo.create(data)

    def update(self, person_id: str, data: dict):
        if not self.repo.find_by_id(person_id):
            return None
        if "email" in data:
            existing = self.repo.find_by_email(data["email"])
            if existing and str(existing["id"]) != person_id:
                raise ValueError(f"Email '{data['email']}' already in use")
        return self.repo.update(person_id, data)

    def delete(self, person_id: str) -> bool:
        return self.repo.delete(person_id)

    def get_overallocated(self):
        return self.repo.get_overallocated()

    def get_resource_stats(self) -> dict:
        all_people = self.repo.find_all()
        overallocated = self.repo.get_overallocated()
        return {
            "total_resources": len(all_people),
            "overallocated_count": len(overallocated),
            "overallocated_people": overallocated,
        }