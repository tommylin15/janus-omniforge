import 'dart:math' as math;

import 'package:flutter/material.dart';

/// Read-only, on-demand Shioaji BidAsk book (not SDK snapshots: one best level).
/// The parent owns the Future so quote-minute refresh does not query depth.
class StockOrderBookPanel extends StatelessWidget {
  const StockOrderBookPanel({
    super.key,
    required this.symbol,
    required this.snapshot,
    required this.onRefresh,
  });

  final String symbol;
  final Future<dynamic>? snapshot;
  final VoidCallback onRefresh;

  static const _buy = Color(0xFF087C8B);
  static const _sell = Color(0xFFC35C29);
  static const _ink = Color(0xFF18343B);
  static const _muted = Color(0xFF62757B);

  static List<Map<String, dynamic>> _rows(dynamic value) {
    if (value is! List) return const [];
    return value.whereType<Map>().map((row) =>
      Map<String, dynamic>.from(row)).take(5).toList();
  }

  static int _volume(Map<String, dynamic> row) {
    final amount = row['volume'];
    if (amount is int) return math.max(0, amount);
    return 0;
  }

  static String _time(dynamic raw) {
    final date = DateTime.tryParse(raw?.toString() ?? '');
    if (date == null) return '資料時間缺值';
    final local = date.toUtc().add(const Duration(hours: 8));
    String two(int value) => value.toString().padLeft(2, '0');
    return '${local.year}-${two(local.month)}-${two(local.day)} '
        '${two(local.hour)}:${two(local.minute)}:${two(local.second)}';
  }

  Widget _side(Map<String, dynamic>? row, int index,
      {required bool buy, required int biggest}) {
    final volume = row == null ? null : _volume(row);
    final price = row?['price']?.toString() ?? '—';
    final tone = buy ? _buy : _sell;
    final ratio = (volume ?? 0) / biggest;
    return Expanded(child: SizedBox(height: 30, child: Stack(
      fit: StackFit.expand,
      children: [
        FractionallySizedBox(
          alignment: buy ? Alignment.centerRight : Alignment.centerLeft,
          widthFactor: ratio.clamp(0.0, 1.0).toDouble(),
          child: ColoredBox(color: tone.withValues(alpha: .12)),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 7),
          child: Row(children: [
            if (!buy) Text('賣${index + 1}',
                style: const TextStyle(fontSize: 13, color: _muted)),
            if (!buy) const SizedBox(width: 4),
            Expanded(child: Text(buy ? '${index + 1} · $price' : price,
              maxLines: 1, overflow: TextOverflow.ellipsis,
              style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600,
                  color: tone))),
            Text(volume?.toString() ?? '—',
                style: const TextStyle(fontSize: 14, color: _ink,
                    fontWeight: FontWeight.w700)),
          ]),
        ),
      ],
    )));
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<dynamic>(
    key: ValueKey('order-book-future-$symbol'),
    future: snapshot,
    builder: (context, state) {
      final data = state.data is Map ? Map<String, dynamic>.from(state.data as Map)
          : const <String, dynamic>{};
      final sameSymbol = data['symbol'] == symbol;
      final status = sameSymbol ? data['status']?.toString() : null;
      final available = status == 'available' || status == 'partial';
      final bid = available ? _rows(data['bid']) : const <Map<String, dynamic>>[];
      final ask = available ? _rows(data['ask']) : const <Map<String, dynamic>>[];
      final totalBid = bid.fold<int>(0, (sum, row) => sum + _volume(row));
      final totalAsk = ask.fold<int>(0, (sum, row) => sum + _volume(row));
      final biggestBid = bid.fold<int>(0, (m, row) => math.max(m, _volume(row)));
      final biggestAsk = ask.fold<int>(0, (m, row) => math.max(m, _volume(row)));
      final biggest = math.max(1, math.max(biggestBid, biggestAsk));
      final hasRows = bid.isNotEmpty || ask.isNotEmpty;
      final loading = state.connectionState != ConnectionState.done;
      return Container(
        padding: const EdgeInsets.all(11),
        decoration: BoxDecoration(
          color: const Color(0xFFF6F9FA),
          border: Border.all(color: const Color(0xFFDCE8EA)),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            const Expanded(child: Text('買賣五檔｜按需快照',
                style: TextStyle(color: _ink, fontSize: 17,
                    fontWeight: FontWeight.w800))),
            IconButton(
              key: Key('today-order-book-refresh-$symbol'),
              tooltip: '手動讀取五檔',
              onPressed: loading ? null : onRefresh,
              icon: const Icon(Icons.refresh, size: 20, color: _buy),
              visualDensity: VisualDensity.compact,
            ),
          ]),
          const Text('永豐 Shioaji BidAsk 訂閱快取 · 整股張數 · 非交易指令',
              style: TextStyle(fontSize: 10, color: _muted)),
          if (loading)
            const Padding(padding: EdgeInsets.only(top: 9),
                child: Text('正在讀取當下五檔…', style: TextStyle(color: _muted)))
          else if (!hasRows)
            Padding(
              padding: const EdgeInsets.only(top: 10),
              child: Text(status == 'stale'
                  ? '五檔已過時，不能代表當前委託簿。'
                  : '尚無有效五檔（休市、訂閱尚未回報或來源暫不可用）。',
                  key: Key('today-order-book-missing-$symbol'),
                  style: const TextStyle(fontSize: 12, color: _muted)),
            )
          else ...[
            const SizedBox(height: 7),
            Text('資料時間 ${_time(data['quote_at'])} · '
                '${status == 'partial' ? '部分檔位' : '五檔完整'}',
                key: Key('today-order-book-time-$symbol'),
                style: const TextStyle(fontSize: 13, color: _muted)),
            const SizedBox(height: 9),
            Row(children: [
              Expanded(child: Text('委買 $totalBid 張',
                  style: const TextStyle(fontSize: 12, color: _buy,
                      fontWeight: FontWeight.w700))),
              Expanded(child: Text('委賣 $totalAsk 張',
                  textAlign: TextAlign.end,
                  style: const TextStyle(fontSize: 12, color: _sell,
                      fontWeight: FontWeight.w700))),
            ]),
            const SizedBox(height: 4),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: totalBid + totalAsk == 0 ? 0.5
                    : totalBid / (totalBid + totalAsk),
                minHeight: 7,
                backgroundColor: _sell.withValues(alpha: .65),
                color: _buy,
              ),
            ),
            const SizedBox(height: 7),
            Row(children: [
              Expanded(child: Text('買價 / 買量（張）',
                  style: const TextStyle(fontSize: 11, color: _muted))),
              Expanded(child: Text('賣價 / 賣量（張）',
                  textAlign: TextAlign.end,
                  style: const TextStyle(fontSize: 11, color: _muted))),
            ]),
            for (var i = 0; i < 5; i++)
              Row(children: [
                _side(i < bid.length ? bid[i] : null, i,
                    buy: true, biggest: biggest),
                const SizedBox(width: 4),
                _side(i < ask.length ? ask[i] : null, i,
                    buy: false, biggest: biggest),
              ]),
          ],
        ]),
      );
    },
  );
}
