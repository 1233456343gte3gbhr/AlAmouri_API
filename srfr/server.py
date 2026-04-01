# ============================================================================
# 🚀 السيرفر الاحترافي (نظام هجين: TikWM + pytubefix + yt-dlp)
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
from pytubefix import YouTube

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from prometheus_fastapi_instrumentator import Instrumentator

load_dotenv()
API_KEY = os.getenv("API_KEY", "AlAmouri_Pro_123456")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("AlAmouriServer")

app = FastAPI(title="AlAmouri Pro API", version="4.0.0")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
Instrumentator().instrument(app).expose(app)

# ----------------------------------------------------------------------------
class MemoryCache:
    def __init__(self): self.store = {}
    async def get(self, key): return self.store.get(key)
    async def set(self, key, value, ex=None): self.store[key] = str(value)
    async def incr(self, key):
        self.store[key] = str(int(self.store.get(key, "0")) + 1)
        return int(self.store[key])
    async def expire(self, key, time): pass 
    async def ping(self): return True

redis_client = MemoryCache()

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
    if response.status_code == 200: await redis_client.incr("stats:total_requests")
    return response

app.middleware("http")(anti_abuse_middleware)

# ----------------------------------------------------------------------------
# 1. 🔴 نظام التيك توك (باستخدام TikWM API المجاني)
# ----------------------------------------------------------------------------
def extract_tiktok(url: str):
    api_url = "https://www.tikwm.com/api/"
    res = httpx.get(api_url, params={"url": url, "hd": 1}, timeout=15.0)
    res_json = res.json()
    
    if res_json.get("code") != 0:
        raise Exception("فشل سحب بيانات التيك توك، قد يكون المقطع خاص أو محذوف.")
        
    data = res_json.get("data", {})
    videos = []
    audios = []
    
    play_url = data.get("hdplay") or data.get("play")
    if play_url:
        videos.append({'quality': 'HD/SD', 'height': 1080, 'size_mb': "غير معروف", 'url': play_url})
        
    if data.get("music"):
        audios.append({'format': 'mp3', 'size_mb': "غير معروف", 'url': data.get("music")})
        
    return {
        "title": data.get("title", "TikTok Video"),
        "thumbnail": data.get("cover", ""),
        "duration": data.get("duration", 0),
        "uploader": data.get("author", {}).get("nickname", "Unknown"),
        "videos": videos,
        "audios": audios
    }

# ----------------------------------------------------------------------------
# 2. 🔴 نظام اليوتيوب (باستخدام pytubefix)
# ----------------------------------------------------------------------------
def extract_youtube(url: str):
    yt = YouTube(url, client='ANDROID')
    videos = []
    audios = []
    
    for stream in yt.streams.filter(type="video", file_extension="mp4", progressive=True):
        if stream.resolution:
            height = int(stream.resolution.replace('p', '')) if stream.resolution.replace('p', '').isdigit() else 0
            size_mb = round(stream.filesize / (1024*1024), 2) if stream.filesize else "غير معروف"
            videos.append({'quality': stream.resolution, 'height': height, 'size_mb': size_mb, 'url': stream.url})
            
    for stream in yt.streams.filter(only_audio=True):
        size_mb = round(stream.filesize / (1024*1024), 2) if stream.filesize else "غير معروف"
        audios.append({'format': stream.mime_type.split('/')[-1], 'size_mb': size_mb, 'url': stream.url})

    videos = sorted(videos, key=lambda k: k['height'], reverse=True)
    return {
        "title": yt.title, "thumbnail": yt.thumbnail_url, "duration": yt.length, "uploader": yt.author,
        "videos": videos, "audios": audios
    }

