# ============================================================================
# 🚀 السيرفر الاحترافي (FastAPI + Async + Queue + Redis + Anti-Abuse)
# المتطلبات قبل التشغيل (قم بتثبيتها عبر الـ CMD):
# pip install fastapi uvicorn redis yt-dlp httpx prometheus-fastapi-instrumentator slowapi python-dotenv pydantic aiofiles
#
# أمر التشغيل للإنتاج:
# uvicorn main:app --host 0.0.0.0 --port 5000 --workers 4
# ============================================================================

import os
import re
import time
import json
import uuid
import logging
import asyncio
from typing import Optional
from dotenv import load_dotenv

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Depends, Header
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import redis.asyncio as redis
import yt_dlp
import httpx

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from prometheus_fastapi_instrumentator import Instrumentator

# ----------------------------------------------------------------------------
# 1. الإعدادات والبيئة (Environment & Setup)
# ----------------------------------------------------------------------------
load_dotenv()
API_KEY = os.getenv("API_KEY", "AlAmouri_Pro_123456")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# إعداد الـ Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("AlAmouriServer")

app = FastAPI(title="AlAmouri Pro API", version="2.0.0", description="Advanced Video Downloader API")

# إعداد CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# إعداد Rate Limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# إعداد Prometheus للمراقبة (Grafana)
Instrumentator().instrument(app).expose(app)

# الاتصال بـ Redis (Async)
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# ----------------------------------------------------------------------------
# 2. وظائف الحماية والذكاء (Security, Anti-Abuse & Detection)
# ----------------------------------------------------------------------------

def detect_platform(url: str):
    """التعرف التلقائي على المنصة وتحديد مدة الكاش (TTL) بناءً عليها"""
    url_lower = url.lower()
    if "tiktok.com" in url_lower or "tiktokv.com" in url_lower:
        return "tiktok", 3600  # 1 ساعة (روابط تيك توك تتغير بسرعة)
    elif "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "youtube", 86400  # 24 ساعة (يوتيوب مستقر)
    elif "facebook.com" in url_lower or "fb.watch" in url_lower:
        return "facebook", 7200  # ساعتين (فيسبوك)
    elif "instagram.com" in url_lower:
        return "instagram", 7200  # ساعتين (انستغرام)
    return "unknown", 600  # افتراضي 10 دقائق للبقية

async def anti_abuse_middleware(request: Request, call_next):
    """
    نظام Anti-Abuse قوي:
    يقوم بحظر الـ IP لمدة ساعة إذا حاول تجاوز الـ API Key بشكل متكرر
    ويقوم بإنشاء سجل إحصائيات للمراقبة
    """
    client_ip = request.client.host
    path = request.url.path

    if not redis_client:
        return await call_next(request)

    # التحقق من أن الآي بي محظور مسبقاً
    is_banned = await redis_client.get(f"ban_ip:{client_ip}")
    if is_banned:
        return JSONResponse(status_code=403, content={"error": "IP Address Banned. محظور بسبب نشاط مشبوه."})

    # التحقق من الـ API Key في المسارات التي تحتاج حماية
    if path.startswith("/api/") and not path.startswith("/api/download") and not path.startswith("/api/health"):
        api_key_header = request.headers.get("X-API-KEY")
        if api_key_header != API_KEY:
            # تسجيل محاولة فاشلة
            failed_attempts = await redis_client.incr(f"abuse:{client_ip}")
            await redis_client.expire(f"abuse:{client_ip}", 600)  # تنتهي المحاولات بعد 10 دقائق
            
            if failed_attempts >= 5:
                # حظر الـ IP لمدة ساعة بعد 5 محاولات فاشلة
                await redis_client.set(f"ban_ip:{client_ip}", "banned", ex=3600)
                logger.warning(f"🚨 تم حظر IP: {client_ip} لمدة ساعة بسبب 5 محاولات غير مصرح بها.")
                return JSONResponse(status_code=403, content={"error": "IP Address Banned for 1 hour."})
            return JSONResponse(status_code=401, content={"error": "Unauthorized Access"})

    # إحصائيات عامة
    response = await call_next(request)
    
    # زيادة عداد الطلبات الناجحة للمراقبة (Stats endpoint)
    if response.status_code == 200:
        await redis_client.incr("stats:total_requests")
    return response

