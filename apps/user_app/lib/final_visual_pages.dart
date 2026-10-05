import 'package:flutter/material.dart';

import 'main.dart' as legacy;

const _ink = Color(0xFF16324A);
const _muted = Color(0xFF5D7180);
const _teal = Color(0xFF177F88);
const _canvas = Color(0xFFF1F6F8);
const _soft = Color(0xFFE6F1F3);

List<dynamic> _rows(dynamic value) {
  if (value is List) return value;
  if (value is Map && value['items'] is List) return value['items'] as List;
  if (value is Map && value['rows'] is List) return value['rows'] as List;
  return const [];
}

Map<String, dynamic> _map(dynamic value) => value is Map
    ? Map<String, dynamic>.from(value as Map)
    : <String, dynamic>{};

String _text(Object? value, {String missing = '—'}) {
  final result = value?.toString().trim() ?? '';
  return result.isEmpty ? missing : result;
}

int _int(Object? value) => int.tryParse('${value ?? ''}') ?? 0;

Widget _pageTitle(BuildContext context, String title, {String? subtitle}) =>
    Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                    color: _ink,
                    fontWeight: FontWeight.w800,
                    letterSpacing: -.4,
                  )),
          if (subtitle != null) ...[
            const SizedBox(height: 4),
            Text(subtitle,
                style: Theme.of(context)
                    .textTheme
                    .bodyMedium
                    ?.copyWith(color: _muted)),
          ],
        ],
      ),
    );

Widget _sectionTitle(BuildContext context, String title, {String? trailing}) =>
    Padding(
      padding: const EdgeInsets.fromLTRB(2, 14, 2, 8),
      child: Row(
        children: [
          Expanded(
            child: Text(title,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    color: _ink, fontWeight: FontWeight.w800)),
          ),
          if (trailing != null)
            Text(trailing,
                style: Theme.of(context)
                    .textTheme
                    .bodySmall
                    ?.copyWith(color: _muted)),
        ],
      ),
    );

Widget _panel({required Widget child, EdgeInsetsGeometry? padding}) => Card(
      margin: const EdgeInsets.only(bottom: 10),
      color: Colors.white,
      elevation: 0,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      child: Padding(
        padding: padding ?? const EdgeInsets.all(16),
        child: child,
      ),
    );

Widget _boundedState(String text, {IconData icon = Icons.info_outline}) =>
    _panel(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: _teal, size: 20),
          const SizedBox(width: 10),
          Expanded(child: Text(text, style: const TextStyle(color: _muted))),
        ],
      ),
    );

Widget _statusPill(Object? value) {
  final label = legacy.uiLabel(value);
  return Container(
    padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
    decoration: BoxDecoration(
      color: _soft,
      borderRadius: BorderRadius.circular(999),
    ),
    child: Text(label,
        style: const TextStyle(
            color: _teal, fontSize: 12, fontWeight: FontWeight.w700)),
  );
}

Widget _metricTile(String label, String value, {String? detail}) => Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
          color: Colors.white, borderRadius: BorderRadius.circular(18)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label,
              style: const TextStyle(
                  color: _muted, fontSize: 12, fontWeight: FontWeight.w600)),
          const SizedBox(height: 7),
          Text(value,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                  color: _ink, fontSize: 17, fontWeight: FontWeight.w800)),
          if (detail != null) ...[
            const SizedBox(height: 5),
            Text(detail,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(color: _muted, fontSize: 11)),
          ]
        ],
      ),
    );

String _coverage(Map section) {
  final coverage = _map(section['coverage']);
  final received = coverage['received_symbols'];
  final requested = coverage['requested_symbols'];
  if (received == null || requested == null) return '';
  return '涵蓋 $received/$requested 檔';
}

String _freshness(Map section) {
  final asOf = section['as_of'];
  final days = section['freshness_days'];
  final parts = <String>[];
  if (asOf != null) parts.add('資料日 $asOf');
  if (days != null) parts.add(days == 0 ? '最新交易日' : '$days 天前');
  final coverage = _coverage(section);
  if (coverage.isNotEmpty) parts.add(coverage);
  return parts.join(' · ');
}

String _benchmarkValue(Map section) {
  final data = _map(section['data']);
  final close = data['close'] ?? data['index'] ?? data['value'];
  return close == null ? '資料尚未取得' : legacy.accountingNumber(close, decimals: 2);
}

String _facts(Map section, Map<String, String> labels) {
  final data = _map(section['data']);
  final values = <String>[];
  for (final entry in labels.entries) {
    if (data[entry.key] != null) {
      values.add('${entry.value} ${legacy.accountingNumber(data[entry.key])}');
    }
  }
  return values.isEmpty ? '目前沒有可顯示資料' : values.join(' · ');
}

class FinalTodayPage extends StatefulWidget {
  const FinalTodayPage(this.api, {this.onOpenStock, super.key});
  final legacy.Api api;
  final ValueChanged<String>? onOpenStock;

  @override
  State<FinalTodayPage> createState() => _FinalTodayPageState();
}

class _FinalTodayPageState extends State<FinalTodayPage> {
  late Future<dynamic> market = _market();
  late Future<dynamic> brief = _brief();

  Future<dynamic> _market() async {
    try {
      return await widget.api.get('/api/v1/public/market-home');
    } catch (_) {
      return null;
    }
  }

  Future<dynamic> _brief() async {
    try {
      return await widget.api.get('/api/v1/public/daily-brief');
    } catch (_) {
      return null;
    }
  }

  void retryMarket() => setState(() => market = _market());
  void retryBrief() => setState(() => brief = _brief());

