// ============================================================================
// الحزم المطلوبة (قم بتشغيل هذا الأمر في الـ CMD قبل تشغيل التطبيق):
// flutter pub add http dio path_provider gal shared_preferences permission_handler share_plus url_launcher cached_network_image
// ============================================================================

import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:http/http.dart' as http;
import 'package:dio/dio.dart';
import 'package:path_provider/path_provider.dart';
import 'package:gal/gal.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:share_plus/share_plus.dart';
import 'package:cached_network_image/cached_network_image.dart';

const String serverUrl = 'https://alamouri-api.onrender.com';
const String apiKey = 'AlAmouri_Pro_123456';

final ValueNotifier<ThemeMode> themeNotifier = ValueNotifier(ThemeMode.light);

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final prefs = await SharedPreferences.getInstance();
  final isDark = prefs.getBool('isDark') ?? false;
  themeNotifier.value = isDark ? ThemeMode.dark : ThemeMode.light;
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<ThemeMode>(
      valueListenable: themeNotifier,
      builder: (_, ThemeMode currentMode, __) {
        return MaterialApp(
          title: 'Al Amouri Pro',
          debugShowCheckedModeBanner: false,
          themeMode: currentMode,
          theme: ThemeData(
            colorScheme: ColorScheme.fromSeed(seedColor: Colors.blueAccent, brightness: Brightness.light),
            useMaterial3: true,
            fontFamily: 'Cairo',
          ),
          darkTheme: ThemeData(
            colorScheme: ColorScheme.fromSeed(seedColor: Colors.blueAccent, brightness: Brightness.dark),
            useMaterial3: true,
            fontFamily: 'Cairo',
          ),
          home: const WelcomeScreen(),
        );
      },
    );
  }
}

// ==========================================
// 1. شاشة الترحيب
// ==========================================
class WelcomeScreen extends StatefulWidget {
  const WelcomeScreen({super.key});

  @override
  State<WelcomeScreen> createState() => _WelcomeScreenState();
}

class _WelcomeScreenState extends State<WelcomeScreen> {
  bool _dontShowAgain = false;

  @override
  void initState() {
    super.initState();
    _checkWelcomeScreen();
  }

  Future<void> _checkWelcomeScreen() async {
    final prefs = await SharedPreferences.getInstance();
    final bool hideWelcome = prefs.getBool('hideWelcome') ?? false;

    if (hideWelcome) {
      _goToMain();
    } else {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _showWelcomeDialog();
      });
    }
  }

  void _goToMain() {
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(builder: (context) => const MainWrapper()),
    );
  }

  void _showWelcomeDialog() {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => StatefulBuilder(
        builder: (context, setState) {
          return AlertDialog(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
            title: const Text('أهلاً بك في تطبيقي', textAlign: TextAlign.center, style: TextStyle(fontWeight: FontWeight.bold)),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text(
                  'لقد قمت بتطوير هذا التطبيق ليكون أداتك الأولى والأسهل لتحميل الفيديوهات والصوتيات من مختلف المنصات بمجرد نسخ الرابط. أتمنى أن ينال إعجابك وتستفيد منه.',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 15, height: 1.5),
                ),
                const SizedBox(height: 20),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Checkbox(
                      value: _dontShowAgain,
                      onChanged: (val) {
                        setState(() {
                          _dontShowAgain = val!;
                        });
                      },
                    ),
                    const Text('عدم إظهار هذه الرسالة مجدداً', style: TextStyle(fontSize: 12)),
                  ],
                ),
              ],
            ),
            actions: [
              Center(
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(horizontal: 40, vertical: 12),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                  onPressed: () async {
                    if (_dontShowAgain) {
                      final prefs = await SharedPreferences.getInstance();
                      await prefs.setBool('hideWelcome', true);
                    }
                    Navigator.pop(context);
                    _goToMain();
                  },
                  child: const Text('البدء الآن', style: TextStyle(fontWeight: FontWeight.bold)),
                ),
              ),
            ],
          );
        }
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(child: CircularProgressIndicator()),
    );
  }
}

// ==========================================
// 2. القائمة السفلية (Main Wrapper)
// ==========================================
class MainWrapper extends StatefulWidget {
  const MainWrapper({super.key});

  @override
  State<MainWrapper> createState() => _MainWrapperState();
}

class _MainWrapperState extends State<MainWrapper> {
  int _bottomNavIndex = 0;

