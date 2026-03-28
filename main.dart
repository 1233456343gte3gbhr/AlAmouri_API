import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:http/http.dart' as http;
import 'package:dio/dio.dart';
import 'package:path_provider/path_provider.dart';
import 'package:gal/gal.dart';

// رابط السيرفر (استخدم 10.0.2.2 لمحاكي الأندرويد، أو الـ IP الخاص بجهازك لو تجرب على هاتف حقيقي)
const String serverUrl = 'http://10.0.2.2:5000';
const String apiKey = 'AlAmouri_Pro_123456';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Al Amouri Pro',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.blueAccent),
        useMaterial3: true,
      ),
      home: const WelcomeScreen(),
    );
  }
}

// ================= شاشة الترحيب =================
class WelcomeScreen extends StatefulWidget {
  const WelcomeScreen({super.key});

  @override
  State<WelcomeScreen> createState() => _WelcomeScreenState();
}

class _WelcomeScreenState extends State<WelcomeScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _showWelcomeDialog();
    });
  }

  void _showWelcomeDialog() {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        title: const Text('مرحباً بك في تطبيقي Al Amouri Pro', textAlign: TextAlign.center),
        content: const Text(
          'في هذا التطبيق يمكنك التحميل من جميع المواقع من الرابط فقط، سواء كان فيديو أو صوت. من تطبيقي يمكنك عمل ذلك بكل سهولة.',
          textAlign: TextAlign.center,
        ),
        actions: [
          Center(
            child: ElevatedButton(
              onPressed: () {
                Navigator.pop(context);
                Navigator.pushReplacement(
                  context,
                  MaterialPageRoute(builder: (context) => const MainScreen()),
                );
              },
              child: const Text('فهمت'),
            ),
          ),
        ],
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

// ================= الشاشة الرئيسية =================
class MainScreen extends StatefulWidget {
  const MainScreen({super.key});

  @override
  State<MainScreen> createState() => _MainScreenState();
}

class _MainScreenState extends State<MainScreen> {
  int _selectedIndex = 0;
  final TextEditingController _linkController = TextEditingController();
  bool _isLoading = false;

  final List<String> _platforms = ['فيسبوك', 'تيك توك', 'انستقرام', 'يوتيوب'];

  // ميزة 1: لصق الرابط تلقائياً من الحافظة
  Future<void> _pasteFromClipboard() async {
    ClipboardData? data = await Clipboard.getData(Clipboard.kTextPlain);
    if (data != null && data.text != null) {
      setState(() {
        _linkController.text = data.text!;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('تم لصق الرابط تلقائياً')),
      );
    }
  }

  // ميزة 2: جلب بيانات الفيديو من السيرفر
  Future<void> _fetchVideoData() async {
    if (_linkController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('الرجاء إدخال الرابط أولاً')),
      );
      return;
    }

    setState(() {
      _isLoading = true;
    });

    try {
      final response = await http.get(
        Uri.parse('$serverUrl/get_video?url=${_linkController.text}'),
        headers: {"X-API-KEY": apiKey},
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        if (data['success']) {
          _showDownloadOptionsSheet(data['data']);
        } else {
          _showError(data['error'] ?? 'حدث خطأ غير معروف');
        }
      } else {
        _showError('خطأ في الاتصال بالسيرفر: ${response.statusCode}');
      }
    } catch (e) {
      _showError('تأكد من تشغيل السيرفر والاتصال بالإنترنت');
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
  }

  void _showError(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg), backgroundColor: Colors.red));
  }

  // ميزة 3: تحميل الملف وحفظه في الاستديو
  Future<void> _downloadAndSave(String url, bool isVideo) async {
    Navigator.pop(context); // إغلاق القائمة
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('جاري التحميل، الرجاء الانتظار...')),
    );

    try {
      final tempDir = await getTemporaryDirectory();
      final ext = isVideo ? '.mp4' : '.mp3';
      final savePath = '${tempDir.path}/AlAmouri_${DateTime.now().millisecondsSinceEpoch}$ext';

      await Dio().download(url, savePath);

      if (isVideo) {
        await Gal.putVideo(savePath); // حفظ الفيديو في الاستديو
      } else {
        // Gal لا يدعم الصوتيات مباشرة للاستديو، يمكن تركه في الملفات أو استخدام إضافة أخرى للصوت
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('تم تحميل الملف الصوتي في: $savePath')),
        );
        return;
      }

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('تم الحفظ في الاستديو بنجاح! ✅'), backgroundColor: Colors.green),
      );
    } catch (e) {
      _showError('فشل التحميل: $e');
    }
  }

  // عرض تفاصيل الفيديو والجودات
  void _showDownloadOptionsSheet(Map<String, dynamic> videoData) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (context) {
        List videos = videoData['videos'] ?? [];
        List audios = videoData['audios'] ?? [];

        return Padding(
          padding: const EdgeInsets.all(20.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (videoData['thumbnail'] != '')
                ClipRRect(
                  borderRadius: BorderRadius.circular(10),
                  child: Image.network(videoData['thumbnail'], height: 150, width: double.infinity, fit: BoxFit.cover),
                ),
              const SizedBox(height: 10),
              Text(
                videoData['title'],
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.center,
              ),
              const Divider(height: 30),
              const Text('اختر جودة الفيديو:', style: TextStyle(fontWeight: FontWeight.bold)),
              ...videos.map((v) => ListTile(
                    leading: const Icon(Icons.video_library, color: Colors.blue),
                    title: Text('تحميل فيديو جودة ${v['quality']}'),
                    trailing: const Icon(Icons.download),
                    onTap: () => _downloadAndSave(v['url'], true),
                  )),
              if (audios.isNotEmpty) ...[
                const Divider(),
                ListTile(
                  leading: const Icon(Icons.audiotrack, color: Colors.green),
                  title: const Text('تحميل كـ مقطع صوتي (MP3/M4A)'),
                  trailing: const Icon(Icons.download),
                  onTap: () => _downloadAndSave(audios.first['url'], false),
                ),
              ],
            ],
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('تحميل من ${_platforms[_selectedIndex]}'),
        centerTitle: true,
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (context) => const SettingsScreen()),
              );
            },
          )
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              'أدخل رابط ${_platforms[_selectedIndex]} هنا:',
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 20),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _linkController,
                    decoration: const InputDecoration(
                      border: OutlineInputBorder(),
                      hintText: 'https://...',
                      prefixIcon: Icon(Icons.link),
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                IconButton(
                  onPressed: _pasteFromClipboard,
                  icon: const Icon(Icons.paste),
                  tooltip: 'لصق الرابط',
                  style: IconButton.styleFrom(
                    backgroundColor: Colors.grey.shade200,
                    padding: const EdgeInsets.all(15),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 30),
            _isLoading
                ? const CircularProgressIndicator()
                : ElevatedButton.icon(
                    onPressed: _fetchVideoData,
                    icon: const Icon(Icons.search),
                    label: const Text('استخراج الروابط', style: TextStyle(fontSize: 18)),
                    style: ElevatedButton.styleFrom(
                      minimumSize: const Size(double.infinity, 55),
                    ),
                  ),
          ],
        ),
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _selectedIndex,
        type: BottomNavigationBarType.fixed,
        onTap: (index) {
          setState(() {
            _selectedIndex = index;
            _linkController.clear();
          });
        },
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.facebook), label: 'فيسبوك'),
          BottomNavigationBarItem(icon: Icon(Icons.tiktok), label: 'تيك توك'),
          BottomNavigationBarItem(icon: Icon(Icons.camera_alt), label: 'انستقرام'),
          BottomNavigationBarItem(icon: Icon(Icons.video_collection), label: 'يوتيوب'),
        ],
      ),
    );
  }
}