  Widget benchmark(String label, IconData icon, dynamic raw) {
    final section = _map(raw);
    return Expanded(
      child: Container(
        constraints: const BoxConstraints(minHeight: 126),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
            color: Colors.white, borderRadius: BorderRadius.circular(20)),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Icon(icon, color: _teal, size: 20),
              const SizedBox(width: 7),
              Expanded(
                  child: Text(label,
                      style: const TextStyle(
                          color: _ink, fontWeight: FontWeight.w800))),
            ]),
            const SizedBox(height: 10),
            Text(_benchmarkValue(section),
                style: const TextStyle(
                    color: _ink, fontSize: 19, fontWeight: FontWeight.w800)),
            const Spacer(),
            Text(_freshness(section).isEmpty
                ? legacy.uiLabel(section['status'] ?? 'missing')
                : _freshness(section),
              style: const TextStyle(color: _muted, fontSize: 11),
              maxLines: 2,
              overflow: TextOverflow.ellipsis),
          ],
        ),
      ),
    );
  }

  Widget marketDetail(String title, IconData icon, dynamic raw,
      Map<String, String> labels) {
    final section = _map(raw);
    return _panel(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(icon, color: _teal, size: 21),
          const SizedBox(width: 9),
          Expanded(
              child: Text(title,
                  style: const TextStyle(
                      color: _ink, fontWeight: FontWeight.w800, fontSize: 16))),
          _statusPill(section['status'] ?? 'missing'),
        ]),
        const SizedBox(height: 10),
        Text(_facts(section, labels),
            style: const TextStyle(color: _ink, height: 1.45)),
        if (_freshness(section).isNotEmpty) ...[
          const SizedBox(height: 8),
          Text(_freshness(section),
              style: const TextStyle(color: _muted, fontSize: 11)),
        ],
      ]),
    );
  }

  @override
  Widget build(BuildContext context) => ColoredBox(
        color: _canvas,
        child: SafeArea(
          bottom: false,
          child: ListView(
            key: const Key('final-today-scroll'),
            padding: const EdgeInsets.fromLTRB(18, 18, 18, 110),
            children: [
              _pageTitle(context, '今日', subtitle: '市場基礎資料與研究內容分開載入'),
              FutureBuilder<dynamic>(
                future: market,
                builder: (context, snapshot) {
                  final root = _map(snapshot.data);
                  final sections = _map(root['sections']);
                  if (snapshot.connectionState != ConnectionState.done) {
                    return Column(children: [
                      Row(children: [
                        benchmark('加權指數', Icons.show_chart, const {}),
                        const SizedBox(width: 10),
                        benchmark('櫃買指數', Icons.stacked_line_chart, const {}),
                      ]),
                      _boundedState('市場基礎資料載入中'),
                    ]);
                  }
                  if (snapshot.data == null) {
                    return Column(children: [
                      Row(children: [
                        benchmark('加權指數', Icons.show_chart, const {}),
                        const SizedBox(width: 10),
                        benchmark('櫃買指數', Icons.stacked_line_chart, const {}),
                      ]),
                      _panel(
                        child: Row(children: [
                          const Expanded(child: Text('市場基礎資料暫時無法使用')),
                          TextButton(onPressed: retryMarket, child: const Text('重試')),
                        ]),
                      ),
                    ]);
                  }
                  return Column(children: [
                    Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                      benchmark('加權指數', Icons.show_chart, sections['taiex']),
                      const SizedBox(width: 10),
                      benchmark('櫃買指數', Icons.stacked_line_chart, sections['tpex']),
                    ]),
                    const SizedBox(height: 10),
                    marketDetail('市場活動', Icons.swap_vert_circle_outlined,
                        sections['market-activity'], const {
                      'day_trade_shares': '當沖股數',
                      'day_trade_buy_twd': '當沖買進',
                      'day_trade_sell_twd': '當沖賣出',
                    }),
                    marketDetail('法人動向', Icons.groups_2_outlined,
                        sections['institutional'], const {
                      'foreign': '外資',
                      'investment_trust': '投信',
                      'dealer': '自營商',
                    }),
                  ]);
                },
              ),
              FutureBuilder<dynamic>(
                future: brief,
                builder: (context, snapshot) {
                  final root = _map(snapshot.data);
                  final reports = _rows(root);
                  final report = reports.isNotEmpty ? _map(reports.first) : <String, dynamic>{};
                  final data = _map(report['data'].isNotEmpty == true ? report['data'] : report);
                  final highlights = _rows(data['highlights']);
                  final sectors = _rows(data['sector_rotation']);
                  final topics = _rows(data['topics'] ?? data['hot_topics']);
                  final candidates = _rows(data['candidates']);
                  final waiting = snapshot.connectionState != ConnectionState.done;
                  final unavailable = snapshot.data == null || reports.isEmpty;
                  final regime = data['market_regime'] ?? data['market_status'];
                  final summary = data['summary'];
                  return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                    _sectionTitle(context, '市場判讀',
                        trailing: _text(report['analysis_as_of'], missing: waiting ? '載入中' : '尚未就緒')),
                    if (waiting)
                      _boundedState('研究內容載入中；市場基礎資料可先使用')
                    else if (unavailable)
                      _panel(
                        child: Row(children: [
                          const Expanded(child: Text('研究內容尚未就緒')),
                          TextButton(onPressed: retryBrief, child: const Text('重試')),
                        ]),
                      )
                    else
                      _panel(
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Row(children: [
                            const Icon(Icons.radar_outlined, color: _teal),
                            const SizedBox(width: 9),
                            Expanded(child: Text(legacy.uiLabel(regime ?? 'available'),
                                style: const TextStyle(color: _ink, fontSize: 17, fontWeight: FontWeight.w800))),
                          ]),
                          if (summary != null) ...[
                            const SizedBox(height: 8),
                            Text('$summary', style: const TextStyle(color: _ink, height: 1.45)),
                          ],
                        ]),
                      ),
                    _sectionTitle(context, '今日三件事'),
                    if (highlights.isEmpty)
                      _boundedState(waiting ? '研究重點載入中' : '目前沒有可發布重點')
                    else
                      _panel(
                        child: Column(children: [
                          for (var i = 0; i < highlights.take(3).length; i++)
                            Padding(
                              padding: EdgeInsets.only(bottom: i == highlights.take(3).length - 1 ? 0 : 12),
                              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                CircleAvatar(radius: 13, backgroundColor: _soft,
                                    child: Text('${i + 1}', style: const TextStyle(color: _teal, fontSize: 12, fontWeight: FontWeight.w800))),
                                const SizedBox(width: 10),
                                Expanded(child: Text(
                                  _text(highlights[i] is Map
                                      ? (_map(highlights[i])['title'] ?? _map(highlights[i])['summary'])
                                      : highlights[i], missing: '重點'),
                                  style: const TextStyle(color: _ink, height: 1.4),
                                )),
                              ]),
                            ),
                        ]),
                      ),
                    _sectionTitle(context, '產業輪動／熱門話題'),
                    if (sectors.isEmpty && topics.isEmpty)
                      _boundedState(waiting ? '產業與話題載入中' : '目前沒有可發布內容')
                    else
                      _panel(
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          for (final row in sectors.take(3))
                            ListTile(
                              contentPadding: EdgeInsets.zero,
                              dense: true,
                              leading: const Icon(Icons.trending_up, color: _teal),
                              title: Text(_text(row is Map
                                  ? (_map(row)['industry'] ?? _map(row)['name'] ?? _map(row)['title'])
                                  : row)),
                              subtitle: row is Map && _map(row)['state'] != null
                                  ? Text(legacy.uiLabel(_map(row)['state']))
                                  : null,
                            ),
                          for (final row in topics.take(3))
                            ListTile(
                              contentPadding: EdgeInsets.zero,
                              dense: true,
                              leading: const Icon(Icons.tag_outlined, color: _teal),
                              title: Text(_text(row is Map
                                  ? (_map(row)['title'] ?? _map(row)['topic'] ?? _map(row)['summary'])
                                  : row)),
                            ),
                        ]),
                      ),
                    _sectionTitle(context, '候選股健康'),
                    if (candidates.isEmpty)
                      _boundedState(waiting ? '候選股資料載入中' : '目前沒有可發布候選股')
                    else
                      ...candidates.take(5).map((item) {
                        final row = _map(item);
                        final symbol = _text(row['stock_id'] ?? row['symbol']);
                        final score = row['mart_health_score'];
                        return _panel(
                          padding: EdgeInsets.zero,
                          child: ListTile(
                            onTap: symbol == '—' ? null : () => widget.onOpenStock?.call(symbol),
                            contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                            title: Text(_text(row['stock_name'] ?? row['name'], missing: symbol),
                                style: const TextStyle(color: _ink, fontWeight: FontWeight.w800)),
                            subtitle: Text('$symbol · ${_text(row['analysis_as_of'] ?? report['analysis_as_of'], missing: '資料日未定')}'),
                            trailing: Text(score == null ? legacy.uiLabel(row['data_status'] ?? 'partial') : '健康度 ${legacy.accountingNumber(score)}',
                                style: const TextStyle(color: _teal, fontWeight: FontWeight.w700)),
                          ),
                        );
                      }),
                    _sectionTitle(context, '全市場篩選'),
                    _boundedState(data['screening'] == null && data['market_screening'] == null
                        ? '全市場篩選結果尚未就緒'
                        : _text(data['screening'] ?? data['market_screening'])),
                  ]);
                },
              ),
              const Padding(
                padding: EdgeInsets.only(top: 12),
                child: Text('本服務提供研究資訊，不構成投資建議。',
                    style: TextStyle(color: _muted, fontSize: 12)),
              ),
            ],
          ),
        ),
      );
}

