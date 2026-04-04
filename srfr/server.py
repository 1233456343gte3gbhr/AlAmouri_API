"""
🚀 السيرفر الرئيسي - Social Downloader Pro
نظام تحميل الفيديوهات من منصات التواصل الاجتماعي بدون علامة مائية
"""
import os
import uuid
import asyncio
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Header
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from prometheus_fastapi_instrumentator import Instrumentator
import httpx

from config import settings
from cache import cache
from extractors import extractor
from utils import logger, detect_platform, sanitize_filename

# ============================================================================
# إعداد التطبيق
# ============================================================================

app = FastAPI(
    title="Social Downloader Pro API",
    description="🎬 نظام تحميل الفيديوهات من منصات التواصل الاجتماعي",
    version="4.0.0"
)

# إضافة CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# إعداد Rate Limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# إضافة Prometheus Metrics
Instrumentator().instrument(app).expose(app)

# ============================================================================
# نماذج البيانات (Pydantic Models)
# ============================================================================

class ExtractRequest(BaseModel):
    """نموذج طلب استخراج البيانات"""
    url: HttpUrl


class DownloadRequest(BaseModel):
    """نموذج طلب التحميل"""
    url: HttpUrl
    quality: str = "best"


class VideoInfo(BaseModel):
    """معلومات الفيديو"""
    title: str
    thumbnail: str
    duration: int
    uploader: str
    platform: str
    videos: list
    audios: list


# ============================================================================
# نظام معالجة الطلبات في الخلفية
# ============================================================================

jobs = {}  # تخزين حالة الوظائف


async def process_video_job(job_id: str, url: str):
    """معالجة الفيديو في الخلفية"""
    try:
        jobs[job_id] = {'status': 'processing', 'progress': 0}
        
        platform, cache_ttl = detect_platform(str(url))
        
        # محاولة الحصول من الـ Cache أولاً
        cache_key = f"video:{url}"
        cached_data = cache.get(cache_key)
        if cached_data:
            jobs[job_id] = {'status': 'completed', 'data': cached_data, 'cached': True}
            return
        
        # استخراج البيانات
        if platform == "tiktok":
            data = await extractor.extract_tiktok(str(url))
        elif platform == "youtube":
            data = await extractor.extract_youtube(str(url))
        else:
            data = await extractor.extract_others(str(url))
        
        if not data.get('videos') and not data.get('audios'):
            raise Exception("لم يتم العثور على وسائط، المقطع محمي أو محذوف.")
        
        # حفظ في الـ Cache
        cache.set(cache_key, data, cache_ttl)
        
        jobs[job_id] = {'status': 'completed', 'data': data, 'cached': False}
        
    except Exception as e:
        logger.error(f"خطأ في معالجة الوظيفة {job_id}: {str(e)}")
        jobs[job_id] = {'status': 'failed', 'error': str(e)}


# ============================================================================
# المسارات (Routes)
# ============================================================================

@app.get("/", tags=["الرئيسية"])
async def root():
    """الصفحة الرئيسية"""
    return {
        "name": "Social Downloader Pro API",
        "version": "4.0.0",
        "status": "🟢 يعمل",
        "description": "نظام تحميل الفيديوهات من منصات التواصل الاجتماعي بدون علامة مائية"
    }


@app.get("/health", tags=["الصحة"])
async def health_check():
    """فحص صحة السيرفر"""
    cache_stats = cache.get_stats()
    return {
        "status": "healthy",
        "cache": cache_stats
    }


@app.post("/api/extract", tags=["استخراج البيانات"])
@limiter.limit("20/minute")
async def extract_video(
    request: Request,
    data: ExtractRequest,
    background_tasks: BackgroundTasks
):
    """
    استخراج بيانات الفيديو من الرابط
    
    - **url**: رابط الفيديو (TikTok, YouTube, Facebook, Instagram)
    """
    try:
        url = str(data.url)
        logger.info(f"طلب استخراج: {url}")
        
        # التحقق من صحة الرابط
        if not url.startswith(('http://', 'https://')):
            raise HTTPException(status_code=400, detail="رابط غير صحيح")
        
        # محاولة الحصول من الـ Cache أولاً
        cache_key = f"video:{url}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return {
                "success": True,
                "data": cached_data,
                "cached": True
            }
        
        # استخراج البيانات مباشرة
        platform, cache_ttl = detect_platform(url)
        
        if platform == "tiktok":
            result = await extractor.extract_tiktok(url)
        elif platform == "youtube":
            result = await extractor.extract_youtube(url)
        else:
            result = await extractor.extract_others(url)
        
        if not result.get('videos') and not result.get('audios'):
            raise HTTPException(
                status_code=404,
                detail="لم يتم العثور على وسائط، المقطع محمي أو محذوف."
            )
        
        # حفظ في الـ Cache
        cache.set(cache_key, result, cache_ttl)
        
        return {
            "success": True,
            "data": result,
            "cached": False
        }
        
    except Exception as e:
        logger.error(f"خطأ في الاستخراج: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/api/extract-async", tags=["استخراج البيانات"])
