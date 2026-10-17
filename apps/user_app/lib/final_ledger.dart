import 'dart:async';

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
    this.now = DateTime.now,
    super.key,
  });

  final legacy.Api api;
  final ValueChanged<String>? onOpenStock;
  final bool active;
  final DateTime Function() now;

  @override
  State<FinalLedgerPage> createState() => _FinalLedgerPageState();
}

class _FinalLedgerPageState extends State<FinalLedgerPage>
    with WidgetsBindingObserver {
  int section = 0;
  int recordGrouping = 0;
  int yearFilter = DateTime.now().year;
  final Map<String, Future<dynamic>> requestCache = {};
  late Future<List<dynamic>> coreData = loadCore();
  List<dynamic>? deferredCore;
  int deferredGeneration = 0;
  Future<List<dynamic>>? sectionData;
  Timer? quoteTimer;
  Timer? recalcTimer;
  bool quoteBusy = false;
  bool pnlRecalcBusy = false;
  bool recalcPollBusy = false;
  Map<String, dynamic>? recalcStatus;
  bool foreground = true;
  int quoteGeneration = 0;
  DateTime? offSessionQuoteDate;
  DateTime? post1430QuoteDate;
  Map<String, dynamic>? intraday;
  String? quoteError;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    loadDeferredCore();
    foreground = WidgetsBinding.instance.lifecycleState == null ||
        WidgetsBinding.instance.lifecycleState == AppLifecycleState.resumed;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) startQuotes();
    });
  }

  bool get quotesActive =>
      widget.active &&
      section == 0 &&
      foreground &&
      (ModalRoute.of(context)?.isCurrent ?? true);

  DateTime get taipeiNow =>
      widget.now().toUtc().add(const Duration(hours: 8));

  bool _sameTaipeiDay(DateTime? left, DateTime right) =>
      left != null &&
      left.year == right.year &&
      left.month == right.month &&
      left.day == right.day;

  bool _marketHoursAt(DateTime taipei) {
    final minutes = taipei.hour * 60 + taipei.minute;
    return taipei.weekday <= 5 && minutes >= 540 && minutes < 810;
  }

  bool get marketHours => _marketHoursAt(taipeiNow);

  bool _after1430(DateTime taipei) {
    final minutes = taipei.hour * 60 + taipei.minute;
    return taipei.weekday <= 5 && minutes >= 870;
  }

  bool _closingPending(DateTime taipei) {
    final minutes = taipei.hour * 60 + taipei.minute;
    return taipei.weekday <= 5 && minutes >= 810 && minutes < 870;
  }

  void startQuotes() {
    quoteTimer?.cancel();
    if (!quotesActive) return;
    final now = taipeiNow;
    if (_marketHoursAt(now)) {
      quoteTimer = Timer.periodic(const Duration(minutes: 1), (_) {
        if (!marketHours) {
          quoteTimer?.cancel();
          startQuotes();
        } else if (quotesActive) {
          unawaited(refreshQuotes());
        }
      });
      unawaited(refreshQuotes());
      return;
    }
    if (_after1430(now)) {
      if (!_sameTaipeiDay(post1430QuoteDate, now)) {
        unawaited(refreshQuotes());
      }
      return;
    }
    if (!_sameTaipeiDay(offSessionQuoteDate, now)) {
      unawaited(refreshQuotes());
    }
    if (_closingPending(now)) {
      final handoff = DateTime(now.year, now.month, now.day, 14, 30);
      final delay = handoff.difference(now);
      if (!delay.isNegative) {
        quoteTimer = Timer(delay, () {
          if (quotesActive) unawaited(refreshQuotes());
        });
      }
    }
  }

  Future<void> refreshQuotes({bool force = false}) async {
    if (!quotesActive || quoteBusy) return;
    final generation = quoteGeneration;
    setState(() => quoteBusy = true);
    try {
      final result = await (force
              ? widget.api.post('/api/v1/me/portfolio/quotes/refresh', const {})
              : widget.api.get('/api/v1/me/portfolio/quotes'))
          .timeout(const Duration(seconds: 9));
      if (mounted && generation == quoteGeneration && quotesActive) {
        final local = taipeiNow;
        setState(() {
          intraday = Map<String, dynamic>.from(result as Map);
          quoteError = null;
          if (!_marketHoursAt(local)) {
            offSessionQuoteDate = local;
            if (_after1430(local)) post1430QuoteDate = local;
          }
        });
        if (intraday!['market_open'] == false && !_closingPending(local)) {
          quoteTimer?.cancel();
        }
      }
    } catch (_) {
      if (mounted && generation == quoteGeneration && quotesActive) {
        setState(() => quoteError = '報價暫時無法更新，保留最後資料；請查看報價時間');
      }
    } finally {
      if (mounted && generation == quoteGeneration) {
        setState(() => quoteBusy = false);
      }
    }
  }

  @override
  void didUpdateWidget(FinalLedgerPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.active != widget.active) {
      quoteGeneration++;
      quoteBusy = false;
      quoteTimer?.cancel();
      if (widget.active && section == 0) {
        // Re-entering the holdings tab must NOT restart the quote/EOD clock.
        // Refresh owner cash/snapshot independently of the MIS quote cycle.
        requestCache.remove('/api/v1/me/portfolio/snapshot');
        coreData = loadCore();
        intraday = null;
        startQuotes();
      }
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    foreground = state == AppLifecycleState.resumed;
    if (!foreground) {
      quoteTimer?.cancel();
      quoteGeneration++;
      quoteBusy = false;
    } else if (section == 0) {
      startQuotes();
    }
  }

  @override
  void dispose() {
    quoteGeneration++;
    deferredGeneration++;
    quoteTimer?.cancel();
    recalcTimer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  Future<dynamic> safe(String path) async {
    try {
      return await widget.api.get(path).timeout(const Duration(seconds: 9));
    } catch (_) {
      return null;
    }
  }

  Future<dynamic> cached(String path) =>
      requestCache.putIfAbsent(path, () => safe(path));

  // The first holdings frame must not wait for history, annual PnL, or queue.
  Future<List<dynamic>> loadCore() async {
    final stopwatch = Stopwatch()..start();
    try {
      final snapshot = await cached('/api/v1/me/portfolio/snapshot');
      if (snapshot is Map &&
          snapshot['items'] is List &&
          snapshot['positions'] is List) {
        return [snapshot['items'], snapshot['positions'], snapshot];
      }
      // Compatibility fallback for previous revisions and bounded failure.
      return await Future.wait([
        cached('/api/v1/me/portfolio/summary'),
        cached('/api/v1/me/journal/positions'),
        safe('/api/v1/me/cash-position'),
      ]);
    } finally {
      stopwatch.stop();
      FinalPerf.recordCore('ledger', stopwatch.elapsed);
    }
  }

  void loadDeferredCore() {
    final generation = ++deferredGeneration;
    final currentYear = DateTime.now().year;
    coreData.then((_) async {
      final result = await Future.wait([
        cached('/api/v1/me/journal/pnl?year=$currentYear'),
        cached('/api/v1/me/journal/history?year=$currentYear'),
        cached('/api/v1/me/journal/recalculation-status'),
      ]);
      if (mounted && generation == deferredGeneration) {
        setState(() => deferredCore = result);
      }
    });
  }

  Future<List<dynamic>> loadSection(int target, int year) {
    return switch (target) {
      1 => Future.wait([
          cached('/api/v1/me/journal/history?year=$year'),
          cached('/api/v1/me/journal/monthly-summary?year=$year'),
          cached('/api/v1/me/journal/symbol-summary?year=$year'),
          cached('/api/v1/me/journal/pnl?year=$year'),
        ]),
      2 => Future.wait([
          cached('/api/v1/me/journal/pnl?year=$year'),
          cached('/api/v1/me/portfolio/performance?year=$year'),
          cached('/api/v1/me/journal/monthly-summary?year=$year'),
          cached('/api/v1/me/journal/history?year=$year'),
        ]),
      3 => Future.wait([cached('/api/v1/me/notes')]),
      _ => Future.value(const <dynamic>[]),
    };
  }

  void reload() {
    quoteGeneration++;
    quoteTimer?.cancel();
    setState(() {
      requestCache.clear();
      deferredCore = null;
      coreData = loadCore();
      sectionData = section == 0 ? null : loadSection(section, yearFilter);
      intraday = null;
      quoteError = null;
      quoteBusy = false;
      offSessionQuoteDate = null;
      post1430QuoteDate = null;
    });
    loadDeferredCore();
    if (section == 0) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) startQuotes();
      });
    }
  }

  void selectYear(int year) {
    if (year == yearFilter) return;
    setState(() {
      yearFilter = year;
      if (section == 1 || section == 2) {
        sectionData = loadSection(section, year);
      }
    });
  }

  Widget yearSelector() {
    final currentYear = DateTime.now().year;
    return MenuAnchor(
      builder: (context, controller, child) => OutlinedButton.icon(
        key: const Key('ledger-year-selector'),
        onPressed: () =>
            controller.isOpen ? controller.close() : controller.open(),
        icon: const Icon(Icons.calendar_month, size: 18),
        label: Text('年度：$yearFilter'),
      ),
      menuChildren: [
        for (var year = currentYear; year >= currentYear - 5; year--)
          MenuItemButton(
            onPressed: () => selectYear(year),
            child: Text('$year 年'),
          ),
      ],
    );
  }

  Future<void> addTrade() async {
    final payload = await legacy.transactionDialog(context, api: widget.api);
    if (payload == null) return;
    var saveStarted = false;
    try {
      final preview = await widget.api.post('/api/v1/me/journal/preview', payload)
          .timeout(const Duration(seconds: 5));
      if (!mounted) return;
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('交易試算'),
          content: SingleChildScrollView(child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('預估淨收付 ${legacy.accountingNumber(preview['net_cash_flow'])}'),
            Text('預估已實現損益 ${legacy.accountingNumber(preview['transaction_realized_pnl'], missing: '不適用')}'),
            Text('交易後股數 ${legacy.accountingNumber(preview['remaining_shares'])}'),
            Text('交易後平均成本 ${legacy.accountingNumber(preview['remaining_average_cost'], decimals: 2)}'),
            const SizedBox(height: 12),
            const Text('此為試算，尚未入帳。請確認實際成交價格、股數與費稅。'),
          ])),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('取消')),
            FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('確認成交並儲存')),
          ],
        ),
      );
      if (confirmed != true || !mounted) return;
      saveStarted = true;
      final saved = await widget.api.post('/api/v1/me/journal/events', {
        ...payload,
        'expected_ledger_version': preview['based_on_ledger_version'],
        'expected_broker_profile_version': preview['broker_profile_version'],
      });
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('交易已保存：股數 ${legacy.accountingNumber(fvMap(saved['transaction_result'])['remaining_shares'])}；${legacy.portfolioPendingMessage}')),
      );
      reload();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(saveStarted
              ? '交易結果尚未確認，請先重新載入核對紀錄'
              : '試算失敗，交易尚未送出')),
        );
        if (saveStarted) reload();
      }
    }
  }

  Future<void> correctTrade(Map<String, dynamic> row) async {
    final replacement = await legacy.transactionDialog(
      context,
      api: widget.api,
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
          const SnackBar(content: Text('更正結果尚未確認，請重新載入核對紀錄')),
        );
        reload();
      }
    }
  }

  Future<void> deleteTrade(Map<String, dynamic> row) async {
    final confirmed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) => AlertDialog(
        title: const Text('刪除這筆交易？'),
        content: const Text(
          '系統會用作廢（REVERSAL）取消這筆交易，不會物理刪除原始紀錄。'
          '持股與損益會重新計算，原始資料仍保留供稽核。',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('取消'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(dialogContext).colorScheme.error,
              foregroundColor: Theme.of(dialogContext).colorScheme.onError,
            ),
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('確認刪除'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    try {
      await widget.api.post(
        '/api/v1/me/journal/events/${row['event_id']}/reversals',
        {'expected_version': row['record_version']},
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('交易已作廢，持股與損益重新計算中')),
      );
      reload();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('作廢結果尚未確認，請重新載入核對紀錄；相依交易可能阻擋作廢'),
          ),
        );
        reload();
      }
    }
  }

  bool recalcActive(Map<String, dynamic>? value) =>
      {'QUEUED', 'RUNNING', 'CANCEL_REQUESTED'}.contains(value?['status']);

  String recalcLabel(Map<String, dynamic>? value) {
    return switch (value?['status']) {
      'QUEUED' => '已排隊，等待重算',
      'RUNNING' => '損益重算中…',
      'CANCEL_REQUESTED' => '正在中止重算…',
      'FAILED' => '重算失敗：${fvText(value?['message'], missing: '可重新嘗試')}',
      'CANCELLED' => '本次重算已中止：${fvText(value?['message'], missing: '可重新嘗試')}',
      _ => '',
    };
  }

  void startRecalcPolling() {
    if (!recalcActive(recalcStatus) || recalcTimer?.isActive == true) return;
    recalcTimer = Timer.periodic(const Duration(seconds: 3), (_) {
      unawaited(refreshRecalcStatus());
    });
  }

  Future<void> refreshRecalcStatus() async {
    if (!mounted || recalcPollBusy) return;
    recalcPollBusy = true;
    try {
      final result = await widget.api
          .get('/api/v1/me/journal/recalculation-status')
          .timeout(const Duration(seconds: 9));
      if (!mounted) return;
      final next = Map<String, dynamic>.from(result as Map);
      final wasActive = recalcActive(recalcStatus);
      setState(() => recalcStatus = next);
      if (recalcActive(next)) {
        startRecalcPolling();
      } else {
        recalcTimer?.cancel();
        if (wasActive) reload();
      }
    } catch (_) {
      // Keep the last visible state; user can manually refresh the page.
    } finally {
      recalcPollBusy = false;
    }
  }

  Future<void> recalculatePnl() async {
    if (pnlRecalcBusy || recalcActive(recalcStatus)) return;
    setState(() => pnlRecalcBusy = true);
    try {
      final result =
          await widget.api.post('/api/v1/me/journal/recalculate', const {});
      if (!mounted) return;
      setState(() => recalcStatus = Map<String, dynamic>.from(result as Map));
      startRecalcPolling();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('損益已排入重新計算')),
      );
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('損益重新計算無法排入，請稍後重試')),
        );
      }
    } finally {
      if (mounted) setState(() => pnlRecalcBusy = false);
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

  String assetWan(Object? value) {
    if (value == null) return '—';
    final amount = double.tryParse('$value');
    if (amount == null || !amount.isFinite) return '—';
    return '${(amount / 10000).toStringAsFixed(1)} 萬元';
  }

  Widget assetOverview(Map<String, dynamic> assets) {
    final cash = fvMap(assets['cash']);
    final cashText = cash['cash_status'] == 'available'
        ? assetWan(cash['cash_balance']) : '未設定';
    final formalAssets = assets['asset_status'] == 'available';
    final referenceAssets = !formalAssets &&
        assets['reference_asset_status'] == 'available';
    final partialAssets = !formalAssets && !referenceAssets &&
        assets['reference_partial_asset_status'] == 'partial';
    final totalText = formalAssets
        ? assetWan(assets['total_asset_value'])
        : referenceAssets
            ? assetWan(assets['reference_total_asset_value'])
            : partialAssets
                ? assetWan(assets['reference_partial_asset_value'])
                : '待完整估值';
    return Card(
      key: const Key('ledger-total-assets'),
      color: Colors.white,
      margin: const EdgeInsets.only(bottom: 10),
      elevation: 0,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('總資產', style: TextStyle(color: fvInk,
            fontSize: 16, fontWeight: FontWeight.w800)),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('現金部位', style: TextStyle(color: fvMuted, fontSize: 11)),
                Text(cashText, maxLines: 1, overflow: TextOverflow.ellipsis,
                  style: const TextStyle(color: fvInk, fontSize: 20,
                    fontWeight: FontWeight.w800)),
              ])),
            const SizedBox(width: 8),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(partialAssets ? '現金＋已計價部分'
                    : referenceAssets ? '現金＋參考市值' : '現金＋持股市值',
                  style: const TextStyle(color: fvMuted, fontSize: 11)),
                Text(totalText, maxLines: 1, overflow: TextOverflow.ellipsis,
                  style: const TextStyle(color: fvInk, fontSize: 20,
                    fontWeight: FontWeight.w800)),
              ])),
          ]),
          const SizedBox(height: 5),
          Text(partialAssets
              ? '僅含已取得報價的持股，未計價部分不包含在內'
              : referenceAssets
                  ? '萬元／小數一位 · 參考估值非正式結算 ·「我的」可修改現金'
                  : '萬元／小數一位 · 可至「我的 → 現金部位」修改',
            maxLines: 2, overflow: TextOverflow.ellipsis,
            style: const TextStyle(color: fvMuted, fontSize: 10)),
        ]),
      ),
    );
  }

  Widget metricGrid({
    required String marketValue,
    required String unrealized,
    required String unrealizedReturn,
    required String ytd,
    required Object? unrealizedAmount,
    required Object? unrealizedReturnAmount,
    required Object? ytdAmount,
    required Map<String, dynamic> aggregate,
    required bool withheld,
    required bool usingReference,
    required bool usingPartial,
  }) => Card(
    margin: const EdgeInsets.only(bottom: 10),
    elevation: 0,
    clipBehavior: Clip.antiAlias,
    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
    child: Container(
      padding: const EdgeInsets.all(18),
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft, end: Alignment.bottomRight,
          colors: [Color(0xFFFFFFFF), Color(0xFFEAF9FB)],
        ),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        const Icon(Icons.account_balance_wallet_outlined, color: fvTeal, size: 22),
        const SizedBox(width: 9),
        Expanded(child: Text(usingPartial ? '持股已計價小計'
            : usingReference ? '持股參考市值' : '持股市值',
          style: const TextStyle(color: fvInk, fontSize: 17, fontWeight: FontWeight.w800))),
        fvStatusPill(withheld ? 'partial' :
          aggregate['valuation_status'] ?? aggregate['aggregate_status'] ?? 'partial'),
      ]),
      const SizedBox(height: 8),
      Text(marketValue,
        key: const Key('ledger-market-value-hero'),
        maxLines: 2, overflow: TextOverflow.ellipsis,
        style: TextStyle(color: withheld && !usingReference && !usingPartial ? fvMuted : fvInk,
          fontSize: 30, fontWeight: FontWeight.w900, height: 1.17)),
      const SizedBox(height: 8),
      // Only one Hero. Secondary totals stay visually subordinate and share
      // the same panel rather than occupying two large empty white cards.
      const Divider(height: 14),
      LayoutBuilder(builder: (context, constraints) {
        final narrow = constraints.maxWidth < 420;
        final fields = <Widget>[
          _compactMetric(usingPartial ? '已計價損益小計'
              : usingReference ? '參考未實現損益' : '未實現損益', unrealized,
            note: '報酬 $unrealizedReturn',
            color: withheld && !usingReference && !usingPartial ? fvMuted : fvSignedColor(unrealizedAmount)),
          _compactMetric('本年已實現損益', ytd,
            note: ytd == '待更新／尚未確認' ? '等候損益批次'
                : ytd == '資料不足' ? '年度損益目前無法確認'
                : ytd == '0' ? '本年度確認無交易'
                : '已實現損益', color: fvSignedColor(ytdAmount)),
        ];
        return narrow
          ? Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Expanded(child: fields[0]), const SizedBox(width: 10),
              Expanded(child: fields[1]),
            ])
          : Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Expanded(child: fields[0]), const SizedBox(width: 24),
              Expanded(child: fields[1]),
            ]);
      }),
      const SizedBox(height: 10),
      Row(children: [
        const Icon(Icons.update, color: fvMuted, size: 15),
        const SizedBox(width: 5),
        Expanded(child: Text(
          usingPartial
              ? '已計價 ${fvText(aggregate['reference_priced_symbol_count'])}/${fvText(aggregate['reference_total_symbol_count'])} 檔 · 其餘未包含'
              : usingReference
                  ? '參考報價日 ${fvRows(aggregate['reference_price_dates']).join('／')} · 非正式收盤總額'
                  : '估值日 ${fvText(aggregate['valuation_date'])} · '
                '狀態 ${withheld ? '完整總額暫不發布' : legacy.uiLabel(aggregate['valuation_status'] ?? aggregate['aggregate_status'] ?? 'partial')}',
          style: const TextStyle(color: fvMuted, fontSize: 11))),
      ]),
      if (withheld && !usingReference && !usingPartial && aggregate['priced_symbol_count'] != null)
        Text(
          '已計價小計 ${fvText(aggregate['currency'])} '
          '${legacy.accountingNumber(aggregate['priced_market_value'])} '
          '· ${fvText(aggregate['priced_symbol_count'])} 檔（非完整總市值）',
          style: const TextStyle(color: fvMuted, fontSize: 11),
        ),
      Text('ledger v${fvText(aggregate['ledger_version'])}',
        style: const TextStyle(color: fvMuted, fontSize: 10)),
      ]),
    ),
  );

  Widget _compactMetric(String title, String value,
      {required String note, required Color color}) =>
    Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(title, style: const TextStyle(color: fvMuted, fontSize: 12)),
      const SizedBox(height: 5),
      Text(value, maxLines: 2, overflow: TextOverflow.ellipsis,
        style: TextStyle(color: color, fontSize: 18, fontWeight: FontWeight.w800)),
      Text(note, maxLines: 1, overflow: TextOverflow.ellipsis,
        style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w600)),
    ]);

  Widget pnlComparison(List<dynamic> rows, Map<String, dynamic> aggregate) {
    // Presentation-only scaling of published owner-scoped per-position PnL.
    // Do not create a portfolio aggregate or cross valuation checkpoints.
    final date = fvText(aggregate['valuation_date'], missing: '');
    final currency = fvText(aggregate['currency'], missing: '');
    if (date.isEmpty || currency.isEmpty || aggregate['aggregate_status'] == 'withheld') {
      return const SizedBox.shrink();
    }
    final items = <Map<String, dynamic>>[];
    for (final raw in rows) {
      final row = fvMap(raw);
      final pnl = fvNumber(row['unrealized_pnl']);
      if (pnl == null || !pnl.isFinite ||
          fvText(row['valuation_date'], missing: '') != date ||
          fvText(row['currency'], missing: '') != currency) continue;
      items.add(row);
    }
    if (items.isEmpty) return const SizedBox.shrink();
    items.sort((a, b) =>
      fvNumber(b['unrealized_pnl'])!.abs().compareTo(fvNumber(a['unrealized_pnl'])!.abs()));
    final largest = fvNumber(items.first['unrealized_pnl'])!.abs();
    return fvPanel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Row(children: [
        Icon(Icons.bar_chart_rounded, color: fvTeal, size: 20),
        SizedBox(width: 8),
        Expanded(child: Text('各持股未實現損益對照',
          style: TextStyle(color: fvInk, fontWeight: FontWeight.w800))),
      ]),
      const SizedBox(height: 5),
      Text('同一估值日 $date · $currency · 長度相對最大單檔',
          style: const TextStyle(color: fvMuted, fontSize: 11)),
      const SizedBox(height: 10),
      for (final row in items.take(5)) ...[
        Row(children: [
          Expanded(child: Text(legacy.stockDisplayName(row),
            maxLines: 1, overflow: TextOverflow.ellipsis,
            style: const TextStyle(color: fvInk, fontSize: 12))),
          const SizedBox(width: 8),
          Text(legacy.accountingNumber(row['unrealized_pnl']),
            style: TextStyle(color: fvSignedColor(row['unrealized_pnl']),
                fontWeight: FontWeight.w800, fontSize: 12)),
        ]),
        const SizedBox(height: 5),
        LayoutBuilder(builder: (context, bounds) {
          final factor = largest > 0
              ? fvNumber(row['unrealized_pnl'])!.abs() / largest : 0.0;
          return Align(alignment: Alignment.centerLeft, child: Container(
            key: Key('holding-comparison-${fvText(row['symbol'])}'),
            width: (bounds.maxWidth * factor).clamp(2.0, bounds.maxWidth),
            height: 7,
            decoration: BoxDecoration(
              color: fvSignedColor(row['unrealized_pnl']),
              borderRadius: BorderRadius.circular(5),
            ),
          ));
        }),
        const SizedBox(height: 10),
      ],
    ]));
  }

  Widget holdings(List<dynamic> positions) {
    if (positions.isEmpty) {
      return fvBoundedState('目前無持股或持股資料尚未取得');
    }
    final sorted = positions.map(fvMap).toList();
    // Put the largest confirmed daily moves first. Missing daily change
    // never becomes a fabricated zero or excludes the original holding.
    num magnitude(Map<String, dynamic> row) =>
        (fvNumber(row['day_change_amount']) ?? 0).abs();
    sorted.sort((a, b) => magnitude(b).compareTo(magnitude(a)));

    Widget header(String label, int flex, {TextAlign align = TextAlign.left}) =>
        Expanded(flex: flex, child: Text(label, textAlign: align,
            style: const TextStyle(color: fvMuted, fontSize: 10,
                fontWeight: FontWeight.w700)));

    return fvPanel(child: Column(children: [
      Row(children: [
        header('持股／股數', 30),
        header('現價／成本', 22, align: TextAlign.end),
        header('當日損益', 22, align: TextAlign.end),
        header('總損益', 26, align: TextAlign.end),
      ]),
      const Divider(height: 14),
      for (final row in sorted) ...[
        Builder(builder: (context) {
          final symbol = fvText(row['symbol']);
          final name = fvText(row['stock_name'], missing: symbol);
          final reference = row['price_status'] == 'stale' &&
              row['reference_eligible'] == true;
          final valid = (row['price_status'] == 'available' || reference) &&
              row['day_change_amount'] != null &&
              row['change_percent'] != null;
          final missingReason = legacy.portfolioMissingReasonLabel(
              row['missing_reason']);
          final hasPnl = (row['price_status'] == 'available' || reference) &&
              row['unrealized_pnl'] != null;
          return InkWell(
            key: Key('holding-row-$symbol'),
            onTap: () => widget.onOpenStock?.call(symbol),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Row(crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                Expanded(flex: 30, child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(children: [
                      Flexible(child: Text(name, maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(color: fvInk, fontSize: 13,
                            fontWeight: FontWeight.w800))),
                      if (reference) Tooltip(
                        message: '非即時報價 · ${fvText(row['price_date'])}',
                        child: const Padding(
                          padding: EdgeInsets.only(left: 3),
                          child: Icon(Icons.schedule, color: fvMuted, size: 12)),
                      ),
                      if (missingReason.isNotEmpty && !reference) Tooltip(
                        message: missingReason,
                        child: const Padding(
                          padding: EdgeInsets.only(left: 3),
                          child: Icon(Icons.info_outline, color: fvMuted, size: 12)),
                      ),
                    ]),
                    Text('$symbol · ${legacy.accountingNumber(row['shares'])} 股',
                      maxLines: 1, overflow: TextOverflow.ellipsis,
                      style: const TextStyle(color: fvMuted, fontSize: 10)),
                  ],
                )),
                Expanded(flex: 22, child: Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(legacy.accountingNumber(row['market_price'],
                          decimals: 2, missing: '—'),
                      key: Key('holding-latest-price-$symbol'),
                      maxLines: 1, overflow: TextOverflow.ellipsis,
                      style: TextStyle(color: valid ? fvSignedColor(row['change']) : fvInk,
                        fontSize: 13, fontWeight: FontWeight.w800)),
                    Text('成本 ${legacy.accountingNumber(row['average_cost'], decimals: 2)}',
                      maxLines: 1, overflow: TextOverflow.ellipsis,
                      style: const TextStyle(color: fvMuted, fontSize: 10)),
                  ],
                )),
                Expanded(flex: 22, child: Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(valid ? legacy.accountingNumber(
                        row['day_change_amount']) : '—',
                      key: Key('holding-day-amount-$symbol'),
                      maxLines: 1, overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: valid ? fvSignedColor(row['day_change_amount'])
                          : fvMuted,
                        fontWeight: FontWeight.w800, fontSize: 12)),
                    Text(valid ? fvSignedPercent(row['change_percent']) : '待行情',
                      key: Key('holding-daily-change-$symbol'),
                      maxLines: 1, overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: valid ? fvSignedColor(row['change_percent'])
                          : fvMuted, fontSize: 10)),
                  ],
                )),
                Expanded(flex: 26, child: Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(hasPnl ? legacy.accountingNumber(
                        row['unrealized_pnl']) : '—',
                      key: Key('holding-pnl-$symbol'),
                      maxLines: 1, overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: hasPnl ? fvSignedColor(row['unrealized_pnl'])
                          : fvMuted, fontWeight: FontWeight.w800, fontSize: 13)),
                    Text(hasPnl
                        ? '${legacy.portfolioReturnLabel(row['unrealized_return'])}${reference ? ' 參考' : ''}'
                        : '待估值',
                      key: Key('holding-return-$symbol'),
                      maxLines: 1, overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: hasPnl ? fvSignedColor(row['unrealized_return'])
                          : fvMuted, fontSize: 10)),
                  ],
                )),
              ]),
            ),
          );
        }),
        const Divider(height: 1),
      ],
      const SizedBox(height: 6),
      const Text('當日損益為持股價格變動估計，非當日實際交易損益。點擊個股查看來源、缺值原因及明細。',
        style: TextStyle(color: fvMuted, fontSize: 10)),
    ]));
  }

  String realizedPnlLabel(Map<String, dynamic>? row) {
    if (row == null) return '已實現損益 待更新';
    final currency = fvText(row['currency'], missing: 'TWD');
    return '已實現損益 $currency ${legacy.accountingNumber(row['realized_pnl'], missing: '資料不足')}';
  }

  String annualRealizedPnlLabel(dynamic raw, List<dynamic> history) {
    if (raw == null) return '年度已實現損益 資料不足';
    final rows = fvRows(raw);
    if (rows.isEmpty) {
      return history.isEmpty ? '年度已實現損益 0' : '年度已實現損益 待更新';
    }
    if (rows.length > 1) return '年度已實現損益 多幣別';
    return '年度${realizedPnlLabel(fvMap(rows.first))}';
  }

  Widget recordTile(Map<String, dynamic> row, int index) {
    final quantity = row['shares'] != null && row['price'] != null
        ? ' · ${legacy.accountingNumber(row['shares'])} 股 × ${legacy.accountingNumber(row['price'], decimals: 2)}'
        : '';
    return Material(color: fvDatedRowColor(index), child: ListTile(
      contentPadding: EdgeInsets.zero,
      dense: true,
      title: Text(
        '${legacy.uiLabel(row['event_type'])} · ${legacy.stockDisplayName(row)}',
      ),
      subtitle: Text('${fvText(row['trade_date'])}$quantity'),
      trailing: row['event_id'] != null && row['record_version'] != null
          ? Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                IconButton(
                  tooltip: '建立更正',
                  visualDensity: VisualDensity.compact,
                  icon: const Icon(Icons.edit_note),
                  onPressed: () => correctTrade(row),
                ),
                IconButton(
                  tooltip: '刪除交易',
                  visualDensity: VisualDensity.compact,
                  icon: const Icon(Icons.delete_outline),
                  color: Theme.of(context).colorScheme.error,
                  onPressed: () => deleteTrade(row),
                ),
              ],
            )
          : null,
    ));
  }

  Widget recordGroup({
    required Key key,
    required String title,
    required String realized,
    required Object? realizedAmount,
    required List<Map<String, dynamic>> events,
  }) =>
      fvPanel(
        padding: EdgeInsets.zero,
        child: ExpansionTile(
          key: key,
          initiallyExpanded: false,
          tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
          childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
          title: Text(
            title,
            style: const TextStyle(
              color: fvInk,
              fontSize: 16,
              fontWeight: FontWeight.w800,
            ),
          ),
          subtitle: Text(
            realized,
            style: TextStyle(
              color: realizedAmount == null
                  ? fvMuted
                  : fvSignedColor(realizedAmount),
              fontWeight: FontWeight.w700,
            ),
          ),
          children: [
            if (events.isEmpty)
              const Padding(
                padding: EdgeInsets.only(bottom: 10),
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: Text(
                    '目前沒有可顯示的交易明細',
                    style: TextStyle(color: fvMuted, fontSize: 12),
                  ),
                ),
              )
            else
              for (final (index, row) in events.indexed) recordTile(row, index),
          ],
        ),
      );

  Widget records(
    List<dynamic> history,
    List<dynamic> monthly,
    List<dynamic> symbolSummary,
  ) {
    final effective = fvNewestRows(legacy.effectiveLedgerEvents(history),
      fields: const ['trade_date'], recentOnly: yearFilter >= DateTime.now().year - 1);
    if (effective.isEmpty && monthly.isEmpty && symbolSummary.isEmpty) {
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
    final orderedMonths = months.toList()
      ..sort((left, right) => right.compareTo(left));

    final symbolSummaries = <String, Map<String, dynamic>>{};
    for (final item in symbolSummary) {
      final row = fvMap(item);
      final symbol = fvText(row['symbol'], missing: '');
      if (symbol.isNotEmpty) symbolSummaries[symbol] = row;
    }
    final symbols = <String>{...symbolSummaries.keys};
    for (final item in effective) {
      final symbol = fvText(fvMap(item)['symbol'], missing: '');
      if (symbol.isNotEmpty) symbols.add(symbol);
    }
    final orderedSymbols = symbols.toList()..sort();

    return Column(
      children: [
        Align(
          alignment: Alignment.centerLeft,
          child: SegmentedButton<int>(
            key: const Key('ledger-record-grouping'),
            style: SegmentedButton.styleFrom(foregroundColor: fvInk,
              selectedForegroundColor: Colors.white, selectedBackgroundColor: fvTeal),
            segments: const [
              ButtonSegment(value: 0, label: Text('按月份')),
              ButtonSegment(value: 1, label: Text('按個股')),
            ],
            selected: {recordGrouping},
            onSelectionChanged: (value) =>
                setState(() => recordGrouping = value.first),
            showSelectedIcon: false,
          ),
        ),
        const SizedBox(height: 12),
        if (recordGrouping == 0)
          for (final month in orderedMonths)
            recordGroup(
              key: Key('ledger-month-$month'),
              title: '$yearFilter 年 $month 月',
              realized: realizedPnlLabel(summaries[month]),
              realizedAmount: summaries[month]?['realized_pnl'],
              events: effective.where((item) {
                final row = fvMap(item);
                final day =
                    DateTime.tryParse(fvText(row['trade_date'], missing: ''));
                return day?.month == month;
              }).map(fvMap).toList(),
            ),
        if (recordGrouping == 1)
          for (final symbol in orderedSymbols)
            Builder(builder: (context) {
              final summary = symbolSummaries[symbol];
              final symbolEvents = effective
                  .where((item) =>
                      fvText(fvMap(item)['symbol'], missing: '') == symbol)
                  .map(fvMap)
                  .toList();
              final display = summary ??
                  (symbolEvents.isEmpty
                      ? <String, dynamic>{'symbol': symbol}
                      : symbolEvents.first);
              return recordGroup(
                key: Key('ledger-symbol-$symbol'),
                title: legacy.stockDisplayName(display),
                realized: realizedPnlLabel(summary),
                realizedAmount: summary?['realized_pnl'],
                events: symbolEvents,
              );
            }),
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
                  Text(
                    '已實現損益 ${legacy.accountingNumber(row['realized_pnl'])}',
                    style: TextStyle(
                      color: fvSignedColor(row['realized_pnl']),
                      fontWeight: FontWeight.w700,
                    ),
                  ),
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
                    style: status == 'available' && row['xirr'] != null
                        ? TextStyle(
                            color: fvSignedColor(row['xirr']),
                            fontWeight: FontWeight.w700,
                          )
                        : null,
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

  Widget notes(List<dynamic> values) {
    final rows = fvNewestRows(values, fields: const ['updated_at', 'created_at']);
    return Column(
        children: [
          Align(
            alignment: Alignment.centerRight,
            child: TextButton.icon(
              onPressed: addNote,
              icon: const Icon(Icons.add),
              label: const Text('新增筆記'),
            ),
          ),
          if (rows.isEmpty) fvBoundedState('近兩年沒有筆記'),
          for (final (index, item) in rows.indexed)
            Builder(builder: (context) {
              final row = fvMap(item);
              return fvPanel(
                color: fvDatedRowColor(index),
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
  }

  Widget lazySection(
    Future<List<dynamic>>? future,
    String loading,
    Widget Function(List<dynamic>) builder,
  ) {
    if (future == null) return fvBoundedState(loading);
    return FutureBuilder<List<dynamic>>(
      future: future,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return fvBoundedState(loading);
        }
        return builder(snapshot.data ?? const <dynamic>[]);
      },
    );
  }

  @override
  Widget build(BuildContext context) => ColoredBox(
        color: fvCanvas,
        child: SafeArea(
          bottom: false,
          child: FutureBuilder<List<dynamic>>(
            future: coreData,
            builder: (context, snapshot) {
              final values = snapshot.data ?? const [null, null];
              final summary = fvRows(values[0]);
              final canonicalPositions = fvRows(values[1]);
              final currentPnl = fvRows(deferredCore == null ? null : deferredCore![0]);
              final currentHistory = fvRows(deferredCore == null ? null : deferredCore![1]);
              final loadedRecalcStatus = deferredCore != null && deferredCore![2] is Map
                  ? Map<String, dynamic>.from(deferredCore![2] as Map)
                  : <String, dynamic>{'status': 'IDLE', 'can_retry': false};
              final effectiveRecalcStatus = recalcStatus ?? loadedRecalcStatus;
              if (recalcStatus == null && recalcActive(loadedRecalcStatus)) {
                WidgetsBinding.instance.addPostFrameCallback((_) {
                  if (!mounted || recalcStatus != null) return;
                  setState(() => recalcStatus = loadedRecalcStatus);
                  startRecalcPolling();
                });
              }
              final quotePositions = section == 0 && intraday != null
                  ? fvRows(intraday!['positions'])
                  : const <dynamic>[];
              final positions = section == 0 && intraday != null
                  ? quotePositions
                  : canonicalPositions;
              final quoteSummary = section == 0 && intraday != null
                  ? fvRows(intraday!['items'])
                  : const <dynamic>[];
              final aggregate = section == 0 && intraday != null
                  ? (quoteSummary.isEmpty
                      ? <String, dynamic>{}
                      : <String, dynamic>{
                          ...fvMap(quoteSummary.first),
                          'ledger_version': intraday!['ledger_version'],
                        })
                  : summary.isEmpty
                      ? <String, dynamic>{}
                      : fvMap(summary.first);
              final assets = section == 0 && intraday != null
                  ? intraday!
                  : values.length > 2 ? fvMap(values[2]) : <String, dynamic>{};
              final coreLoading =
                  snapshot.connectionState != ConnectionState.done;
              final withheld = aggregate['aggregate_status'] == 'withheld';
              final usingReference = withheld &&
                  aggregate['reference_status'] == 'available' &&
                  aggregate['reference_market_value'] != null;
              final usingPartial = withheld && !usingReference &&
                  (fvNumber(aggregate['reference_priced_symbol_count']) ?? 0) > 0 &&
                  aggregate['reference_priced_market_value'] != null;
              final currency = fvText(aggregate['currency'], missing: 'TWD');
              final marketValue = usingReference
                  ? '$currency ${legacy.accountingNumber(aggregate['reference_market_value'])}'
                  : usingPartial
                      ? '$currency ${legacy.accountingNumber(aggregate['reference_priced_market_value'])}'
                  : withheld
                      ? '總額暫不發布'
                  : aggregate.isEmpty
                      ? coreLoading
                          ? '載入中'
                          : '資料不足'
                      : '$currency ${legacy.accountingNumber(aggregate['market_value'], missing: '資料不足')}';
              final unrealized = usingReference
                  ? '$currency ${legacy.accountingNumber(aggregate['reference_unrealized_pnl'])}'
                  : usingPartial
                      ? '$currency ${legacy.accountingNumber(aggregate['reference_priced_unrealized_pnl'])}'
                  : withheld
                      ? '總額暫不發布'
                  : aggregate.isEmpty
                      ? coreLoading
                          ? '載入中'
                          : '資料不足'
                      : '$currency ${legacy.accountingNumber(aggregate['unrealized_pnl'], missing: '資料不足')}';
              final unrealizedReturn = usingReference
                  ? legacy.portfolioReturnLabel(aggregate['reference_unrealized_return'])
                  : usingPartial
                      ? legacy.portfolioReturnLabel(aggregate['reference_priced_unrealized_return'])
                  : withheld
                      ? '總額暫不發布'
                  : aggregate.isEmpty
                      ? coreLoading
                          ? '載入中'
                          : '資料不足'
                      : legacy.portfolioReturnLabel(
                          aggregate['unrealized_return'],
                        );
              final pnlUnavailable = deferredCore == null || deferredCore![0] == null;
              final historyUnavailable = deferredCore == null || deferredCore![1] == null;
              final ytd = deferredCore == null
                  ? '載入中'
                  : pnlUnavailable || historyUnavailable
                      ? '資料不足'
                      : currentPnl.isNotEmpty
                          ? currentPnl.length == 1
                              ? '${fvText(fvMap(currentPnl.first)['currency'], missing: 'TWD')} ${legacy.accountingNumber(fvMap(currentPnl.first)['realized_pnl'])}'
                              : '多幣別'
                          : currentHistory.isNotEmpty
                              ? '待更新／尚未確認'
                              : '0';
              final ytdAmount = currentPnl.length == 1
                  ? fvMap(currentPnl.first)['realized_pnl']
                  : null;
              final affected = fvRows(aggregate['affected_symbols']);

              final scrollContent = ListView(
                key: const Key('final-ledger-scroll'),
                padding: const EdgeInsets.fromLTRB(18, 18, 18, 110),
                children: [
                  const SizedBox(height: 12),
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
                  if (section == 0) assetOverview(assets),
                  if (section == 0) metricGrid(
                    marketValue: marketValue,
                    unrealized: unrealized,
                    unrealizedReturn: unrealizedReturn,
                    ytd: ytd,
                    unrealizedAmount: usingReference
                        ? aggregate['reference_unrealized_pnl']
                        : usingPartial ? aggregate['reference_priced_unrealized_pnl']
                        : aggregate['unrealized_pnl'],
                    unrealizedReturnAmount: usingReference
                        ? aggregate['reference_unrealized_return']
                        : usingPartial ? aggregate['reference_priced_unrealized_return']
                        : aggregate['unrealized_return'],
                    ytdAmount: ytdAmount,
                    aggregate: aggregate,
                    withheld: withheld,
                    usingReference: usingReference,
                    usingPartial: usingPartial,
                  ),
                  // Recalculation is an explicit Owner action, even when annual totals are ready.
                  // Do not hide the only manual recovery path behind YTD missingness.
                  if (section == 0) ...[
                    Align(
                      alignment: Alignment.centerLeft,
                      child: OutlinedButton.icon(
                        key: const Key('recalculate-pnl'),
                        onPressed: pnlRecalcBusy ||
                                recalcActive(effectiveRecalcStatus)
                            ? null
                            : recalculatePnl,
                        icon: const Icon(Icons.calculate_outlined, size: 18),
                        label: Text(
                          pnlRecalcBusy
                              ? '排入中'
                              : recalcActive(effectiveRecalcStatus)
                                  ? '重算進行中'
                                  : effectiveRecalcStatus['status'] == 'FAILED' ||
                                          effectiveRecalcStatus['status'] ==
                                              'CANCELLED'
                                      ? '重新嘗試'
                                      : '重新計算損益',
                        ),
                      ),
                    ),
                    if (recalcLabel(effectiveRecalcStatus).isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: 6),
                        child: Text(
                          recalcLabel(effectiveRecalcStatus),
                          key: const Key('recalculate-pnl-status'),
                          style: TextStyle(
                            color: effectiveRecalcStatus['status'] == 'FAILED'
                                ? Theme.of(context).colorScheme.error
                                : fvMuted,
                            fontSize: 12,
                          ),
                        ),
                      ),
                  ],
                  if (section == 0 && withheld)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 5),
                      child: Row(children: [
                        const Icon(Icons.info_outline, size: 15, color: fvMuted),
                        const SizedBox(width: 5),
                        Expanded(child: Text(
                          usingPartial
                            ? '目前顯示已計價部分，缺價持股不包含於小計。'
                            : usingReference
                                ? '以下為最近有效報價估算，正式結算待同步。'
                                : '暫無合格報價 · ${affected.length} 檔需確認。',
                          maxLines: 2, overflow: TextOverflow.ellipsis,
                          style: const TextStyle(color: fvMuted, fontSize: 11),
                        )),
                      ]),
                    ),
                  const SizedBox(height: 12),
                  if (section == 0) ...[
                    pnlComparison(positions, aggregate),
                    fvSectionTitle(context, '持股'),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        OutlinedButton.icon(
                          onPressed: quoteBusy
                              ? null
                              : () => refreshQuotes(force: true),
                          icon: const Icon(Icons.refresh, size: 18),
                          label: Text(
                            quoteBusy ? '更新中' : '更新持股股價',
                          ),
                        ),
                        FilledButton.icon(
                          onPressed: addTrade,
                          icon: const Icon(Icons.add, size: 18),
                          label: const Text('新增交易'),
                          style: FilledButton.styleFrom(
                            backgroundColor: fvTeal,
                          ),
                        ),
                      ],
                    ),
                    if (intraday != null) ...[
                      const SizedBox(height: 8),
                      Text(
                        '最新行情 · ${fvText(intraday!['checked_at'])} · ${intraday!['session'] == 'regular' ? '盤中' : intraday!['session'] == 'closing_pending_eod' ? '收盤待正式資料' : '正式／休市'}',
                        style: const TextStyle(
                          color: fvMuted,
                          fontSize: 11,
                        ),
                      ),
                    ],
                    if (quoteError != null) ...[
                      const SizedBox(height: 8),
                      fvBoundedState(quoteError!),
                    ],
                    const SizedBox(height: 8),
                    if (coreLoading && intraday == null)
                      fvBoundedState('持股資料載入中')
                    else
                      holdings(positions),
                  ],
                  if (section == 1) ...[
                    fvSectionTitle(
                      context,
                      '紀錄',
                      trailing: '$yearFilter 年',
                    ),
                    lazySection(sectionData, '紀錄載入中', (detail) {
                      final history =
                          fvRows(detail.isNotEmpty ? detail[0] : null);
                      final monthly =
                          fvRows(detail.length > 1 ? detail[1] : null);
                      final symbolSummary =
                          fvRows(detail.length > 2 ? detail[2] : null);
                      final annualPnl = detail.length > 3 ? detail[3] : null;
                      return Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Wrap(
                            spacing: 10,
                            runSpacing: 8,
                            crossAxisAlignment: WrapCrossAlignment.center,
                            children: [
                              yearSelector(),
                              fvTag(
                                annualRealizedPnlLabel(annualPnl, history),
                                color: fvRows(annualPnl).length == 1
                                    ? fvSignedColor(
                                        fvMap(fvRows(annualPnl).first)['realized_pnl'],
                                      )
                                    : null,
                              ),
                            ],
                          ),
                          const SizedBox(height: 10),
                          records(history, monthly, symbolSummary),
                        ],
                      );
                    }),
                  ],
                  if (section == 2) ...[
                    fvSectionTitle(
                      context,
                      '報表',
                      trailing: '$yearFilter 年',
                    ),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: yearSelector(),
                    ),
                    const SizedBox(height: 10),
                    lazySection(sectionData, '報表載入中', (detail) {
                      final reportPnl =
                          fvRows(detail.isNotEmpty ? detail[0] : null);
                      final performance =
                          fvRows(detail.length > 1 ? detail[1] : null);
                      final monthly =
                          fvRows(detail.length > 2 ? detail[2] : null);
                      final history =
                          fvRows(detail.length > 3 ? detail[3] : null);
                      final selectedYtd = yearFilter == DateTime.now().year
                          ? ytd
                          : reportPnl.isNotEmpty
                              ? reportPnl.length == 1
                                  ? '${fvText(fvMap(reportPnl.first)['currency'], missing: 'TWD')} ${legacy.accountingNumber(fvMap(reportPnl.first)['realized_pnl'])}'
                                  : '多幣別'
                              : history.isNotEmpty
                                  ? '待更新／尚未確認'
                                  : '0';
                      return reports(
                        reportPnl,
                        performance,
                        monthly: monthly,
                        ytd: selectedYtd,
                      );
                    }),
                  ],
                  if (section == 3) ...[
                    fvSectionTitle(context, '筆記'),
                    lazySection(sectionData, '筆記載入中', (detail) {
                      final noteRows =
                          fvRows(detail.isNotEmpty ? detail[0] : null);
                      return notes(noteRows);
                    }),
                  ],
                ],
              );
              return Column(children: [
                Padding(padding: const EdgeInsets.fromLTRB(18, 8, 18, 0), child: SegmentedButton<int>(
                    style: SegmentedButton.styleFrom(foregroundColor: fvInk,
                      selectedForegroundColor: Colors.white, selectedBackgroundColor: fvTeal),
                    segments: const [
                      ButtonSegment(value: 0, label: Text('持股')),
                      ButtonSegment(value: 1, label: Text('紀錄')),
                      ButtonSegment(value: 2, label: Text('報表')),
                      ButtonSegment(value: 3, label: Text('筆記')),
                    ],
                    selected: {section},
                    onSelectionChanged: (value) {
                      final next = value.first;
                      quoteGeneration++;
                      quoteBusy = false;
                      quoteTimer?.cancel();
                      setState(() {
                        section = next;
                        sectionData =
                            next == 0 ? null : loadSection(next, yearFilter);
                      });
                      if (next == 0) {
                        WidgetsBinding.instance.addPostFrameCallback((_) {
                          if (mounted) startQuotes();
                        });
                      }
                    },
                    showSelectedIcon: false,
                  )),
                Expanded(child: Center(child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 940),
                  child: scrollContent,
                ))),
              ]);
            },
          ),
        ),
      );
}
