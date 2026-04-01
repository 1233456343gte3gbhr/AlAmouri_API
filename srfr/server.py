# ============================================================================
# 🚀 السيرفر الاحترافي (FastAPI + Async + Queue + Memory Cache + Anti-Abuse)
# تم التحديث: تخطي حمايات تيك توك، انستقرام، يوتيوب، فيسبوك ومنع الملفات المعطوبة
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("AlAmouriServer")

app = FastAPI(title="AlAmouri Pro API", version="2.0.0", description="Advanced Video Downloader API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

Instrumentator().instrument(app).expose(app)

# ----------------------------------------------------------------------------
# ⚡ بديل Redis (نظام كاش يعتمد على الذاكرة)
# ----------------------------------------------------------------------------
class MemoryCache:
    def __init__(self):
        self.store = {}
    
    async def get(self, key):
        return self.store.get(key)
        
    async def set(self, key, value, ex=None):
        self.store[key] = str(value)
        
    async def incr(self, key):
        self.store[key] = str(int(self.store.get(key, "0")) + 1)
        return int(self.store[key])
        
    async def expire(self, key, time):
        pass 
        
    async def ping(self):
        return True

redis_client = MemoryCache()

# ----------------------------------------------------------------------------
# 2. وظائف الحماية والذكاء (Security, Anti-Abuse & Detection)
# ----------------------------------------------------------------------------

def detect_platform(url: str):
    url_lower = url.lower()
    if "tiktok.com" in url_lower or "tiktokv.com" in url_lower:
        return "tiktok", 3600  
    elif "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "youtube", 86400  
    elif "facebook.com" in url_lower or "fb.watch" in url_lower:
        return "facebook", 7200  
    elif "instagram.com" in url_lower:
        return "instagram", 7200  
    return "unknown", 600  

async def anti_abuse_middleware(request: Request, call_next):
    client_ip = request.client.host
    path = request.url.path

    is_banned = await redis_client.get(f"ban_ip:{client_ip}")
    if is_banned:
        return JSONResponse(status_code=403, content={"error": "IP Address Banned. محظور بسبب نشاط مشبوه."})

    if path.startswith("/api/") and not path.startswith("/api/download") and not path.startswith("/api/health"):
        api_key_header = request.headers.get("X-API-KEY")
        if api_key_header != API_KEY:
            failed_attempts = await redis_client.incr(f"abuse:{client_ip}")
            await redis_client.expire(f"abuse:{client_ip}", 600)
            
            if failed_attempts >= 5:
                await redis_client.set(f"ban_ip:{client_ip}", "banned", ex=3600)
                logger.warning(f"🚨 تم حظر IP: {client_ip} لمدة ساعة بسبب 5 محاولات غير مصرح بها.")
                return JSONResponse(status_code=403, content={"error": "IP Address Banned for 1 hour."})
            return JSONResponse(status_code=401, content={"error": "Unauthorized Access"})

    response = await call_next(request)
    
    if response.status_code == 200:
        await redis_client.incr("stats:total_requests")
    return response

app.middleware("http")(anti_abuse_middleware)

# ----------------------------------------------------------------------------
# 3. وظائف الخلفية (Background Tasks & Workers)
# ----------------------------------------------------------------------------

async def yt_dlp_auto_updater():
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
        except Exception as e:
            logger.error(f"خطأ أثناء تحديث yt-dlp: {e}")
        await asyncio.sleep(86400)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(yt_dlp_auto_updater())

class VideoRequest(BaseModel):
    url: str

@app.get("/api/health")
async def health_check():
    return {
        "status": "Healthy 🚀",
        "cache_system": "Memory",
        "uptime_info": "See Prometheus /metrics endpoint"
    }

@app.get("/api/stats")
async def get_stats():
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
# 6. نظام الاستخراج المتقدم (Advanced Extraction)
# ----------------------------------------------------------------------------

def get_base_ydl_opts(is_download=False):
    """إعدادات قوية لتخطي الحماية وجلب أعلى جودة بدون علامة مائية"""
    return {
        'quiet': True,
        'no_warnings': True,
        'skip_download': not is_download,
        'socket_timeout': 30,
        'geo_bypass': True,
        'nocheckcertificate': True,
        # انتحال شخصية متصفح وتطبيق حقيقي لتفادي الحظر
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Sec-Fetch-Mode': 'navigate',
        },
        'extractor_args': {
            # إجبار تيك توك على جلب الرابط من الـ API المخفي بدون علامة مائية
            'tiktok': ['api_hostname=api16-normal-c-useast1a.tiktokv.com', 'app_info=7355_200.0.0'],
            'youtube': ['skip=dash', 'player_client=android']
        },
    }

def extract_video_info(url: str):
    ydl_opts = get_base_ydl_opts(is_download=False)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info

