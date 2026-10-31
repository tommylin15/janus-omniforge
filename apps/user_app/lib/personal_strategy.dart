import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'main.dart' as legacy;
import 'research_link.dart' if (dart.library.html) 'research_link_web.dart';

const _root = '/api/v1/me/personal-strategy';
const _types = {'premarket': '盤前', 'intraday': '盤中', 'postmarket': '盤後', 'saturday': '週六'};
Map<String, dynamic> _map(dynamic v) => v is Map ? Map<String, dynamic>.from(v) : {};
List<dynamic> _list(dynamic v) => v is List ? v : [];

/// Deliberately small Markdown subset rendered as native widgets, never HTML.
class ResearchMarkdown extends StatelessWidget {
  const ResearchMarkdown(this.text, {super.key});
  final String text;
  @override
  Widget build(BuildContext context) => SelectionArea(child: Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: text.split('\n').map((line) {
      if (line.trim() == '---') return const Divider();
      final heading = RegExp(r'^(#{1,6})\s+').firstMatch(line);
      final clean = heading == null ? line : line.substring(heading.end);
      final spans = <InlineSpan>[];
      final bold = RegExp(r'\*\*([^*]+)\*\*');
      var offset = 0;
      for (final match in bold.allMatches(clean)) {
        spans.add(TextSpan(text: clean.substring(offset, match.start)));
        spans.add(TextSpan(text: match[1], style: const TextStyle(fontWeight: FontWeight.bold)));
        offset = match.end;
      }
      spans.add(TextSpan(text: clean.substring(offset)));
      final links = RegExp(r'https://[^\s<>\]\)\uFF08\uFF09]+').allMatches(line).map((m) => m[0]!).toSet();
      return Padding(padding: const EdgeInsets.symmetric(vertical: 4), child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [Text.rich(TextSpan(children: spans), style: heading == null
          ? const TextStyle(height: 1.5) : Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
          for (final url in links) TextButton.icon(onPressed: () => openResearchLink(url),
            icon: const Icon(Icons.open_in_new, size: 16), label: const Text('開啟來源')),
        ]));
    }).toList(),
  ));
}

