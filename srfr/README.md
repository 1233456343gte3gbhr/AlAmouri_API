# 🎬 Social Downloader Pro - المحمل الخارق

نظام متكامل وخارق لتحميل الفيديوهات من منصات التواصل الاجتماعي **بدون علامة مائية** مع واجهة ويب أنيقة وسريعة.

## ✨ الميزات الرئيسية

### 🎯 المنصات المدعومة
- ✅ **TikTok** - مع دعم كامل وبدون مشاكل (الأولوية القصوى)
- ✅ **YouTube** - استخراج بجودات متعددة
- ✅ **Facebook** - دعم كامل للفيديوهات
- ✅ **Instagram** - استخراج الفيديوهات والقصص

### 🚀 الأداء والسرعة
- ⚡ استخراج البيانات في ثوان معدودة
- 💾 نظام Cache ذكي مع أوقات انتهاء صلاحية مختلفة
- 🔄 معالجة الطلبات في الخلفية (Background Jobs)
- 📊 مراقبة الأداء مع Prometheus Metrics

### 🛡️ الأمان والحماية
- 🔒 تحميل آمن ومباشر بدون وسيط
- 🚫 نظام Rate Limiting (20 طلب/دقيقة للاستخراج، 10/دقيقة للتحميل)
- 🛡️ حماية من سوء الاستخدام
- 🔐 لا نحفظ أي بيانات شخصية

### 📥 خيارات التحميل
- 🎬 جودات فيديو متعددة
- 🎵 استخراج الصوت بجودة عالية
- 📊 عرض حجم الملف قبل التحميل
- ⏸️ دعم استئناف التحميل

### 🎨 الواجهة الأمامية
- ✨ تصميم أنيق وعصري (Dark Theme)
- 📱 متجاوب يعمل على جميع الأجهزة
- 🌍 دعم كامل للغة العربية
- ⚡ سريع وسلس جداً

## 📋 المتطلبات

```bash
Python 3.8+
pip (مدير الحزم)
```

## 🚀 التثبيت والتشغيل

### 1️⃣ استنساخ المشروع
```bash
cd /path/to/social-downloader-python
```

### 2️⃣ تثبيت المكتبات
```bash
pip install -r requirements.txt
```

### 3️⃣ تشغيل السيرفر
```bash
python main.py
```

السيرفر سيبدأ على `http://localhost:8000`

## 📚 استخدام API

### استخراج بيانات الفيديو (متزامن)
```bash
curl -X POST http://localhost:8000/api/extract \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@user/video/123456"}'
```

**الرد:**
```json
{
  "success": true,
  "data": {
    "title": "عنوان الفيديو",
    "thumbnail": "https://...",
    "duration": 15,
    "uploader": "اسم المستخدم",
    "platform": "tiktok",
    "videos": [
      {
        "quality": "HD/SD",
        "height": 1080,
        "size_mb": 5.2,
        "url": "https://...",
        "format": "mp4"
      }
    ],
    "audios": [
      {
        "format": "mp3",
        "size_mb": 0.5,
        "url": "https://..."
      }
    ]
  },
  "cached": false
}
```

### استخراج بيانات الفيديو (غير متزامن)
```bash
curl -X POST http://localhost:8000/api/extract-async \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

**الرد:**
```json
{
  "success": true,
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending"
}
```

### التحقق من حالة الوظيفة
```bash
curl http://localhost:8000/api/job/550e8400-e29b-41d4-a716-446655440000
```

### تحميل الفيديو مباشرة
```bash
curl http://localhost:8000/api/download?url=https://www.tiktok.com/@user/video/123456 \
  --output video.mp4
```

### الحصول على الإحصائيات
```bash
curl http://localhost:8000/api/stats
```

### فحص صحة السيرفر
```bash
curl http://localhost:8000/health
```

## 📖 التوثيق التفاعلي

بعد تشغيل السيرفر، يمكنك الوصول إلى:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🗂️ هيكل المشروع

```
social-downloader-python/
├── main.py                 # ملف التشغيل الرئيسي
├── server.py              # السيرفر الرئيسي (FastAPI)
├── config.py              # إعدادات التطبيق
├── utils.py               # دوال مساعدة
├── cache.py               # نظام التخزين المؤقت
├── extractors.py          # استخراج بيانات الفيديو
├── requirements.txt       # المكتبات المطلوبة
├── .env                   # متغيرات البيئة
├── README.md              # هذا الملف
└── templates/
    └── index.html         # الواجهة الأمامية
```

## ⚙️ الإعدادات

تعديل ملف `.env` لتخصيص الإعدادات:

```env
# API Configuration
API_KEY=AlAmouri_Pro_123456
DEBUG=True

# Server Configuration
HOST=0.0.0.0
PORT=8000

# Rate Limiting
RATE_LIMIT_EXTRACT=20/minute
RATE_LIMIT_DOWNLOAD=10/minute

# Cache Configuration
CACHE_TTL_TIKTOK=3600        # 1 ساعة
CACHE_TTL_YOUTUBE=86400      # 24 ساعة
CACHE_TTL_FACEBOOK=7200      # ساعتين
CACHE_TTL_INSTAGRAM=7200     # ساعتين

# Logging
LOG_LEVEL=INFO
```

## 🔧 استكشاف الأخطاء

### المشكلة: "ModuleNotFoundError"
**الحل:**
```bash
pip install -r requirements.txt
```

### المشكلة: "Connection refused"
**الحل:** تأكد من أن السيرفر يعمل على المنفذ الصحيح:
```bash
python main.py
```

### المشكلة: "Rate limit exceeded"
**الحل:** انتظر قليلاً أو عدّل إعدادات Rate Limiting في `.env`

### المشكلة: TikTok لا يعمل
**الحل:** تأكد من:
1. اتصالك بالإنترنت
2. الرابط صحيح وليس خاص
3. استخدم أحدث إصدار من المكتبات:
```bash
pip install --upgrade yt-dlp
```

## 📊 الإحصائيات والمراقبة

### عرض إحصائيات الـ Cache
```bash
curl http://localhost:8000/api/stats
```

### Prometheus Metrics
```bash
curl http://localhost:8000/metrics
```

## 🤝 المساهمة

نرحب بالمساهمات والتحسينات! يرجى:
1. Fork المشروع
2. إنشاء فرع جديد
3. إرسال Pull Request

## 📝 الترخيص

هذا المشروع مرخص تحت MIT License

## 📞 التواصل والدعم

- 📧 البريد الإلكتروني: support@example.com
- 🐛 الإبلاغ عن الأخطاء: GitHub Issues
- 💬 النقاشات: GitHub Discussions

## 🙏 شكر خاص

شكر لجميع المساهمين والمطورين الذين ساعدوا في تطوير هذا المشروع.

---

**تم التطوير بـ ❤️ من قبل فريق Social Downloader Pro**

**الإصدار:** 4.0.0  
**آخر تحديث:** 2024
