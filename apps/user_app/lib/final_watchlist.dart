import 'dart:async';

import 'package:flutter/material.dart';

import 'final_perf.dart';
import 'final_visual_common.dart';
import 'main.dart' as legacy;

class FinalWatchlistPage extends StatefulWidget {
  const FinalWatchlistPage(this.api, {this.onOpenStock, this.active = true, super.key});

  final legacy.Api api;
  final ValueChanged<String>? onOpenStock;
  final bool active;

  @override
  State<FinalWatchlistPage> createState() => _FinalWatchlistPageState();
}

class _FinalWatchlistPageState extends State<FinalWatchlistPage> with WidgetsBindingObserver {
  late Future<dynamic> data = _load();
  dynamic lastGoodData;
  int loadGeneration = 0;
  Timer? quoteTimer;
  bool foreground = true;

  bool get marketHours {
    final taipei = DateTime.now().toUtc().add(const Duration(hours: 8));
    final minutes = taipei.hour * 60 + taipei.minute;
    return taipei.weekday <= 5 && minutes >= 540 && minutes < 810;
  }

  bool get quotesActive =>
      widget.active && foreground && (ModalRoute.of(context)?.isCurrent ?? true);

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    foreground = WidgetsBinding.instance.lifecycleState == null ||
        WidgetsBinding.instance.lifecycleState == AppLifecycleState.resumed;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _startQuoteTimer();
    });
  }

  void _startQuoteTimer() {
    quoteTimer?.cancel();
    if (quotesActive && marketHours) {
      quoteTimer = Timer.periodic(const Duration(minutes: 1), (_) {
        if (!quotesActive || !marketHours) {
          quoteTimer?.cancel();
        } else {
          reload();
        }
      });
    }
  }

  @override
  void didUpdateWidget(FinalWatchlistPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.api, widget.api)) {
      // Owner/API token transitions must never reuse another owner's snapshot.
      lastGoodData = null;
      data = _load();
    }
    if (oldWidget.active != widget.active) {
      if (widget.active) {
        reload();
        _startQuoteTimer();
      } else {
        quoteTimer?.cancel();
      }
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    foreground = state == AppLifecycleState.resumed;
    if (foreground) {
      if (widget.active) {
        reload();
        _startQuoteTimer();
      }
    } else {
      quoteTimer?.cancel();
    }
  }

  @override
  void dispose() {
    quoteTimer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  Future<dynamic> _load() async {
    final generation = ++loadGeneration;
    final stopwatch = Stopwatch()..start();
    try {
      final response = await widget.api.get('/api/v1/me/watchlist')
          .timeout(const Duration(seconds: 9));
      if (generation == loadGeneration) lastGoodData = response;
      return generation == loadGeneration ? response : null;
    } finally {
      stopwatch.stop();
      FinalPerf.recordCore('watchlist', stopwatch.elapsed);
    }
  }

  void reload() => setState(() => data = _load());

  Future<void> add() async {
    final query = await legacy.textDialog(
      context,
      '搜尋關注股票',
      '股票代號或中文名稱',
      confirmLabel: '搜尋',
    );
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
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('關注已保存，分析快照將於背景更新')),
        );
      }
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
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('排序已保存，分析快照將於背景更新')),
        );
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('排序未更新，請重新整理')),
        );
      }
    }
  }

  Widget header(BuildContext context, int count, {int followups = 0}) => Column(
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
                if (followups > 0) ...[
                  fvTag('待追蹤筆記 $followups', icon: Icons.flag_outlined),
                  const SizedBox(height: 8),
                ],
                Text(
                  '我的關注 $count/50',
                  style: const TextStyle(
                    color: fvInk,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 4),
                const Text(
                  '新加入可選上市／上櫃全部個股；既有退出名冊股票仍保留關注。',
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
    final offUniverse = row['in_market'] == false;
    final pending = fvInt(row['pending_note_count']);
    return Card(
      key: ValueKey('watch-$symbol'),
      margin: const EdgeInsets.only(bottom: 10),
      elevation: 0,
      color: Colors.white,
      clipBehavior: Clip.antiAlias,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      child: Ink(
        decoration: fvPastelDecoration(
          tone: offUniverse ? FvCardTone.peach
              : pending > 0 ? FvCardTone.lavender
              : row['held'] == true ? FvCardTone.mint : FvCardTone.sky,
        ),
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
                        if (mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('關注已移除，分析快照將於背景更新')),
                          );
                        }
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
                      style: TextStyle(
                        color: fvSignedColor(row['change']),
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
              if (row['change'] != null && row['change_percent'] != null) ...[
                const SizedBox(height: 3),
                Row(children: [
                  Icon(fvNumber(row['change']) != null && fvNumber(row['change'])! >= 0
                    ? Icons.arrow_upward : Icons.arrow_downward,
                    size: 16, color: fvSignedColor(row['change'])),
                  const SizedBox(width: 4),
                  Text('${legacy.accountingNumber(row['change'], decimals: 2)}  ${fvSignedPercent(row['change_percent'])}',
                    key: Key('watch-price-change-$symbol'),
                    style: TextStyle(color: fvSignedColor(row['change']),
                      fontSize: 15, fontWeight: FontWeight.w800)),
                  const SizedBox(width: 7),
                  Expanded(child: Text('前收 ${legacy.accountingNumber(row['previous_close'], decimals: 2)}',
                    textAlign: TextAlign.end, style: const TextStyle(color: fvMuted, fontSize: 11))),
                ]),
              ],
              const SizedBox(height: 10),
              Wrap(
                spacing: 7,
                runSpacing: 7,
                children: [
                  fvTag(row['held'] == true ? '已持有' : '未持有',
                      icon: row['held'] == true ? Icons.account_balance_wallet_outlined : Icons.bookmark_outline),
                  fvTag(row['target_price'] == null
                      ? '目標價未設定'
                      : '目標 ${legacy.accountingNumber(row['target_price'], decimals: 2)}',
                      icon: Icons.track_changes_outlined),
                  if (pending > 0) fvTag('待追蹤 $pending', icon: Icons.flag_outlined),
                  if (offUniverse)
                    fvTag('已退出有效名冊 · 仍保留關注', warning: true,
                        icon: Icons.bookmark_added_outlined),
                ],
              ),
            ],
          ),
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
              final rows = fvRows(snapshot.data ?? lastGoodData);
              if (snapshot.connectionState != ConnectionState.done && lastGoodData == null) {
                return ListView(
                  padding: const EdgeInsets.fromLTRB(18, 18, 18, 110),
                  children: [header(context, 0), fvBoundedState('關注清單載入中')],
                );
              }
              if (snapshot.hasError && lastGoodData == null) {
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
                header: Column(children: [
                  header(context, rows.length, followups: rows.fold<int>(0,
                      (total, row) => total + fvInt(fvMap(row)['pending_note_count']))),
                  if (snapshot.connectionState != ConnectionState.done)
                    fvBoundedState('清單更新中，保留上次有效資料', icon: Icons.sync),
                  if (snapshot.hasError)
                    fvPanel(child: Row(children: [
                      const Expanded(child: Text('更新失敗，顯示上次有效資料')),
                      TextButton(onPressed: reload, child: const Text('重試')),
                    ])),
                ]),
                footer: const SizedBox(height: 8),
                itemCount: rows.length,
                buildDefaultDragHandles: false,
                onReorder: (oldIndex, newIndex) => reorder(rows, oldIndex, newIndex),
                itemBuilder: (context, index) => ReorderableDelayedDragStartListener(
                  key: ValueKey('watch-${fvMap(rows[index])['symbol']}'),
                  index: index,
                  child: card(fvMap(rows[index])),
                ),
              );
            },
          ),
        ),
      );
}
