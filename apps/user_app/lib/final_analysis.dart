import 'dart:async';

import 'package:flutter/material.dart';

import 'final_visual_common.dart';
import 'main.dart' as legacy;

String analysisState(Object? value) =>
    const {
      'QUEUED': '分析已排隊',
      'RUNNING': '分析中',
      'CANCEL_REQUESTED': '正在中止',
      'SUCCEEDED': '分析完成',
      'PARTIAL': '部分可用',
      'BLOCKED': '分析受阻',
      'FAILED': '分析失敗',
      'CANCELLED': '已中止',
    }[value] ??
    legacy.uiLabel(value);

bool analysisActive(Object? value) =>
    const {'QUEUED', 'RUNNING', 'CANCEL_REQUESTED'}.contains(value);

class FinalAnalysisPanel extends StatefulWidget {
  const FinalAnalysisPanel(this.api, this.symbol, {super.key});
  final legacy.Api api;
  final String symbol;
  @override
  State<FinalAnalysisPanel> createState() => _FinalAnalysisPanelState();
}

class _FinalAnalysisPanelState extends State<FinalAnalysisPanel>
    with WidgetsBindingObserver {
  Map<String, dynamic> baseline = {}, capability = {};
  List<dynamic> history = [], reportHistory = [];
  String reportHistoryStatus = 'waiting';
  Timer? poll;
  bool loading = true, busy = false, foreground = true;
  String? error;
  DateTime? pollUntil;
  String get path =>
      '/api/v1/me/analysis/${Uri.encodeComponent(widget.symbol)}';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    unawaited(load());
  }

  Future<void> load() async {
    try {
      final results = await Future.wait([
        widget.api.get(path),
        widget.api.get('$path/ceo'),
        widget.api.get('$path/reports').catchError((_) => <String, dynamic>{
          'status': 'unavailable', 'items': []}),
      ]).timeout(const Duration(seconds: 20));
      if (!mounted) return;
      final ceo = fvMap(results[1]);
      setState(() {
        baseline = fvMap(results[0]);
        capability = fvMap(ceo['capability']);
        history = fvRows(ceo['items']);
        reportHistory = fvRows(fvMap(results[2])['items']);
        reportHistoryStatus = fvText(fvMap(results[2])['status']);
        error = null;
      });
      schedulePoll();
    } catch (_) {
      if (mounted) setState(() => error = '分析資料暫時無法取得；可重新讀取狀態');
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  void schedulePoll() {
    poll?.cancel();
    if (history.isEmpty ||
        !analysisActive(fvMap(history.first)['status']) ||
        !foreground) return;
    pollUntil ??= DateTime.now().add(const Duration(minutes: 5));
    if (DateTime.now().isAfter(pollUntil!)) {
      setState(() => error = '分析仍未取得終態，請稍後重新讀取；不會自動重新送出');
      return;
    }
    poll = Timer(const Duration(seconds: 5), () {
      if (mounted && foreground && (ModalRoute.of(context)?.isCurrent ?? true))
        unawaited(load());
    });
  }

  Future<void> command({bool cancel = false, bool reconcile = false}) async {
    setState(() {
      busy = true;
      error = null;
    });
    try {
      if (cancel || reconcile) {
        final id = fvMap(history.first)['request_id'];
        await widget.api.post(
            '/api/v1/me/ceo-requests/$id/${reconcile ? 'reconcile' : 'cancel'}',
            {});
      } else {
        await widget.api.post('$path/ceo', {'profile_id': 'default'});
      }
      pollUntil = DateTime.now().add(const Duration(minutes: 5));
      await load();
    } catch (_) {
      await load();
      if (mounted) setState(() => error = '指令未確認；請先核對執行狀態與額度，再決定是否重新送出');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    foreground = state == AppLifecycleState.resumed;
    if (!foreground) {
      poll?.cancel();
    } else {
      unawaited(load());
    }
  }

  @override
  void dispose() {
    poll?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  Widget _stockReport(Map<String, dynamic> saved) {
    final report = fvMap(saved);
    if (report.isEmpty) return fvBoundedState('個股週期報告尚未就緒');
    final inputDates = fvMap(report['inputs_as_of']);
    final statuses = fvRows(report['serving_roles']);
    final gaps = fvMap(report['input_gaps']);
    final reason = const {
      'first_report': '首次報告', 'model_changed': '模型版本更新',
      'financial_changed': '財務資料變更', 'price_move_5pct': '價格異動',
      'weekly_new_inputs': '每週資料更新', 'policy_changed': '政策版本更新',
      'on_demand': '手動重新產生'
    }[report['generation_reason']] ?? '已保存版本';
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('事實報告 · $reason',
          style: const TextStyle(fontWeight: FontWeight.w800)),
      Text('報告資料日 ${fvText(report['report_as_of'])} · 版本 ${fvText(report['policy_version'])}',
          style: const TextStyle(color: fvMuted, fontSize: 12)),
      const Text('報告是後端確定性事實摘要，不是 CEO 或四模型預測驗證。',
          style: TextStyle(color: fvMuted, fontSize: 12)),
      for (final role in const ['quant', 'risk', 'fundamental', 'valuation']) ...[
        const SizedBox(height: 6),
        Text('${legacy.uiLabel(role)} · 輸入日 ${fvText(inputDates[role])}',
            style: const TextStyle(fontWeight: FontWeight.w600)),
        if (fvRows(gaps[role]).isNotEmpty)
          Text('輸入缺口：${fvRows(gaps[role]).join('、')}',
              style: const TextStyle(color: Colors.orange, fontSize: 12)),
        for (final item in statuses.where((x) => fvMap(x)['role'] == role)) ...[
          Text('模型狀態 ${fvText(fvMap(item)['status'])} · ${fvText(fvMap(item)['model_version'])}',
              style: const TextStyle(color: fvMuted, fontSize: 12)),
          if (const {'ACTIVE_PREDICTED', 'ACTIVE_CACHED'}.contains(fvMap(item)['status']) &&
              fvMap(item)['prediction'] is num)
            Text('模型原始輸出 ${fvText(fvMap(item)['output_name'])}: ${fvMap(item)['prediction']}'),
        ],
      ],
      const Text('缺少正式模型時保留缺值；價格／估值不由 App 重新計算。',
          style: TextStyle(color: fvMuted, fontSize: 12)),
    ]);
  }

  Widget report(Map<String, dynamic> request) {
    final saved = fvMap(request['report_json']);
    final output = fvMap(saved['output']);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(analysisState(request['status']),
          style: const TextStyle(fontWeight: FontWeight.w800)),
      Text(
          '分析日 ${fvText(saved['analysis_as_of'])} · 產生時間 ${fvText(request['finished_at'] ?? request['requested_at'])}',
          style: const TextStyle(color: fvMuted, fontSize: 12)),
      if (request['material_change'] == true)
        const Text('五分析師已有變更；此報告保留原始分析資料',
            style: TextStyle(color: Colors.orange)),
      if (request['specialist_freshness'] == 'stale')
        const Text('目前基準資料已過期', style: TextStyle(color: Colors.orange)),
      if (output.isNotEmpty) ...[
        Text(fvText(fvMap(output['thesis'])['text'], missing: '資料不足，無方向性結論')),
        for (final section in const {
          'bull_case': '樂觀情境',
          'bear_case': '悲觀情境',
          'contradictions': '分析分歧',
          'principal_risks': '主要風險',
          'watch_items': '追蹤／失效條件'
        }.entries)
          if (fvRows(output[section.key]).isNotEmpty) ...[
            Text(section.value,
                style: const TextStyle(fontWeight: FontWeight.w700)),
            for (final item in fvRows(output[section.key]))
              Text('• ${fvText(fvMap(item)['text'])}'),
          ],
        if (fvRows(output['missing_information']).isNotEmpty)
          Text('未知／缺口：${fvRows(output['missing_information']).join('、')}'),
        const Text('分析信心不是獲利機率；CEO 不修改正式數值。',
            style: TextStyle(color: fvMuted, fontSize: 12)),
      ] else if (request['safe_reason'] != null)
        const Text('資料、權限或 provider 驗證未通過；本次沒有有效報告'),
    ]);
  }

  @override
  Widget build(BuildContext context) {
    final roles = fvRows(baseline['specialists']);
    final active =
        history.isNotEmpty && analysisActive(fvMap(history.first)['status']);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      fvSectionTitle(context, '四模型／事件相容基準'),
      if (loading)
        fvBoundedState('分析資料載入中')
      else if (roles.isEmpty)
        fvBoundedState('基準分析尚未就緒')
      else ...[
        Text(
            '分析日 ${fvText(baseline['analysis_as_of'])} · ${baseline['freshness'] == 'stale' ? '資料過期' : '已保存基準'}'),
        const Text('基準計算與模型品質分開驗收；模型品質尚未驗證。',
            style: TextStyle(color: fvMuted, fontSize: 12)),
        for (final item in roles)
          Padding(
              padding: const EdgeInsets.only(top: 8),
              child: fvPanel(
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                    Text(
                        '${legacy.uiLabel(fvMap(item)['role'])} · ${fvMap(item)['baseline_status'] == 'available' ? '基準可用' : '資料不足'}',
                        style: const TextStyle(fontWeight: FontWeight.w800)),
                    Text(fvText(fvMap(item)['plain_language'])),
                    Text(
                        '資料日 ${fvText(fvMap(item)['analysis_as_of'])} · ${fvMap(item)['reused'] == true ? '沿用未變更資料' : '已更新'}',
                        style: const TextStyle(color: fvMuted, fontSize: 12)),
                  ]))),
      ],
      if (fvMap(baseline['market_context']).isNotEmpty) ...[
        Text(
            '市場比較：${fvMap(baseline['market_context'])['cohort_size']} 檔官方名單 · ${fvMap(baseline['market_context'])['analysis_as_of']}'),
        Text(
            '20 日相對強弱排名 ${fvText(fvMap(fvMap(baseline['market_context'])['cross_sectional_rank'])['relative_strength_20d_percent'])}；規則篩選排名 ${fvText(fvMap(baseline['market_context'])['candidate_rank'])}'),
        const Text('排名屬當日市場基準，並非未來獲利機率。',
            style: TextStyle(color: fvMuted, fontSize: 12)),
      ] else if (roles.isNotEmpty)
        const Text('同日市場比較尚不可用；不以個人關注名單代替市場排名。',
            style: TextStyle(color: fvMuted, fontSize: 12)),
      fvSectionTitle(context, '週期／異動事實報告'),
      fvPanel(child: _stockReport(fvMap(baseline['stock_report']))),
      if (fvMap(baseline['stock_report_refresh']).isNotEmpty)
        Text('檢查資料日 ${fvText(fvMap(baseline['stock_report_refresh'])['checked_as_of'])} · ${fvMap(baseline['stock_report_refresh'])['generated'] == true ? '已更新' : '沿用上次成功報告'}',
            style: const TextStyle(color: fvMuted, fontSize: 12)),
      if (fvMap(baseline['valuation_reference']).isNotEmpty) ...[
        fvSectionTitle(context, '唯一估值參考區間'),
        fvPanel(child: Text(
            fvMap(baseline['valuation_reference'])['status'] == 'available'
                ? '下緣 ${fvText(fvMap(baseline['valuation_reference'])['lower'])} · 中位 ${fvText(fvMap(baseline['valuation_reference'])['mid'])} · 上緣 ${fvText(fvMap(baseline['valuation_reference'])['upper'])}'
                : '估值區間尚不完整；不補造參考價')),
      ],
      if (reportHistoryStatus == 'unavailable')
        const Text('本人歷史報告目前無法讀取；不影響最新事實報告',
            style: TextStyle(color: Colors.orange)),
      if (reportHistory.where((row) =>
            fvMap(fvMap(row)['report'])['report_hash'] !=
              fvMap(baseline['stock_report'])['report_hash']).isNotEmpty)
        ExpansionTile(title: const Text('本人歷史事實報告'), children: [
          for (final row in reportHistory)
            if (fvMap(fvMap(row)['report'])['report_hash'] !=
                fvMap(baseline['stock_report'])['report_hash'])
              Padding(padding: const EdgeInsets.all(12),
                  child: _stockReport(fvMap(fvMap(row)['report']))),
        ]),
      fvSectionTitle(context, 'On-demand CEO'),
      if (history.isEmpty)
        fvBoundedState('尚無 CEO 分析；開頁不會自動呼叫 LLM')
      else
        fvPanel(child: report(fvMap(history.first))),
      if (capability['can_request'] == true)
        Wrap(spacing: 8, children: [
          FilledButton(
              onPressed: busy ||
                      active ||
                      capability['profile_approved'] != true ||
                      roles.isEmpty ||
                      baseline['freshness'] == 'stale'
                  ? null
                  : () => command(),
              child: Text(history.isEmpty ? '分析' : '重新分析')),
          if (active)
            OutlinedButton(
                onPressed: busy ? null : () => command(cancel: true),
                child: const Text('中止')),
          if (active)
            OutlinedButton(
                onPressed: busy ? null : () => command(reconcile: true),
                child: const Text('核對執行終態')),
        ]),
      if (capability['can_request'] == true &&
          capability['profile_approved'] != true)
        const Text('CEO provider 尚待核准／真實驗收'),
      if (history.length > 1)
        ExpansionTile(title: const Text('不可覆寫的分析歷史'), children: [
          for (final item in history.skip(1))
            Padding(
                padding: const EdgeInsets.all(12), child: report(fvMap(item))),
        ]),
      if (error != null)
        Text(error!, style: const TextStyle(color: Colors.orange)),
      TextButton(
          onPressed: busy
              ? null
              : () {
                  pollUntil = null;
                  unawaited(load());
                },
          child: const Text('重新讀取分析狀態')),
    ]);
  }
}
