"""
💾 نظام التخزين المؤقت الذكي (Smart Cache)
"""
import time
import json
from typing import Any, Optional, Dict
from threading import Lock


class SmartCache:
    """نظام تخزين مؤقت ذكي مع دعم انتهاء الصلاحية"""
    
    def __init__(self):
        self.store: Dict[str, Dict[str, Any]] = {}
        self.lock = Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """
        📥 الحصول على قيمة من الـ Cache
        
        Args:
            key: مفتاح البيانات
            
        Returns:
            القيمة المخزنة أو None إذا انتهت صلاحيتها
        """
        with self.lock:
            if key not in self.store:
                return None
            
            entry = self.store[key]
            
            # التحقق من انتهاء الصلاحية
            if time.time() > entry['expires_at']:
                del self.store[key]
                return None
            
            return entry['data']
    
    def set(self, key: str, value: Any, ttl: int) -> None:
        """
        📤 حفظ قيمة في الـ Cache
        
        Args:
            key: مفتاح البيانات
            value: القيمة المراد حفظها
            ttl: مدة الصلاحية بالثواني
        """
        with self.lock:
            self.store[key] = {
                'data': value,
                'expires_at': time.time() + ttl,
                'created_at': time.time()
            }
    
    def delete(self, key: str) -> bool:
        """
        🗑️ حذف قيمة من الـ Cache
        
        Args:
            key: مفتاح البيانات
            
        Returns:
            True إذا تم الحذف، False إذا لم توجد
        """
        with self.lock:
            if key in self.store:
                del self.store[key]
                return True
            return False
    
    def clear(self) -> None:
        """🧹 مسح جميع البيانات المخزنة"""
        with self.lock:
            self.store.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        📊 الحصول على إحصائيات الـ Cache
        
        Returns:
            dict: معلومات عن الـ Cache
        """
        with self.lock:
            total_entries = len(self.store)
            expired_entries = 0
            
            current_time = time.time()
            for entry in self.store.values():
                if current_time > entry['expires_at']:
                    expired_entries += 1
            
            return {
                'total_entries': total_entries,
                'expired_entries': expired_entries,
                'active_entries': total_entries - expired_entries
            }
    
    def cleanup_expired(self) -> int:
        """
        🧹 تنظيف البيانات المنتهية الصلاحية
        
        Returns:
            عدد العناصر المحذوفة
        """
        with self.lock:
            current_time = time.time()
            expired_keys = [
                key for key, entry in self.store.items()
                if current_time > entry['expires_at']
            ]
            
            for key in expired_keys:
                del self.store[key]
            
            return len(expired_keys)


# إنشاء instance واحد من الـ Cache
cache = SmartCache()
