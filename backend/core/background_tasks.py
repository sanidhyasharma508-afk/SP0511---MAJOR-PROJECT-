import asyncio
import uuid
from typing import Callable, Any, Optional, Dict, List
from datetime import datetime, timedelta
from enum import Enum
import json

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger("background_tasks")


class TaskStatus(str, Enum):
    """Task status enum"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BackgroundTask:
    """Represents a background task"""

    def __init__(
        self, task_id: str, name: str, func: Callable, args: tuple = (), kwargs: dict = None
    ):
        self.task_id = task_id
        self.name = name
        self.func = func
        self.args = args
        self.kwargs = kwargs or {}
        self.status = TaskStatus.PENDING
        self.result = None
        self.error = None
        self.created_at = datetime.utcnow()
        self.started_at = None
        self.completed_at = None
        self.progress = 0
        self.metadata: Dict[str, Any] = {}

    async def execute(self) -> Any:
        """Execute the task"""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.utcnow()

        logger.log_event("task_started", level="INFO", task_id=self.task_id, task_name=self.name)

        try:
            if asyncio.iscoroutinefunction(self.func):
                self.result = await self.func(*self.args, **self.kwargs)
            else:
                self.result = self.func(*self.args, **self.kwargs)

            self.status = TaskStatus.COMPLETED
            self.completed_at = datetime.utcnow()
            duration = (self.completed_at - self.started_at).total_seconds()

            logger.log_event(
                "task_completed",
                level="INFO",
                task_id=self.task_id,
                task_name=self.name,
                duration=duration,
            )

            return self.result

        except Exception as e:
            self.status = TaskStatus.FAILED
            self.error = str(e)
            self.completed_at = datetime.utcnow()

            logger.log_error("task_failed", e, task_id=self.task_id, task_name=self.name)

            raise

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary"""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress": self.progress,
            "metadata": self.metadata,
        }


class TaskQueue:
    """Task queue for managing background tasks"""

    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers
        self.tasks: Dict[str, BackgroundTask] = {}
        self.queue: asyncio.Queue = asyncio.Queue()
        self.workers_running = False
        self.completed_tasks: List[str] = []  # Store completed task IDs
        self.retention_days = 7  # Keep completed tasks for 7 days

    async def start(self):
        """Start task queue workers"""
        if self.workers_running:
            return

        self.workers_running = True

        for _ in range(self.max_workers):
            asyncio.create_task(self._worker())

        logger.log_event("task_queue_started", level="INFO", max_workers=self.max_workers)

    async def stop(self):
        """Stop task queue workers"""
        self.workers_running = False
        logger.log_event("task_queue_stopped", level="INFO")

    async def _worker(self):
        """Worker coroutine to process tasks"""
        while self.workers_running:
            try:
                task_id = await asyncio.wait_for(self.queue.get(), timeout=1.0)

                if task_id is None:  # Sentinel value to stop worker
                    break

                task = self.tasks.get(task_id)
                if task:
                    await task.execute()
                    self.completed_tasks.append(task_id)

                self.queue.task_done()

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.log_error("worker_error", e)

    async def submit(self, name: str, func: Callable, *args, **kwargs) -> str:
        """Submit a task to the queue"""
        task_id = str(uuid.uuid4())
        task = BackgroundTask(task_id, name, func, args, kwargs)

        self.tasks[task_id] = task
        await self.queue.put(task_id)

        logger.log_event("task_submitted", level="INFO", task_id=task_id, task_name=name)

        return task_id

    def get_task(self, task_id: str) -> Optional[BackgroundTask]:
        """Get task by ID"""
        return self.tasks.get(task_id)

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status"""
        task = self.tasks.get(task_id)
        if task:
            return task.to_dict()
        return None

    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """Get all tasks"""
        return [task.to_dict() for task in self.tasks.values()]

    def get_pending_tasks(self) -> List[Dict[str, Any]]:
        """Get pending tasks"""
        return [task.to_dict() for task in self.tasks.values() if task.status == TaskStatus.PENDING]

    def get_running_tasks(self) -> List[Dict[str, Any]]:
        """Get running tasks"""
        return [task.to_dict() for task in self.tasks.values() if task.status == TaskStatus.RUNNING]

    def get_completed_tasks(self) -> List[Dict[str, Any]]:
        """Get completed tasks"""
        return [
            task.to_dict() for task in self.tasks.values() if task.status == TaskStatus.COMPLETED
        ]

    def get_failed_tasks(self) -> List[Dict[str, Any]]:
        """Get failed tasks"""
        return [task.to_dict() for task in self.tasks.values() if task.status == TaskStatus.FAILED]

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task"""
        task = self.tasks.get(task_id)
        if task and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.CANCELLED
            logger.log_event("task_cancelled", level="INFO", task_id=task_id)
            return True
        return False

    async def cleanup_old_tasks(self):
        """Clean up old completed tasks"""
        cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)

        tasks_to_delete = [
            task_id
            for task_id, task in self.tasks.items()
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]
            and task.completed_at
            and task.completed_at < cutoff_date
        ]

        for task_id in tasks_to_delete:
            del self.tasks[task_id]

        if tasks_to_delete:
            logger.log_event("old_tasks_cleaned", level="INFO", cleaned_count=len(tasks_to_delete))


