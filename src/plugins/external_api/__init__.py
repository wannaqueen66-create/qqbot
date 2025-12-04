import nonebot
from fastapi import FastAPI
from pydantic import BaseModel
from nonebot.log import logger
from nonebot import get_bot

app: FastAPI = nonebot.get_app()

class NotifyRequest(BaseModel):
    message: str
    group_id: int = None
    user_id: int = None

@app.post("/api/notify")
async def notify(request: NotifyRequest):
    logger.info(f"Received API notification: {request}")
    
    # In a real scenario, we would get the bot instance and send the message
    # bot = get_bot()
    # if request.group_id:
    #     await bot.send_group_msg(group_id=request.group_id, message=request.message)
    # elif request.user_id:
    #     await bot.send_private_msg(user_id=request.user_id, message=request.message)
    
    return {"status": "success", "message": "Notification received (logged only for MVP)"}

# Example of another endpoint
@app.get("/api/status")
async def status():
    return {"status": "online", "plugins": ["basic_ops", "rss_sub", "scheduler", "ai_summary", "external_api"]}
