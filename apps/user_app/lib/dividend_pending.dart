import 'package:flutter/material.dart';

import 'final_visual_common.dart';
import 'main.dart' as legacy;

String _warningLabel(String code) => switch (code) {
      'NHI_ESTIMATED' => '單筆達2萬，已預估2.11%補充保費（可微調）',
      'ETF_EQUALIZATION_CHECK' => 'ETF配息可能含平準金，補充保費預設0元，請依通知書核對',
      'KY_OVERSEAS_INCOME' => 'KY股屬海外所得，免扣國內二代健保補充保費',
      'HAS_FRACTIONAL_SHARES' => '含未滿1股之畸零股，請依實際集保入帳股數微調',
      'FRACTIONAL_ONLY' => '僅餘畸零股（不足1股），建議核對或忽略',
      'PAYMENT_DATE_TBD' => '發放日尚未公告，建議發放後再確認入帳',
      'LEDGER_UPDATED_RECALC' => '偵測到除權息日前有補登交易，已自動重算',
      _ => code,
    };

Map<String, dynamic> _summarizePending(List<dynamic> items) {
  var cashTotal = 0.0;
  var stockTotal = 0.0;
  for (final raw in items) {
    final row = fvMap(raw);
    if (row['action_type'] == 'CASH_DIVIDEND') {
      cashTotal += fvNumber(row['net_cash_amount']) ?? 0;
    } else if (row['action_type'] == 'STOCK_DIVIDEND') {
      stockTotal += fvNumber(row['confirmed_stock_shares']) ?? 0;
    }
  }
  return {'cashTotal': cashTotal, 'stockTotal': stockTotal};
}

/// 輕量待確認股利提示橫幅：僅於 pending_count > 0 時顯示，不干擾主持股清單。
class PendingDividendsBanner extends StatelessWidget {
  const PendingDividendsBanner({
    required this.pendingCount,
    required this.items,
    required this.onReview,
    super.key,
  });

  final int pendingCount;
  final List<dynamic> items;
  final VoidCallback onReview;