class PersonalStrategyPage extends StatefulWidget {
  const PersonalStrategyPage(this.api, {this.active = true, super.key});
  final legacy.Api api;
  final bool active;
  @override
  State<PersonalStrategyPage> createState() => _PersonalStrategyPageState();
}
class _PersonalStrategyPageState extends State<PersonalStrategyPage> with WidgetsBindingObserver {
  String type = 'premarket';
  Map<String, dynamic> summary = {};
  List<dynamic> reports = [];
  String? error;
  bool busy = false, loading = true;
  Timer? timer;
  int generation = 0;
  @override
  void initState() { super.initState(); WidgetsBinding.instance.addObserver(this); load(); }
  @override
  void dispose() { timer?.cancel(); WidgetsBinding.instance.removeObserver(this); super.dispose(); }
  @override
  void didUpdateWidget(PersonalStrategyPage old) {
    super.didUpdateWidget(old);
    if (old.api != widget.api) { summary = {}; reports = []; }
    if (widget.active && (old.active != widget.active || old.api != widget.api)) load();
    if (!widget.active) timer?.cancel();
  }
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed) { timer?.cancel(); }
    else if (widget.active) { load(); }
  }
  Future<void> load() async {
    final ticket = ++generation;
    timer?.cancel();
    try {
      final result = await Future.wait([widget.api.get(_root), widget.api.get('$_root/reports/$type')]);
      if (!mounted || ticket != generation) return;
      setState(() { summary = _map(result[0]); reports = _list(_map(result[1])['items']); error = null; loading = false; });
      if (widget.active && _list(summary['requests']).any((v) => ['QUEUED', 'RUNNING'].contains(v['status']))) {
        timer = Timer(const Duration(seconds: 8), load);
      }
    } catch (e) { if (mounted && ticket == generation) setState(() { error = '$e'; loading = false; }); }
  }
  Future<void> run() async {
    bool? sync;
    if (type == 'saturday') {
      sync = await showDialog<bool>(context: context, builder: (context) => AlertDialog(
        title: const Text('本次週六分析是否同步觀察池？'),
        content: const Text('同步可新增、升降級或移除觀察；鎖定股不變。執行期間名單或帳本有變動則跳過同步。'),
        actions: [TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('不同步')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('同步觀察池'))]));
      if (sync == null || !mounted) return;
    }
    setState(() { busy = true; error = null; });
    try { await widget.api.post('$_root/reports', {'report_type': type, 'sync_watchlist': sync}); await load(); }
    catch (e) { await load(); if (mounted) setState(() => error = '$e'); }
    finally { if (mounted) setState(() => busy = false); }
  }
  @override
  Widget build(BuildContext context) {
    final active = _map(summary['active']);
    final requests = _list(summary['requests']);
    final used = requests.any((v) => v['kind'] == type);
    return SafeArea(child: ListView(padding: const EdgeInsets.all(18), children: [
      Row(children: [Expanded(child: Text('個人策略', style: Theme.of(context).textTheme.headlineSmall)),
        IconButton(onPressed: load, icon: const Icon(Icons.refresh), tooltip: '重新整理')]),
      const Text('AI研究報告唯讀；每類最近3份。修改策略請至「我的」。'),
      if (loading) const LinearProgressIndicator(),
      if (error != null) Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
      if (active.isEmpty && !loading) const Card(child: Padding(padding: EdgeInsets.all(16), child: Text('請先到「我的」產出個人策略'))),
      if (active.isNotEmpty) Card(child: ExpansionTile(title: Text('${_map(_map(active['rules'])['template'])['name'] ?? '生效策略'}'),
        subtitle: Text('生效 ${active['created_at']}'), children: [Padding(padding: const EdgeInsets.all(16), child: ResearchMarkdown('${active['markdown']}'))])),
      if (active.isNotEmpty) SwitchListTile(title: const Text('暫停新建／加碼建議'), value: active['paused'] == true,
        onChanged: busy ? null : (value) async {
          setState(() => busy = true);
          try { await widget.api.put('$_root/pause', {'paused': value}); await load(); }
          catch (e) { if (mounted) setState(() => error = '$e'); }
          finally { if (mounted) setState(() => busy = false); }
        }),
      Wrap(spacing: 8, children: _types.entries.map((e) => ChoiceChip(label: Text(e.value), selected: type == e.key,
        onSelected: busy ? null : (_) { setState(() { type = e.key; reports = []; loading = true; }); load(); })).toList()),
      const SizedBox(height: 12),
      FilledButton.icon(onPressed: busy || loading || active.isEmpty || used || summary['enabled'] != true ||
        (type == 'saturday' && summary['saturday'] != true) ? null : run,
        icon: const Icon(Icons.bolt), label: Text(used ? '今日此類已送出' : '立即更新${_types[type]}分析')),
      for (final item in requests.where((v) => v['kind'] == type || v['kind'] == 'strategy'))
        Card(child: ListTile(title: Text('${_types[item['kind']] ?? '策略生成'}：${item['status']}'),
          subtitle: Text('${item['safe_error'] ?? '背景處理，可離開頁面；重新整理查詢進度。'}'),
          trailing: ['FAILED', 'QUEUED', 'RUNNING'].contains(item['status']) ? TextButton(onPressed: busy ? null : () async {
            setState(() => busy = true);
            try { await widget.api.post('$_root/requests/${item['request_id']}/retry', {}); await load(); }
            catch (e) { if (mounted) setState(() => error = '$e'); }
            finally { if (mounted) setState(() => busy = false); }
          }, child: const Text('重試原請求')) : null)),
      for (final item in reports) Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('${item['created_at']} · ${item['status']} · ${item['model']}'),
          Align(alignment: Alignment.centerRight, child: TextButton.icon(onPressed: () => Clipboard.setData(ClipboardData(text: '${item['markdown']}')),
            icon: const Icon(Icons.copy), label: const Text('複製Markdown'))),
          ResearchMarkdown('${item['markdown']}'),
        ]))),
      if (!loading && reports.isEmpty) const Padding(padding: EdgeInsets.all(20), child: Text('此類尚無報告')),
    ]));
  }
}

