import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/usage.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('default off, opt in, idle, background and no identity payload',
      () async {
    var now = DateTime.utc(2026, 10, 18, 4);
    final batches = <Map<String, dynamic>>[];
    final tracker = UsageTracker(
        send: (batch) async {
          batches.add(batch);
        },
        read: () async => {'enabled': false},
        save: (_) async {},
        erase: () async {},
        clock: () => now);
    await tracker.start();
    tracker.record('page_view');
    await tracker.flush();
    expect(batches, isEmpty);
    await tracker.setEnabled(true);
    now = now.add(const Duration(seconds: 90));
    tracker.tick();
    await tracker.flush();
    final events = batches.expand((b) => b['events'] as List).cast<Map>();
    expect(
        events
            .where((e) => e['event_type'] == 'active_interval')
            .fold<int>(0, (n, e) => n + (e['active_duration_ms'] as int)),
        60000);
    expect(
        events.any((e) => e.containsKey('user_id') || e.containsKey('symbol')),
        isFalse);
    batches.clear();
    tracker.didChangeAppLifecycleState(AppLifecycleState.paused);
    now = now.add(const Duration(seconds: 30));
    tracker.tick();
    await tracker.flush();
    expect(batches, isEmpty);
    await tracker.setEnabled(false);
    tracker.record('page_view');
    await tracker.flush();
    expect(batches, isEmpty);
    tracker.dispose();
  });

  test('cross Taipei midnight splits intervals and retries the same batch once',
      () async {
    var now = DateTime.utc(2026, 10, 17, 15, 59, 55);
    final attempts = <Map<String, dynamic>>[];
    final tracker = UsageTracker(
        send: (batch) async {
          attempts.add(batch);
          throw StateError('offline');
        },
        read: () async => {'enabled': true},
        save: (_) async {},
        erase: () async {},
        clock: () => now);
    await tracker.start();
    now = now.add(const Duration(seconds: 10));
    tracker.tick();
    await tracker.flush();
    expect(attempts.length, 2);
    expect(attempts[0]['batch_id'], attempts[1]['batch_id']);
    final intervals = (attempts[0]['events'] as List)
        .where((e) => e['event_type'] == 'active_interval')
        .toList();
    expect(intervals.length, 2);
    expect(intervals[0]['active_duration_ms'], 4999);
    expect(intervals[1]['active_duration_ms'], 5000);
    tracker.dispose();
  });

  test('page changes flush old feature duration and stop on deletion',
      () async {
    var now = DateTime.utc(2026, 10, 18, 4);
    final batches = <Map<String, dynamic>>[];
    final tracker = UsageTracker(
        send: (batch) async {
          batches.add(batch);
        },
        read: () async => {'enabled': true},
        save: (_) async {},
        erase: () async {},
        clock: () => now);
    await tracker.start();
    now = now.add(const Duration(seconds: 10));
    tracker.select('watchlist');
    await tracker.flush();
    final events = batches[0]['events'] as List;
    expect(
        events.where((e) =>
            e['feature_id'] == 'today' && e['active_duration_ms'] == 10000),
        hasLength(1));
    expect(events.last['feature_id'], 'watchlist');
    await tracker.delete();
    tracker.record('page_view');
    await tracker.flush();
    expect(batches, hasLength(1));
    tracker.dispose();
  });
}
