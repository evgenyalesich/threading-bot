from fastapi import APIRouter, HTTPException

from app.schemas.automation import (
    AutomationConfigUpdate,
    AutomationModeUpdate,
    AutomationStateRead,
    AutomationTradeEnvUpdate,
)
from app.services.automation_runtime import get_automation_runtime


router = APIRouter()


@router.get("")
async def get_automation_state() -> AutomationStateRead:
    return await get_automation_runtime().snapshot()


@router.post("/configure")
async def configure_automation(payload: AutomationConfigUpdate) -> AutomationStateRead:
    runtime = get_automation_runtime()
    runtime.update_config(**payload.model_dump(exclude_none=True))
    return await runtime.snapshot()


@router.post("/enable")
async def enable_automation() -> AutomationStateRead:
    runtime = get_automation_runtime()
    runtime.set_enabled(True)
    return await runtime.snapshot()


@router.post("/disable")
async def disable_automation() -> AutomationStateRead:
    runtime = get_automation_runtime()
    runtime.set_enabled(False)
    return await runtime.snapshot()


@router.post("/mode")
async def set_automation_mode(payload: AutomationModeUpdate) -> AutomationStateRead:
    runtime = get_automation_runtime()
    runtime.set_mode(payload.mode)
    return await runtime.snapshot()


@router.post("/trade-env")
async def set_automation_trade_env(payload: AutomationTradeEnvUpdate) -> AutomationStateRead:
    runtime = get_automation_runtime()
    runtime.set_trade_env(payload.trade_env)
    return await runtime.snapshot()


@router.post("/run")
async def run_automation_now() -> AutomationStateRead:
    runtime = get_automation_runtime()
    await runtime.run_cycle_now()
    return await runtime.snapshot()


@router.post("/pending/{signal_id}/approve")
async def approve_pending_signal(signal_id: int) -> AutomationStateRead:
    runtime = get_automation_runtime()
    order = await runtime.approve(signal_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Pending signal not found")
    return await runtime.snapshot()


@router.post("/pending/{signal_id}/reject")
async def reject_pending_signal(signal_id: int) -> AutomationStateRead:
    runtime = get_automation_runtime()
    if not runtime.reject(signal_id):
        raise HTTPException(status_code=404, detail="Pending signal not found")
    return await runtime.snapshot()