async def process_queue_worker(job_id: str, url: str):
    try:
        await redis_client.set(f"job:{job_id}:status", "processing")
        info = await asyncio.to_thread(extract_video_info, url)
        
        if not info:
            raise Exception("لم يتم العثور على بيانات في هذا الرابط، قد يكون محمي جداً أو محذوف.")

        duration = info.get('duration', 0)
        if duration > 7200:
            raise Exception("الفيديو طويل جداً، الحد الأقصى ساعتين")

        title = info.get('title', 'Unknown Video')
        thumbnail = info.get('thumbnail', '')
        uploader = info.get('uploader', 'Unknown')
        
        formats = info.get('formats', [])
        videos = []
        audios = []
        
        for f in formats:
            filesize = f.get('filesize') or f.get('filesize_approx') or 0
            filesize_mb = round(filesize / (1024 * 1024), 2) if filesize else "غير معروف"

            # استخراج الفيديو بدون صوت (إذا تطلب الأمر دمج) أو فيديو كامل
            if f.get('vcodec') != 'none' and f.get('ext') == 'mp4' and f.get('url') and f.get('height'):
                # تجاهل الروابط اللي تحتوي على m3u8 لأنها لا تحمل كملف مباشر بسهولة في الفلاتر
                if "m3u8" not in f.get('url'):
                    videos.append({'quality': f"{f.get('height')}p", 'height': f.get('height'), 'size_mb': filesize_mb, 'url': f.get('url')})
            
            # استخراج الصوت فقط
            if f.get('acodec') != 'none' and f.get('vcodec') == 'none' and f.get('url'):
                if "m3u8" not in f.get('url'):
                    audios.append({'format': f.get('ext'), 'size_mb': filesize_mb, 'url': f.get('url')})

        # ترتيب واختيار الجودات الفريدة
        videos = sorted(videos, key=lambda k: k['height'], reverse=True)
        unique_videos = list({v['height']: v for v in videos}.values())

        # إذا كانت القائمة فارغة بسبب التصفية، محاولة استخدام الرابط المباشر الافتراضي
        if not unique_videos and info.get('url'):
             unique_videos.append({'quality': 'Default', 'height': 0, 'size_mb': 'غير معروف', 'url': info.get('url')})

        if not unique_videos and not audios:
            raise Exception("تعذر العثور على روابط تحميل مباشرة مسموحة لهذا المقطع.")

        download_token = str(uuid.uuid4())
        
        result_data = {
            "title": title,
            "thumbnail": thumbnail,
            "duration": duration,
            "uploader": uploader,
            "videos": unique_videos,
            "audios": audios,
            "download_token": download_token,
        }
        
        platform, cache_ttl = detect_platform(url)
        
        await redis_client.set(f"dl_token:{download_token}", url, ex=3600)
        await redis_client.set(f"job:{job_id}:status", "completed", ex=cache_ttl)
        await redis_client.set(f"job:{job_id}:data", json.dumps(result_data), ex=cache_ttl)
        await redis_client.set(f"video_cache:{url}", json.dumps(result_data), ex=cache_ttl)
        await redis_client.incr("stats:total_extracts")

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        await redis_client.set(f"job:{job_id}:status", "failed", ex=600)
        await redis_client.set(f"job:{job_id}:error", str(e), ex=600)

@app.post("/api/extract")
@app.get("/api/extract")
@limiter.limit("20/minute")
async def extract_api(request: Request, bg_tasks: BackgroundTasks, url: str = None):
    if request.method == 'POST':
        body = await request.json()
        url = body.get('url', url)
        
    if not url or not url.startswith("http"):
        return JSONResponse({"success": False, "error": "رابط غير صالح"}, status_code=400)

    cache_key = f"video_cache:{url}"
    cached_data = await redis_client.get(cache_key)
    if cached_data:
        return {"success": True, "job_id": "cached", "status": "completed", "data": json.loads(cached_data)}

    job_id = str(uuid.uuid4())
    await redis_client.set(f"job:{job_id}:status", "pending", ex=600)
    
    bg_tasks.add_task(process_queue_worker, job_id, url)
    
    return {"success": True, "job_id": job_id, "status": "pending", "message": "تم إضافة الرابط في قائمة المعالجة"}

@app.get("/api/progress")
async def check_progress(job_id: str):
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
# 7. نقطة التحميل مع الحماية من الملفات المعطوبة (Corrupted Files Preventer)
# ----------------------------------------------------------------------------