  final List<Widget> _screens = [
    const DownloaderScreen(),
    const DownloadsHistoryScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: AnimatedSwitcher(
        duration: const Duration(milliseconds: 300),
        child: _screens[_bottomNavIndex],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _bottomNavIndex,
        onDestinationSelected: (index) {
          setState(() {
            _bottomNavIndex = index;
          });
        },
        destinations: const [
          NavigationDestination(icon: Icon(Icons.download), label: 'التحميل'),
          NavigationDestination(icon: Icon(Icons.folder_special), label: 'التنزيلات'),
        ],
      ),
    );
  }
}

// ==========================================
// 3. شاشة التحميل الأساسية
// ==========================================
class DownloaderScreen extends StatefulWidget {
  const DownloaderScreen({super.key});

  @override
  State<DownloaderScreen> createState() => _DownloaderScreenState();
}

class _DownloaderScreenState extends State<DownloaderScreen> {
  int _selectedPlatformIndex = 0;
  final TextEditingController _linkController = TextEditingController();
  bool _isLoading = false;

  final List<Map<String, dynamic>> _platforms = [
    {'name': 'فيسبوك', 'icon': Icons.facebook, 'color': Colors.blue},
    {'name': 'تيك توك', 'icon': Icons.tiktok, 'color': Colors.black},
    {'name': 'انستقرام', 'icon': Icons.camera_alt, 'color': Colors.pink},
    {'name': 'يوتيوب', 'icon': Icons.video_collection, 'color': Colors.red},
  ];

  Future<void> _pasteFromClipboard() async {
    ClipboardData? data = await Clipboard.getData(Clipboard.kTextPlain);
    if (data != null && data.text != null) {
      setState(() {
        _linkController.text = data.text!;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('تم لصق الرابط'), duration: Duration(seconds: 1)),
      );
    }
  }