@limiter.limit("20/minute")
async def extract_video_async(
    request: Request,
    data: ExtractRequest,
    background_tasks: BackgroundTasks
):
    """
    استخراج بيانات الفيديو بشكل غير متزامن (في الخلفية)
    
    - **url**: رابط الفيديو
    
    Returns:
        job_id: معرف الوظيفة للتحقق من الحالة
    """
    try:
        url = str(data.url)
        job_id = str(uuid.uuid4())
        
        logger.info(f"وظيفة جديدة: {job_id} - {url}")
        
        # بدء المعالجة في الخلفية
        background_tasks.add_task(process_video_job, job_id, url)
        
        return {
            "success": True,
            "job_id": job_id,
            "status": "pending"
        }
        
    except Exception as e:
        logger.error(f"خطأ في الاستخراج غير المتزامن: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/api/job/{job_id}", tags=["حالة الوظائف"])
async def get_job_status(job_id: str):
    """الحصول على حالة الوظيفة"""
    if job_id not in jobs:
        return {
            "success": False,
            "error": "الوظيفة غير موجودة"
        }
    
    job = jobs[job_id]
    return {
        "success": True,
        "job_id": job_id,
        "status": job['status'],
        "data": job.get('data'),
        "error": job.get('error')
    }


@app.post("/api/download", tags=["التحميل"])
@limiter.limit("10/minute")
async def download_video(
    request: Request,
    url: str,
    quality: str = "best",
    range: str = Header(None)
):
    """
    تحميل الفيديو مباشرة
    
    - **url**: رابط الفيديو
    - **quality**: الجودة المطلوبة (best, worst, إلخ)
    """
    try:
        logger.info(f"طلب تحميل: {url}")
        
        platform, _ = detect_platform(url)
        
        # استخراج البيانات أولاً
        if platform == "tiktok":
            data = await extractor.extract_tiktok(url)
        elif platform == "youtube":
            data = await extractor.extract_youtube(url)
        else:
            data = await extractor.extract_others(url)
        
        # اختيار أفضل جودة
        if data.get('videos'):
            video = data['videos'][0]  # الأولى هي الأفضل (مرتبة)
            video_url = video.get('url')
            title = sanitize_filename(data.get('title', 'video'))
        else:
            raise HTTPException(status_code=404, detail="لا توجد فيديوهات متاحة")
        
        # تحميل الفيديو
        async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
            response = await client.get(video_url)
            
            if response.status_code not in [200, 206]:
                raise HTTPException(
                    status_code=400,
                    detail="المصدر رفض الطلب"
                )
            
            return StreamingResponse(
                response.aiter_bytes(chunk_size=1024*1024),
                media_type=response.headers.get('Content-Type', 'video/mp4'),
                headers={
                    'Content-Disposition': f'attachment; filename=\"{title}.mp4\"',
                    'Accept-Ranges': 'bytes'
                }
            )
        
    except Exception as e:
        logger.error(f"خطأ في التحميل: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/api/stats", tags=["الإحصائيات"])
async def get_stats():
    """الحصول على إحصائيات السيرفر"""
    cache_stats = cache.get_stats()
    
    return {
        "cache": cache_stats,
        "jobs": {
            "total": len(jobs),
            "completed": sum(1 for j in jobs.values() if j['status'] == 'completed'),
            "failed": sum(1 for j in jobs.values() if j['status'] == 'failed'),
            "processing": sum(1 for j in jobs.values() if j['status'] == 'processing')
        }
    }


# ============================================================================
# معالجة الأخطاء
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"خطأ عام: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "حدث خطأ داخلي في السيرفر"
        }
    )


# ============================================================================
# تشغيل السيرفر
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"🚀 بدء السيرفر على {settings.host}:{settings.port}")
    
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower()
    )
