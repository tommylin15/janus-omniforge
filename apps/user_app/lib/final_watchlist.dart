import 'package:flutter/material.dart';

import 'final_visual_common.dart';
import 'main.dart' as legacy;

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
    final query =
        await legacy.textDialog(context, '搜尋關注股票', '股票代號或中文名稱');
    if (query == null || query.trim().isEmpty) return;
    try {
      final result = await widget.api.get(Uri(
        path: '/api/v1/me/watchlist/search',
        queryParameters: {'q': query.trim()},
      ).toString());
      if (!mounted) return;
      final matches = fvRows(result);
      final symbol = await showDialog<String>(
        context: context,
        builder: (context) => SimpleDialog(
          title: const Text('選擇股票'),
          children: [
            if (matches.isEmpty)
              const Padding(
                padding: EdgeInsets.all(16),
                child: Text('沒有符合的股票'),
              ),
            for (final item in matches)
              SimpleDialogOption(
                onPressed: () =>
                    Navigator.pop(context, fvText(fvMap(item)['symbol'])),
                child: Text(legacy.stockDisplayName(fvMap(item))),
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
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('目前無法加入關注')),
        );
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
      final value = fvInt(fvMap(item)['version']);
      if (value > version) version = value;
    }
    if (version < 1) return;
    try {
      await widget.api.put('/api/v1/me/watchlist/order', {
        'symbols': [for (final item in reordered) fvMap(item)['symbol']],
        'expected_version': version,
      });
      reload();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('排序未更新，請重新整理')),
        );
      }
    }
  }

  Widget header(BuildContext context, int count) => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          fvPageTitle(context, '關注', subtitle: '我的關注清單與待追蹤事項'),
          fvPanel(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                FilledButton.icon(
                  onPressed: add,
                  icon: const Icon(Icons.search),
                  label: const Text('搜尋股票代號或中文名稱'),
                  style: FilledButton.styleFrom(backgroundColor: fvTeal),
                ),
                const SizedBox(height: 10),
                Text(
                  '我的關注 $count/50',
                  style: const TextStyle(
                    color: fvInk,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 4),
                const Text(
                  '新加入股票限目前有效市場約 500 檔；既有離榜股票仍保留關注。',
                  style: TextStyle(color: fvMuted, fontSize: 12),
                ),
              ],
            ),
          ),
          fvSectionTitle(
            context,
            '我的關注',
            trailing: count == 0 ? null : '長按拖曳排序',
          ),
        ],
      );

  Widget card(Map<String, dynamic> row) {
    final symbol = fvText(row['symbol']);
    final offUniverse = row['in_market_500'] == false;
    final pending = fvInt(row['pending_note_count']);
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
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          legacy.stockDisplayName(row),
                          style: const TextStyle(
                            color: fvInk,
                            fontSize: 17,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          '資料日 ${fvText(row['price_date'], missing: '尚未取得')}',
                          style: const TextStyle(color: fvMuted, fontSize: 11),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    tooltip: '移除關注',
                    onPressed: () async {
                      try {
                        await widget.api.delete(
                          '/api/v1/me/watchlist/${Uri.encodeComponent(symbol)}',
                        );
                        reload();
                      } catch (_) {
                        if (mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('目前無法移除關注')),
                          );
                        }
                      }
                    },
                    icon: const Icon(Icons.close, color: fvMuted),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(
                    child: Text(
                      legacy.accountingNumber(
                        row['market_price'],
                        decimals: 2,
                        missing: '行情尚未取得',
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: fvInk,
                        fontSize: 22,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  fvStatusPill(
                    row['price_status'] ??
                        (row['market_price'] == null ? 'partial' : 'available'),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              Wrap(
                spacing: 7,
                runSpacing: 7,
                children: [
                  fvTag(row['held'] == true ? '已持有' : '未持有'),
                  fvTag(row['target_price'] == null
                      ? '目標價未設定'
                      : '目標 ${legacy.accountingNumber(row['target_price'], decimals: 2)}'),
                  if (pending > 0) fvTag('待追蹤 $pending'),
                  if (offUniverse)
                    fvTag('已離開本週 500 · 仍保留關注', warning: true),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => ColoredBox(
        color: fvCanvas,
        child: SafeArea(
          bottom: false,
          child: FutureBuilder<dynamic>(
            future: data,
            builder: (context, snapshot) {
              final rows = fvRows(snapshot.data);
              if (snapshot.connectionState != ConnectionState.done) {
                return ListView(
                  padding: const EdgeInsets.fromLTRB(18, 18, 18, 110),
                  children: [header(context, 0), fvBoundedState('關注清單載入中')],
                );
              }
              if (snapshot.hasError) {
                return ListView(
                  padding: const EdgeInsets.fromLTRB(18, 18, 18, 110),
                  children: [
                    header(context, 0),
                    fvPanel(
                      child: Row(
                        children: [
                          const Expanded(child: Text('關注清單暫時無法使用')),
                          TextButton(onPressed: reload, child: const Text('重試')),
                        ],
                      ),
                    ),
                  ],
                );
              }
              if (rows.isEmpty) {
                return ListView(
                  padding: const EdgeInsets.fromLTRB(18, 18, 18, 110),
                  children: [header(context, 0), fvBoundedState('目前沒有關注股票')],
                );
              }
              return ReorderableListView.builder(
                key: const Key('final-watchlist-scroll'),
                padding: const EdgeInsets.fromLTRB(18, 18, 18, 110),
                header: header(context, rows.length),
                footer: const SizedBox(height: 8),
                itemCount: rows.length,
                onReorder: (oldIndex, newIndex) => reorder(rows, oldIndex, newIndex),
                itemBuilder: (context, index) => card(fvMap(rows[index])),
              );
            },
          ),
        ),
      );
}
