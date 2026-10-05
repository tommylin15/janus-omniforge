import 'package:flutter/material.dart';

import 'final_visual_common.dart';
import 'main.dart' as legacy;

class FinalTodayPage extends StatefulWidget {
  const FinalTodayPage(this.api, {this.onOpenStock, super.key});

  final legacy.Api api;
  final ValueChanged<String>? onOpenStock;

  @override
  State<FinalTodayPage> createState() => _FinalTodayPageState();
}

class _FinalTodayPageState extends State<FinalTodayPage> {
  late Future<dynamic> market = _read('/api/v1/public/market-home');
  late Future<dynamic> brief = _read('/api/v1/public/daily-brief');

  Future<dynamic> _read(String path) async {
    try {
      return await widget.api.get(path);
    } catch (_) {
      return null;
    }
  }

  String _freshness(Map<String, dynamic> section) {
    final coverage = fvMap(section['coverage']);
    final parts = <String>[];
    if (section['as_of'] != null) parts.add('資料日 ${section['as_of']}');
    if (section['freshness_days'] != null) {
      final days = fvInt(section['freshness_days']);
      parts.add(days == 0 ? '最新交易日' : '$days 天前');
    }
    if (coverage['received_symbols'] != null && coverage['requested_symbols'] != null) {
      parts.add('涵蓋 ${coverage['received_symbols']}/${coverage['requested_symbols']} 檔');
    }
    return parts.join(' · ');
  }

  String _value(Map<String, dynamic> section) {
    final data = fvMap(section['data']);
    final value = data['close'] ?? data['index'] ?? data['value'];
    return value == null ? '資料尚未取得' : legacy.accountingNumber(value, decimals: 2);
  }

