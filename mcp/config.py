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

CATEGORY_COLOR_PALETTE = [
    "#5E81AC",
    "#88C0D0",
    "#A3BE8C",
    "#EBCB8B",
    "#D08770",
    "#B48EAD",
    "#7CC6FE",
    "#95E1D3",
    "#FFD6A5",
    "#FFB4A2",
    "#BDE0FE",
    "#CDB4DB",
    "#F4A259",
    "#C0D9AF",
    "#9C89B8",
    "#F6BD60",
    "#A0D2DB",
    "#C9BBCF",
    "#B5E48C",
    "#F1A7A1",
    "#9ADCFF",
    "#E8E8A6",
    "#D4A5A5",
    "#A29BFE",
    "#E3B5A4",
    "#86A8E7",
    "#BEE3DB",
    "#F2A7B3",
    "#B3C5F2",
    "#F4D6CC",
]

UNCATEGORIZED_CATEGORY_COLOR = "#CBD5E1"
OTHER_CATEGORY_COLOR = "#E2E8F0"

DEFAULT_CATEGORIES = [
    {"name": "外卖", "description": "点外卖相关支出", "color": "#5E81AC"},
    {"name": "生活用品", "description": "日常生活用品的消费，如洗衣液、纸巾等", "color": "#88C0D0"},
    {"name": "电子产品", "description": "购买手机、电脑等电子设备的费用", "color": "#A3BE8C"},
    {"name": "房租水电", "description": "房屋租金与水电煤等杂费", "color": "#EBCB8B"},
    {"name": "外出就餐", "description": "在餐厅等外面吃饭的消费", "color": "#D08770"},
    {"name": "周末游玩", "description": "周末娱乐、电影、聚会等花销", "color": "#B48EAD"},
    {"name": "旅行", "description": "长途或短途旅行的全部花销", "color": "#7CC6FE"},
    {"name": "网络订阅", "description": "各类互联网订阅服务，如视频网站、音乐等", "color": "#95E1D3"},
    {"name": "便利店", "description": "便利店的小额消费", "color": "#FFD6A5"},
    {"name": "Drinks", "description": "饮品、咖啡、奶茶等相关消费, 以及网购买酒等", "color": "#FFB4A2"},
    {"name": "出行", "description": "交通、打车、地铁、公交等相关费用", "color": "#BDE0FE"},
    {"name": "宠物", "description": "宠物相关的费用，如宠物食品、医疗等", "color": "#CDB4DB"},
    {"name": "医疗", "description": "医疗相关的费用，如看病、药品等", "color": "#F4A259"},
    {"name": "人情开销", "description": "人情往来、送礼等费用", "color": "#C0D9AF"},
    {"name": "娱乐", "description": "娱乐相关的费用，如电影、演唱会、游戏、网吧等", "color": "#9C89B8"},
]

COS_SECRET_ID = os.getenv("TENCENT_COS_SECRET_ID")
COS_SECRET_KEY = os.getenv("TENCENT_COS_SECRET_KEY")
COS_REGION = os.getenv("TENCENT_COS_REGION")
COS_BUCKET = os.getenv("TENCENT_COS_BUCKET")
COS_BASE_URL = os.getenv("TENCENT_COS_BASE_URL")
COS_PATH_PREFIX = os.getenv("TENCENT_COS_PATH_PREFIX", "finance-tracker/charts")