# Global task queue
task_queue = TaskQueue(max_workers=5)


async def submit_background_task(name: str, func: Callable, *args, **kwargs) -> str:
    """Submit a background task"""
    if not settings.ENABLE_BACKGROUND_TASKS:
        logger.log_event("background_tasks_disabled", level="WARNING")
        return ""

    return await task_queue.submit(name, func, *args, **kwargs)


def background_task(name: str = None):
    """Decorator to run function as background task"""

    def decorator(func: Callable):
        task_name = name or func.__name__

        async def async_wrapper(*args, **kwargs):
            if not settings.ENABLE_BACKGROUND_TASKS:
                # Run synchronously if background tasks disabled
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                return func(*args, **kwargs)

            # Submit as background task
            task_id = await submit_background_task(task_name, func, *args, **kwargs)
            return {"task_id": task_id, "status": "submitted"}

        def sync_wrapper(*args, **kwargs):
            if not settings.ENABLE_BACKGROUND_TASKS:
                return func(*args, **kwargs)

            # Submit as background task (sync)
            import asyncio

            loop = asyncio.get_event_loop()
            task_id = loop.run_until_complete(
                submit_background_task(task_name, func, *args, **kwargs)
            )
            return {"task_id": task_id, "status": "submitted"}

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class ScheduledTask:
    """Represents a scheduled task"""

    def __init__(self, name: str, func: Callable, interval: int, description: str = ""):
        self.name = name
        self.func = func
        self.interval = interval  # seconds
        self.description = description
        self.last_run = None
        self.next_run = datetime.utcnow()
        self.run_count = 0
        self.error_count = 0

    async def should_run(self) -> bool:
        """Check if task should run"""
        return datetime.utcnow() >= self.next_run

    async def execute(self):
        """Execute the task"""
        try:
            logger.log_event("scheduled_task_started", level="INFO", task_name=self.name)

            if asyncio.iscoroutinefunction(self.func):
                await self.func()
            else:
                self.func()

            self.last_run = datetime.utcnow()
            self.next_run = datetime.utcnow() + timedelta(seconds=self.interval)
            self.run_count += 1

            logger.log_event(
                "scheduled_task_completed",
                level="INFO",
                task_name=self.name,
                run_count=self.run_count,
            )

        except Exception as e:
            self.error_count += 1
            logger.log_error(
                "scheduled_task_failed", e, task_name=self.name, error_count=self.error_count
            )


class TaskScheduler:
    """Scheduler for periodic tasks"""

    def __init__(self):
        self.tasks: Dict[str, ScheduledTask] = {}
        self.running = False

    def schedule(self, name: str, func: Callable, interval: int, description: str = "") -> str:
        """Schedule a periodic task"""
        task = ScheduledTask(name, func, interval, description)
        self.tasks[name] = task

        logger.log_event(
            "task_scheduled",
            level="INFO",
            task_name=name,
            interval=interval,
            description=description,
        )

        return name

    async def start(self):
        """Start the scheduler"""
        if self.running:
            return

        self.running = True
        logger.log_event("scheduler_started", level="INFO", tasks_count=len(self.tasks))

        while self.running:
            for task in self.tasks.values():
                if await task.should_run():
                    await task.execute()

            await asyncio.sleep(1)  # Check every second

    async def stop(self):
        """Stop the scheduler"""
        self.running = False
        logger.log_event("scheduler_stopped", level="INFO")


# Global scheduler
scheduler = TaskScheduler()
