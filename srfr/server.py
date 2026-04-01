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
import redis.asyncio as redis

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from prometheus_fastapi_instrumentator import Instrumentator

load_dotenv()
API_KEY = os.getenv("API_KEY", "AlAmouri_Pro_123456")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("AlAmouriServer")

app = FastAPI(title="AlAmouri Pro API", version="5.0.0")

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
    if "youtube.com" in url_lower or "youtu.be" in url_lower: return "youtube", 86400  
    elif "tiktok.com" in url_lower or "tiktokv.com" in url_lower: return "tiktok", 3600  
    elif "facebook.com" in url_lower or "fb.watch" in url_lower: return "facebook", 7200  
    elif "instagram.com" in url_lower: return "instagram", 7200  
    return "other", 600  

async def anti_abuse_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/") and not request.url.path.startswith("/api/download") and not request.url.path.startswith("/api/health"):
        if request.headers.get("X-API-KEY") != API_KEY:
            return JSONResponse(status_code=401, content={"error": "Unauthorized Access"})
    response = await call_next(request)
    if response.status_code == 200: 
        try:
            await redis_client.incr("stats:total_requests")
        except: pass
    return response

app.middleware("http")(anti_abuse_middleware)

# ----------------------------------------------------------------------------
def extract_tiktok(url: str):
    res = httpx.get("https://www.tikwm.com/api/", params={"url": url, "hd": 1}, timeout=15.0)
    res_json = res.json()
    if res_json.get("code") != 0: raise Exception("المقطع خاص أو محذوف من التيك توك.")
        
    data = res_json.get("data", {})
    videos, audios = [], []
    
    play_url = data.get("hdplay") or data.get("play")
    if play_url: videos.append({'quality': 'HD', 'height': 1080, 'size_mb': "غير معروف", 'url': play_url})
    if data.get("music"): audios.append({'format': 'mp3', 'size_mb': "غير معروف", 'url': data.get("music")})
        
    return {
        "title": data.get("title", "TikTok Video").replace('/', '_'), 
        "thumbnail": data.get("cover", ""), 
        "duration": data.get("duration", 0),
        "uploader": data.get("author", {}).get("nickname", "Unknown"), 
        "videos": videos, 
        "audios": audios,
        "best_direct_url": play_url # تخزين الرابط المباشر
    }

def extract_others(url: str):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'cookiefile': 'cookies.txt',  # 🔥 مهم جداً
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        videos, audios = [], []
        
        # استخراج القوائم بشكل نظيف
        for f in info.get('formats', []):
            filesize = round((f.get('filesize') or 0) / (1024 * 1024), 2)
            if f.get('vcodec') != 'none' and f.get('ext') == 'mp4' and f.get('url') and "m3u8" not in f.get('url'):
                videos.append({'quality': f"{f.get('height')}p", 'height': f.get('height'), 'size_mb': filesize, 'url': f.get('url')})
            if f.get('acodec') != 'none' and f.get('vcodec') == 'none' and f.get('url') and "m3u8" not in f.get('url'):
                audios.append({'format': f.get('ext'), 'size_mb': filesize, 'url': f.get('url')})

        unique_videos = list({v['height']: v for v in sorted(videos, key=lambda k: k['height'], reverse=True)}.values())
        
        # 🔥 الحل الصحيح لجلب أفضل رابط فيديو مباشر MP4 (يحتوي على صوت وصورة)
        formats = info.get("formats", [])
        video_url = None
        for f in formats:
            if f.get("ext") == "mp4" and f.get("vcodec") != "none" and f.get("acodec") != "none":
                video_url = f.get("url")
                break

        if not video_url:
            video_url = info.get("url") # Fallback نهائي

        if not video_url:
            raise Exception("لم يتم العثور على فيديو صالح")

        return {
            "title": info.get('title', 'Video').replace('/', '_'), 
            "thumbnail": info.get('thumbnail', ''), 
            "duration": info.get('duration', 0),
            "uploader": info.get('uploader', 'Unknown'), 
            "videos": unique_videos, 
            "audios": audios,
            "best_direct_url": video_url, # تخزين الرابط المباشر لمنع إعادة التحليل
            "headers": info.get('http_headers', {})
        }

