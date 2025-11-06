"""应用配置模块"""
import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "4406")
DB_USER = os.getenv("DB_USER", "finance_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "finance_password")
DB_NAME = os.getenv("DB_NAME", "finance_db")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4",
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

DEFAULT_CATEGORIES = [
    {"name": "外卖", "description": "点外卖相关支出"},
    {"name": "生活用品", "description": "日常生活用品的消费，如洗衣液、纸巾等"},
    {"name": "电子产品", "description": "购买手机、电脑等电子设备的费用"},
    {"name": "房租水电", "description": "房屋租金与水电煤等杂费"},
    {"name": "外出就餐", "description": "在餐厅等外面吃饭的消费"},
    {"name": "周末游玩", "description": "周末娱乐、电影、聚会等花销"},
    {"name": "旅行", "description": "长途或短途旅行的全部花销"},
    {"name": "网络订阅", "description": "各类互联网订阅服务，如视频网站、音乐等"},
    {"name": "便利店", "description": "便利店的小额消费"},
    {"name": "Drinks", "description": "饮品、咖啡、奶茶等相关消费, 以及网购买酒等"},
    {"name": "出行", "description": "交通、打车、地铁、公交等相关费用"},
    {"name": "宠物", "description": "宠物相关的费用，如宠物食品、医疗等"},
    {"name": "医疗", "description": "医疗相关的费用，如看病、药品等"},
    {"name": "人情开销", "description": "人情往来、送礼等费用"},
    {"name": "娱乐", "description": "娱乐相关的费用，如电影、演唱会、游戏、网吧等"},
]
