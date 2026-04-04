"""
🚀 ملف التشغيل الرئيسي
"""
import os
import uvicorn
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from server import app
from utils import logger

# إضافة خادم الملفات الثابتة
if os.path.exists("templates"):
    @app.get("/")
    async def root():
        return FileResponse("templates/index.html")
    
    app.mount("/static", StaticFiles(directory="templates"), name="static")

if __name__ == "__main__":
    # 🔴 التعديل الأهم: جعل البورت ديناميكي ليتوافق مع Render المجاني
    port = int(os.environ.get("PORT", 8000))
    
    logger.info("=" * 60)
    logger.info("🚀 Social Downloader Pro - المحمل الخارق")
    logger.info("=" * 60)
    logger.info(f"📡 الواجهة الأمامية تعمل على البورت: {port}")
    logger.info("📚 توثيق API: /docs")
    logger.info("=" * 60)
    
    # 🔴 استخدمنا "main:app" كـ string لتفادي مشاكل الـ Workers
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_level="info"
    )