@app.get("/api/download")
@limiter.limit("10/minute")
async def download_secure(request: Request, token: str, range: Optional[str] = Header(None)):
    client_ip = request.client.host

    url = await redis_client.get(f"dl_token:{token}")
    if not url:
        return JSONResponse({"success": False, "error": "انتهت صلاحية جلسة التحميل، يرجى استخراج الرابط من جديد"}, status_code=403)

    ip_binder_key = f"dl_token_ip:{token}"
    bound_ip = await redis_client.get(ip_binder_key)
    
    if not bound_ip:
        await redis_client.set(ip_binder_key, client_ip, ex=3600)
    elif bound_ip != client_ip:
        logger.warning(f"🚨 توكن مسروق! {token}")
        return JSONResponse({"success": False, "error": "لا يمكن استكمال التحميل من شبكة إنترنت مختلفة"}, status_code=403)

    ydl_opts = get_base_ydl_opts(is_download=True)
    ydl_opts['format'] = 'best' # إجبار سحب أفضل جودة للتحميل المباشر

    try:
        # استخراج رابط التحميل النهائي
        info = await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(url, download=False))
        video_url = info.get('url')
        title = info.get('title', 'video').replace('/', '_').replace('\\', '_')
        
        if not video_url:
            raise HTTPException(status_code=404, detail="عذراً، فشل السيرفر في توليد رابط التحميل النهائي.")

        headers = {
            'User-Agent': ydl_opts['http_headers']['User-Agent']
        }
        if range:
            headers['Range'] = range
            
        client = httpx.AsyncClient(timeout=45.0, follow_redirects=True)
        req = await client.get(video_url, headers=headers)
        
        # 🔴 الحماية من الملفات المعطوبة: التأكد من أن السيرفر المصدر وافق على طلب التحميل
        if req.status_code not in [200, 206]:
            await req.aclose()
            logger.error(f"Source server rejected stream: Status {req.status_code}")
            return JSONResponse({"success": False, "error": "المصدر الأصلي (تيك توك/يوتيوب) رفض إرسال الملف، يرجى المحاولة لاحقاً."}, status_code=400)

        max_size_bytes = 200 * 1024 * 1024 
        content_length = int(req.headers.get('Content-Length', 0))
        
        total_size = content_length
        content_range = req.headers.get('Content-Range')
        if content_range:
            try:
                total_size = int(content_range.split('/')[-1])
            except: pass
            
        if total_size > max_size_bytes:
            await req.aclose()
            return JSONResponse({"success": False, "error": "حجم الملف يتجاوز الحد المسموح به مجاناً (200MB)"}, status_code=400)

        response_headers = {
            'Content-Disposition': f'attachment; filename="{title}.mp4"',
            'Content-Type': req.headers.get('Content-Type', 'video/mp4'),
            'Accept-Ranges': 'bytes'
        }
        
        if 'Content-Range' in req.headers:
            response_headers['Content-Range'] = req.headers['Content-Range']
        if 'Content-Length' in req.headers:
            response_headers['Content-Length'] = req.headers['Content-Length']

        if not range: 
            await redis_client.incr("stats:total_downloads")

        async def stream_generator():
            try:
                async for chunk in req.aiter_bytes(chunk_size=1024*1024): 
                    if chunk:
                        yield chunk
            except Exception as e:
                logger.error(f"Stream interrupted: {e}")
            finally:
                await req.aclose()

        status_code = req.status_code if req.status_code in [200, 206] else 200
        return StreamingResponse(
            stream_generator(),
            status_code=status_code,
            headers=response_headers
        )

    except httpx.TimeoutException:
        return JSONResponse({"success": False, "error": "انتهى وقت الاتصال بالسيرفر المصدر (Timeout)"}, status_code=504)
    except Exception as e:
        logger.error(f"Download stream error: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

# ============================================================================
# مسار التوافق القديم
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
        
        if not info:
            return JSONResponse({"success": False, "error": "المقطع محمي أو محذوف"}, status_code=404)

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
                if "m3u8" not in f.get('url'):
                    videos.append({'quality': f"{f.get('height')}p", 'height': f.get('height'), 'size_mb': filesize_mb, 'url': f.get('url')})
            if f.get('acodec') != 'none' and f.get('vcodec') == 'none' and f.get('url'):
                if "m3u8" not in f.get('url'):
                    audios.append({'format': f.get('ext'), 'size_mb': filesize_mb, 'url': f.get('url')})

        videos = sorted(videos, key=lambda k: k['height'], reverse=True)
        unique_videos = list({v['height']: v for v in videos}.values())

        if not unique_videos and info.get('url'):
            unique_videos.append({'quality': 'Default', 'height': 0, 'size_mb': 'غير معروف', 'url': info.get('url')})

        if not unique_videos and not audios:
            return JSONResponse({"success": False, "error": "تم منع التحميل من قبل صاحب المقطع"}, status_code=404)

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
        return JSONResponse({"success": False, "error": "حدث خطأ أثناء معالجة الرابط، قد يكون محمي."}, status_code=500)