  Future<void> _fetchVideoData() async {
    if (_linkController.text.isEmpty) {
      _showError('الرجاء إدخال الرابط أولاً');
      return;
    }

    setState(() => _isLoading = true);

    try {
      final response = await http.get(
        Uri.parse('$serverUrl/get_video?url=${_linkController.text}'),
        headers: {"X-API-KEY": apiKey},
      ).timeout(const Duration(seconds: 15)); // إضافة مهلة للاتصال

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        if (data['success']) {
          _showFormatSelectionDialog(data['data']);
        } else {
          _showError(data['error'] ?? 'حدث خطأ غير معروف');
        }
      } else {
        _showError('خطأ في الاتصال بالسيرفر: ${response.statusCode}');
      }
    } catch (e) {
      _showError('تأكد من تشغيل السيرفر والاتصال بالإنترنت');
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  void _showError(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg), backgroundColor: Colors.redAccent, behavior: SnackBarBehavior.floating));
  }

  Future<void> _saveToHistory(String title, String type, String thumbnail) async {
    final prefs = await SharedPreferences.getInstance();
    List<String> history = prefs.getStringList('downloads_history') ?? [];
    
    final newItem = {
      'title': title,
      'link': _linkController.text,
      'platform': _platforms[_selectedPlatformIndex]['name'],
      'type': type,
      'thumbnail': thumbnail,
      'date': DateTime.now().toString(),
    };
    
    history.insert(0, json.encode(newItem));
    await prefs.setStringList('downloads_history', history);
  }

  // استخدام ValueNotifier لتحسين الأداء وتجنب markNeedsBuild
  Future<void> _downloadFile(String url, bool isVideo, String format, String title, String thumbnail) async {
    Navigator.pop(context); 
    
    try {
      if (Platform.isAndroid) {
        await [Permission.storage, Permission.videos, Permission.audio].request();
      }
      if (isVideo) {
        if (!await Gal.hasAccess()) await Gal.requestAccess();
      }
    } catch (e) {
      debugPrint('Permission error: $e');
    }

    final ValueNotifier<double> progressNotifier = ValueNotifier(0.0);
    final ValueNotifier<bool> hasErrorNotifier = ValueNotifier(false);
    CancelToken cancelToken = CancelToken();

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15)),
        title: const Text('جاري التنزيل...', textAlign: TextAlign.center),
        content: ValueListenableBuilder<bool>(
          valueListenable: hasErrorNotifier,
          builder: (context, hasError, child) {
            if (hasError) {
              return Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.error_outline, color: Colors.red, size: 50),
                  const SizedBox(height: 10),
                  const Text('فشل التحميل، يرجى المحاولة مرة أخرى.', textAlign: TextAlign.center),
                  const SizedBox(height: 15),
                  ElevatedButton(
                    style: ElevatedButton.styleFrom(backgroundColor: Colors.blueAccent),
                    onPressed: () {
                      Navigator.pop(context);
                      _downloadFile(url, isVideo, format, title, thumbnail); // إعادة المحاولة
                    },
                    child: const Text('إعادة المحاولة', style: TextStyle(color: Colors.white)),
                  ),
                  TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('إلغاء', style: TextStyle(color: Colors.grey)),
                  )
                ],
              );
            }

            return ValueListenableBuilder<double>(
              valueListenable: progressNotifier,
              builder: (context, progress, child) {
                return Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    LinearProgressIndicator(
                      value: progress > 0 ? progress : null,
                      backgroundColor: Colors.grey.shade200,
                      color: Colors.blueAccent,
                      minHeight: 10,
                      borderRadius: BorderRadius.circular(10),
                    ),
                    const SizedBox(height: 15),
                    Text('${(progress * 100).toStringAsFixed(1)} %', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
                    const SizedBox(height: 15),
                    TextButton(
                      onPressed: () {
                        cancelToken.cancel();
                        Navigator.pop(context);
                      },
                      child: const Text('إلغاء التحميل', style: TextStyle(color: Colors.red)),
                    )
                  ],
                );
              },
            );
          },
        ),
      ),
    );

    String tempPath = '';
    try {
      final tempDir = await getTemporaryDirectory();
      tempPath = '${tempDir.path}/AlAmouri_${DateTime.now().millisecondsSinceEpoch}.$format';

      await Dio().download(
        url, 
        tempPath, 
        cancelToken: cancelToken,
        onReceiveProgress: (received, total) {
          if (total != -1) {
            progressNotifier.value = received / total;
          }
        }
      );

      await _saveToHistory(title, isVideo ? 'فيديو' : 'صوت', thumbnail);
      
      if (!mounted) return;
      Navigator.pop(context); 
      
      if (isVideo) {
        await Gal.putVideo(tempPath); 
        _showSuccess('تم الحفظ في الاستديو بنجاح! ✅');
      } else {
        await Share.shareXFiles([XFile(tempPath)], text: 'مقطع صوتي محمل بواسطة العموري برو');
      }
      _linkController.clear();

    } catch (e) {
      if (CancelToken.isCancel(e)) {
        debugPrint('تم إلغاء التحميل');
      } else {
        hasErrorNotifier.value = true;
        debugPrint('Download error: $e');
      }
    } finally {
      // تنظيف الملفات المؤقتة لتوفير مساحة الجهاز
      if (tempPath.isNotEmpty) {
        final file = File(tempPath);
        if (await file.exists()) {
          // หน่วง وقت قليل للتأكد من انتهاء المشاركة قبل الحذف
          Future.delayed(const Duration(minutes: 2), () async {
            if (await file.exists()) await file.delete();
          });
        }
      }
    }
  }

  void _showSuccess(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg), backgroundColor: Colors.green, behavior: SnackBarBehavior.floating));
  }

  void _showFormatSelectionDialog(Map<String, dynamic> videoData) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15)),
        title: const Text('اختر نوع التنزيل', textAlign: TextAlign.center),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.video_library, color: Colors.blueAccent, size: 35),
              title: const Text('تنزيل كـ فيديو', style: TextStyle(fontWeight: FontWeight.bold)),
              onTap: () {
                Navigator.pop(context);
                _showVideoQualityDialog(videoData);
              },
            ),
            const Divider(),
            ListTile(
              leading: const Icon(Icons.audiotrack, color: Colors.green, size: 35),
              title: const Text('تنزيل كـ مقطع صوتي', style: TextStyle(fontWeight: FontWeight.bold)),
              onTap: () {
                Navigator.pop(context);
                _showAudioFormatDialog(videoData);
              },
            ),
          ],
        ),
      ),
    );
  }

  void _showVideoQualityDialog(Map<String, dynamic> videoData) {
    List videos = videoData['videos'] ?? [];
    
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15)),
        contentPadding: const EdgeInsets.all(20),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (videoData['thumbnail'] != '')
              ClipRRect(
                borderRadius: BorderRadius.circular(10),
                child: CachedNetworkImage( // استخدام الكاش للصور
                  imageUrl: videoData['thumbnail'], 
                  height: 120, 
                  width: double.infinity, 
                  fit: BoxFit.cover,
                  placeholder: (context, url) => Container(height: 120, color: Colors.grey.shade200, child: const Center(child: CircularProgressIndicator())),
                  errorWidget: (context, url, error) => Container(height: 120, color: Colors.grey.shade300, child: const Icon(Icons.image_not_supported)),
                ),
              ),
            const SizedBox(height: 15),
            Text(videoData['title'], style: const TextStyle(fontWeight: FontWeight.bold), maxLines: 2, overflow: TextOverflow.ellipsis, textAlign: TextAlign.center),
            const SizedBox(height: 20),
            const Text('اختر الدقة المطلوبة:', style: TextStyle(color: Colors.grey)),
            const SizedBox(height: 10),
            ...videos.map((v) => Padding(
              padding: const EdgeInsets.only(bottom: 8.0),
              child: ElevatedButton(
                style: ElevatedButton.styleFrom(minimumSize: const Size(double.infinity, 45)),
                onPressed: () => _downloadFile(v['url'], true, 'mp4', videoData['title'], videoData['thumbnail']),
                child: Text('جودة ${v['quality'] ?? '720p (افتراضي)'}'),
              ),
            )),
          ],
        ),
      ),
    );
  }

  void _showAudioFormatDialog(Map<String, dynamic> videoData) {
    List audios = videoData['audios'] ?? [];
    String audioUrl = audios.isNotEmpty ? audios.first['url'] : (videoData['videos'][0]['url']);

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15)),
        title: const Text('اختر صيغة الصوت', textAlign: TextAlign.center),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ElevatedButton(
              style: ElevatedButton.styleFrom(minimumSize: const Size(double.infinity, 50), backgroundColor: Colors.green.shade100),
              onPressed: () => _downloadFile(audioUrl, false, 'mp3', videoData['title'], videoData['thumbnail']),
              child: const Text('صيغة MP3', style: TextStyle(color: Colors.green, fontWeight: FontWeight.bold, fontSize: 16)),
            ),
            const SizedBox(height: 10),
            ElevatedButton(
              style: ElevatedButton.styleFrom(minimumSize: const Size(double.infinity, 50), backgroundColor: Colors.orange.shade100),
              onPressed: () => _downloadFile(audioUrl, false, 'wav', videoData['title'], videoData['thumbnail']),
              child: const Text('صيغة WAV', style: TextStyle(color: Colors.orange, fontWeight: FontWeight.bold, fontSize: 16)),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Al Amouri Pro', style: TextStyle(fontWeight: FontWeight.bold)),
        centerTitle: true,
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (context) => const SettingsScreen())),
          )
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20.0),
        child: Column(
          children: [
            SizedBox(
              height: 100,
              child: ListView.builder(
                scrollDirection: Axis.horizontal,
                itemCount: _platforms.length,
                itemBuilder: (context, index) {
                  bool isSelected = _selectedPlatformIndex == index;
                  return GestureDetector(
                    onTap: () {
                      setState(() {
                        _selectedPlatformIndex = index;
                        _linkController.clear();
                      });
                    },
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 300),
                      margin: const EdgeInsets.symmetric(horizontal: 8),
                      width: 80,
                      decoration: BoxDecoration(
                        color: isSelected ? _platforms[index]['color'].withOpacity(0.2) : Colors.transparent,
                        borderRadius: BorderRadius.circular(15),
                        border: Border.all(color: isSelected ? _platforms[index]['color'] : Colors.grey.shade300, width: 2),
                      ),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(_platforms[index]['icon'], color: _platforms[index]['color'], size: 30),
                          const SizedBox(height: 5),
                          Text(_platforms[index]['name'], style: TextStyle(fontSize: 12, fontWeight: isSelected ? FontWeight.bold : FontWeight.normal)),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
            const SizedBox(height: 40),
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Theme.of(context).cardColor,
                borderRadius: BorderRadius.circular(20),
                boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.05), blurRadius: 10, spreadRadius: 2)],
              ),
              child: Column(
                children: [
                  Text(
                    'أدخل رابط ${_platforms[_selectedPlatformIndex]['name']} هنا',
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 20),
                  TextField(
                    controller: _linkController,
                    decoration: InputDecoration(
                      filled: true,
                      fillColor: Theme.of(context).scaffoldBackgroundColor,
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(15), borderSide: BorderSide.none),
                      hintText: 'https://...',
                      prefixIcon: const Icon(Icons.link),
                      suffixIcon: IconButton(
                        icon: const Icon(Icons.paste, color: Colors.blueAccent),
                        onPressed: _pasteFromClipboard,
                      ),
                    ),
                  ),
                  const SizedBox(height: 25),
                  AnimatedSwitcher(
                    duration: const Duration(milliseconds: 300),
                    child: _isLoading
                        ? const CircularProgressIndicator()
                        : ElevatedButton.icon(
                            onPressed: _fetchVideoData,
                            icon: const Icon(Icons.download_rounded, color: Colors.white),
                            label: const Text('تنزيل الملف', style: TextStyle(fontSize: 18, color: Colors.white, fontWeight: FontWeight.bold)),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.blueAccent,
                              minimumSize: const Size(double.infinity, 55),
                              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15)),
                              elevation: 5,
                            ),
                          ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ==========================================
// 4. شاشة سجل التنزيلات
// ==========================================
class DownloadsHistoryScreen extends StatefulWidget {
  const DownloadsHistoryScreen({super.key});

  @override
  State<DownloadsHistoryScreen> createState() => _DownloadsHistoryScreenState();
}

class _DownloadsHistoryScreenState extends State<DownloadsHistoryScreen> {
  List<dynamic> _allDownloads = [];
  String _selectedFilter = 'الكل';
  final List<String> _filters = ['الكل', 'تيك توك', 'فيسبوك', 'يوتيوب', 'انستقرام'];

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  Future<void> _loadHistory() async {
    final prefs = await SharedPreferences.getInstance();
    List<String> history = prefs.getStringList('downloads_history') ?? [];
    setState(() {
      _allDownloads = history.map((e) => json.decode(e)).toList();
    });
  }

  Future<void> _clearHistory() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('downloads_history');
    setState(() {
      _allDownloads.clear();
    });
  }

  @override
  Widget build(BuildContext context) {
    List<dynamic> filteredDownloads = _selectedFilter == 'الكل' 
        ? _allDownloads 
        : _allDownloads.where((item) => item['platform'] == _selectedFilter).toList();

    return Scaffold(
      appBar: AppBar(
        title: const Text('سجل التنزيلات'),
        centerTitle: true,
        actions: [
          IconButton(
            icon: const Icon(Icons.delete_outline),
            onPressed: _allDownloads.isEmpty ? null : () {
              showDialog(
                context: context,
                builder: (c) => AlertDialog(
                  title: const Text('مسح السجل'),
                  content: const Text('هل أنت متأكد من مسح جميع التنزيلات السابقة؟'),
                  actions: [
                    TextButton(onPressed: () => Navigator.pop(c), child: const Text('إلغاء')),
                    TextButton(onPressed: () { Navigator.pop(c); _clearHistory(); }, child: const Text('مسح', style: TextStyle(color: Colors.red))),
                  ],
                )
              );
            },
          )
        ],
      ),
      body: Column(
        children: [
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
            child: Row(
              children: _filters.map((filter) => Padding(
                padding: const EdgeInsets.symmetric(horizontal: 5),
                child: ChoiceChip(
                  label: Text(filter),
                  selected: _selectedFilter == filter,
                  onSelected: (selected) {
                    setState(() {
                      _selectedFilter = filter;
                    });
                  },
                ),
              )).toList(),
            ),
          ),
          
          Expanded(
            child: filteredDownloads.isEmpty
                ? Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.inbox, size: 80, color: Colors.grey.shade400),
                        const SizedBox(height: 15),
                        Text(
                          'لم تقم بتنزيل أي ملفات بعد.\nابدأ الآن واستمتع بمحتواك المفضل!',
                          textAlign: TextAlign.center,
                          style: TextStyle(color: Colors.grey.shade600, fontSize: 16),
                        ),
                      ],
                    ),
                  )
                : ListView.builder(
                    itemCount: filteredDownloads.length,
                    itemBuilder: (context, index) {
                      final item = filteredDownloads[index];
                      return Card(
                        margin: const EdgeInsets.symmetric(horizontal: 15, vertical: 8),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15)),
                        child: ListTile(
                          contentPadding: const EdgeInsets.all(10),
                          leading: ClipRRect(
                            borderRadius: BorderRadius.circular(8),
                            child: item['thumbnail'] != '' 
                              ? CachedNetworkImage( // استخدام الكاش للصور
                                  imageUrl: item['thumbnail'], 
                                  width: 60, height: 60, fit: BoxFit.cover,
                                  placeholder: (context, url) => Container(width: 60, height: 60, color: Colors.grey.shade200),
                                  errorWidget: (context, url, error) => Container(width: 60, height: 60, color: Colors.grey.shade300, child: const Icon(Icons.video_file)),
                                )
                              : Container(width: 60, height: 60, color: Colors.grey.shade300, child: const Icon(Icons.video_file)),
                          ),
                          title: Text(item['title'] ?? 'بدون عنوان', maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
                          subtitle: Padding(
                            padding: const EdgeInsets.only(top: 8.0),
                            child: Row(
                              children: [
                                Icon(item['type'] == 'فيديو' ? Icons.video_library : Icons.audiotrack, size: 14, color: Colors.blue),
                                const SizedBox(width: 5),
                                Text(item['type']),
                                const Spacer(),
                                Text(item['platform'], style: const TextStyle(color: Colors.grey, fontSize: 12)),
                              ],
                            ),
                          ),
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}

// ==========================================
// 5. شاشة الإعدادات
// ==========================================
class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  
  Future<void> _launchWhatsApp() async {
    final Uri url = Uri.parse('whatsapp://send?phone=+218946604729');
    if (!await launchUrl(url)) {
      debugPrint('لا يمكن فتح الواتساب');
    }
  }

  void _showAboutDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: const Text('حول التطبيق', textAlign: TextAlign.center, style: TextStyle(fontWeight: FontWeight.bold)),
        content: const Text(
          'أهلاً بكم.\nأنا محمد العموري، مطور هذا التطبيق. حرصت على تصميم هذه الأداة لتكون خفيفة وسريعة وتلبي احتياجاتكم في حفظ المحتوى من الإنترنت بسهولة تامة وبأعلى جودة ممكنة. أعمل باستمرار على تحسين التطبيق، ويسعدني دائماً تواصلكم للاقتراحات والتطوير.',
          textAlign: TextAlign.center,
          style: TextStyle(height: 1.6, fontSize: 15),
        ),
        actions: [
          Center(
            child: ElevatedButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('إغلاق'),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('الإعدادات'),
        centerTitle: true,
      ),
      body: ListView(
        padding: const EdgeInsets.all(10),
        children: [
          Card(
            elevation: 0,
            color: Theme.of(context).cardColor,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15)),
            child: Column(
              children: [
                ValueListenableBuilder<ThemeMode>(
                  valueListenable: themeNotifier,
                  builder: (context, currentMode, child) {
                    bool isDarkMode = currentMode == ThemeMode.dark;
                    return SwitchListTile(
                      secondary: Icon(isDarkMode ? Icons.dark_mode : Icons.light_mode, color: isDarkMode ? Colors.yellow : Colors.orange),
                      title: const Text('الوضع المظلم', style: TextStyle(fontWeight: FontWeight.bold)),
                      value: isDarkMode,
                      onChanged: (value) async {
                        final prefs = await SharedPreferences.getInstance();
                        await prefs.setBool('isDark', value);
                        themeNotifier.value = value ? ThemeMode.dark : ThemeMode.light;
                      },
                    );
                  }
                ),
                const Divider(height: 1),
                ListTile(
                  leading: const Icon(Icons.language, color: Colors.blue),
                  title: const Text('لغة التطبيق', style: TextStyle(fontWeight: FontWeight.bold)),
                  trailing: const Text('العربية', style: TextStyle(color: Colors.grey)),
                ),
              ],
            ),
          ),
          const SizedBox(height: 15),
          Card(
            elevation: 0,
            color: Theme.of(context).cardColor,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15)),
            child: Column(
              children: [
                ListTile(
                  leading: const Icon(Icons.chat, color: Colors.green),
                  title: const Text('تواصل مع المطور', style: TextStyle(fontWeight: FontWeight.bold)),
                  subtitle: const Text('لأي استفسار أو مشكلة'),
                  trailing: const Icon(Icons.arrow_forward_ios, size: 15),
                  onTap: _launchWhatsApp,
                ),
                const Divider(height: 1),
                ListTile(
                  leading: const Icon(Icons.info, color: Colors.purple),
                  title: const Text('حول التطبيق', style: TextStyle(fontWeight: FontWeight.bold)),
                  trailing: const Icon(Icons.arrow_forward_ios, size: 15),
                  onTap: () => _showAboutDialog(context),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}