// ================= شاشة الإعدادات =================
class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

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
        title: const Text('حول التطبيق', textAlign: TextAlign.center),
        content: const Text(
          'تطبيق Al Amouri Pro.\nمن تطوير وبرمجة خونا: محمد العموري.\n\nالتطبيق هذا درناه باش يسهل عليكم التحميل من أي منصة بكل سهولة وبدون تعقيد. إن شاء الله يعجبكم وتستفيدوا منه، وأي ملاحظات مرحبتين بيها في أي وقت يا عيلة!',
          textAlign: TextAlign.center,
          style: TextStyle(height: 1.5),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('تسكير'),
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
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
      ),
      body: ListView(
        children: [
          const ListTile(
            leading: Icon(Icons.language),
            title: Text('اللغة: العربية'),
            subtitle: Text('قريباً سيتم العمل على إضافة المزيد من اللغات'),
          ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.chat, color: Colors.green),
            title: const Text('تواصل مع المطور'),
            onTap: _launchWhatsApp,
          ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.info, color: Colors.blue),
            title: const Text('حول التطبيق'),
            onTap: () => _showAboutDialog(context),
          ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.share, color: Colors.orange),
            title: const Text('مشاركة التطبيق'),
            onTap: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('قريباً سيتم إضافة هذه الميزة')),
              );
            },
          ),
        ],
      ),
    );
  }
}