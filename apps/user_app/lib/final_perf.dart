import 'package:flutter/material.dart';

class FinalPerf {
  FinalPerf._();

  static final ValueNotifier<int> revision = ValueNotifier<int>(0);
  static final Map<String, List<int>> _coreMs = <String, List<int>>{};
  static final List<int> _restoreMs = <int>[];

  static bool get enabled => Uri.base.queryParameters['perf'] == '1';

  static Map<String, int> get latestCoreMs => <String, int>{
        for (final entry in _coreMs.entries)
          if (entry.value.isNotEmpty) entry.key: entry.value.last,
      };

  static int get coreSamples =>
      _coreMs.values.fold<int>(0, (sum, values) => sum + values.length);

  static int get restoreSamples => _restoreMs.length;

  static int? get coreP95 {
    final values = <int>[
      for (final samples in _coreMs.values) ...samples,
    ];
    return _p95(values);
  }

  static int? get restoreP95 => _p95(_restoreMs);

  static void recordCore(String page, Duration elapsed) {
    final samples = _coreMs.putIfAbsent(page, () => <int>[]);
    samples.add(elapsed.inMilliseconds);
    if (samples.length > 60) samples.removeAt(0);
    revision.value++;
  }

  static void recordRestore(Duration elapsed) {
    _restoreMs.add(elapsed.inMilliseconds);
    if (_restoreMs.length > 120) _restoreMs.removeAt(0);
    revision.value++;
  }

  static int? _p95(List<int> source) {
    if (source.isEmpty) return null;
    final values = List<int>.from(source)..sort();
    final index =
        ((values.length * .95).ceil() - 1).clamp(0, values.length - 1).toInt();
    return values[index];
  }

  static void resetForTest() {
    _coreMs.clear();
    _restoreMs.clear();
    revision.value++;
  }
}

class FinalPerfBadge extends StatelessWidget {
  const FinalPerfBadge({this.alwaysShow = false, super.key});

  final bool alwaysShow;

  String _value(int? value, int target) =>
      value == null ? '—' : '${value}ms / ≤${target}ms';

  Color _color(int? value, int target) {
    if (value == null) return const Color(0xFF5D7180);
    return value <= target
        ? const Color(0xFF177F88)
        : const Color(0xFFC47A28);
  }

  @override
  Widget build(BuildContext context) {
    if (!alwaysShow && !FinalPerf.enabled) return const SizedBox.shrink();
    return ValueListenableBuilder<int>(
      valueListenable: FinalPerf.revision,
      builder: (context, _, __) {
        final core = FinalPerf.coreP95;
        final restore = FinalPerf.restoreP95;
        final latest = FinalPerf.latestCoreMs;
        const names = <String, String>{
          'today': '今日',
          'watchlist': '關注',
          'ledger': '記帳',
          'stock-detail': '個股',
        };
        final detail = <String>[
          for (final entry in names.entries)
            if (latest[entry.key] != null)
              '${entry.value} ${latest[entry.key]}ms',
        ].join(' · ');
        return Material(
          key: const Key('final-perf-badge'),
          elevation: 2,
          borderRadius: BorderRadius.circular(12),
          color: Colors.white.withValues(alpha: .96),
          child: Container(
            constraints: const BoxConstraints(maxWidth: 330),
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
            decoration: BoxDecoration(
              border: Border.all(color: const Color(0xFFD8E4E8)),
              borderRadius: BorderRadius.circular(12),
            ),
            child: DefaultTextStyle(
              style: const TextStyle(
                color: Color(0xFF16324A),
                fontSize: 10.5,
                height: 1.25,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text(
                    'A 組真機效能',
                    style: TextStyle(fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    'core p95 ${_value(core, 2000)} · n=${FinalPerf.coreSamples}',
                    softWrap: true,
                    style: TextStyle(
                      color: _color(core, 2000),
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  Text(
                    'restore p95 ${_value(restore, 300)} · n=${FinalPerf.restoreSamples}',
                    softWrap: true,
                    style: TextStyle(
                      color: _color(restore, 300),
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  if (detail.isNotEmpty) ...[
                    const SizedBox(height: 2),
                    Text(detail),
                  ],
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}
