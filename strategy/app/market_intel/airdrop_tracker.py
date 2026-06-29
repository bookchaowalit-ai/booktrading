"""
Airdrop Task Tracker — persist and manage airdrop task completion state.
Uses Redis for storage (already available in the trading system).
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Redis key prefix
TRACKER_KEY = "airdrop_tracker:v1"


class AirdropTask:
    """Represents a tracked airdrop with task completion status."""

    def __init__(
        self,
        task_id: str,
        name: str,
        chain: str = "",
        task_description: str = "",
        estimated_value: str = "",
        difficulty: str = "",
        cost: str = "",
        url: str = "",
        deadline: str = "",
        status: str = "not_started",  # not_started, in_progress, completed, expired
        subtasks: Optional[List[Dict[str, Any]]] = None,
        notes: str = "",
        created_at: str = "",
        updated_at: str = "",
    ):
        self.task_id = task_id
        self.name = name
        self.chain = chain
        self.task_description = task_description
        self.estimated_value = estimated_value
        self.difficulty = difficulty
        self.cost = cost
        self.url = url
        self.deadline = deadline
        self.status = status
        self.subtasks = subtasks or []
        self.notes = notes
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self.updated_at = updated_at or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "chain": self.chain,
            "task_description": self.task_description,
            "estimated_value": self.estimated_value,
            "difficulty": self.difficulty,
            "cost": self.cost,
            "url": self.url,
            "deadline": self.deadline,
            "status": self.status,
            "subtasks": self.subtasks,
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AirdropTask":
        return cls(**{k: v for k, v in data.items() if k in cls.__init__.__code__.co_varnames})


class AirdropTracker:
    """Manages airdrop task tracking with Redis persistence."""

    def __init__(self, redis_client=None):
        self._redis = redis_client

    async def _load_all(self) -> Dict[str, Dict[str, Any]]:
        """Load all tracked airdrops from Redis."""
        if not self._redis:
            return {}
        try:
            raw = await self._redis.get(TRACKER_KEY)
            if raw:
                return json.loads(raw)
        except Exception as e:
            logger.warning(f"Failed to load airdrop tracker: {e}")
        return {}

    async def _save_all(self, data: Dict[str, Dict[str, Any]]):
        """Save all tracked airdrops to Redis."""
        if not self._redis:
            return
        try:
            await self._redis.set(TRACKER_KEY, json.dumps(data))
        except Exception as e:
            logger.warning(f"Failed to save airdrop tracker: {e}")

    async def list_tasks(self) -> List[Dict[str, Any]]:
        """List all tracked airdrop tasks."""
        data = await self._load_all()
        tasks = [AirdropTask.from_dict(v).to_dict() for v in data.values()]
        # Sort: in_progress first, then not_started, then completed, then expired
        status_order = {"in_progress": 0, "not_started": 1, "completed": 2, "expired": 3}
        tasks.sort(key=lambda t: status_order.get(t["status"], 99))
        return tasks

    async def add_task(
        self,
        name: str,
        chain: str = "",
        task_description: str = "",
        estimated_value: str = "",
        difficulty: str = "",
        cost: str = "",
        url: str = "",
        deadline: str = "",
    ) -> Dict[str, Any]:
        """Add a new airdrop task to track."""
        data = await self._load_all()
        task_id = str(uuid.uuid4())[:8]
        task = AirdropTask(
            task_id=task_id,
            name=name,
            chain=chain,
            task_description=task_description,
            estimated_value=estimated_value,
            difficulty=difficulty,
            cost=cost,
            url=url,
            deadline=deadline,
            status="not_started",
        )
        data[task_id] = task.to_dict()
        await self._save_all(data)
        return task.to_dict()

    async def update_task(self, task_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an existing airdrop task."""
        data = await self._load_all()
        if task_id not in data:
            return None

        task_data = data[task_id]
        for key, value in updates.items():
            if key in task_data and key not in ("task_id", "created_at"):
                task_data[key] = value

        task_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        data[task_id] = task_data
        await self._save_all(data)
        return AirdropTask.from_dict(task_data).to_dict()

    async def update_subtask(self, task_id: str, subtask_idx: int, completed: bool) -> Optional[Dict[str, Any]]:
        """Toggle a subtask completion status."""
        data = await self._load_all()
        if task_id not in data:
            return None

        task_data = data[task_id]
        subtasks = task_data.get("subtasks", [])
        if 0 <= subtask_idx < len(subtasks):
            subtasks[subtask_idx]["completed"] = completed
            # Auto-update parent status based on subtask completion
            all_done = all(st.get("completed", False) for st in subtasks)
            any_done = any(st.get("completed", False) for st in subtasks)
            if all_done:
                task_data["status"] = "completed"
            elif any_done:
                task_data["status"] = "in_progress"

        task_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        data[task_id] = task_data
        await self._save_all(data)
        return AirdropTask.from_dict(task_data).to_dict()

    async def delete_task(self, task_id: str) -> bool:
        """Remove a tracked airdrop task."""
        data = await self._load_all()
        if task_id not in data:
            return False
        del data[task_id]
        await self._save_all(data)
        return True

    async def get_stats(self) -> Dict[str, Any]:
        """Get tracker statistics."""
        tasks = await self.list_tasks()
        by_status = {}
        total_est_low = 0
        for t in tasks:
            status = t["status"]
            by_status[status] = by_status.get(status, 0) + 1
            # Parse estimated value
            est = t.get("estimated_value", "$0")
            try:
                val = int(est.replace("$", "").replace(",", "").split("-")[0].replace("+", ""))
                total_est_low += val
            except (ValueError, IndexError):
                pass

        return {
            "total": len(tasks),
            "by_status": by_status,
            "total_estimated_low": total_est_low,
        }


# Singleton
_tracker: Optional[AirdropTracker] = None


def get_airdrop_tracker(redis_client=None) -> AirdropTracker:
    global _tracker
    if _tracker is None:
        _tracker = AirdropTracker(redis_client=redis_client)
    return _tracker
