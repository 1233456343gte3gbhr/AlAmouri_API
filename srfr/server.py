import os
import json
import uuid
import logging
import asyncio
from typing import Optional
from dotenv import load_dotenv

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Header
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

import yt_dlp
import httpx
import aiohttp
import redis.asyncio as redis

try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from prometheus_fastapi_instrumentator import Instrumentator

load_dotenv()
API_KEY = os.getenv("API_KEY", "AlAmouri_Pro_123456")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("AlAmouriServer")

app = FastAPI(title="AlAmouri Pro API", version="6.5.0")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
Instrumentator().instrument(app).expose(app)

# ----------------------------------------------------------------------------
# ⚡ إعداد Redis الحقيقي للاحترافية والسرعة
# ----------------------------------------------------------------------------
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
redis_client = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)

# ----------------------------------------------------------------------------
def detect_platform(url: str):
    url_lower = url.lower()
    if "youtube.com" in url_lower or "youtu.be" in url_lower: return "youtube"
    elif "tiktok.com" in url_lower or "tiktokv.com" in url_lower: return "tiktok"
    elif "facebook.com" in url_lower or "fb.watch" in url_lower: return "facebook"
    elif "instagram.com" in url_lower: return "instagram"
    return "other"

async def anti_abuse_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/") and not request.url.path.startswith("/api/download"):
        if request.headers.get("X-API-KEY") != API_KEY:
            return JSONResponse(status_code=401, content={"error": "Unauthorized Access"})
    response = await call_next(request)
    if response.status_code == 200: 
        try: await redis_client.incr("stats:total_requests")
        except: pass
    return response

app.middleware("http")(anti_abuse_middleware)

# ----------------------------------------------------------------------------
# 🚀 محركات التحميل (Extractors) المتقدمة
# ----------------------------------------------------------------------------

async def extract_fastapi(url: str):
    """Fallback API خارجي للحالات الصعبة"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.vevioz.com/api/button/mp4/{url}", timeout=15) as res:
                text = await res.text()
                if not text.startswith("http"): raise Exception("Invalid API response")
                return {
                    "title": "Video_Fallback",
                    "thumbnail": "",
                    "duration": 0,
                    "uploader": "Unknown",
                    "videos": [{"quality": "HD", "height": 720, "size_mb": "غير معروف", "url": text}],
                    "audios": [],
                    "best_direct_url": text,
                    "headers": {}
                }
    except Exception as e:
        logger.error(f"FastAPI fallback failed: {e}")
        raise Exception("فشل التحميل من جميع المصادر الاحتياطية.")

async def extract_tiktok_clean(url: str):
    """استخراج TikTok بدون علامة مائية (Multi-API)"""
    try:
        # المحاولة الأولى: TikDown
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get("https://tikdown.org/api", params={"url": url})
            data = res.json()
            if data.get("video_no_watermark"):
                video_url = data.get("video_no_watermark")
                return {
                    "title": "TikTok Video", "thumbnail": "", "duration": 0, "uploader": "TikTok",
                    "videos": [{"quality": "HD", "height": 1080, "size_mb": "غير معروف", "url": video_url}],
                    "audios": [],
                    "best_direct_url": video_url,
                    "headers": {}
                }
    except Exception as e:
        logger.warning(f"Tikdown failed, trying TikWM: {e}")
        
    # المحاولة الثانية: TikWM كاحتياطي
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get("https://www.tikwm.com/api/", params={"url": url, "hd": 1})
            data = res.json().get("data", {})
            play_url = data.get("hdplay") or data.get("play")
            if not play_url: raise Exception("No URL found in TikWM")
            return {
                "title": data.get("title", "TikTok Video").replace('/', '_'), "thumbnail": data.get("cover", ""),
                "duration": data.get("duration", 0), "uploader": data.get("author", {}).get("nickname", "Unknown"),
                "videos": [{'quality': 'HD', 'height': 1080, 'size_mb': "غير معروف", 'url': play_url}],
                "audios": [{'format': 'mp3', 'size_mb': "غير معروف", 'url': data.get("music", "")}],
                "best_direct_url": play_url, "headers": {}
            }
    except Exception as e:
        raise Exception("فشل تحميل TikTok بدون علامة مائية من جميع الـ APIs.")

def extract_general(url: str):
    """المحرك الرئيسي الأقوى (yt-dlp) معدل بأعلى الإعدادات"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'format': 'best[ext=mp4]/bv*+ba/best',
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'retries': 10,
        'fragment_retries': 10,
        'concurrent_fragment_downloads': 5,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    }
    
    # معالجة ذكية للكوكيز
    if os.path.exists('cookies.txt'):
        ydl_opts['cookiefile'] = 'cookies.txt'
    else:
        try:
            import browser_cookie3
            ydl_opts['cookiesfrombrowser'] = ('chrome',)
        except: pass

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        
        videos, audios = [], []
        for f in info.get('formats', []):
            filesize = round((f.get('filesize') or 0) / (1024 * 1024), 2)
            if f.get('ext') == 'mp4' and f.get('vcodec') != 'none':
                videos.append({'quality': f"{f.get('height')}p", 'height': f.get('height'), 'size_mb': filesize, 'url': f.get('url')})
            if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                audios.append({'format': f.get('ext'), 'size_mb': filesize, 'url': f.get('url')})

        # محاولة إيجاد أفضل رابط مدمج (MP4)
        video_url = None
        for f in info.get("formats", []):
            if f.get("ext") == "mp4" and f.get("vcodec") != "none" and f.get("acodec") != "none":
                video_url = f.get("url")
                break
        
        if not video_url: video_url = info.get("url")
        if not video_url: raise Exception("لم يتم العثور على فيديو صالح للاستخراج")

        return {
            "title": info.get('title', 'Video').replace('/', '_'), "thumbnail": info.get('thumbnail', ''),
            "duration": info.get('duration', 0), "uploader": info.get('uploader', 'Unknown'),
            "videos": sorted(videos, key=lambda k: k['height'], reverse=True)[:5], 
            "audios": audios[:3],
            "best_direct_url": video_url,
            "headers": info.get('http_headers', {})
        }

