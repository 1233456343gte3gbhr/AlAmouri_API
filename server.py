import logging
import subprocess
import requests
import os
import re
import time
import json
import uuid
import threading
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
import redis
import yt_dlp

# 1. تحميل المتغيرات البيئية من ملف .env
load_dotenv()
API_KEY = os.getenv("API_KEY", "AlAmouri_Pro_123456")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# إعداد الاتصال بقاعدة بيانات Redis
try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    redis_client.ping()
except Exception as e:
    print(f"⚠️ تحذير: لم يتم الاتصال بـ Redis. تأكد من تشغيل الخادم. سيتم إيقاف بعض الميزات. ({e})")
    redis_client = None

# إعداد Logging قوي يظهر الـ IP
class RequestFormatter(logging.Formatter):
    def format(self, record):
        from flask import has_request_context, request
        if has_request_context():
            record.url = request.url
            record.remote_addr = request.remote_addr
        else:
            record.url = None
            record.remote_addr = None
        return super().format(record)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(RequestFormatter('%(asctime)s - %(remote_addr)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# 2. إعداد Limiter باستخدام Redis (لحماية السيرفر من هجمات الـ Spam)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["500 per day", "50 per minute"],
    storage_uri=REDIS_URL if redis_client else "memory://"
)

CACHE_DURATION = 600  # 10 دقائق

def is_valid_url(url):
    regex = re.compile(r'^(?:http|ftp)s?://', re.IGNORECASE)
    return re.match(regex, url) is not None

# 4. تحديث yt-dlp في الخلفية (Cron Job بديل) لمنع إبطاء السيرفر عند التشغيل
def auto_update_ytdlp():
    while True:
        try:
            logger.info("جاري فحص وتحديث yt-dlp في الخلفية...")
            subprocess.run(["yt-dlp", "-U"], check=True, stdout=subprocess.DEVNULL)
            logger.info("تم تحديث yt-dlp التلقائي بنجاح 🔥")
        except Exception as e:
            logger.error(f"فشل تحديث yt-dlp: {e}")
        time.sleep(86400) # ينام لـ 24 ساعة ثم يكرر التحديث

# تشغيل خيط التحديث في الخلفية
threading.Thread(target=auto_update_ytdlp, daemon=True).start()

# حماية السيرفر عن طريق التحقق من الـ API Key
@app.before_request
def require_api_key():
    if request.method == 'OPTIONS': 
        return
    # السماح لمسار /download بالمرور ليتم حمايته عبر التوكن المؤقت بدل الـ Header
    if request.path.startswith('/download'):
        return
    if request.headers.get("X-API-KEY") != API_KEY:
        logger.warning(f"محاولة وصول غير مصرح بها من IP: {request.remote_addr}")
        return jsonify({"success": False, "error": "Unauthorized Access - الوصول مرفوض"}), 403

@app.route('/get_video', methods=['GET'])
@limiter.limit("15 per minute")
def get_video():
    url = request.args.get('url')
    
    if not url or not is_valid_url(url):
        return jsonify({"success": False, "error": "الرجاء إرسال رابط صحيح"}), 400

    logger.info(f"طلب استخراج جديد للرابط: {url}")

    # 1. نظام كاش احترافي باستخدام Redis
    cache_key = f"video_cache:{url}"
    if redis_client:
        cached_data = redis_client.get(cache_key)
        if cached_data:
            logger.info("تم إرجاع النتيجة من Redis Cache بسرعة البرق ⚡")
            return jsonify(json.loads(cached_data))

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'extractor_args': {'tiktok': ['api_hostname=api22-normal-c-alisg.tiktokv.com']},
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # نظام Retry: المحاولة مرتين في حال تعثر الشبكة
            info = None
            for attempt in range(2):
                try:
                    info = ydl.extract_info(url, download=False)
                    break
                except Exception as e:
                    logger.warning(f"المحاولة {attempt + 1} فشلت: {e}")
                    time.sleep(1.5)
            
            if not info:
                raise Exception("فشل استخراج البيانات من المصدر")

            duration = info.get('duration', 0)
            if duration and duration > 7200:
                logger.warning(f"تم رفض طلب: فيديو طويل جداً ({duration} ثانية)")
                return jsonify({"success": False, "error": "الفيديو طويل جداً، الحد الأقصى ساعتين"}), 400

            title = info.get('title', 'Unknown Video')
            thumbnail = info.get('thumbnail', '')
            uploader = info.get('uploader', 'Unknown')
            
            # 3. إنشاء Token مؤقت لحماية نقطة التحميل
            download_token = str(uuid.uuid4())
            if redis_client:
                # التوكن صالح لمدة ساعة واحدة فقط (3600 ثانية)
                redis_client.setex(f"dl_token:{download_token}", 3600, url)
            
            formats = info.get('formats', [])
            videos = []
            audios = []
            
            for f in formats:
                filesize = f.get('filesize') or f.get('filesize_approx') or 0
                filesize_mb = round(filesize / (1024 * 1024), 2) if filesize else "غير معروف"

                if f.get('vcodec') != 'none' and f.get('ext') == 'mp4':
                    if f.get('url') and f.get('height'):
                        videos.append({
                            'quality': f"{f.get('height')}p",
                            'height': f.get('height'),
                            'size_mb': filesize_mb,
                            'url': f.get('url')
                        })
                
                if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                    if f.get('url'):
                        audios.append({
                            'format': f.get('ext'),
                            'size_mb': filesize_mb,
                            'url': f.get('url')
                        })

            if not videos and not audios:
                return jsonify({"success": False, "error": "لم يتم العثور على وسائط قابلة للتحميل"}), 404

            videos = sorted(videos, key=lambda k: k['height'], reverse=True)
            unique_videos = list({v['height']: v for v in videos}.values())

            result = {
                "success": True,
                "note": "⚠️ الروابط مؤقتة.",
                "download_token": download_token, # توكن مؤقت صالح للتحميل مرة واحدة أو لفترة محدودة
                "data": {
                    "title": title,
                    "thumbnail": thumbnail,
                    "duration": duration,
                    "uploader": uploader,
                    "videos": unique_videos,
                    "audios": audios
                }
            }

            # حفظ النتيجة في Redis
            if redis_client:
                redis_client.setex(cache_key, CACHE_DURATION, json.dumps(result))
            return jsonify(result)
            
    except Exception as e:
        logger.error(f"خطأ داخلي في الاستخراج: {str(e)}")
        return jsonify({"success": False, "error": "حدث خطأ أثناء معالجة الرابط، تأكد من صحته"}), 500


# 3. نقطة التحميل محمية الآن باستخدام Token
@app.route('/download', methods=['GET'])
@limiter.limit("5 per minute")
def download():
    token = request.args.get('token')
    
    if not token or not redis_client:
        return jsonify({"success": False, "error": "غير مصرح لك بالتحميل أو لا يوجد توكن"}), 403

    # التحقق من أن التوكن ساري المفعول في Redis
    url = redis_client.get(f"dl_token:{token}")
    if not url:
        return jsonify({"success": False, "error": "رابط التحميل غير صالح أو منتهي الصلاحية"}), 403

    logger.info(f"طلب تحميل آمن للرابط: {url}")

    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {'tiktok': ['api_hostname=api22-normal-c-alisg.tiktokv.com']},
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_url = info.get('url')
            title = info.get('title', 'video').replace('/', '_').replace('\\', '_')
            
            if not video_url:
                return jsonify({"success": False, "error": "لم يتم العثور على رابط التحميل"}), 404

            # 5. الحد الأقصى لحجم الفيديو (200 ميجابايت)
            max_size_bytes = 200 * 1024 * 1024 
            filesize = info.get('filesize') or info.get('filesize_approx') or 0
            if filesize > max_size_bytes:
                logger.warning(f"مرفوض: محاولة تحميل ملف كبير الحجم ({filesize} bytes)")
                return jsonify({"success": False, "error": "حجم الملف يتجاوز الحد المسموح به (200 ميجابايت)"}), 400

            req = requests.get(video_url, stream=True, timeout=15)
            
            if req.status_code != 200:
                logger.error(f"فشل جلب الملف، الكود: {req.status_code}")
                return jsonify({"success": False, "error": "فشل تحميل الملف من المصدر"}), 502
            
            # التحقق الإضافي من حجم الملف عبر الـ Header
            content_length = int(req.headers.get('Content-Length', 0))
            if content_length > max_size_bytes:
                return jsonify({"success": False, "error": "حجم الملف الفعلي يتجاوز 200 ميجابايت"}), 400

            headers = {
                'Content-Disposition': f'attachment; filename="{title}.mp4"',
                'Content-Type': req.headers.get('content-type', 'video/mp4')
            }
            
            return Response(
                stream_with_context(req.iter_content(chunk_size=1024*1024)), 
                headers=headers
            )

    except requests.exceptions.Timeout:
        logger.error("انتهى وقت الاتصال (Timeout)")
        return jsonify({"success": False, "error": "انتهى وقت الاتصال بالسيرفر المصدر"}), 504
    except Exception as e:
        logger.error(f"خطأ داخلي أثناء الدفق: {str(e)}")
        return jsonify({"success": False, "error": "حدث خطأ غير متوقع"}), 500

# للتشغيل الاحترافي على الاستضافة السحابية يُفضل استخدام:
# gunicorn server:app -w 4 -b 0.0.0.0:5000
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)