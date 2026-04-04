"""
🛠️ دوال مساعدة وأدوات عامة
"""
import logging
from typing import Tuple
from config import settings

# إعداد نظام السجلات
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("AlAmouriServer")


def detect_platform(url: str) -> Tuple[str, int]:
    """
    🔍 كشف منصة الفيديو من الرابط
    
    Args:
        url: رابط الفيديو
        
    Returns:
        tuple: (اسم المنصة، مدة الـ Cache بالثواني)
    """
    url_lower = url.lower()
    
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "youtube", settings.cache_ttl_youtube
    elif "tiktok.com" in url_lower or "tiktokv.com" in url_lower:
        return "tiktok", settings.cache_ttl_tiktok
    elif "facebook.com" in url_lower or "fb.watch" in url_lower:
        return "facebook", settings.cache_ttl_facebook
    elif "instagram.com" in url_lower:
        return "instagram", settings.cache_ttl_instagram
    else:
        return "other", 600  # 10 minutes


def format_file_size(size_bytes: int) -> str:
    """
    📊 تحويل حجم الملف إلى صيغة قابلة للقراءة
    
    Args:
        size_bytes: حجم الملف بالبايتات
        
    Returns:
        str: الحجم بصيغة قابلة للقراءة (MB, GB, إلخ)
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def sanitize_filename(filename: str) -> str:
    """
    🔒 تنظيف اسم الملف من الأحرف الخطرة
    
    Args:
        filename: اسم الملف الأصلي
        
    Returns:
        str: اسم الملف المنظف
    """
    import re
    # إزالة الأحرف غير الآمنة
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # استبدال المسافات بشرطات سفلية
    filename = filename.replace(' ', '_')
    # إزالة الأحرف الخاصة
    filename = re.sub(r'[^\w\-]', '', filename, flags=re.UNICODE)
    return filename[:255]  # تحديد الطول الأقصى لاسم الملف