# ----------------------------------------------------------------------------
# 🧠 نظام الاستخراج الذكي متعدد المصادر (Smart Multi-Source)
# ----------------------------------------------------------------------------
async def smart_extract(url: str, platform: str):
    if platform == "tiktok":
        try: return await extract_tiktok_clean(url)
        except Exception as e:
            logger.warning(f"TikTok API failed: {e}. Falling back to yt-dlp.")
            try: return await asyncio.to_thread(extract_general, url)
            except: return await extract_fastapi(url)
    else:
        try: return await asyncio.to_thread(extract_general, url)
        except Exception as e:
            logger.warning(f"yt-dlp failed for {platform}: {e}. Falling back to API.")
            return await extract_fastapi(url)

# ----------------------------------------------------------------------------
# 🔗 نقاط الاتصال (Endpoints)
# ----------------------------------------------------------------------------
@app.get("/get_video")
@limiter.limit("30/minute")
async def get_video_legacy(request: Request, url: str = None):
    if not url or not url.startswith("http"):
        return JSONResponse({"success": False, "error": "رابط غير صالح"}, status_code=400)

    try:
        platform = detect_platform(url)
        data = await smart_extract(url, platform)

        download_token = str(uuid.uuid4())
        
        # تخزين الرابط المباشر للتحميل السريع
        await redis_client.set(f"dl_url:{download_token}", data["best_direct_url"], ex=7200)
        await redis_client.set(f"dl_title:{download_token}", data["title"], ex=7200)
        await redis_client.set(f"dl_headers:{download_token}", json.dumps(data["headers"]), ex=7200)

        return {"success": True, "download_token": download_token, "data": data}

    except Exception as e:
        logger.error(f"Extraction Error: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.post("/api/extract")
@app.get("/api/extract")
@limiter.limit("20/minute")
async def extract_api(request: Request, bg_tasks: BackgroundTasks, url: str = None):
    if request.method == 'POST':
        body = await request.json()
        url = body.get('url', url)
        
    if not url or not url.startswith("http"): return JSONResponse({"success": False, "error": "رابط غير صالح"}, status_code=400)

    job_id = str(uuid.uuid4())
    await redis_client.set(f"job:{job_id}:status", "processing", ex=600)
    
    async def background_worker():
        try:
            platform = detect_platform(url)
            data = await smart_extract(url, platform)
            token = str(uuid.uuid4())
            data["download_token"] = token
            
            await redis_client.set(f"dl_url:{token}", data["best_direct_url"], ex=7200)
            await redis_client.set(f"dl_title:{token}", data["title"], ex=7200)
            await redis_client.set(f"dl_headers:{token}", json.dumps(data["headers"]), ex=7200)
            
            await redis_client.set(f"job:{job_id}:status", "completed", ex=3600)
            await redis_client.set(f"job:{job_id}:data", json.dumps(data), ex=3600)
        except Exception as e:
            await redis_client.set(f"job:{job_id}:status", "failed", ex=600)
            await redis_client.set(f"job:{job_id}:error", str(e), ex=600)

    bg_tasks.add_task(background_worker)
    return {"success": True, "job_id": job_id, "status": "pending"}

@app.get("/api/progress")
async def check_progress(job_id: str):
    status = await redis_client.get(f"job:{job_id}:status")
    if not status: return JSONResponse({"success": False, "error": "المعاملة غير موجودة"}, status_code=404)
        
    if status == "completed": return {"success": True, "status": status, "data": json.loads(await redis_client.get(f"job:{job_id}:data"))}
    elif status == "failed": return {"success": False, "status": status, "error": await redis_client.get(f"job:{job_id}:error")}
    return {"success": True, "status": status}

# ----------------------------------------------------------------------------
# 🚀 نقطة التحميل السريعة والمستقرة (HTTPX Boost)
# ----------------------------------------------------------------------------
@app.get("/api/download")
@limiter.limit("20/minute")
async def download_secure(request: Request, token: str, range: Optional[str] = Header(None)):
    video_url = await redis_client.get(f"dl_url:{token}")
    if not video_url: return JSONResponse({"success": False, "error": "الرابط منتهي الصلاحية أو غير صالح"}, status_code=403)

    title = await redis_client.get(f"dl_title:{token}") or "video"
    saved_headers = await redis_client.get(f"dl_headers:{token}")
    
    headers = json.loads(saved_headers) if saved_headers else {}
    if range: headers['Range'] = range

    try:
        # إعداد HTTPX بأقصى سرعة واستقرار
        limits = httpx.Limits(max_connections=100, max_keepalive_connections=20)
        client = httpx.AsyncClient(timeout=60.0, limits=limits, http2=True, follow_redirects=True)
        
        req = await client.get(video_url, headers=headers)
        
        if req.status_code not in [200, 206]:
            await req.aclose()
            return JSONResponse({"success": False, "error": f"المصدر الأصلي رفض الطلب بالكود {req.status_code}"}, status_code=400)

        response_headers = {
            'Content-Disposition': f'attachment; filename="{title}.mp4"',
            'Content-Type': req.headers.get('Content-Type', 'video/mp4'),
            'Accept-Ranges': 'bytes'
        }
        if 'Content-Range' in req.headers: response_headers['Content-Range'] = req.headers['Content-Range']
        if 'Content-Length' in req.headers: response_headers['Content-Length'] = req.headers['Content-Length']

        async def stream_generator():
            try:
                # Chunk size 10MB لسرعة تحميل قصوى
                async for chunk in req.aiter_bytes(chunk_size=10*1024*1024): 
                    if chunk: yield chunk
            finally: await req.aclose()

        return StreamingResponse(stream_generator(), status_code=req.status_code, headers=response_headers)

    except httpx.TimeoutException:
        return JSONResponse({"success": False, "error": "انتهى وقت الاتصال بالسيرفر المصدر"}, status_code=504)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)