# ----------------------------------------------------------------------------
async def process_queue_worker(job_id: str, url: str):
    try:
        await redis_client.set(f"job:{job_id}:status", "processing")
        platform, cache_ttl = detect_platform(url)
        
        data = None
        if platform == "tiktok":
            try:
                data = await asyncio.to_thread(extract_tiktok, url)
            except Exception as e:
                logger.warning(f"TikTok API failed, fallback to yt-dlp: {e}")
                data = await asyncio.to_thread(extract_others, url)
        elif platform == "youtube":
            data = await asyncio.to_thread(extract_others, url) # yt-dlp هو الأساس القوي
        else:
            data = await asyncio.to_thread(extract_others, url)

        if not data or (not data.get("videos") and not data.get("audios")):
            raise Exception("لم يتم العثور على وسائط، المقطع محمي أو محذوف.")

        download_token = str(uuid.uuid4())
        data["download_token"] = download_token
        
        # 🔥 تخزين الرابط المباشر للتحميل السريع بدون إعادة الاستخراج
        await redis_client.set(f"dl_direct_url:{download_token}", data.get("best_direct_url", ""), ex=3600)
        await redis_client.set(f"dl_title:{download_token}", data.get("title", "video"), ex=3600)
        await redis_client.set(f"dl_headers:{download_token}", json.dumps(data.get("headers", {})), ex=3600)
        
        await redis_client.set(f"job:{job_id}:status", "completed", ex=cache_ttl)
        await redis_client.set(f"job:{job_id}:data", json.dumps(data), ex=cache_ttl)

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
        
    if not url or not url.startswith("http"): return JSONResponse({"success": False, "error": "رابط غير صالح"}, status_code=400)

    job_id = str(uuid.uuid4())
    await redis_client.set(f"job:{job_id}:status", "pending", ex=600)
    bg_tasks.add_task(process_queue_worker, job_id, url)
    return {"success": True, "job_id": job_id, "status": "pending"}

@app.get("/api/progress")
async def check_progress(job_id: str):
    status = await redis_client.get(f"job:{job_id}:status")
    if not status: return JSONResponse({"success": False, "error": "المعاملة غير موجودة"}, status_code=404)
        
    if status == "completed": return {"success": True, "status": status, "data": json.loads(await redis_client.get(f"job:{job_id}:data"))}
    elif status == "failed": return {"success": False, "status": status, "error": await redis_client.get(f"job:{job_id}:error")}
    return {"success": True, "status": status}

@app.get("/get_video")
@limiter.limit("20/minute")
async def get_video_legacy(request: Request, url: str = None):
    if not url or not url.startswith("http"):
        return JSONResponse({"success": False, "error": "رابط غير صالح"}, status_code=400)

    try:
        platform, _ = detect_platform(url)
        
        data = None
        if platform == "tiktok":
            try:
                data = await asyncio.to_thread(extract_tiktok, url)
            except Exception as e:
                logger.warning(f"TikTok fallback in legacy API: {e}")
                data = await asyncio.to_thread(extract_others, url)
        elif platform == "youtube":
            data = await asyncio.to_thread(extract_others, url)
        else:
            data = await asyncio.to_thread(extract_others, url)

        if not data or (not data.get("videos") and not data.get("audios")):
            return JSONResponse({"success": False, "error": "المقطع محمي أو غير متوفر."}, status_code=404)

        download_token = str(uuid.uuid4())
        
        # 🔥 تخزين الرابط المباشر للتحميل السريع
        await redis_client.set(f"dl_direct_url:{download_token}", data.get("best_direct_url", ""), ex=3600)
        await redis_client.set(f"dl_title:{download_token}", data.get("title", "video"), ex=3600)
        await redis_client.set(f"dl_headers:{download_token}", json.dumps(data.get("headers", {})), ex=3600)

        return {
            "success": True,
            "download_token": download_token,
            "data": data
        }

    except Exception as e:
        logger.error(f"Extraction Error: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

# ============================================================================
# 🔥 نقطة التحميل (سريعة جداً - بدون إعادة استخراج) 🔥
# ============================================================================
@app.get("/api/download")
@limiter.limit("10/minute")
async def download_secure(request: Request, token: str, range: Optional[str] = Header(None)):
    video_url = await redis_client.get(f"dl_direct_url:{token}")
    if not video_url: return JSONResponse({"success": False, "error": "انتهت صلاحية الجلسة أو الرابط غير صالح"}, status_code=403)

    title = await redis_client.get(f"dl_title:{token}") or "video"
    saved_headers = await redis_client.get(f"dl_headers:{token}")
    
    headers = json.loads(saved_headers) if saved_headers else {}
    if range: headers['Range'] = range

    try:
        client = httpx.AsyncClient(timeout=45.0, follow_redirects=True)
        req = await client.get(video_url, headers=headers)
        
        if req.status_code not in [200, 206]:
            await req.aclose()
            return JSONResponse({"success": False, "error": f"المصدر رفض الطلب بالكود {req.status_code}"}, status_code=400)

        response_headers = {
            'Content-Disposition': f'attachment; filename="{title}.mp4"',
            'Content-Type': req.headers.get('Content-Type', 'video/mp4'),
            'Accept-Ranges': 'bytes'
        }
        if 'Content-Range' in req.headers: response_headers['Content-Range'] = req.headers['Content-Range']
        if 'Content-Length' in req.headers: response_headers['Content-Length'] = req.headers['Content-Length']

        async def stream_generator():
            try:
                async for chunk in req.aiter_bytes(chunk_size=1024*1024): 
                    if chunk: yield chunk
            finally: await req.aclose()

        return StreamingResponse(stream_generator(), status_code=req.status_code, headers=response_headers)

    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)