  Widget _benchmark(String label, IconData icon, dynamic raw) {
    final section = fvMap(raw);
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Icon(icon, color: fvTeal, size: 19),
              const SizedBox(width: 7),
              Expanded(
                child: Text(label,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(color: fvInk, fontWeight: FontWeight.w800)),
              ),
            ]),
            const SizedBox(height: 9),
            Text(_value(section),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(color: fvInk, fontSize: 18, fontWeight: FontWeight.w800)),
            const SizedBox(height: 7),
            Text(
              _freshness(section).isEmpty
                  ? legacy.uiLabel(section['status'] ?? 'partial')
                  : _freshness(section),
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(color: fvMuted, fontSize: 10.5, height: 1.25),
            ),
          ],
        ),
      ),
    );
  }

  String _facts(Map<String, dynamic> section, Map<String, String> labels) {
    final data = fvMap(section['data']);
    final values = <String>[];
    for (final entry in labels.entries) {
      if (data[entry.key] != null) {
        values.add('${entry.value} ${legacy.accountingNumber(data[entry.key])}');
      }
    }
    return values.isEmpty ? '目前沒有可顯示資料' : values.join(' · ');
  }

  Widget _marketCard(String title, IconData icon, dynamic raw, Map<String, String> labels) {
    final section = fvMap(raw);
    return fvPanel(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(icon, color: fvTeal, size: 20),
          const SizedBox(width: 8),
          Expanded(child: Text(title,
              style: const TextStyle(color: fvInk, fontWeight: FontWeight.w800, fontSize: 16))),
          fvStatusPill(section['status'] ?? 'partial'),
        ]),
        const SizedBox(height: 9),
        Text(_facts(section, labels), style: const TextStyle(color: fvInk, height: 1.4)),
        if (_freshness(section).isNotEmpty) ...[
          const SizedBox(height: 7),
          Text(_freshness(section), style: const TextStyle(color: fvMuted, fontSize: 11)),
        ],
      ]),
    );
  }

  Widget _market() => FutureBuilder<dynamic>(
    future: market,
    builder: (context, snapshot) {
      final root = fvMap(snapshot.data);
      final sections = fvMap(root['sections']);
      return Column(children: [
        IntrinsicHeight(
          child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            _benchmark('加權指數', Icons.show_chart, sections['taiex']),
            const SizedBox(width: 10),
            _benchmark('櫃買指數', Icons.stacked_line_chart, sections['tpex']),
          ]),
        ),
        const SizedBox(height: 10),
        if (snapshot.connectionState != ConnectionState.done)
          fvBoundedState('市場基礎資料載入中')
        else if (snapshot.data == null)
          fvPanel(child: Row(children: [
            const Expanded(child: Text('市場基礎資料暫時無法使用')),
            TextButton(
              onPressed: () => setState(() => market = _read('/api/v1/public/market-home')),
              child: const Text('重試'),
            ),
          ]))
        else ...[
          _marketCard('市場活動', Icons.swap_vert_circle_outlined, sections['market-activity'], const {
            'day_trade_shares': '當沖股數',
            'day_trade_buy_twd': '當沖買進',
            'day_trade_sell_twd': '當沖賣出',
          }),
          _marketCard('法人動向', Icons.groups_2_outlined, sections['institutional'], const {
            'foreign': '外資',
            'investment_trust': '投信',
            'dealer': '自營商',
          }),
        ],
      ]);
    },
  );

  Widget _brief() => FutureBuilder<dynamic>(
    future: brief,
    builder: (context, snapshot) {
      final reports = fvRows(fvMap(snapshot.data));
      final report = reports.isEmpty ? <String, dynamic>{} : fvMap(reports.first);
      final nested = fvMap(report['data']);
      final data = nested.isEmpty ? report : nested;
      final highlights = fvRows(data['highlights']);
      final sectors = fvRows(data['sector_rotation']);
      final topics = fvRows(data['topics'] ?? data['hot_topics']);
      final candidates = fvRows(data['candidates']);
      final loading = snapshot.connectionState != ConnectionState.done;
      final unavailable = !loading && (snapshot.data == null || reports.isEmpty);

      return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        fvSectionTitle(context, '市場判讀',
            trailing: loading ? '載入中' : fvText(report['analysis_as_of'], missing: '尚未就緒')),
        if (loading)
          fvBoundedState('研究內容載入中；市場基礎資料可先使用')
        else if (unavailable)
          fvPanel(child: Row(children: [
            const Expanded(child: Text('研究內容尚未就緒')),
            TextButton(
              onPressed: () => setState(() => brief = _read('/api/v1/public/daily-brief')),
              child: const Text('重試'),
            ),
          ]))
        else
          fvPanel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              const Icon(Icons.radar_outlined, color: fvTeal),
              const SizedBox(width: 8),
              Expanded(child: Text(legacy.uiLabel(data['market_regime'] ?? data['market_status'] ?? 'available'),
                  style: const TextStyle(color: fvInk, fontSize: 17, fontWeight: FontWeight.w800))),
            ]),
            if (data['summary'] != null) ...[
              const SizedBox(height: 8),
              Text('${data['summary']}', style: const TextStyle(color: fvInk, height: 1.45)),
            ],
          ])),
        fvSectionTitle(context, '今日三件事'),
        if (highlights.isEmpty)
          fvBoundedState(loading ? '研究重點載入中' : '目前沒有可發布重點')
        else
          fvPanel(child: Column(children: [
            for (var i = 0; i < highlights.take(3).length; i++)
              Padding(
                padding: EdgeInsets.only(bottom: i == highlights.take(3).length - 1 ? 0 : 10),
                child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  CircleAvatar(radius: 12, backgroundColor: fvSoft,
                      child: Text('${i + 1}', style: const TextStyle(color: fvTeal, fontSize: 11, fontWeight: FontWeight.w800))),
                  const SizedBox(width: 9),
                  Expanded(child: Text(fvText(highlights[i] is Map
                      ? (fvMap(highlights[i])['title'] ?? fvMap(highlights[i])['summary'])
                      : highlights[i], missing: '重點'),
                      style: const TextStyle(color: fvInk, height: 1.4))),
                ]),
              ),
          ])),
        fvSectionTitle(context, '產業輪動／熱門話題'),
        if (sectors.isEmpty && topics.isEmpty)
          fvBoundedState(loading ? '產業與話題載入中' : '目前沒有可發布內容')
        else
          fvPanel(child: Column(children: [
            for (final item in sectors.take(3))
              ListTile(contentPadding: EdgeInsets.zero, dense: true,
                leading: const Icon(Icons.trending_up, color: fvTeal),
                title: Text(fvText(item is Map
                    ? (fvMap(item)['industry'] ?? fvMap(item)['name'] ?? fvMap(item)['title'])
                    : item))),
            for (final item in topics.take(3))
              ListTile(contentPadding: EdgeInsets.zero, dense: true,
                leading: const Icon(Icons.tag_outlined, color: fvTeal),
                title: Text(fvText(item is Map
                    ? (fvMap(item)['title'] ?? fvMap(item)['topic'] ?? fvMap(item)['summary'])
                    : item))),
          ])),
        fvSectionTitle(context, '候選股健康'),
        if (candidates.isEmpty)
          fvBoundedState(loading ? '候選股資料載入中' : '目前沒有可發布候選股')
        else
          ...candidates.take(5).map((item) {
            final row = fvMap(item);
            final symbol = fvText(row['stock_id'] ?? row['symbol']);
            return fvPanel(padding: EdgeInsets.zero, child: ListTile(
              onTap: symbol == '—' ? null : () => widget.onOpenStock?.call(symbol),
              contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 5),
              title: Text(fvText(row['stock_name'] ?? row['name'], missing: symbol),
                  style: const TextStyle(color: fvInk, fontWeight: FontWeight.w800)),
              subtitle: Text('$symbol · ${fvText(row['analysis_as_of'] ?? report['analysis_as_of'], missing: '資料日未定')}'),
              trailing: Text(row['mart_health_score'] == null
                  ? legacy.uiLabel(row['data_status'] ?? 'partial')
                  : '健康度 ${legacy.accountingNumber(row['mart_health_score'])}',
                  style: const TextStyle(color: fvTeal, fontWeight: FontWeight.w700)),
            ));
          }),
        fvSectionTitle(context, '全市場篩選'),
        fvBoundedState(data['screening'] == null && data['market_screening'] == null
            ? '全市場篩選結果尚未就緒'
            : fvText(data['screening'] ?? data['market_screening'])),
      ]);
    },
  );

  @override
  Widget build(BuildContext context) => ColoredBox(
    color: fvCanvas,
    child: SafeArea(
      bottom: false,
      child: ListView(
        key: const Key('final-today-scroll'),
        padding: const EdgeInsets.fromLTRB(18, 18, 18, 110),
        children: [
          fvPageTitle(context, '今日', subtitle: '市場基礎資料與研究內容分開載入'),
          _market(),
          _brief(),
          const Padding(
            padding: EdgeInsets.only(top: 12),
            child: Text('本服務提供研究資訊，不構成投資建議。',
                style: TextStyle(color: fvMuted, fontSize: 12)),
          ),
        ],
      ),
    ),
  );
}
