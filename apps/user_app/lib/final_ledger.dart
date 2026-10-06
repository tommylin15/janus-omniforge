import 'package:flutter/material.dart';

import 'final_charts.dart';
import 'final_perf.dart';
import 'final_visual_common.dart';
import 'main.dart' as legacy;

class FinalLedgerPage extends StatefulWidget {
  const FinalLedgerPage(
    this.api, {
    this.onOpenStock,
    this.active = true,
    super.key,
  });

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

  Future<List<dynamic>> load() async {
    final stopwatch = Stopwatch()..start();
    final year = DateTime.now().year;
    try {
      return await Future.wait([
        safe('/api/v1/me/portfolio/summary'),
        safe('/api/v1/me/journal/pnl?year=$year'),
        safe('/api/v1/me/journal/positions'),
        safe('/api/v1/me/journal/history?year=$year'),
        safe('/api/v1/me/journal/monthly-summary?year=$year'),
        safe('/api/v1/me/portfolio/performance?year=$year'),
        safe('/api/v1/me/notes'),
      ]);
    } finally {
      stopwatch.stop();
      FinalPerf.recordCore('ledger', stopwatch.elapsed);
    }
  }

  void reload() => setState(() => data = load());

  Future<void> addTrade() async {
    final payload = await legacy.transactionDialog(context);
    if (payload == null) return;
    try {
      await widget.api.post('/api/v1/me/journal/events', payload);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text(legacy.portfolioPendingMessage)),
      );
      reload();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('交易尚未儲存')),
        );
      }
    }
  }

  Future<void> correctTrade(Map<String, dynamic> row) async {
    final replacement = await legacy.transactionDialog(
      context,
      initial: row,
      title: '建立更正',
    );
    if (replacement == null || !mounted) return;
    try {
      await widget.api.post(
        '/api/v1/me/journal/events/${row['event_id']}/corrections',
        {
          'expected_version': row['record_version'],
          'replacement': replacement,
        },
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text(legacy.portfolioPendingMessage)),
      );
      reload();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('交易更正尚未儲存')),
        );
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
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('筆記尚未儲存')),
        );
      }
    }
  }

  Widget metricGrid({
    required String marketValue,
    required String unrealized,
    required String unrealizedReturn,
    required String ytd,
    required Map<String, dynamic> aggregate,
    required bool withheld,
  }) => Column(
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: fvMetricTile(
                  '持股市值',
                  marketValue,
                  detail: '估值日 ${fvText(aggregate['valuation_date'])}',
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: fvMetricTile(
                  '未實現損益',
                  unrealized,
                  detail: '報酬 $unrealizedReturn',
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: fvMetricTile(
                  '本年已實現損益',
                  ytd,
                  detail: ytd == '待更新／尚未確認'
                      ? 'Private Mart 尚未確認時不補 0'
                      : ytd == '資料不足'
                          ? '年度損益目前無法確認'
                          : ytd == '0'
                              ? '本年度確認無交易'
                              : '正式年度損益',
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: fvMetricTile(
                  '估值狀態',
                  withheld
                      ? '暫不發布'
                      : legacy.uiLabel(
                          aggregate['valuation_status'] ??
                              (aggregate.isEmpty ? 'partial' : 'available'),
                        ),
                  detail:
                      'ledger v${fvText(aggregate['ledger_version'], missing: '—')}',
                ),
              ),
            ],
          ),
        ],
      );

  Widget holdings(List<dynamic> positions) {
    if (positions.isEmpty) return fvBoundedState('目前無持股或持股資料尚未取得');
    return Column(
      children: [
        for (final item in positions)
          Builder(builder: (context) {
            final row = fvMap(item);
            final symbol = fvText(row['symbol']);
            final reason = legacy.portfolioMissingReasonLabel(row['missing_reason']);
            return fvPanel(
              padding: EdgeInsets.zero,
              child: InkWell(
                borderRadius: BorderRadius.circular(20),
                onTap: () => widget.onOpenStock?.call(symbol),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
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
                                const SizedBox(height: 6),
                                Text(
                                  '持有 ${legacy.accountingNumber(row['shares'])} 股',
                                  style: const TextStyle(color: fvInk),
                                ),
                                Text(
                                  '現價 ${legacy.accountingNumber(row['market_price'], decimals: 2, missing: '缺價')} · 均價 ${legacy.accountingNumber(row['average_cost'], decimals: 2)}',
                                  style: const TextStyle(
                                    color: fvMuted,
                                    fontSize: 12,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(width: 10),
                          ConstrainedBox(
                            constraints: const BoxConstraints(maxWidth: 118),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.end,
                              children: [
                                Text(
                                  legacy.accountingNumber(
                                    row['unrealized_pnl'],
                                    missing: '資料不足',
                                  ),
                                  textAlign: TextAlign.end,
                                  style: const TextStyle(
                                    color: fvInk,
                                    fontSize: 16,
                                    fontWeight: FontWeight.w800,
                                  ),
                                ),
                                Text(
                                  legacy.portfolioReturnLabel(
                                    row['unrealized_return'],
                                  ),
                                  style: const TextStyle(
                                    color: fvTeal,
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      Text(
                        '估值日 ${fvText(row['valuation_date'])} · 行情日 ${fvText(row['price_date'])} · ${row['price_status'] == null ? '狀態未知' : legacy.uiLabel(row['price_status'])}',
                        style: const TextStyle(color: fvMuted, fontSize: 11),
                      ),
                      if (reason.isNotEmpty) ...[
                        const SizedBox(height: 4),
                        Text(
                          reason,
                          style: const TextStyle(color: fvMuted, fontSize: 11),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            );
          }),
      ],
    );
  }

  Widget records(List<dynamic> history, List<dynamic> monthly) {
    final effective = legacy.effectiveLedgerEvents(history);
    if (effective.isEmpty && monthly.isEmpty) {
      return fvBoundedState('本年度尚無交易紀錄');
    }
    final summaries = <int, Map<String, dynamic>>{};
    for (final item in monthly) {
      final row = fvMap(item);
      summaries[fvInt(row['month'])] = row;
    }
    final months = <int>{...summaries.keys};
    for (final item in effective) {
      final row = fvMap(item);
      final day = DateTime.tryParse(fvText(row['trade_date'], missing: ''));
      if (day != null) months.add(day.month);
    }
    final ordered = months.toList()..sort((left, right) => right.compareTo(left));
    return Column(
      children: [
        for (final month in ordered)
          fvPanel(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${DateTime.now().year} 年 $month 月',
                  style: const TextStyle(
                    color: fvInk,
                    fontSize: 16,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                if (summaries[month] != null) ...[
                  const SizedBox(height: 10),
                  Wrap(
                    spacing: 12,
                    runSpacing: 6,
                    children: [
                      Text('買進支出 ${legacy.accountingNumber(summaries[month]!['purchase_outflow'])}'),
                      Text('賣出回收 ${legacy.accountingNumber(summaries[month]!['sale_proceeds'])}'),
                      Text('股利收入 ${legacy.accountingNumber(summaries[month]!['cash_dividends'])}'),
                      Text('已實現損益 ${legacy.accountingNumber(summaries[month]!['realized_pnl'])}'),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(
                    '資料日期 ${fvText(summaries[month]!['valuation_date'])}',
                    style: const TextStyle(color: fvMuted, fontSize: 11),
                  ),
                ],
                const Divider(height: 22),
                for (final item in effective.where((item) {
                  final row = fvMap(item);
                  final day = DateTime.tryParse(
                    fvText(row['trade_date'], missing: ''),
                  );
                  return day?.month == month;
                }))
                  Builder(builder: (context) {
                    final row = fvMap(item);
                    return ListTile(
                      contentPadding: EdgeInsets.zero,
                      dense: true,
                      title: Text(
                        '${legacy.uiLabel(row['event_type'])} · ${legacy.stockDisplayName(row)}',
                      ),
                      subtitle: Text(
                        '${fvText(row['trade_date'])} · 淨現金流 ${legacy.accountingNumber(row['net_cash_flow'], missing: '資料不足')} ${fvText(row['currency'], missing: '')}',
                      ),
                      trailing: row['event_id'] != null &&
                              row['record_version'] != null
                          ? IconButton(
                              tooltip: '建立更正',
                              icon: const Icon(Icons.edit_note),
                              onPressed: () => correctTrade(row),
                            )
                          : null,
                    );
                  }),
              ],
            ),
          ),
      ],
    );
  }

  Widget reports(
    List<dynamic> pnl,
    List<dynamic> performance, {
    required List<dynamic> monthly,
    required String ytd,
  }) {
    final emptyPnlMessage = switch (ytd) {
      '0' => '本年度確認無交易；已實現損益 0',
      '待更新／尚未確認' => '本年已實現損益仍待 Private Mart 更新',
      _ => '本年已實現損益目前無法確認',
    };
    if (pnl.isEmpty && performance.isEmpty) {
      return fvBoundedState(emptyPnlMessage);
    }
    return Column(
      children: [
        FvMonthlyPnlChart(rows: monthly),
        if (pnl.isEmpty) fvBoundedState(emptyPnlMessage),
        for (final item in pnl)
          Builder(builder: (context) {
            final row = fvMap(item);
            return fvPanel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${fvText(row['currency'], missing: 'TWD')} · 本年損益',
                    style: const TextStyle(
                      color: fvInk,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text('已實現損益 ${legacy.accountingNumber(row['realized_pnl'])}'),
                  Text('股利收入 ${legacy.accountingNumber(row['cash_dividends'])}'),
                  Text(
                    '手續費 ${legacy.accountingNumber(row['fees'])} · 稅 ${legacy.accountingNumber(row['taxes'])}',
                  ),
                  const SizedBox(height: 6),
                  Text(
                    '資料日期 ${fvText(row['valuation_date'])}',
                    style: const TextStyle(color: fvMuted, fontSize: 11),
                  ),
                ],
              ),
            );
          }),
        for (final item in performance)
          Builder(builder: (context) {
            final row = fvMap(item);
            final status = row['xirr_status'];
            return fvPanel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    '年度績效',
                    style: TextStyle(
                      color: fvInk,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    status == 'available' && row['xirr'] != null
                        ? 'XIRR ${legacy.portfolioReturnLabel(row['xirr'])}'
                        : 'XIRR ${legacy.uiLabel(status ?? 'insufficient_data')}',
                  ),
                  Text(
                    '資料日期 ${fvText(row['valuation_date'])}',
                    style: const TextStyle(color: fvMuted, fontSize: 11),
                  ),
                ],
              ),
            );
          }),
      ],
    );
  }

  Widget notes(List<dynamic> values) => Column(
        children: [
          Align(
            alignment: Alignment.centerRight,
            child: TextButton.icon(
              onPressed: addNote,
              icon: const Icon(Icons.add),
              label: const Text('新增筆記'),
            ),
          ),
          if (values.isEmpty) fvBoundedState('目前沒有筆記'),
          for (final item in values)
            Builder(builder: (context) {
              final row = fvMap(item);
              return fvPanel(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      fvText(
                        row['body'] ?? row['text'] ?? row['content'],
                        missing: '筆記內容不可用',
                      ),
                      style: const TextStyle(color: fvInk, height: 1.45),
                    ),
                    if (row['symbol'] != null || row['needs_follow_up'] == true) ...[
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 7,
                        runSpacing: 7,
                        children: [
                          if (row['symbol'] != null) fvTag('${row['symbol']}'),
                          if (row['needs_follow_up'] == true) fvTag('待追蹤'),
                        ],
                      ),
                    ],
                  ],
                ),
              );
            }),
        ],
      );

  @override
  Widget build(BuildContext context) => ColoredBox(
        color: fvCanvas,
        child: SafeArea(
          bottom: false,
          child: FutureBuilder<List<dynamic>>(
            future: data,
            builder: (context, snapshot) {
              final values = snapshot.data ??
                  const [null, null, null, null, null, null, null];
              final summary = fvRows(values[0]);
              final pnl = fvRows(values[1]);
              final positions = fvRows(values[2]);
              final history = fvRows(values[3]);
              final monthly = fvRows(values[4]);
              final performance = fvRows(values[5]);
              final noteRows = fvRows(values[6]);
              final aggregate = summary.isEmpty
                  ? <String, dynamic>{}
                  : fvMap(summary.first);
              final withheld = aggregate['aggregate_status'] == 'withheld';
              final currency = fvText(aggregate['currency'], missing: 'TWD');
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
              final pnlUnavailable = values[1] == null;
              final historyUnavailable = values[3] == null;
              final ytd = pnlUnavailable || historyUnavailable
                  ? '資料不足'
                  : pnl.isNotEmpty
                      ? pnl.length == 1
                          ? '${fvText(fvMap(pnl.first)['currency'], missing: 'TWD')} ${legacy.accountingNumber(fvMap(pnl.first)['realized_pnl'])}'
                          : '多幣別'
                      : withheld || history.isNotEmpty
                          ? '待更新／尚未確認'
                          : '0';
              final affected = fvRows(aggregate['affected_symbols']);

              return ListView(
                key: const Key('final-ledger-scroll'),
                padding: const EdgeInsets.fromLTRB(18, 18, 18, 110),
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: fvPageTitle(
                          context,
                          '記帳／筆記',
                          subtitle: '持股、交易與正式報表使用同一資料語意',
                        ),
                      ),
                      IconButton(
                        onPressed: reload,
                        tooltip: '重新整理',
                        icon: const Icon(Icons.refresh, color: fvTeal),
                      ),
                    ],
                  ),
                  metricGrid(
                    marketValue: marketValue,
                    unrealized: unrealized,
                    unrealizedReturn: unrealizedReturn,
                    ytd: ytd,
                    aggregate: aggregate,
                    withheld: withheld,
                  ),
                  if (withheld)
                    fvBoundedState(
                      '正式總額暫不發布${affected.isEmpty ? '' : ' · 受影響 ${affected.join('、')}'}；持股 operational shares／cost 仍可顯示。',
                    ),
                  const SizedBox(height: 12),
                  SegmentedButton<int>(
                    segments: const [
                      ButtonSegment(value: 0, label: Text('持股')),
                      ButtonSegment(value: 1, label: Text('紀錄')),
                      ButtonSegment(value: 2, label: Text('報表')),
                      ButtonSegment(value: 3, label: Text('筆記')),
                    ],
                    selected: {section},
                    onSelectionChanged: (value) =>
                        setState(() => section = value.first),
                    showSelectedIcon: false,
                  ),
                  const SizedBox(height: 12),
                  if (snapshot.connectionState != ConnectionState.done)
                    fvBoundedState('Ledger 資料載入中')
                  else ...[
                    if (section == 0) ...[
                      Row(
                        children: [
                          Expanded(child: fvSectionTitle(context, '持股')),
                          FilledButton.icon(
                            onPressed: addTrade,
                            icon: const Icon(Icons.add, size: 18),
                            label: const Text('新增交易'),
                            style: FilledButton.styleFrom(backgroundColor: fvTeal),
                          ),
                        ],
                      ),
                      holdings(positions),
                    ],
                    if (section == 1) ...[
                      fvSectionTitle(
                        context,
                        '紀錄',
                        trailing: '${DateTime.now().year} 年',
                      ),
                      records(history, monthly),
                    ],
                    if (section == 2) ...[
                      fvSectionTitle(context, '報表'),
                      reports(
                        pnl,
                        performance,
                        monthly: monthly,
                        ytd: ytd,
                      ),
                    ],
                    if (section == 3) ...[
                      fvSectionTitle(context, '筆記'),
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
