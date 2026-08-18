import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from auth.dependencies import require_auth
from auth.models import User
from auth.store import get_notifications_for_user, mark_notification_read, mark_all_notifications_read

logger = logging.getLogger("backend")
router = APIRouter(prefix="/api/notifications", tags=["Notifications"])

@router.get("")
async def get_notifications(user: User = Depends(require_auth)) -> List[Dict[str, Any]]:
    return await get_notifications_for_user(user.id)

@router.post("/{notification_id}/read")
async def read_notification(notification_id: int, user: User = Depends(require_auth)):
    success = await mark_notification_read(notification_id, user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "success"}

@router.post("/read-all")
async def read_all_notifications(user: User = Depends(require_auth)):
    await mark_all_notifications_read(user.id)
    return {"status": "success"}