class FinalWatchlistPage extends StatefulWidget {
  const FinalWatchlistPage(this.api, {this.onOpenStock, super.key});
  final legacy.Api api;
  final ValueChanged<String>? onOpenStock;

  @override
  State<FinalWatchlistPage> createState() => _FinalWatchlistPageState();
}

class _FinalWatchlistPageState extends State<FinalWatchlistPage> {
  late Future<dynamic> data = widget.api.get('/api/v1/me/watchlist');

  void reload() => setState(() => data = widget.api.get('/api/v1/me/watchlist'));

  Future<void> add() async {
    final query = await legacy.textDialog(context, '搜尋關注股票', '股票代號或中文名稱');
    if (query == null || query.trim().isEmpty) return;
    try {
      final result = await widget.api.get(Uri(
        path: '/api/v1/me/watchlist/search',
        queryParameters: {'q': query.trim()},
      ).toString());
      if (!mounted) return;
      final matches = _rows(result);
      final symbol = await showDialog<String>(
        context: context,
        builder: (context) => SimpleDialog(
          title: const Text('選擇股票'),
          children: [
            if (matches.isEmpty)
              const Padding(padding: EdgeInsets.all(16), child: Text('沒有符合的股票')),
            for (final item in matches)
              SimpleDialogOption(
                onPressed: () => Navigator.pop(context, _text(_map(item)['symbol'])),
                child: Text(legacy.stockDisplayName(_map(item))),
              ),
          ],
        ),
      );
      if (symbol == null || !mounted) return;
      final target = await legacy.textDialog(context, '設定目標價', '可留空');
      await widget.api.post('/api/v1/me/watchlist', {
        'symbol': symbol,
        if (target?.trim().isNotEmpty == true) 'target_price': target!.trim(),
      });
      reload();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('目前無法加入關注')));
      }
    }
  }

  Future<void> reorder(List<dynamic> rows, int oldIndex, int newIndex) async {
    if (newIndex > oldIndex) newIndex -= 1;
    final reordered = List<dynamic>.from(rows);
    final moved = reordered.removeAt(oldIndex);
    reordered.insert(newIndex, moved);
    var version = 0;
    for (final item in rows) {
      final value = _int(_map(item)['version']);
      if (value > version) version = value;
    }
    if (version < 1) return;
    try {
      await widget.api.put('/api/v1/me/watchlist/order', {
        'symbols': [for (final item in reordered) _map(item)['symbol']],
        'expected_version': version,
      });
      reload();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('排序未更新，請重新整理')));
      }
    }
  }

  @override
  Widget build(BuildContext context) => ColoredBox(
    color: _canvas,
    child: SafeArea(
      bottom: false,
      child: FutureBuilder<dynamic>(
        future: data,
        builder: (context, snapshot) {
          final rows = _rows(snapshot.data);
          return ListView(
            key: const Key('final-watchlist-scroll'),
            padding: const EdgeInsets.fromLTRB(18, 18, 18, 110),
            children: [
              _pageTitle(context, '關注', subtitle: '我的關注清單與待追蹤事項'),
              _panel(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  FilledButton.icon(
                    onPressed: add,
                    icon: const Icon(Icons.search),
                    label: const Text('搜尋股票代號或中文名稱'),
                    style: FilledButton.styleFrom(backgroundColor: _teal),
                  ),
                  const SizedBox(height: 10),
                  Text('我的關注 ${rows.length}/50',
                      style: const TextStyle(color: _ink, fontWeight: FontWeight.w800)),
                  const SizedBox(height: 4),
                  const Text('新加入股票限目前有效市場約 500 檔；既有離榜股票仍保留關注。',
                      style: TextStyle(color: _muted, fontSize: 12)),
                ]),
              ),
              _sectionTitle(context, '我的關注', trailing: rows.isEmpty ? null : '長按拖曳排序'),
              if (snapshot.connectionState != ConnectionState.done)
                _boundedState('關注清單載入中')
              else if (snapshot.hasError)
                _panel(child: Row(children: [
                  const Expanded(child: Text('關注清單暫時無法使用')),
                  TextButton(onPressed: reload, child: const Text('重試')),
                ]))
              else if (rows.isEmpty)
                _boundedState('目前沒有關注股票')
              else
                ReorderableListView.builder(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  itemCount: rows.length,
                  onReorder: (oldIndex, newIndex) => reorder(rows, oldIndex, newIndex),
                  itemBuilder: (context, index) {
                    final row = _map(rows[index]);
                    final symbol = _text(row['symbol']);
                    final offUniverse = row['in_market_500'] == false;
                    final pending = _int(row['pending_note_count']);
                    return Card(
                      key: ValueKey('watch-$symbol'),
                      margin: const EdgeInsets.only(bottom: 10),
                      elevation: 0,
                      color: Colors.white,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                      child: InkWell(
                        borderRadius: BorderRadius.circular(20),
                        onTap: () => widget.onOpenStock?.call(symbol),
                        child: Padding(
                          padding: const EdgeInsets.fromLTRB(16, 14, 10, 14),
                          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            Row(children: [
                              Expanded(
                                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                  Text(legacy.stockDisplayName(row),
                                      style: const TextStyle(color: _ink, fontSize: 17, fontWeight: FontWeight.w800)),
                                  const SizedBox(height: 2),
                                  Text('資料日 ${_text(row['price_date'], missing: '尚未取得')}',
                                      style: const TextStyle(color: _muted, fontSize: 11)),
                                ]),
                              ),
                              IconButton(
                                tooltip: '移除關注',
                                onPressed: () async {
                                  try {
                                    await widget.api.delete('/api/v1/me/watchlist/${Uri.encodeComponent(symbol)}');
                                    reload();
                                  } catch (_) {
                                    if (mounted) {
                                      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('目前無法移除關注')));
                                    }
                                  }
                                },
                                icon: const Icon(Icons.close, color: _muted),
                              ),
                            ]),
                            const SizedBox(height: 8),
                            Row(children: [
                              Text(legacy.accountingNumber(row['market_price'], decimals: 2, missing: '行情尚未取得'),
                                  style: const TextStyle(color: _ink, fontSize: 22, fontWeight: FontWeight.w800)),
                              const Spacer(),
                              _statusPill(row['price_status'] ?? (row['market_price'] == null ? 'missing' : 'available')),
                            ]),
                            const SizedBox(height: 10),
                            Wrap(spacing: 7, runSpacing: 7, children: [
                              _tag(row['held'] == true ? '已持有' : '未持有'),
                              _tag(row['target_price'] == null
                                  ? '目標價未設定'
                                  : '目標 ${legacy.accountingNumber(row['target_price'], decimals: 2)}'),
                              if (pending > 0) _tag('待追蹤 $pending'),
                              if (offUniverse) _tag('已離開本週 500 · 仍保留關注', warning: true),
                            ]),
                          ]),
                        ),
                      ),
                    );
                  },
                ),
            ],
          );
        },
      ),
    ),
  );
}