class PersonalStrategySettings extends StatefulWidget {
  const PersonalStrategySettings(this.api, {super.key});
  final legacy.Api api;
  @override
  State<PersonalStrategySettings> createState() => _PersonalStrategySettingsState();
}
class _PersonalStrategySettingsState extends State<PersonalStrategySettings> {
  List<dynamic> templates = [];
  Map<String, dynamic> summary = {};
  String template = 'stock', tolerance = 'moderate', horizon = 'medium';
  final custom = TextEditingController(), liquidity = TextEditingController(), protected = TextEditingController();
  final cash = TextEditingController(), position = TextEditingController(), sector = TextEditingController(), loss = TextEditingController(), drawdown = TextEditingController();
  bool consent = false, busy = false, loaded = false;
  String? error;
  Map<String, dynamic>? prepared;
  @override
  void initState() { super.initState(); load(); }
  @override
  void dispose() { for (final c in [custom, liquidity, protected, cash, position, sector, loss, drawdown]) { c.dispose(); } super.dispose(); }
  Future<void> load() async {
    try {
      final result = await Future.wait([widget.api.get('$_root/templates'), widget.api.get(_root), widget.api.get('/api/v1/me/investment-profile')]);
      if (!mounted) return;
      summary = _map(result[1]);
      final rules = _map(_map(summary['active'])['rules']);
      final risk = _map(rules['risk']); final old = _map(result[2]);
      setState(() {
        templates = _list(_map(result[0])['items']);
        template = '${rules['template_id'] ?? 'stock'}';
        tolerance = '${risk['tolerance'] ?? old['risk_tolerance'] ?? 'moderate'}';
        horizon = '${risk['horizon'] ?? old['investment_horizon'] ?? 'medium'}';
        custom.text = '${rules['custom_text'] ?? ''}'; liquidity.text = '${risk['liquidity_need'] ?? ''}';
        protected.text = _list(rules['protected_symbols']).join(',');
        consent = rules['private_ai_consent'] == true;
        void percent(TextEditingController c, dynamic value) { c.text = value == null ? '' : '${(num.parse('$value') * 100)}'; }
        percent(cash, risk['minimum_cash_ratio'] ?? old['minimum_cash_ratio']);
        percent(position, risk['max_position_ratio']); percent(sector, risk['max_sector_ratio']);
        percent(loss, risk['loss_budget_ratio']); percent(drawdown, risk['max_drawdown_ratio']);
        loaded = true; error = null;
      });
    } catch (e) { if (mounted) setState(() => error = '$e'); }
  }
  Map<String, dynamic> payload() => {'template_id': template, 'custom_text': custom.text,
    'private_ai_consent': consent, 'protected_symbols': protected.text.split(RegExp(r'[,，\s]+')).where((s) => s.isNotEmpty).toSet().toList(),
    'risk': {'tolerance': tolerance, 'horizon': horizon, 'liquidity_need': liquidity.text,
      'minimum_cash_ratio': double.parse(cash.text) / 100, 'max_position_ratio': double.parse(position.text) / 100,
      'max_sector_ratio': double.parse(sector.text) / 100, 'loss_budget_ratio': double.parse(loss.text) / 100,
      'max_drawdown_ratio': double.parse(drawdown.text) / 100}};
  void changed() => setState(() => prepared = null);
  Future<void> action(bool generate) async {
    setState(() { busy = true; error = null; });
    try {
      final body = payload();
      final result = await widget.api.post('$_root/${generate ? 'generate' : 'preview'}', body);
      if (!mounted) return;
      if (generate) {
        await load();
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('策略已送出；請至個人策略頁查看進度')));
      } else { setState(() => prepared = _map(result)); }
    } catch (e) { if (mounted) setState(() => error = '$e'); }
    finally { if (mounted) setState(() => busy = false); }
  }
  Widget number(TextEditingController c, String label) => Padding(padding: const EdgeInsets.only(bottom: 8),
    child: TextField(controller: c, enabled: !busy, keyboardType: const TextInputType.numberWithOptions(decimal: true),
      decoration: InputDecoration(labelText: '$label（%）'), onChanged: (_) => changed()));
  @override
  Widget build(BuildContext context) => Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(
    crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Text('個人策略設定', style: Theme.of(context).textTheme.titleLarge),
      const Text('先選操作策略，再選風險。每台北時間週一重置，每週成功產出一次。'),
      if (error != null) Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
      if (!loaded) TextButton(onPressed: load, child: const Text('載入設定')),
      if (loaded) ...[
        DropdownButtonFormField<String>(initialValue: template, isExpanded: true, decoration: const InputDecoration(labelText: '1. 操作策略'),
          items: templates.map((t) => DropdownMenuItem(value: '${t['id']}', child: Text('${t['name']}', overflow: TextOverflow.ellipsis))).toList(),
          onChanged: busy ? null : (v) { template = v!; changed(); }),
        TextField(controller: custom, enabled: !busy, minLines: 3, maxLines: 8,
          decoration: const InputDecoration(labelText: '自訂規則／個人補充（進場、退出、A/B/C條件）'), onChanged: (_) => changed()),
        DropdownButtonFormField<String>(initialValue: tolerance, decoration: const InputDecoration(labelText: '2. 風險特性'),
          items: const [DropdownMenuItem(value: 'conservative', child: Text('保守')), DropdownMenuItem(value: 'moderate', child: Text('平衡')), DropdownMenuItem(value: 'aggressive', child: Text('積極'))],
          onChanged: busy ? null : (v) { tolerance = v!; changed(); }),
        DropdownButtonFormField<String>(initialValue: horizon, decoration: const InputDecoration(labelText: '操作期限'),
          items: const [DropdownMenuItem(value: 'short', child: Text('短期')), DropdownMenuItem(value: 'medium', child: Text('中期')), DropdownMenuItem(value: 'long', child: Text('長期'))],
          onChanged: busy ? null : (v) { horizon = v!; changed(); }),
        number(cash, '最低現金'), number(position, '單股上限'), number(sector, '產業上限'), number(loss, '單筆損失預算'), number(drawdown, '可承受總損失'),
        TextField(controller: liquidity, enabled: !busy, decoration: const InputDecoration(labelText: '資金需求／不可動用資金'), onChanged: (_) => changed()),
        TextField(controller: protected, enabled: !busy, decoration: const InputDecoration(labelText: '保護池股票代號（逗號分隔）'), onChanged: (_) => changed()),
        CheckboxListTile(contentPadding: EdgeInsets.zero, title: const Text('同意將必要持股、現金與策略送 Gemini 分析；公開搜尋不傳數量與成本'),
          value: consent, onChanged: busy ? null : (v) { consent = v!; changed(); }),
        OutlinedButton(onPressed: busy ? null : () => action(false), child: const Text('預覽策略與風險限制')),
        if (prepared != null) ...[
          ResearchMarkdown('${prepared!['markdown']}'),
          Text('風險限制：${jsonEncode(_map(prepared!['rules'])['risk'])}'),
          for (final warning in _list(prepared!['warnings'])) Text('• $warning'),
        ],
        if (summary['strategy_locked'] == true) Text('本週已使用；下次可變更：${summary['next_change_at']}'),
        FilledButton(onPressed: busy || prepared == null || prepared!['blocked'] == true || !consent || summary['strategy_locked'] == true || summary['enabled'] != true
          ? null : () => action(true), child: const Text('產出個人策略並生效（每週一次）')),
        TextButton(onPressed: busy ? null : () async {
          try { final result = await widget.api.get('$_root/export'); await Clipboard.setData(ClipboardData(text: jsonEncode(result))); }
          catch (e) { if (mounted) setState(() => error = '$e'); }
        }, child: const Text('複製策略與報告匯出資料')),
        TextButton(onPressed: busy ? null : () async {
          final text = await legacy.textDialog(context, '匯入私人Markdown種子', '貼上原文（保留原文，不改帳本）');
          if (text == null || text.isEmpty || !mounted) return;
          final body = {'documents': {'股市.md': text}};
          try {
            final result = await widget.api.post('$_root/seed/preview', body);
            if (!mounted) return;
            final apply = await showDialog<bool>(context: context, builder: (ctx) => AlertDialog(title: const Text('匯入預覽'),
              content: Text('${result['note']}'), actions: [TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
                FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('保存原文'))]));
            if (apply == true) {
              await widget.api.post('$_root/seed/apply', body);
              if (mounted && text.length <= 12000) { custom.text = text; changed(); }
              if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('原文已保存；設定預覽並產出後才會生效。超過12000字請選取操作條文。')));
            }
          } catch (e) { if (mounted) setState(() => error = '$e'); }
        }, child: const Text('私人Markdown種子匯入')),
      ],
    ])));
}
