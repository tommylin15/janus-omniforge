import 'dart:async';
import 'dart:math';
import 'package:flutter/material.dart';

String _id() {
  final random = Random.secure();
  final bytes = List.generate(16, (_) => random.nextInt(256));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  final hex = bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
  return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
}

class UsageTracker extends ChangeNotifier with WidgetsBindingObserver {
  UsageTracker(
      {required this.send,
      required this.read,
      required this.save,
      required this.erase,
      DateTime Function()? clock})
      : clock = clock ?? DateTime.now;
  final Future<dynamic> Function(Map<String, dynamic>) send;
  final Future<dynamic> Function() read;
  final Future<dynamic> Function(bool) save;
  final Future<dynamic> Function() erase;
  final DateTime Function() clock;
  final session = _id();
  final List<Map<String, dynamic>> _queue = [];
  bool enabled = false, foreground = true, _sending = false, _disposed = false;
  String feature = 'today';
  DateTime? _last, _interaction;
  Timer? _timer;
  int _ticks = 0;

  Future<void> start() async {
    WidgetsBinding.instance.addObserver(this);
    try {
      enabled =
          (await read().timeout(const Duration(seconds: 3)))['enabled'] == true;
    } catch (_) {
      enabled = false;
    }
    if (_disposed) return;
    interaction();
    _last = clock();
    if (enabled) record('page_view');
    _startTimer();
    notifyListeners();
  }

  void _startTimer() {
    if (!enabled || _timer != null) return;
    _timer = Timer.periodic(const Duration(seconds: 10), (_) {
      tick();
      if (++_ticks % 6 == 0) unawaited(flush());
    });
    notifyListeners();
  }

  Future<void> setEnabled(bool value) async {
    // Stop immediately on opt-out even if the preference request fails.
    if (!value) {
      enabled = false;
      _queue.clear();
      notifyListeners();
    }
    await save(value).timeout(const Duration(seconds: 3));
    if (_disposed) return;
    enabled = value;
    _last = clock();
    interaction();
    if (enabled) {
      _startTimer();
      record('page_view');
    } else {
      _timer?.cancel();
      _timer = null;
    }
    notifyListeners();
  }

  Future<void> delete() async {
    enabled = false;
    _queue.clear();
    notifyListeners();
    await erase().timeout(const Duration(seconds: 3));
  }

  void interaction() {
    if (_interaction != null &&
        clock().difference(_interaction!).inSeconds >= 60) tick();
    _interaction = clock();
  }

  void select(String value) {
    if (feature == value) return;
    tick();
    feature = value;
    _last = clock();
    interaction();
    record('page_view');
  }

  void record(String type,
      {String action = 'open',
      String outcome = 'unknown',
      int duration = 0,
      DateTime? at}) {
    if (!enabled || _disposed) return;
    if (_queue.length >= 100) _queue.removeAt(0);
    _queue.add({
      'schema_version': 'usage-event.v1',
      'event_id': _id(),
      'session_id': session,
      'feature_id': feature,
      'event_type': type,
      'action_key': action,
      'outcome': outcome,
      'client_time': (at ?? clock()).toUtc().toIso8601String(),
      'active_duration_ms': duration
    });
    if (_queue.length >= 20) unawaited(flush());
  }

  void tick() {
    final now = clock();
    final previous = _last;
    _last = now;
    if (!enabled || !foreground || previous == null || _interaction == null)
      return;
    final idleAt = _interaction!.add(const Duration(seconds: 60));
    final end = now.isBefore(idleAt) ? now : idleAt;
    var start = previous;
    if (end.difference(start).inMilliseconds > 60000)
      start = end.subtract(const Duration(seconds: 60));
    if (!end.isAfter(start)) return;
    // Split at Taipei midnight regardless of the device's local timezone.
    final taipei = start.toUtc().add(const Duration(hours: 8));
    final midnight = DateTime.utc(taipei.year, taipei.month, taipei.day + 1)
        .subtract(const Duration(hours: 8));
    if (!end.isBefore(midnight)) {
      final before = midnight.subtract(const Duration(milliseconds: 1));
      if (before.isAfter(start))
        record('active_interval',
            duration: before.difference(start).inMilliseconds, at: before);
      start = midnight;
    }
    if (end.isAfter(start))
      record('active_interval',
          duration: end.difference(start).inMilliseconds, at: end);
  }

  Future<void> flush() async {
    if (!enabled || _sending || _queue.isEmpty || _disposed) return;
    _sending = true;
    final events = <Map<String, dynamic>>[];
    var duration = 0;
    for (final event in _queue.take(20)) {
      final next = event['active_duration_ms'] as int;
      if (duration + next > 60000) break;
      events.add(event);
      duration += next;
    }
    _queue.removeRange(0, events.length);
    final batch = {'batch_id': _id(), 'events': events};
    try {
      await send(batch).timeout(const Duration(seconds: 3));
    } catch (_) {
      if (enabled && !_disposed) {
        try {
          await send(batch).timeout(const Duration(seconds: 3));
        } catch (_) {}
      }
    } finally {
      _sending = false;
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    tick();
    foreground = state == AppLifecycleState.resumed;
    _last = clock();
    if (!foreground) unawaited(flush());
  }

  @override
  void dispose() {
    _disposed = true;
    enabled = false;
    _queue.clear();
    _timer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }
}

class UsageActivity extends StatelessWidget {
  const UsageActivity({required this.tracker, required this.child, super.key});
  final UsageTracker tracker;
  final Widget child;
  @override
  Widget build(BuildContext context) => Listener(
      onPointerDown: (_) => tracker.interaction(),
      child: Focus(
          onKeyEvent: (_, __) {
            tracker.interaction();
            return KeyEventResult.ignored;
          },
          child: child));
}

class UsagePrivacy extends StatelessWidget {
  const UsagePrivacy(this.tracker, {super.key});
  final UsageTracker tracker;
  @override
  Widget build(BuildContext context) => ListenableBuilder(
      listenable: tracker,
      builder: (context, _) => Column(children: [
            SwitchListTile(
                title: const Text('協助改善功能使用體驗'),
                value: tracker.enabled,
                subtitle: const Text(
                    '自願提供功能開啟、操作結果與估計活躍時間，僅授權管理者可查看。不收集股票、金額、筆記或輸入文字。原始事件及防重收據保留7天，每日統計180天，去識別月統計12個月；停用不影響功能。'),
                onChanged: (value) async {
                  try {
                    await tracker.setEnabled(value);
                  } catch (_) {
                    if (context.mounted)
                      ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('設定尚未保存，請重試')));
                  }
                }),
            TextButton(
                onPressed: () async {
                  try {
                    await tracker.delete();
                    if (context.mounted)
                      ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('使用分析資料已刪除並停用')));
                  } catch (_) {
                    if (context.mounted)
                      ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('刪除尚未確認，請重試')));
                  }
                },
                child: const Text('刪除我的使用分析資料')),
          ]));
}
