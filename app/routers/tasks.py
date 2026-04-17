from fastapi import APIRouter, HTTPException
from celery.result import AsyncResult
from app.workers.tasks import celery_app
from app.schemas.schemas import TaskStatusResponse

router = APIRouter(prefix="/tasks", tags=["Tasks"])

@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task(task_id: str):
    r = AsyncResult(task_id, app=celery_app)
    return TaskStatusResponse(
        task_id=task_id, status=r.status,
        result=r.result if r.successful() else None,
        error=str(r.result) if r.failed() else None,
    )