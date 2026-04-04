"""
🎬 نظام استخراج بيانات الفيديو من المنصات المختلفة
"""
import httpx
import yt_dlp
from typing import Dict, List, Any, Optional
from utils import logger, sanitize_filename
import asyncio


class VideoExtractor:
    """فئة استخراج بيانات الفيديو"""
    
    def __init__(self):
        self.timeout = 30.0
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    async def extract_tiktok(self, url: str) -> Dict[str, Any]:
        """
        🎵 استخراج بيانات TikTok (بنظام البدائل الذكي TikDown ثم TikWM)
        """
        logger.info(f"استخراج بيانات TikTok من: {url}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get("https://tikdown.org/api", params={"url": url})
                data = res.json()
                if data.get("video_no_watermark"):
                    result = {
                        'title': 'TikTok Video',
                        'thumbnail': '',
                        'duration': 0,
                        'uploader': 'TikTok',
                        'platform': 'tiktok',
                        'videos': [{
                            'quality': 'HD',
                            'height': 1080,
                            'size_mb': 'غير معروف',
                            'url': data.get("video_no_watermark"),
                            'format': 'mp4'
                        }],
                        'audios': []
                    }
                    logger.info("✅ تم استخراج بيانات TikTok بنجاح عبر TikDown")
                    return result
        except Exception as e:
            logger.warning(f"⚠️ فشل TikDown، جاري تجربة البديل TikWM: {e}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    "https://www.tikwm.com/api/",
                    params={"url": url, "hd": 1},
                    headers=self.headers
                )
                
                if response.status_code != 200:
                    raise Exception(f"خطأ API: {response.status_code}")
                
                data = response.json()
                
                if data.get("code") != 0:
                    raise Exception("فشل سحب بيانات التيك توك، قد يكون المقطع خاص أو محذوف.")
                
                video_data = data.get("data", {})
                
                videos = []
                play_url = video_data.get("hdplay") or video_data.get("play")
                if play_url:
                    videos.append({
                        'quality': 'HD/SD',
                        'height': 1080,
                        'size_mb': 'غير معروف',
                        'url': play_url,
                        'format': 'mp4'
                    })
                
                audios = []
                if video_data.get("music"):
                    audios.append({
                        'format': 'mp3',
                        'size_mb': 'غير معروف',
                        'url': video_data.get("music")
                    })
                
                result = {
                    'title': video_data.get('title', 'TikTok Video').replace('/', '_'),
                    'thumbnail': video_data.get('cover', ''),
                    'duration': video_data.get('duration', 0),
                    'uploader': video_data.get('author', {}).get('nickname', 'Unknown'),
                    'platform': 'tiktok',
                    'videos': videos,
                    'audios': audios
                }
                
                logger.info(f"✅ تم استخراج بيانات TikTok بنجاح عبر TikWM: {result['title']}")
                return result
                
        except Exception as e:
            logger.error(f"❌ فشل جميع بدائل TikTok: {str(e)}")
            raise Exception(f"خطأ في استخراج بيانات TikTok: {str(e)}")
    
    async def extract_youtube(self, url: str) -> Dict[str, Any]:
        """
        📺 استخراج بيانات YouTube
        
        Args:
            url: رابط الفيديو
            
        Returns:
            dict: بيانات الفيديو
        """
        try:
            logger.info(f"استخراج بيانات YouTube من: {url}")
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._extract_youtube_sync, url)
            
            logger.info(f"✅ تم استخراج بيانات YouTube بنجاح: {result['title']}")
            return result
            
        except Exception as e:
            logger.error(f"❌ خطأ في استخراج YouTube: {str(e)}")
            raise Exception(f"خطأ في استخراج بيانات YouTube: {str(e)}")
    
    def _extract_youtube_sync(self, url: str) -> Dict[str, Any]:
        """نسخة متزامنة من استخراج YouTube"""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'socket_timeout': 30,
            'http_headers': {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)'},
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            videos = []
            audios = []
            
            for fmt in info.get('formats', []):
                filesize_mb = round((fmt.get('filesize') or 0) / (1024 * 1024), 2)
                
                # استخراج الفيديو
                if fmt.get('vcodec') != 'none' and fmt.get('height') and fmt.get('url'):
                    if 'm3u8' not in fmt.get('url', ''):
                        videos.append({
                            'quality': f"{fmt.get('height')}p",
                            'height': fmt.get('height'),
                            'size_mb': filesize_mb,
                            'url': fmt.get('url'),
                            'format': fmt.get('ext', 'mp4')
                        })
                
                # استخراج الصوت
                if fmt.get('acodec') != 'none' and fmt.get('vcodec') == 'none' and fmt.get('url'):
                    if 'm3u8' not in fmt.get('url', ''):
                        audios.append({
                            'format': fmt.get('ext', 'mp3'),
                            'size_mb': filesize_mb,
                            'url': fmt.get('url')
                        })
            
            # ترتيب الفيديوهات حسب الجودة
            videos.sort(key=lambda x: x['height'], reverse=True)
            
            return {
                'title': info.get('title', 'YouTube Video'),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'Unknown'),
                'platform': 'youtube',
                'videos': videos,
                'audios': audios
            }
    
    async def extract_others(self, url: str) -> Dict[str, Any]:
        """
        📱 استخراج بيانات Facebook و Instagram
        
        Args:
            url: رابط الفيديو
            
        Returns:
            dict: بيانات الفيديو
        """
        try:
            logger.info(f"استخراج بيانات من: {url}")
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._extract_others_sync, url)
            
            logger.info(f"✅ تم استخراج البيانات بنجاح: {result['title']}")
            return result
            
        except Exception as e:
            logger.error(f"❌ خطأ في الاستخراج: {str(e)}")
            raise Exception(f"خطأ في استخراج البيانات: {str(e)}")
    
    def _extract_others_sync(self, url: str) -> Dict[str, Any]:
        """نسخة متزامنة من استخراج Facebook و Instagram"""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'socket_timeout': 30,
            'http_headers': {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)'},
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            videos = []
            audios = []
            
            for fmt in info.get('formats', []):
                filesize_mb = round((fmt.get('filesize') or 0) / (1024 * 1024), 2)
                
                # استخراج الفيديو
                if (fmt.get('vcodec') != 'none' and fmt.get('height') and fmt.get('url') and
                    'm3u8' not in fmt.get('url', '')):
                    videos.append({
                        'quality': f"{fmt.get('height')}p",
                        'height': fmt.get('height'),
                        'size_mb': filesize_mb,
                        'url': fmt.get('url'),
                        'format': fmt.get('ext', 'mp4')
                    })
                
                # استخراج الصوت
                if (fmt.get('acodec') != 'none' and fmt.get('vcodec') == 'none' and fmt.get('url') and
                    'm3u8' not in fmt.get('url', '')):
                    audios.append({
                        'format': fmt.get('ext', 'mp3'),
                        'size_mb': filesize_mb,
                        'url': fmt.get('url')
                    })
            
            # ترتيب الفيديوهات حسب الجودة
            videos.sort(key=lambda x: x['height'], reverse=True)
            
            # إزالة التكرارات
            unique_videos = {}
            for v in videos:
                if v['height'] not in unique_videos:
                    unique_videos[v['height']] = v
            
            return {
                'title': info.get('title', 'Video'),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'Unknown'),
                'platform': 'other',
                'videos': list(unique_videos.values()),
                'audios': audios
            }


# إنشاء instance واحد من الـ Extractor
extractor = VideoExtractor()