Widget _tag(String text, {bool warning = false}) => Container(
  padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
  decoration: BoxDecoration(
    color: warning ? const Color(0xFFFFF2E2) : _soft,
    borderRadius: BorderRadius.circular(999),
  ),
  child: Text(text,
      style: TextStyle(color: warning ? const Color(0xFF9A5A10) : _teal,
          fontSize: 11, fontWeight: FontWeight.w700)),
);

class FinalLedgerPage extends StatefulWidget {
  const FinalLedgerPage(this.api, {this.onOpenStock, this.active = true, super.key});
  final legacy.Api api;
  final ValueChanged<String>? onOpenStock;
  final bool active;

  @override
  State<FinalLedgerPage> createState() => _FinalLedgerPageState();
}

class _FinalLedgerPageState extends State<FinalLedgerPage> {
  int section = 0;
  late Future<List<dynamic>> data = load();

  Future<dynamic> safe(String path) async {
    try {
      return await widget.api.get(path);
    } catch (_) {
      return null;
    }
  }

  Future<List<dynamic>> load() {
    final year = DateTime.now().year;
    return Future.wait([
      safe('/api/v1/me/portfolio/summary'),
      safe('/api/v1/me/journal/pnl?year=$year'),
      safe('/api/v1/me/journal/positions'),
      safe('/api/v1/me/journal/history?year=$year'),
      safe('/api/v1/me/journal/monthly-summary?year=$year'),
      safe('/api/v1/me/portfolio/performance?year=$year'),
      safe('/api/v1/me/notes'),
    ]);
  }

  void reload() => setState(() => data = load());