# ----------------------------------------------------------------------------
# 3. 🔴 نظام باقي المنصات فيسبوك/انستقرام (باستخدام yt-dlp)
# ----------------------------------------------------------------------------
def extract_others(url: str):
    ydl_opts = {
        'quiet': True, 'no_warnings': True, 'skip_download': True, 'socket_timeout': 30,
        'http_headers': {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)'},
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        videos, audios = [], []
        for f in info.get('formats', []):
            filesize_mb = round((f.get('filesize') or 0) / (1024 * 1024), 2)
            if f.get('vcodec') != 'none' and f.get('ext') == 'mp4' and f.get('url') and f.get('height'):
                if "m3u8" not in f.get('url'):
                    videos.append({'quality': f"{f.get('height')}p", 'height': f.get('height'), 'size_mb': filesize_mb, 'url': f.get('url')})
            if f.get('acodec') != 'none' and f.get('vcodec') == 'none' and f.get('url'):
                if "m3u8" not in f.get('url'):
                    audios.append({'format': f.get('ext'), 'size_mb': filesize_mb, 'url': f.get('url')})

        videos = sorted(videos, key=lambda k: k['height'], reverse=True)
        unique_videos = list({v['height']: v for v in videos}.values())
        return {
            "title": info.get('title', 'Video'), "thumbnail": info.get('thumbnail', ''), "duration": info.get('duration', 0),
            "uploader": info.get('uploader', 'Unknown'), "videos": unique_videos, "audios": audios
        }

# ----------------------------------------------------------------------------
async def process_queue_worker(job_id: str, url: str):
    try:
        await redis_client.set(f"job:{job_id}:status", "processing")
        platform, cache_ttl = detect_platform(url)
        
        if platform == "tiktok":
            result_data = await asyncio.to_thread(extract_tiktok, url)
        elif platform == "youtube":
            result_data = await asyncio.to_thread(extract_youtube, url)
        else:
            result_data = await asyncio.to_thread(extract_others, url)

        if not result_data.get("videos") and not result_data.get("audios"):
            raise Exception("لم يتم العثور على وسائط، المقطع محمي أو محذوف.")

        download_token = str(uuid.uuid4())
        result_data["download_token"] = download_token
        
        await redis_client.set(f"dl_token:{download_token}", url, ex=3600)
        await redis_client.set(f"job:{job_id}:status", "completed", ex=cache_ttl)
        await redis_client.set(f"job:{job_id}:data", json.dumps(result_data), ex=cache_ttl)

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

@app.get("/api/download")
@limiter.limit("10/minute")
async def download_secure(request: Request, token: str, range: Optional[str] = Header(None)):
    url = await redis_client.get(f"dl_token:{token}")
    if not url: return JSONResponse({"success": False, "error": "انتهت صلاحية الجلسة"}, status_code=403)

    platform, _ = detect_platform(url)
    headers = {}

    try:
        if platform == "tiktok":
            res = await asyncio.to_thread(lambda: httpx.get("https://www.tikwm.com/api/", params={"url": url, "hd": 1}).json())
            video_url = res.get("data", {}).get("hdplay") or res.get("data", {}).get("play")
            title = res.get("data", {}).get("title", "tiktok_video").replace('/', '_')
        elif platform == "youtube":
            yt = await asyncio.to_thread(lambda: YouTube(url, client='ANDROID'))
            stream = yt.streams.filter(type="video", file_extension="mp4", progressive=True).get_highest_resolution()
            video_url, title = stream.url, yt.title.replace('/', '_')
        else:
            ydl_opts = {'quiet': True, 'format': 'best', 'http_headers': {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0)'}}
            info = await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(url, download=False))
            video_url, title = info.get('url'), info.get('title', 'video').replace('/', '_')
            headers.update(info.get('http_headers', {}))

        if not video_url: raise HTTPException(status_code=404, detail="فشل توليد رابط التحميل.")
        if range: headers['Range'] = range
            
        client = httpx.AsyncClient(timeout=45.0, follow_redirects=True)
        req = await client.get(video_url, headers=headers)
        
        if req.status_code not in [200, 206]:
            await req.aclose()
            return JSONResponse({"success": False, "error": "المصدر رفض الطلب."}, status_code=400)

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
        return JSONResponse({"success": False, "error": f"خطأ داخلي: {str(e)}"}, status_code=500)