app.middleware("http")(anti_abuse_middleware)

# ----------------------------------------------------------------------------
# 3. وظائف الخلفية (Background Tasks & Workers)
# ----------------------------------------------------------------------------

async def yt_dlp_auto_updater():
    """تحديث yt-dlp في الخلفية بدون حجب الاستجابات للمستخدمين (Async)"""
    while True:
        try:
            logger.info("جاري فحص وتحديث yt-dlp في الخلفية ♻️...")
            process = await asyncio.create_subprocess_exec(
                "yt-dlp", "-U",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            if process.returncode == 0:
                logger.info("تم تحديث yt-dlp التلقائي بنجاح 🔥")
            else:
                logger.error(f"فشل التحديث: {stderr.decode()}")
        except Exception as e:
            logger.error(f"خطأ أثناء تحديث yt-dlp: {e}")
        await asyncio.sleep(86400)  # يكرر كل 24 ساعة

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(yt_dlp_auto_updater())

# ----------------------------------------------------------------------------
# 4. نماذج التحقق (Pydantic Models)
# ----------------------------------------------------------------------------

class VideoRequest(BaseModel):
    url: str

# ----------------------------------------------------------------------------
# 5. نقاط نهاية المراقبة (Health & Stats)
# ----------------------------------------------------------------------------

@app.get("/api/health")
async def health_check():
    """حالة السيرفر للتحقق من كفاءته"""
    redis_status = await redis_client.ping() if redis_client else False
    return {
        "status": "Healthy 🚀",
        "redis_connected": redis_status,
        "uptime_info": "See Prometheus /metrics endpoint"
    }

@app.get("/api/stats")
async def get_stats():
    """إحصائيات السيرفر وطلبات التحميل"""
    if not redis_client:
        return {"error": "Redis Not Available"}
    
    total_req = await redis_client.get("stats:total_requests") or "0"
    total_dl = await redis_client.get("stats:total_downloads") or "0"
    total_extracts = await redis_client.get("stats:total_extracts") or "0"
    
    return {
        "success": True,
        "metrics": {
            "total_requests": int(total_req),
            "total_downloads": int(total_dl),
            "total_extractions": int(total_extracts)
        }
    }

# ----------------------------------------------------------------------------
# 6. نظام الانتظار والاستخراج الاحترافي (Queue System & Progress API)
# ----------------------------------------------------------------------------

def extract_video_info(url: str):
    """
    الدالة الثقيلة التي تستخدم yt-dlp، مجهزة للعمل داخل خيط منفصل لتفادي حظر (Blocking) سيرفر FastAPI.
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'socket_timeout': 15, # تقليل وقت الانتظار الطويل
        'extractor_args': {'tiktok': ['api_hostname=api22-normal-c-alisg.tiktokv.com']},
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info

async def process_queue_worker(job_id: str, url: str):
    """عامل الخلفية لمعالجة الرابط وحفظ النتيجة في Redis"""
    try:
        await redis_client.set(f"job:{job_id}:status", "processing")
        
        # تنفيذ الاستخراج في Thread منفصل للحفاظ على الـ Asynchronous
        info = await asyncio.to_thread(extract_video_info, url)
        
        if not info:
            raise Exception("No data returned")

        duration = info.get('duration', 0)
        if duration > 7200:
            raise Exception("الفيديو طويل جداً، الحد الأقصى ساعتين")

        # تنسيق البيانات
        title = info.get('title', 'Unknown Video')
        thumbnail = info.get('thumbnail', '')
        uploader = info.get('uploader', 'Unknown')
        
        formats = info.get('formats', [])
        videos = []
        audios = []
        
        for f in formats:
            filesize = f.get('filesize') or f.get('filesize_approx') or 0
            filesize_mb = round(filesize / (1024 * 1024), 2) if filesize else "غير معروف"

            if f.get('vcodec') != 'none' and f.get('ext') == 'mp4' and f.get('url') and f.get('height'):
                videos.append({'quality': f"{f.get('height')}p", 'height': f.get('height'), 'size_mb': filesize_mb, 'url': f.get('url')})
            if f.get('acodec') != 'none' and f.get('vcodec') == 'none' and f.get('url'):
                audios.append({'format': f.get('ext'), 'size_mb': filesize_mb, 'url': f.get('url')})

        videos = sorted(videos, key=lambda k: k['height'], reverse=True)
        unique_videos = list({v['height']: v for v in videos}.values())

        if not unique_videos and not audios:
            raise Exception("لم يتم العثور على وسائط قابلة للتحميل")

        # إعداد توكن محمي بالـ IP
        download_token = str(uuid.uuid4())
        
        # حفظ النتيجة في Redis
        result_data = {
            "title": title,
            "thumbnail": thumbnail,
            "duration": duration,
            "uploader": uploader,
            "videos": unique_videos,
            "audios": audios,
            "download_token": download_token,
        }
        
        # تحديد TTL بناءً على المنصة
        platform, cache_ttl = detect_platform(url)
        
        # حفظ التوكن (مرتبط بالرابط) لمدة ساعة
        await redis_client.set(f"dl_token:{download_token}", url, ex=3600)
        
        # حفظ نتيجة الجوب كـ Completed
        await redis_client.set(f"job:{job_id}:status", "completed", ex=cache_ttl)
        await redis_client.set(f"job:{job_id}:data", json.dumps(result_data), ex=cache_ttl)
        
        # حفظ كاش عام للرابط لتقليل الطلبات المستقبلية
        await redis_client.set(f"video_cache:{url}", json.dumps(result_data), ex=cache_ttl)

        # تحديث الإحصائيات
        await redis_client.incr("stats:total_extracts")

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        await redis_client.set(f"job:{job_id}:status", "failed", ex=600)
        await redis_client.set(f"job:{job_id}:error", str(e), ex=600)

@app.post("/api/extract")
@app.get("/api/extract")
@limiter.limit("15/minute")
async def extract_api(request: Request, bg_tasks: BackgroundTasks, url: str = None):
    """
    نقطة النهاية الحديثة بنظام Queue (الطابور).
    تُرجع job_id فوراً ليقوم العميل (Flutter) بتتبعه عبر Progress API.
    """
    # يدعم الـ GET والـ POST
    if request.method == 'POST':
        body = await request.json()
        url = body.get('url', url)
        
    if not url or not url.startswith("http"):
        return JSONResponse({"success": False, "error": "رابط غير صالح"}, status_code=400)

    # 1. فلترة وتحديد المنصة الذكي
    platform, _ = detect_platform(url)
    if platform == "unknown" and ("vimeo" not in url and "twitter" not in url):
        logger.warning(f"مرفوض: تم محاولة إدخال منصة غير مدعومة: {url}")
        # يمكن فتح الحظر لاحقاً، لكن هذه إضافة للحماية
        pass 

    # 2. الكاش الذكي: إذا كان الرابط موجود مسبقاً، نرجعه فوراً كـ completed job
    cache_key = f"video_cache:{url}"
    cached_data = await redis_client.get(cache_key)
    if cached_data:
        return {"success": True, "job_id": "cached", "status": "completed", "data": json.loads(cached_data)}

    # 3. إنشاء وظيفة جديدة
    job_id = str(uuid.uuid4())
    await redis_client.set(f"job:{job_id}:status", "pending", ex=600)
    
    # 4. إضافة للمعالجة في الخلفية
    bg_tasks.add_task(process_queue_worker, job_id, url)
    
    return {"success": True, "job_id": job_id, "status": "pending", "message": "تم إضافة الرابط في قائمة المعالجة"}

@app.get("/api/progress")
async def check_progress(job_id: str):
    """Progress API: لتتبع حالة استخراج الروابط (Pending -> Processing -> Completed/Failed)"""
    if job_id == "cached":
        return {"success": False, "error": "استخدم البيانات المعادة مباشرة"}
        
    status = await redis_client.get(f"job:{job_id}:status")
    if not status:
        return JSONResponse({"success": False, "status": "not_found", "error": "معرف المهمة غير موجود أو انتهت صلاحيته"}, status_code=404)
        
    if status == "completed":
        data = await redis_client.get(f"job:{job_id}:data")
        return {"success": True, "status": status, "data": json.loads(data)}
    elif status == "failed":
        error = await redis_client.get(f"job:{job_id}:error")
        return {"success": False, "status": status, "error": error}
    else:
        return {"success": True, "status": status}

# ----------------------------------------------------------------------------
# 7. نقطة التحميل مع دعم الـ (Resume/Range) والـ (Single-Use Token per IP)
# ----------------------------------------------------------------------------

@app.get("/api/download")
@limiter.limit("5/minute")
async def download_secure(request: Request, token: str, range: Optional[str] = Header(None)):
    """
    نقطة تحميل آمنة جداً تدعم:
    1. Single-use (محدود بـ IP).
    2. استكمال التحميل (Resume Download Support) عبر HTTP Range requests.
    3. البث المباشر (Streaming Response) لتفادي استهلاك سيرفر الـ RAM/Disk.
    """
    client_ip = request.client.host

    # 1. التحقق من التوكن (ربط التوكن بالـ IP)
    url = await redis_client.get(f"dl_token:{token}")
    if not url:
        return JSONResponse({"success": False, "error": "التوكن غير صالح أو منتهي الصلاحية"}, status_code=403)

    # التحقق من IP (نخزن الآي بي الأصلي في التوكن بمجرد الاستخدام الأول لضمان Resume لنفس الآي بي فقط)
    ip_binder_key = f"dl_token_ip:{token}"
    bound_ip = await redis_client.get(ip_binder_key)
    
    if not bound_ip:
        # الاستخدام الأول: نربط التوكن بالآي بي هذا لتفادي السرقة
        await redis_client.set(ip_binder_key, client_ip, ex=3600)
    elif bound_ip != client_ip:
        # إذا تم محاولة استخدام التوكن من شبكة أخرى (مسروق)
        logger.warning(f"🚨 محاولة سرقة توكن! توكن: {token} مسجل لـ {bound_ip} ومطلوب من {client_ip}")
        return JSONResponse({"success": False, "error": "عذراً، لا يمكن استكمال التحميل من شبكة إنترنت مختلفة"}, status_code=403)

    logger.info(f"طلب تحميل آمن للرابط عبر التوكن (IP: {client_ip}) - Range: {range}")

    # استخراج الرابط المباشر للملف الفعلي عبر yt-dlp
    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {'tiktok': ['api_hostname=api22-normal-c-alisg.tiktokv.com']},
    }

    try:
        # نستخدم to_thread لتفادي إيقاف السيرفر
        info = await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(url, download=False))
        video_url = info.get('url')
        title = info.get('title', 'video').replace('/', '_').replace('\\', '_')
        
        if not video_url:
            raise HTTPException(status_code=404, detail="لم يتم العثور على رابط التحميل المباشر")

        # تجهيز الترويسات لدعم الـ Resume (Range requests)
        headers = {}
        if range:
            headers['Range'] = range
            
        # الاتصال بالسيرفر المصدر بشكل غير متزامن (Async) ودعم الـ Stream
        # نستعمل timeout طويل نسبياً للـ stream
        client = httpx.AsyncClient(timeout=30.0)
        req = await client.get(video_url, headers=headers)
        
        # التحقق من حجم الملف
        max_size_bytes = 200 * 1024 * 1024  # 200 ميجا
        content_length = int(req.headers.get('Content-Length', 0))
        
        # إذا كان طلب Range، الحجم الإجمالي يكون في Content-Range
        total_size = content_length
        content_range = req.headers.get('Content-Range')
        if content_range:
            try:
                total_size = int(content_range.split('/')[-1])
            except: pass
            
        if total_size > max_size_bytes:
            await req.aclose()
            return JSONResponse({"success": False, "error": "حجم الملف يتجاوز الحد المسموح به (200MB)"}, status_code=400)

        # الترويسات التي سنرسلها لتطبيق الموبايل
        response_headers = {
            'Content-Disposition': f'attachment; filename="{title}.mp4"',
            'Content-Type': req.headers.get('Content-Type', 'video/mp4'),
            'Accept-Ranges': 'bytes'
        }
        
        if 'Content-Range' in req.headers:
            response_headers['Content-Range'] = req.headers['Content-Range']
        if 'Content-Length' in req.headers:
            response_headers['Content-Length'] = req.headers['Content-Length']

        # زيادة الإحصائيات (نجاح التحميل)
        if not range:  # نحسب التحميلة مرة واحدة وليست مع كل Range chunk
            await redis_client.incr("stats:total_downloads")

        # بث الاستجابة لتطبيق الموبايل بشكل متزامن وبدعم كامل للاستكمال
        async def stream_generator():
            async for chunk in req.aiter_bytes(chunk_size=1024*1024):  # 1MB Chunks
                if chunk:
                    yield chunk
            await req.aclose()

        status_code = req.status_code if req.status_code in [200, 206] else 200
        return StreamingResponse(
            stream_generator(),
            status_code=status_code,
            headers=response_headers
        )

    except httpx.TimeoutException:
        logger.error("Timeout fetching final video url.")
        return JSONResponse({"success": False, "error": "انتهى وقت الاتصال بالسيرفر المصدر"}, status_code=504)
    except Exception as e:
        logger.error(f"Download stream error: {e}")
        return JSONResponse({"success": False, "error": f"حدث خطأ غير متوقع: {str(e)}"}, status_code=500)

# ============================================================================
# دالة التوافقية للمسار القديم (/get_video) في تطبيق الفلاتر
# (تقوم بالاستخراج المباشر بدون Queue إذا كان التطبيق يستخدم الطريقة القديمة)
# ============================================================================
@app.get("/get_video")
@limiter.limit("15/minute")
async def get_video_legacy(request: Request, url: str = None):
    if not url or not url.startswith("http"):
        return JSONResponse({"success": False, "error": "الرجاء إرسال رابط صحيح"}, status_code=400)
        
    cache_key = f"video_cache:{url}"
    cached_data = await redis_client.get(cache_key)
    if cached_data:
        return json.loads(cached_data)

    try:
        info = await asyncio.to_thread(extract_video_info, url)
        
        duration = info.get('duration', 0)
        if duration > 7200:
             return JSONResponse({"success": False, "error": "الفيديو طويل جداً، الحد الأقصى ساعتين"}, status_code=400)

        title = info.get('title', 'Unknown Video')
        thumbnail = info.get('thumbnail', '')
        uploader = info.get('uploader', 'Unknown')
        
        download_token = str(uuid.uuid4())
        await redis_client.set(f"dl_token:{download_token}", url, ex=3600)
        
        formats = info.get('formats', [])
        videos, audios = [], []
        
        for f in formats:
            filesize = f.get('filesize') or f.get('filesize_approx') or 0
            filesize_mb = round(filesize / (1024 * 1024), 2) if filesize else "غير معروف"
            if f.get('vcodec') != 'none' and f.get('ext') == 'mp4' and f.get('url') and f.get('height'):
                videos.append({'quality': f"{f.get('height')}p", 'height': f.get('height'), 'size_mb': filesize_mb, 'url': f.get('url')})
            if f.get('acodec') != 'none' and f.get('vcodec') == 'none' and f.get('url'):
                audios.append({'format': f.get('ext'), 'size_mb': filesize_mb, 'url': f.get('url')})

        if not videos and not audios:
            return JSONResponse({"success": False, "error": "لم يتم العثور على وسائط قابلة للتحميل"}, status_code=404)

        videos = sorted(videos, key=lambda k: k['height'], reverse=True)
        unique_videos = list({v['height']: v for v in videos}.values())

        result = {
            "success": True,
            "note": "⚠️ الروابط مؤقتة.",
            "download_token": download_token,
            "data": {
                "title": title,
                "thumbnail": thumbnail,
                "duration": duration,
                "uploader": uploader,
                "videos": unique_videos,
                "audios": audios
            }
        }
        
        platform, cache_ttl = detect_platform(url)
        await redis_client.set(cache_key, json.dumps(result), ex=cache_ttl)
        await redis_client.incr("stats:total_extracts")
        
        return result
        
    except Exception as e:
        logger.error(f"Legacy Extraction Error: {e}")
        return JSONResponse({"success": False, "error": "حدث خطأ أثناء معالجة الرابط، تأكد من صحته"}, status_code=500)