  Future<void> addTrade() async {
    final payload = await legacy.transactionDialog(context);
    if (payload == null) return;
    try {
      await widget.api.post('/api/v1/me/journal/events', payload);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text(legacy.portfolioPendingMessage)));
      reload();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('交易尚未儲存')));
      }
    }
  }

  Future<void> addNote() async {
    final body = await legacy.textDialog(context, '新增筆記', '筆記內容');
    if (body == null || body.trim().isEmpty) return;
    try {
      await widget.api.post('/api/v1/me/notes', {'body': body.trim()});
      reload();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('筆記尚未儲存')));
      }
    }
  }

  Widget holdings(List<dynamic> positions) {
    if (positions.isEmpty) return _boundedState('目前無持股或持股資料尚未取得');
    return Column(children: [
      for (final item in positions)
        Builder(builder: (context) {
          final row = _map(item);
          final symbol = _text(row['symbol']);
          final reason = legacy.portfolioMissingReasonLabel(row['missing_reason']);
          return _panel(
            padding: EdgeInsets.zero,
            child: InkWell(
              onTap: () => widget.onOpenStock?.call(symbol),
              borderRadius: BorderRadius.circular(20),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Expanded(
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text(legacy.stockDisplayName(row),
                            style: const TextStyle(color: _ink, fontSize: 17, fontWeight: FontWeight.w800)),
                        const SizedBox(height: 6),
                        Text('持有 ${legacy.accountingNumber(row['shares'])} 股',
                            style: const TextStyle(color: _ink)),
                        Text('現價 ${legacy.accountingNumber(row['market_price'], decimals: 2, missing: '缺價')} · 均價 ${legacy.accountingNumber(row['average_cost'], decimals: 2)}',
                            style: const TextStyle(color: _muted, fontSize: 12)),
                      ]),
                    ),
                    const SizedBox(width: 12),
                    Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
                      Text(legacy.accountingNumber(row['unrealized_pnl'], missing: '資料不足'),
                          style: const TextStyle(color: _ink, fontSize: 17, fontWeight: FontWeight.w800)),
                      Text(legacy.portfolioReturnLabel(row['unrealized_return']),
                          style: const TextStyle(color: _teal, fontWeight: FontWeight.w700)),
                    ]),
                  ]),
                  const SizedBox(height: 10),
                  Text('估值日 ${_text(row['valuation_date'])} · 行情日 ${_text(row['price_date'])} · ${row['price_status'] == null ? '狀態未知' : legacy.uiLabel(row['price_status'])}',
                      style: const TextStyle(color: _muted, fontSize: 11)),
                  if (reason.isNotEmpty) ...[
                    const SizedBox(height: 4),
                    Text(reason, style: const TextStyle(color: _muted, fontSize: 11)),
                  ],
                ]),
              ),
            ),
          );
        }),
    ]);
  }

  Widget records(List<dynamic> history, List<dynamic> monthly) {
    final effective = legacy.effectiveLedgerEvents(history);
    if (effective.isEmpty && monthly.isEmpty) return _boundedState('本年度尚無交易紀錄');
    final summaries = <int, Map<String, dynamic>>{};
    for (final item in monthly) {
      final row = _map(item);
      summaries[_int(row['month'])] = row;
    }
    final months = <int>{...summaries.keys};
    for (final item in effective) {
      final date = DateTime.tryParse(_text(_map(item)['trade_date'], missing: ''));
      if (date != null) months.add(date.month);
    }
    final ordered = months.toList()..sort((a, b) => b.compareTo(a));
    return Column(children: [
      for (final month in ordered)
        _panel(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('${DateTime.now().year} 年 $month 月',
                style: const TextStyle(color: _ink, fontSize: 16, fontWeight: FontWeight.w800)),
            if (summaries[month] != null) ...[
              const SizedBox(height: 10),
              Wrap(spacing: 12, runSpacing: 6, children: [
                Text('買進支出 ${legacy.accountingNumber(summaries[month]!['purchase_outflow'])}'),
                Text('賣出回收 ${legacy.accountingNumber(summaries[month]!['sale_proceeds'])}'),
                Text('股利收入 ${legacy.accountingNumber(summaries[month]!['cash_dividends'])}'),
                Text('已實現損益 ${legacy.accountingNumber(summaries[month]!['realized_pnl'])}'),
              ]),
              const SizedBox(height: 6),
              Text('資料日期 ${_text(summaries[month]!['valuation_date'])}',
                  style: const TextStyle(color: _muted, fontSize: 11)),
            ],
            const Divider(height: 22),
            for (final item in effective.where((item) {
              final row = _map(item);
              final date = DateTime.tryParse(_text(row['trade_date'], missing: ''));
              return date?.month == month;
            }))
              Builder(builder: (context) {
                final row = _map(item);
                return ListTile(
                  contentPadding: EdgeInsets.zero,
                  dense: true,
                  title: Text('${legacy.uiLabel(row['event_type'])} · ${legacy.stockDisplayName(row)}'),
                  subtitle: Text('${_text(row['trade_date'])} · 淨現金流 ${legacy.accountingNumber(row['net_cash_flow'], missing: '資料不足')} ${_text(row['currency'], missing: '')}'),
                );
              }),
          ]),
        ),
    ]);
  }

  Widget reports(List<dynamic> pnl, List<dynamic> performance) {
    if (pnl.isEmpty && performance.isEmpty) {
      return _boundedState('報表聚合尚未就緒或仍待 Private Mart 更新');
    }
    return Column(children: [
      for (final item in pnl)
        Builder(builder: (context) {
          final row = _map(item);
          return _panel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('${_text(row['currency'], missing: 'TWD')} · 本年損益',
                style: const TextStyle(color: _ink, fontWeight: FontWeight.w800)),
            const SizedBox(height: 8),
            Text('已實現損益 ${legacy.accountingNumber(row['realized_pnl'])}'),
            Text('股利收入 ${legacy.accountingNumber(row['cash_dividends'])}'),
            Text('手續費 ${legacy.accountingNumber(row['fees'])} · 稅 ${legacy.accountingNumber(row['taxes'])}'),
            const SizedBox(height: 6),
            Text('資料日期 ${_text(row['valuation_date'])}',
                style: const TextStyle(color: _muted, fontSize: 11)),
          ]));
        }),
      for (final item in performance)
        Builder(builder: (context) {
          final row = _map(item);
          final status = row['xirr_status'];
          return _panel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('年度績效', style: TextStyle(color: _ink, fontWeight: FontWeight.w800)),
            const SizedBox(height: 8),
            Text(status == 'available' && row['xirr'] != null
                ? 'XIRR ${legacy.portfolioReturnLabel(row['xirr'])}'
                : 'XIRR ${legacy.uiLabel(status ?? 'insufficient_data')}'),
            Text('資料日期 ${_text(row['valuation_date'])}',
                style: const TextStyle(color: _muted, fontSize: 11)),
          ]));
        }),
    ]);
  }

  Widget notes(List<dynamic> values) => Column(children: [
    Align(
      alignment: Alignment.centerRight,
      child: TextButton.icon(onPressed: addNote, icon: const Icon(Icons.add), label: const Text('新增筆記')),
    ),
    if (values.isEmpty) _boundedState('目前沒有筆記'),
    for (final item in values)
      Builder(builder: (context) {
        final row = _map(item);
        return _panel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(_text(row['body'] ?? row['text'] ?? row['content'], missing: '筆記內容不可用'),
              style: const TextStyle(color: _ink, height: 1.45)),
          if (row['symbol'] != null || row['needs_follow_up'] == true) ...[
            const SizedBox(height: 8),
            Wrap(spacing: 7, runSpacing: 7, children: [
              if (row['symbol'] != null) _tag('${row['symbol']}'),
              if (row['needs_follow_up'] == true) _tag('待追蹤'),
            ]),
          ],
        ]));
      }),
  ]);

  @override
  Widget build(BuildContext context) => ColoredBox(
    color: _canvas,
    child: SafeArea(
      bottom: false,
      child: FutureBuilder<List<dynamic>>(
        future: data,
        builder: (context, snapshot) {
          final values = snapshot.data ?? const [null, null, null, null, null, null, null];
          final summary = _rows(values[0]);
          final pnl = _rows(values[1]);
          final positions = _rows(values[2]);
          final history = _rows(values[3]);
          final monthly = _rows(values[4]);
          final performance = _rows(values[5]);
          final noteRows = _rows(values[6]);
          final aggregate = summary.isNotEmpty ? _map(summary.first) : <String, dynamic>{};
          final withheld = aggregate['aggregate_status'] == 'withheld';
          final currency = _text(aggregate['currency'], missing: 'TWD');
          final marketValue = withheld
              ? '總額暫不發布'
              : aggregate.isEmpty
                  ? '資料不足'
                  : '$currency ${legacy.accountingNumber(aggregate['market_value'], missing: '資料不足')}';
          final unrealized = withheld
              ? '總額暫不發布'
              : aggregate.isEmpty
                  ? '資料不足'
                  : '$currency ${legacy.accountingNumber(aggregate['unrealized_pnl'], missing: '資料不足')}';
          final unrealizedReturn = withheld
              ? '總額暫不發布'
              : aggregate.isEmpty
                  ? '資料不足'
                  : legacy.portfolioReturnLabel(aggregate['unrealized_return']);
          final ytd = pnl.isEmpty
              ? '待更新／尚未確認'
              : pnl.length == 1
                  ? '${_text(_map(pnl.first)['currency'], missing: 'TWD')} ${legacy.accountingNumber(_map(pnl.first)['realized_pnl'])}'
                  : '多幣別';
          final affected = _rows(aggregate['affected_symbols']);
          return ListView(
            key: const Key('final-ledger-scroll'),
            padding: const EdgeInsets.fromLTRB(18, 18, 18, 110),
            children: [
              Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Expanded(child: _pageTitle(context, '記帳／筆記', subtitle: '持股、交易與正式報表使用同一資料語意')),
                IconButton(onPressed: reload, tooltip: '重新整理', icon: const Icon(Icons.refresh, color: _teal)),
              ]),
              GridView.count(
                crossAxisCount: 2,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                mainAxisSpacing: 10,
                crossAxisSpacing: 10,
                childAspectRatio: 1.45,
                children: [
                  _metricTile('持股市值', marketValue,
                      detail: '估值日 ${_text(aggregate['valuation_date'])}'),
                  _metricTile('未實現損益', unrealized,
                      detail: '報酬 $unrealizedReturn'),
                  _metricTile('本年已實現損益', ytd,
                      detail: pnl.isEmpty ? 'Private Mart 尚未確認時不補 0' : 'canonical aggregate'),
                  _metricTile('估值狀態',
                      withheld ? '暫不發布' : legacy.uiLabel(aggregate['valuation_status'] ?? (aggregate.isEmpty ? 'partial' : 'available')),
                      detail: 'ledger v${_text(aggregate['ledger_version'], missing: '—')}'),
                ],
              ),
              if (withheld)
                _boundedState('正式總額暫不發布${affected.isEmpty ? '' : ' · 受影響 ${affected.join('、')}'}；持股 operational shares／cost 仍可顯示。'),
              const SizedBox(height: 12),
              SegmentedButton<int>(
                segments: const [
                  ButtonSegment(value: 0, label: Text('持股')),
                  ButtonSegment(value: 1, label: Text('紀錄')),
                  ButtonSegment(value: 2, label: Text('報表')),
                  ButtonSegment(value: 3, label: Text('筆記')),
                ],
                selected: {section},
                onSelectionChanged: (value) => setState(() => section = value.first),
                showSelectedIcon: false,
              ),
              const SizedBox(height: 12),
              if (snapshot.connectionState != ConnectionState.done)
                _boundedState('Ledger 資料載入中')
              else ...[
                if (section == 0) ...[
                  Row(children: [
                    Expanded(child: _sectionTitle(context, '持股')),
                    FilledButton.icon(
                      onPressed: addTrade,
                      icon: const Icon(Icons.add, size: 18),
                      label: const Text('新增交易'),
                      style: FilledButton.styleFrom(backgroundColor: _teal),
                    ),
                  ]),
                  holdings(positions),
                ],
                if (section == 1) ...[
                  _sectionTitle(context, '紀錄', trailing: '${DateTime.now().year} 年'),
                  records(history, monthly),
                ],
                if (section == 2) ...[
                  _sectionTitle(context, '報表'),
                  reports(pnl, performance),
                ],
                if (section == 3) ...[
                  _sectionTitle(context, '筆記'),
                  notes(noteRows),
                ],
              ],
            ],
          );
        },
      ),
    ),
  );
}