  @override
  Widget build(BuildContext context) {
    if (pendingCount <= 0) return const SizedBox.shrink();
    final summary = _summarizePending(items);
    final cashTotal = summary['cashTotal'] as double;
    final stockTotal = summary['stockTotal'] as double;
    final parts = <String>[];
    if (cashTotal > 0) {
      parts.add('現金 +${legacy.accountingNumber(cashTotal)} 元');
    }
    if (stockTotal > 0) {
      parts.add('配股 +${legacy.accountingNumber(stockTotal)} 股');
    }
    final detail = parts.isEmpty ? '請點擊核對除權息明細' : parts.join(' · ');

    return Card(
      key: const Key('pending-dividends-banner'),
      margin: const EdgeInsets.only(bottom: 10),
      elevation: 0,
      clipBehavior: Clip.antiAlias,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
      child: Ink(
        decoration: fvPastelDecoration(tone: FvCardTone.lavender, radius: 18),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          child: Wrap(
            spacing: 10,
            runSpacing: 8,
            alignment: WrapAlignment.spaceBetween,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.savings_outlined, color: fvTeal, size: 22),
                  const SizedBox(width: 10),
                  Flexible(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '待確認股利（$pendingCount 筆）',
                          style: const TextStyle(
                            color: fvInk,
                            fontSize: 15,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          detail,
                          style: const TextStyle(color: fvMuted, fontSize: 12),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              FilledButton.tonal(
                key: const Key('open-pending-dividends'),
                onPressed: onReview,
                style: FilledButton.styleFrom(
                  backgroundColor: fvTeal,
                  foregroundColor: Colors.white,
                ),
                child: const Text('查看核對'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

Future<bool> showPendingDividendsSheet(
  BuildContext context, {
  required legacy.Api api,
  required DateTime Function() now,
  Map<String, dynamic>? initialData,
}) async {
  final changed = await showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    backgroundColor: fvCanvas,
    builder: (sheetContext) => FractionallySizedBox(
      heightFactor: 0.92,
      child: PendingDividendsSheet(
        api: api,
        now: now,
        initialData: initialData,
      ),
    ),
  );
  return changed == true;
}

class PendingDividendsSheet extends StatefulWidget {
  const PendingDividendsSheet({
    required this.api,
    required this.now,
    this.initialData,
    super.key,
  });

  final legacy.Api api;
  final DateTime Function() now;
  final Map<String, dynamic>? initialData;

  @override
  State<PendingDividendsSheet> createState() => _PendingDividendsSheetState();
}

class _PendingDividendsSheetState extends State<PendingDividendsSheet> {
  late int ledgerVersion;
  late List<Map<String, dynamic>> items;
  final Set<String> selectedIds = <String>{};
  bool loading = false;
  bool busy = false;
  bool anyCommitted = false;
  String? errorMessage;

  @override
  void initState() {
    super.initState();
    _applyPayload(widget.initialData);
    if (widget.initialData == null) {
      unawaitedFetch();
    } else {
      _selectPayableByDefault();
    }
  }

  void unawaitedFetch() {
    Future.microtask(refreshList);
  }

  void _applyPayload(Map<String, dynamic>? data) {
    ledgerVersion = fvInt(data?['ledger_version']);
    items = fvRows(data?['items']).map(fvMap).toList();
    selectedIds.removeWhere(
      (id) => !items.any((row) => fvText(row['draft_id'], missing: '') == id),
    );
  }

  bool _isPayable(Map<String, dynamic> row) {
    final paymentStr = fvText(row['payment_date'], missing: '');
    if (paymentStr.isEmpty) return false;
    final payment = DateTime.tryParse(paymentStr);
    if (payment == null) return false;
    final taipei = widget.now().toUtc().add(const Duration(hours: 8));
    final today = DateTime(taipei.year, taipei.month, taipei.day);
    return !payment.isAfter(today);
  }

  bool _canConfirm(Map<String, dynamic> row) {
    if (row['action_type'] == 'STOCK_DIVIDEND') {
      return (fvNumber(row['confirmed_stock_shares']) ?? 0) > 0;
    }
    return true;
  }

  void _selectPayableByDefault() {
    selectedIds.clear();
    for (final row in items) {
      if (_isPayable(row) && _canConfirm(row)) {
        final id = fvText(row['draft_id'], missing: '');
        if (id.isNotEmpty) selectedIds.add(id);
      }
    }
  }

  Future<void> refreshList({bool clearError = true}) async {
    setState(() {
      loading = true;
      if (clearError) errorMessage = null;
    });
    try {
      final response = await widget.api
          .get('/api/v1/me/dividends/pending')
          .timeout(const Duration(seconds: 12));
      if (!mounted) return;
      if (response is Map) {
        setState(() {
          _applyPayload(Map<String, dynamic>.from(response));
          _selectPayableByDefault();
        });
      }
    } catch (error) {
      if (!mounted) return;
      setState(() => errorMessage = '讀取待確認股利失敗：$error');
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> scanHistory() async {
    if (busy) return;
    setState(() {
      busy = true;
      errorMessage = null;
    });
    try {
      final result = await widget.api
          .post('/api/v1/me/dividends/scan', const {})
          .timeout(const Duration(seconds: 18));
      await refreshList();
      if (!mounted) return;
      final summary = fvMap(result);
      final created = fvInt(summary['newly_created']);
      final recalc = fvInt(summary['recalculated']);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('歷史掃描完成：新增 $created 筆、更新 $recalc 筆')),
      );
    } catch (error) {
      if (!mounted) return;
      setState(() => errorMessage = '掃描失敗，請稍後重試');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> editDraft(Map<String, dynamic> row) async {
    final isCash = row['action_type'] == 'CASH_DIVIDEND';
    final remitCtrl = TextEditingController(
      text: fvText(row['estimated_remit_fee'], missing: '10'),
    );
    final nhiCtrl = TextEditingController(
      text: fvText(row['estimated_nhi_fee'], missing: '0'),
    );
    final netCtrl = TextEditingController(
      text: fvText(row['net_cash_amount'], missing: '0'),
    );
    final stockCtrl = TextEditingController(
      text: fvText(row['confirmed_stock_shares'], missing: '0'),
    );
    final noteCtrl = TextEditingController(
      text: fvText(row['user_note'], missing: ''),
    );
    final gross = fvNumber(row['gross_cash_amount']) ?? 0;

    void recomputeNet() {
      final r = double.tryParse(remitCtrl.text.trim()) ?? 0;
      final n = double.tryParse(nhiCtrl.text.trim()) ?? 0;
      final net = (gross - r - n).clamp(0, double.infinity);
      netCtrl.text = net.toStringAsFixed(0);
    }

    final saved = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (modalContext) => Padding(
        padding: EdgeInsets.fromLTRB(
          18,
          18,
          18,
          18 + MediaQuery.of(modalContext).viewInsets.bottom,
        ),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '${fvText(row['company_name'], missing: fvText(row['symbol']))} · '
                '${isCash ? '現金股利微調' : '股票股利微調'}',
                style: const TextStyle(
                  color: fvInk,
                  fontSize: 17,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                '除權息日 ${fvText(row['ex_date'])} · 基準持股 ${legacy.accountingNumber(row['eligible_shares'])} 股',
                style: const TextStyle(color: fvMuted, fontSize: 12),
              ),
              const SizedBox(height: 12),
              if (isCash) ...[
                Text('試算現金毛額：${legacy.accountingNumber(gross)} 元'),
                const SizedBox(height: 10),
                Wrap(
                  spacing: 8,
                  runSpacing: 6,
                  children: [
                    ActionChip(
                      key: const Key('remit-fee-zero'),
                      label: const Text('同銀行免匯費 (0元)'),
                      onPressed: () {
                        remitCtrl.text = '0';
                        recomputeNet();
                      },
                    ),
                    ActionChip(
                      key: const Key('remit-fee-ten'),
                      label: const Text('跨行匯費 (10元)'),
                      onPressed: () {
                        remitCtrl.text = '10';
                        recomputeNet();
                      },
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                TextField(
                  key: const Key('edit-remit-fee'),
                  controller: remitCtrl,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(labelText: '銀行匯費（元）'),
                  onChanged: (_) => recomputeNet(),
                ),
                const SizedBox(height: 8),
                TextField(
                  key: const Key('edit-nhi-fee'),
                  controller: nhiCtrl,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(labelText: '二代健保補充保費（元）'),
                  onChanged: (_) => recomputeNet(),
                ),
                const SizedBox(height: 8),
                TextField(
                  key: const Key('edit-net-cash'),
                  controller: netCtrl,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(labelText: '實領現金金額（元）'),
                ),
              ] else ...[
                TextField(
                  key: const Key('edit-stock-shares'),
                  controller: stockCtrl,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(labelText: '實得股票股利（股）'),
                ),
              ],
              const SizedBox(height: 8),
              TextField(
                controller: noteCtrl,
                decoration: const InputDecoration(labelText: '備註（選填）'),
              ),
              const SizedBox(height: 16),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: () => Navigator.pop(modalContext, false),
                    child: const Text('取消'),
                  ),
                  const SizedBox(width: 8),
                  FilledButton(
                    key: const Key('save-dividend-patch'),
                    style: FilledButton.styleFrom(backgroundColor: fvTeal),
                    onPressed: () => Navigator.pop(modalContext, true),
                    child: const Text('儲存微調'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );

    if (saved == true && mounted) {
      final body = <String, dynamic>{
        if (isCash) 'estimated_remit_fee': remitCtrl.text.trim(),
        if (isCash) 'estimated_nhi_fee': nhiCtrl.text.trim(),
        if (isCash) 'net_cash_amount': netCtrl.text.trim(),
        if (!isCash) 'confirmed_stock_shares': stockCtrl.text.trim(),
        if (noteCtrl.text.trim().isNotEmpty) 'user_note': noteCtrl.text.trim(),
      };
      try {
        await widget.api
            .patch('/api/v1/me/dividends/pending/${row['draft_id']}', body)
            .timeout(const Duration(seconds: 10));
        await refreshList();
      } catch (error) {
        if (mounted) {
          setState(() => errorMessage = '儲存微調失敗：$error');
        }
      }
    }
    remitCtrl.dispose();
    nhiCtrl.dispose();
    netCtrl.dispose();
    stockCtrl.dispose();
    noteCtrl.dispose();
  }

  Future<void> confirmSelected() async {
    if (busy || selectedIds.isEmpty) return;
    setState(() {
      busy = true;
      errorMessage = null;
    });
    try {
      final response = await widget.api.post(
        '/api/v1/me/dividends/pending/confirm',
        {
          'draft_ids': selectedIds.toList(),
          'expected_ledger_version': ledgerVersion,
        },
      ).timeout(const Duration(seconds: 15));
      if (!mounted) return;
      anyCommitted = true;
      final confirmedCount = fvInt(fvMap(response)['confirmed_count']);
      await refreshList();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('已將 $confirmedCount 筆股利入帳至交易紀錄')),
      );
      if (items.isEmpty) {
        Navigator.pop(context, true);
      }
    } catch (error) {
      if (!mounted) return;
      final text = error.toString();
      setState(() => errorMessage = text.contains('版本') || text.contains('409')
          ? '交易版本已變動，已為你重新載入最新股利試算'
          : '入帳失敗：$text');
      await refreshList(clearError: false);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> dismissSelected() async {
    if (busy || selectedIds.isEmpty) return;
    setState(() {
      busy = true;
      errorMessage = null;
    });
    try {
      await widget.api.post(
        '/api/v1/me/dividends/pending/dismiss',
        {'draft_ids': selectedIds.toList()},
      ).timeout(const Duration(seconds: 12));
      await refreshList();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('已忽略所選股利草稿')),
      );
    } catch (error) {
      if (!mounted) return;
      setState(() => errorMessage = '忽略失敗：$error');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final groups = <String, List<Map<String, dynamic>>>{};
    for (final row in items) {
      final key = '${fvText(row['symbol'])}|${fvText(row['ex_date'])}';
      groups.putIfAbsent(key, () => <Map<String, dynamic>>[]).add(row);
    }

    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) Navigator.pop(context, anyCommitted);
      },
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 12, 8),
            child: Wrap(
              spacing: 8,
              runSpacing: 8,
              alignment: WrapAlignment.spaceBetween,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      '待確認股利核對',
                      style: TextStyle(
                        color: fvInk,
                        fontSize: 19,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    Text(
                      '帳本版本 v$ledgerVersion · 核對後寫入交易紀錄',
                      style: const TextStyle(color: fvMuted, fontSize: 12),
                    ),
                  ],
                ),
                Wrap(
                  spacing: 6,
                  children: [
                    OutlinedButton.icon(
                      key: const Key('sheet-scan-dividends'),
                      onPressed: busy ? null : scanHistory,
                      icon: const Icon(Icons.manage_search, size: 18),
                      label: const Text('掃描歷史'),
                    ),
                    IconButton(
                      onPressed: () => Navigator.pop(context, anyCommitted),
                      icon: const Icon(Icons.close),
                      tooltip: '關閉',
                    ),
                  ],
                ),
              ],
            ),
          ),
          if (errorMessage != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
              child: fvBoundedState(errorMessage!, icon: Icons.warning_amber),
            ),
          if (items.isNotEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
              child: Wrap(
                spacing: 8,
                runSpacing: 6,
                children: [
                  ActionChip(
                    key: const Key('select-payable-dividends'),
                    label: const Text('選取已達發放日'),
                    onPressed: () => setState(_selectPayableByDefault),
                  ),
                  ActionChip(
                    key: const Key('select-all-dividends'),
                    label: const Text('全選'),
                    onPressed: () => setState(() {
                      selectedIds
                        ..clear()
                        ..addAll(items
                            .where(_canConfirm)
                            .map((r) => fvText(r['draft_id'], missing: ''))
                            .where((id) => id.isNotEmpty));
                    }),
                  ),
                  ActionChip(
                    label: const Text('清除選取'),
                    onPressed: () => setState(selectedIds.clear),
                  ),
                ],
              ),
            ),
          Expanded(
            child: loading
                ? const Center(child: CircularProgressIndicator())
                : items.isEmpty
                    ? Center(
                        child: Padding(
                          padding: const EdgeInsets.all(24),
                          child: fvBoundedState('目前沒有待確認的股利項目，可點擊右上角「掃描歷史」檢查過去持股期間漏記股利。'),
                        ),
                      )
                    : ListView(
                        padding: const EdgeInsets.fromLTRB(16, 8, 16, 20),
                        children: [
                          for (final entry in groups.entries)
                            _buildGroupCard(entry.value),
                        ],
                      ),
          ),
          Container(
            decoration: const BoxDecoration(
              color: Colors.white,
              border: Border(top: BorderSide(color: Color(0xFFE0E9E9))),
            ),
            padding: const EdgeInsets.fromLTRB(16, 10, 16, 14),
            child: Wrap(
              spacing: 10,
              runSpacing: 8,
              alignment: WrapAlignment.spaceBetween,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                OutlinedButton(
                  key: const Key('dismiss-selected-dividends'),
                  onPressed: busy || selectedIds.isEmpty ? null : dismissSelected,
                  child: const Text('忽略已選'),
                ),
                FilledButton.icon(
                  key: const Key('confirm-selected-dividends'),
                  style: FilledButton.styleFrom(backgroundColor: fvTeal),
                  onPressed: busy || selectedIds.isEmpty ? null : confirmSelected,
                  icon: const Icon(Icons.check_circle_outline, size: 18),
                  label: Text('確認入帳 (${selectedIds.length})'),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildGroupCard(List<Map<String, dynamic>> group) {
    final head = group.first;
    final symbol = fvText(head['symbol']);
    final name = fvText(head['company_name'], missing: symbol);
    final payable = _isPayable(head);
    final paymentText = fvText(head['payment_date'], missing: '尚未公告');

    return fvPanel(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            spacing: 8,
            runSpacing: 6,
            alignment: WrapAlignment.spaceBetween,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Text(
                '$symbol $name',
                style: const TextStyle(
                  color: fvInk,
                  fontSize: 16,
                  fontWeight: FontWeight.w800,
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: payable ? fvSoft : const Color(0xFFFFEEE1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  payable ? '已發放（可核對入帳）' : '已除息（待發放）',
                  style: TextStyle(
                    color: payable ? fvTeal : fvInk,
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            '除權息日 ${fvText(head['ex_date'])} · 發放日 $paymentText · 基準股數 ${legacy.accountingNumber(head['eligible_shares'])} 股',
            style: const TextStyle(color: fvMuted, fontSize: 12),
          ),
          const Divider(height: 16),
          for (final row in group) _buildDraftItem(row),
        ],
      ),
    );
  }

  Widget _buildDraftItem(Map<String, dynamic> row) {
    final id = fvText(row['draft_id'], missing: '');
    final isCash = row['action_type'] == 'CASH_DIVIDEND';
    final selected = selectedIds.contains(id);
    final canSelect = _canConfirm(row);
    final warnings = fvRows(row['warnings']).map((w) => '$w').toList();

    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Checkbox(
                key: Key('dividend-check-$id'),
                value: selected,
                onChanged: !canSelect
                    ? null
                    : (checked) => setState(() {
                          if (checked == true) {
                            selectedIds.add(id);
                          } else {
                            selectedIds.remove(id);
                          }
                        }),
              ),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Wrap(
                      spacing: 8,
                      runSpacing: 4,
                      alignment: WrapAlignment.spaceBetween,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        Text(
                          isCash ? '現金股利' : '股票股利',
                          style: const TextStyle(
                            color: fvInk,
                            fontWeight: FontWeight.w700,
                            fontSize: 14,
                          ),
                        ),
                        Text(
                          isCash
                              ? '+${legacy.accountingNumber(row['net_cash_amount'])} 元'
                              : '+${legacy.accountingNumber(row['confirmed_stock_shares'])} 股',
                          style: const TextStyle(
                            color: fvTeal,
                            fontWeight: FontWeight.w800,
                            fontSize: 15,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 3),
                    if (isCash)
                      Text(
                        '毛額 ${legacy.accountingNumber(row['gross_cash_amount'])} · '
                        '匯費 ${legacy.accountingNumber(row['estimated_remit_fee'])} · '
                        '健保 ${legacy.accountingNumber(row['estimated_nhi_fee'])}',
                        style: const TextStyle(color: fvMuted, fontSize: 12),
                      )
                    else
                      Text(
                        '配股率 ${fvText(row['rate_per_share'])} · '
                        '畸零股 ${fvText(row['fractional_shares'], missing: '0')}',
                        style: const TextStyle(color: fvMuted, fontSize: 12),
                      ),
                    for (final code in warnings)
                      Padding(
                        padding: const EdgeInsets.only(top: 3),
                        child: Text(
                          '• ${_warningLabel(code)}',
                          style: const TextStyle(color: fvMuted, fontSize: 11),
                        ),
                      ),
                  ],
                ),
              ),
              TextButton(
                key: Key('dividend-edit-$id'),
                onPressed: busy ? null : () => editDraft(row),
                child: const Text('微調'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
