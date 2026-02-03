import aiohttp
from nonebot import require, get_bot, on_command
from src.utils.safe_bot import safe_get_bot
from nonebot.log import logger
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent
from nonebot.params import CommandArg
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import json
import os
from typing import Union
from nonebot import get_driver

# Initialize Scheduler
scheduler = AsyncIOScheduler()
driver = get_driver()

@driver.on_startup
async def start_scheduler():
    if not scheduler.running:
        scheduler.start()

CITY_MAPPING = {
    "北京": "Beijing",
    "上海": "Shanghai",
    "广州": "Guangzhou",
    "深圳": "Shenzhen",
    "杭州": "Hangzhou",
    "成都": "Chengdu",
    "武汉": "Wuhan",
    "南京": "Nanjing",
    "西安": "Xi'an",
    "重庆": "Chongqing",
    "天津": "Tianjin",
    "苏州": "Suzhou",
    "长沙": "Changsha",
    "沈阳": "Shenyang",
    "青岛": "Qingdao",
    "郑州": "Zhengzhou",
    "大连": "Dalian",
    "东莞": "Dongguan",
    "宁波": "Ningbo",
    "厦门": "Xiamen",
    "福州": "Fuzhou",
    "哈尔滨": "Harbin",
    "济南": "Jinan",
    "长春": "Changchun",
    "温州": "Wenzhou",
    "石家庄": "Shijiazhuang",
    "南宁": "Nanning",
    "合肥": "Hefei",
    "昆明": "Kunming",
    "南昌": "Nanchang",
    "无锡": "Wuxi",
    "常州": "Changzhou",
    "佛山": "Foshan"
}

async def get_weather(city="Guangzhou"):
    # Translate Chinese city name to English if possible
    query_city = CITY_MAPPING.get(city, city)
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        return "⚠️ 缺少 OpenWeatherMap API Key。请在 .env 文件中配置 OPENWEATHER_API_KEY。"

    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": query_city,
        "appid": api_key,
        "units": "metric",
        "lang": "zh_cn"
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    return f"⚠️ 获取 {city} 天气失败。状态码: {resp.status}"
                
                data = await resp.json()
                
                # Parse Data
                weather_desc = data["weather"][0]["description"]
                temp = data["main"]["temp"]
                feels_like = data["main"]["feels_like"]
                humidity = data["main"]["humidity"]
                wind_speed = data["wind"]["speed"]
                city_name = data["name"]
                
                # Format Report
                report = (
                    f"🌍 **{city_name} 实时天气播报**\n"
                    f"------------------------\n"
                    f"☁️ 天气状况：{weather_desc}\n"
                    f"🌡️ 当前温度：{temp}°C (体感 {feels_like}°C)\n"
                    f"💧 空气湿度：{humidity}%\n"
                    f"🌬️ 风速风向：{wind_speed} m/s\n"
                    f"------------------------\n"
                    f"最后更新：{data.get('dt')}"
                )
                return report
        except Exception as e:
            logger.error(f"Weather API Error: {e}")
            return f"⚠️ 获取天气出错: {str(e)}"

# Weather Command
weather_cmd = on_command("weather", aliases={"天气"}, priority=5)

@weather_cmd.handle()
async def handle_weather(event: Union[GroupMessageEvent, PrivateMessageEvent], args: Message = CommandArg()):
    city = args.extract_plain_text().strip()
    if not city:
        city = "Guangzhou"
    
    w = await get_weather(city)
    
    # Use smart forwarding
    from src.utils.message_forwarder import send_message_smart
    threshold = int(os.getenv("FORWARD_THRESHOLD", "100"))
    
    try:
        bot = get_bot()
        await send_message_smart(bot, w, event, threshold)
    except Exception:
        await weather_cmd.finish(w)

async def send_daily_weather():
    logger.info("Sending daily weather...")
    weather_report = await get_weather("Guangzhou")
    msg = f"🌅 早安！今日天气播报：\n\n{weather_report}"
    
    # Load target groups
    target_groups = json.loads(os.getenv("TARGET_GROUPS", "[]"))
    
    bot = safe_get_bot()
    if not bot:
        return
    for group_id in target_groups:
        try:
            # Check length for smart forwarding
            threshold = int(os.getenv("FORWARD_THRESHOLD", "100"))
            
            if len(msg) > threshold:
                from src.utils.message_forwarder import send_group_forward_message, split_text_into_paragraphs
                paragraphs = split_text_into_paragraphs(msg)
                await send_group_forward_message(bot, int(group_id), paragraphs)
            else:
                await bot.send_group_msg(group_id=int(group_id), message=msg)
                
            logger.info(f"Sent weather to group {group_id}")
        except Exception as e:
            logger.error(f"Failed to send weather to group {group_id}: {e}")

# Schedule weather at 8:00 AM
scheduler.add_job(send_daily_weather, "cron", hour=8, minute=0)