class FinalStockDetailPage extends StatefulWidget {
  const FinalStockDetailPage({required this.api, required this.symbol, super.key});
  final legacy.Api api;
  final String symbol;

  @override
  State<FinalStockDetailPage> createState() => _FinalStockDetailPageState();
}

class _FinalStockDetailPageState extends State<FinalStockDetailPage> {
  final values = <String, dynamic>{};
  final errors = <String>{};
  bool loading = true;
  bool klineLoading = false;
  bool klineRequested = false;

  Future<dynamic> safe(String key, String path) async {
    try {
      final value = await widget.api.get(path);
      values[key] = value;
      errors.remove(key);
      return value;
    } catch (_) {
      errors.add(key);
      return null;
    }
  }

  @override
  void initState() {
    super.initState();
    loadPrimary();
  }

  Future<void> loadPrimary() async {
    setState(() => loading = true);
    await Future.wait([
      safe('health', '/api/v1/public/stock-health/${Uri.encodeComponent(widget.symbol)}'),
      safe('positions', '/api/v1/me/journal/positions'),
      safe('notes', '/api/v1/me/notes?symbol=${Uri.encodeQueryComponent(widget.symbol)}'),
      safe('events', '/api/v1/public/events/${Uri.encodeComponent(widget.symbol)}'),
    ]);
    if (mounted) setState(() => loading = false);
  }

  Future<void> loadKline() async {
    if (klineRequested) return;
    setState(() {
      klineRequested = true;
      klineLoading = true;
    });
    await safe('kline', '/api/v1/public/kline/${Uri.encodeComponent(widget.symbol)}');
    if (mounted) setState(() => klineLoading = false);
  }

  List<dynamic> get positions => _rows(values['positions']).where((item) =>
      _text(_map(item)['symbol'], missing: '') == widget.symbol).toList();

  @override
  Widget build(BuildContext context) {
    final report = _map(values['health']);
    final health = _map(report['data'].isNotEmpty == true ? report['data'] : report);
    final name = _text(health['stock_name'] ?? health['name'], missing: widget.symbol);
    final notes = _rows(values['notes']);
    final events = _rows(values['events']);
    final position = positions.isNotEmpty ? _map(positions.first) : <String, dynamic>{};
    final summary = health['plain_language_summary'] ?? health['summary'];
    final supports = _rows(health['supports'] ?? health['why'] ?? health['reasons']);
    final risks = _rows(health['risks'] ?? health['watchouts'] ?? health['warnings']);
    final dimensions = _map(health['dimensions'] ?? health['role_scores'] ?? health['scores']);
    final chips = health['chips'] ?? health['institutional'] ?? health['positioning'];
    final evidence = _map(report['provenance'] ?? health['provenance'] ?? health['sources']);
    return Scaffold(
      backgroundColor: _canvas,
      appBar: AppBar(
        backgroundColor: _canvas,
        surfaceTintColor: _canvas,
        elevation: 0,
        foregroundColor: _ink,
        title: Text('$widget.symbol $name', style: const TextStyle(fontWeight: FontWeight.w800)),
      ),
      body: RefreshIndicator(
        onRefresh: loadPrimary,
        child: ListView(
          key: const Key('final-stock-detail-scroll'),
          padding: const EdgeInsets.fromLTRB(18, 8, 18, 40),
          children: [
            _panel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Expanded(child: Text(name,
                    style: const TextStyle(color: _ink, fontSize: 25, fontWeight: FontWeight.w800))),
                _statusPill(report['data_status'] ?? health['data_status'] ?? (loading ? 'partial' : 'available')),
              ]),
              const SizedBox(height: 3),
              Text(widget.symbol, style: const TextStyle(color: _muted)),
              if (report['analysis_as_of'] != null || health['analysis_as_of'] != null) ...[
                const SizedBox(height: 8),
                Text('資料日 ${_text(report['analysis_as_of'] ?? health['analysis_as_of'])}',
                    style: const TextStyle(color: _muted, fontSize: 11)),
              ],
            ])),
            _sectionTitle(context, '我的持股'),
            if (errors.contains('positions'))
              _boundedState('持股資料尚未取得')
            else if (position.isEmpty)
              _boundedState('目前無持股')
            else
              _panel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('持有 ${legacy.accountingNumber(position['shares'])} 股',
                    style: const TextStyle(color: _ink, fontSize: 18, fontWeight: FontWeight.w800)),
                const SizedBox(height: 7),
                Text('平均成本 ${legacy.accountingNumber(position['average_cost'], decimals: 2)} · 現價 ${legacy.accountingNumber(position['market_price'], decimals: 2, missing: '缺價')}',
                    style: const TextStyle(color: _ink)),
                Text('未實現損益 ${legacy.accountingNumber(position['unrealized_pnl'], missing: '資料不足')} · ${legacy.portfolioReturnLabel(position['unrealized_return'])}',
                    style: const TextStyle(color: _ink)),
                const SizedBox(height: 7),
                Text('估值日 ${_text(position['valuation_date'])} · 行情日 ${_text(position['price_date'])}',
                    style: const TextStyle(color: _muted, fontSize: 11)),
              ])),
            _sectionTitle(context, '筆記與待追蹤'),
            if (errors.contains('notes'))
              _boundedState('筆記資料尚未取得')
            else if (notes.isEmpty)
              _boundedState('目前沒有這檔股票的筆記')
            else
              _panel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                for (final item in notes.take(3))
                  Padding(
                    padding: const EdgeInsets.only(bottom: 9),
                    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Icon(_map(item)['needs_follow_up'] == true ? Icons.flag_outlined : Icons.notes_outlined,
                          color: _teal, size: 19),
                      const SizedBox(width: 9),
                      Expanded(child: Text(_text(_map(item)['body'] ?? _map(item)['text'] ?? _map(item)['content'], missing: '筆記內容不可用'),
                          style: const TextStyle(color: _ink, height: 1.4))),
                    ]),
                  ),
              ])),
            _sectionTitle(context, '五面向健康度'),
            if (dimensions.isEmpty && health['mart_health_score'] == null)
              _boundedState('五面向健康度尚未就緒')
            else
              _panel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                if (health['mart_health_score'] != null)
                  Text('整體健康度 ${legacy.accountingNumber(health['mart_health_score'])}',
                      style: const TextStyle(color: _ink, fontSize: 18, fontWeight: FontWeight.w800)),
                for (final entry in dimensions.entries)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Row(children: [
                      Expanded(child: Text(legacy.uiLabel(entry.key), style: const TextStyle(color: _ink))),
                      Text(_text(entry.value), style: const TextStyle(color: _teal, fontWeight: FontWeight.w700)),
                    ]),
                  ),
              ])),
            _sectionTitle(context, '白話摘要'),
            summary == null
                ? _boundedState('白話摘要尚未就緒；不會在開頁時自動呼叫 LLM')
                : _panel(child: Text('$summary', style: const TextStyle(color: _ink, height: 1.55))),
            _sectionTitle(context, '為什麼／要注意什麼'),
            Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Expanded(child: _reasonColumn('支持', supports, Icons.check_circle_outline)),
              const SizedBox(width: 10),
              Expanded(child: _reasonColumn('風險', risks, Icons.warning_amber_outlined)),
            ]),
            _sectionTitle(context, '籌碼與定位'),
            chips == null
                ? _boundedState('籌碼與定位資料尚未就緒')
                : _panel(child: Text(_text(chips), style: const TextStyle(color: _ink, height: 1.45))),
            _sectionTitle(context, '公司事件'),
            if (errors.contains('events'))
              _boundedState('公司事件暫時無法使用')
            else if (events.isEmpty)
              _boundedState('目前沒有可發布事件')
            else
              _panel(child: Column(children: [
                for (final item in events.take(6))
                  Builder(builder: (context) {
                    final row = _map(item);
                    return ListTile(
                      contentPadding: EdgeInsets.zero,
                      dense: true,
                      leading: const Icon(Icons.event_outlined, color: _teal),
                      title: Text(_text(row['title'] ?? row['event_type'] ?? row['summary'], missing: '事件')),
                      subtitle: Text(_text(row['event_date'] ?? row['date'] ?? row['published_at'], missing: '日期未定')),
                    );
                  }),
              ])),
            ExpansionTile(
              tilePadding: const EdgeInsets.symmetric(horizontal: 4),
              title: const Text('證據與來源', style: TextStyle(color: _ink, fontWeight: FontWeight.w800)),
              children: [
                if (evidence.isEmpty)
                  _boundedState('證據與來源尚未就緒')
                else
                  _panel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    for (final entry in evidence.entries)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 6),
                        child: Text('${entry.key}：${_text(entry.value)}',
                            style: const TextStyle(color: _muted, fontSize: 12)),
                      ),
                  ])),
              ],
            ),
            ExpansionTile(
              key: const Key('advanced-section'),
              tilePadding: const EdgeInsets.symmetric(horizontal: 4),
              onExpansionChanged: (expanded) {
                if (expanded) loadKline();
              },
              title: const Text('進階資料', style: TextStyle(color: _ink, fontWeight: FontWeight.w800)),
              subtitle: const Text('K 線、Fact Pack、specialist、CEO 與完整 provenance 依能力載入'),
              children: [
                if (klineLoading)
                  _boundedState('K 線載入中')
                else if (klineRequested && errors.contains('kline'))
                  _boundedState('K 線暫時無法使用')
                else if (klineRequested && _rows(values['kline']).isEmpty)
                  _boundedState('K 線資料尚未就緒')
                else if (klineRequested)
                  _panel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    const Text('K 線／OHLCV', style: TextStyle(color: _ink, fontWeight: FontWeight.w800)),
                    for (final item in _rows(values['kline']).take(5))
                      Builder(builder: (context) {
                        final row = _map(item);
                        return ListTile(
                          dense: true,
                          contentPadding: EdgeInsets.zero,
                          title: Text(_text(row['trade_date'] ?? row['date'])),
                          subtitle: Text('O ${_text(row['open'])} · H ${_text(row['high'])} · L ${_text(row['low'])} · C ${_text(row['close'])}'),
                        );
                      }),
                  ])),
                _boundedState('Fact Pack、五 specialist 與 On-demand CEO 僅在 persisted artifact 可用時顯示。'),
              ],
            ),
            const SizedBox(height: 14),
            const Text('本頁提供研究資訊，不構成投資建議。資料可能為 partial、stale 或 unavailable，請以標示的資料日期與來源為準。',
                style: TextStyle(color: _muted, fontSize: 12, height: 1.45)),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }
}

Widget _reasonColumn(String title, List<dynamic> values, IconData icon) =>
    _panel(
      padding: const EdgeInsets.all(13),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(icon, size: 18, color: _teal),
          const SizedBox(width: 6),
          Text(title, style: const TextStyle(color: _ink, fontWeight: FontWeight.w800)),
        ]),
        const SizedBox(height: 9),
        if (values.isEmpty)
          const Text('尚未就緒', style: TextStyle(color: _muted, fontSize: 12))
        else
          for (final item in values.take(3))
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Text('• ${_text(item is Map ? (_map(item)['title'] ?? _map(item)['summary'] ?? _map(item)['reason']) : item)}',
                  style: const TextStyle(color: _ink, fontSize: 12, height: 1.35)),
            ),
      ]),
    );
