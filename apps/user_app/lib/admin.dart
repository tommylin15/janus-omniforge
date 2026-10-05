import 'package:flutter/material.dart';

abstract class AdminApi {
  Future<dynamic> get(String path);
  Future<dynamic> post(String path, Map<String, dynamic> body);
  Future<dynamic> put(String path, Map<String, dynamic> body);
  Future<dynamic> patch(String path, Map<String, dynamic> body);
}

List<Map<String, dynamic>> _items(dynamic value) =>
    ((value as Map<String, dynamic>?)?['items'] as List? ?? const [])
        .cast<Map<String, dynamic>>();

String _label(Object? value) =>
    const {
      'queued': '排隊中',
      'running': '執行中',
      'retrying': '重試中',
      'succeeded': '成功',
      'partial': '部分完成',
      'failed': '失敗',
      'success': '正常',
      'fallback': '備援',
      'unavailable': '無法使用',
      'schema_drift': '結構變更',
      'blocked': '已阻擋',
      'review_required': '需要審查',
      'invalid': '無效',
      'retryable': '可重試',
      'non_retryable': '不可重試',
      'collection': '資料收集',
      'analysis': '分析',
      'passed': '檢查通過',
      'attention_required': '需要處理',
      'execution_failed': '檢查執行失敗',
      'history_incomplete': '歷史資料不足',
      'unit_mismatch': '單位或幣別不一致',
      'invalid_numeric_value': '數值格式異常',
      'conflicting_version': '相同版次數值衝突',
      'missing_receipt_time': '缺少取得時間',
      'source_value_changed': '官方數值已變動',
      'source_check_failed': '官方來源核對失敗',
    }[value?.toString()] ??
    value?.toString() ??
    '—';

bool _executionNeedsAttention(Map<String, dynamic> value) =>
    {'failed', 'partial', 'retrying'}.contains(value['status']);

int _executionOrder(Map<String, dynamic> value) {
  switch (value['status']) {
    case 'failed':
      return 0;
    case 'partial':
      return 1;
    case 'retrying':
      return 2;
    case 'running':
      return 3;
    case 'queued':
      return 4;
    case 'succeeded':
      return 5;
    default:
      return 6;
  }
}

Future<bool> _showExecutionDetails(
  BuildContext context,
  AdminApi api,
  String id,
) async {
  late final Map<String, dynamic> detail;
  try {
    detail = await api.get(
      '/api/v1/admin/executions/${Uri.encodeComponent(id)}',
    ) as Map<String, dynamic>;
  } catch (_) {
    if (context.mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('執行明細暫時無法使用')));
    }
    return false;
  }
  if (!context.mounted) return false;
  final result = await showDialog<bool>(
    context: context,
    builder: (dialogContext) => AlertDialog(
      title: Text('執行 ${_label(detail['status'])}'),
      content: SizedBox(
        width: 680,
        child: ListView(
          shrinkWrap: true,
          children: [
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(
                '${detail['config_id'] ?? '—'} · ${_label(detail['trigger_type'])}',
              ),
              subtitle: Text(
                '執行 ID ${detail['execution_id'] ?? '—'}\n追蹤 ID ${detail['trace_id'] ?? '—'}',
              ),
            ),
            const Divider(),
            Text('失敗項目與重試分類',
                style: Theme.of(dialogContext).textTheme.titleMedium),
            if (_items(detail).isEmpty)
              const ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text('沒有逐項執行紀錄'),
              ),
            ..._items(detail).map(
              (item) => ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text('${item['dataset_id']} · ${item['source_id']}'),
                subtitle: Text(
                  '${_label(item['state'])} · ${item['safe_message'] ?? '—'} · 重試 ${item['retry_count'] ?? 0} 次',
                ),
                trailing: item['retry_classification'] == 'retryable'
                    ? FilledButton.tonal(
                        onPressed: () async {
                          try {
                            await api.post(
                              '/api/v1/admin/executions/${Uri.encodeComponent(id)}/items/${Uri.encodeComponent(item['item_key'].toString())}/retry',
                              const {},
                            );
                          } catch (_) {
                            if (dialogContext.mounted) {
                              ScaffoldMessenger.of(dialogContext).showSnackBar(
                                const SnackBar(content: Text('此項目目前無法重試')),
                              );
                            }
                            return;
                          }
                          if (dialogContext.mounted) {
                            Navigator.pop(dialogContext, true);
                          }
                        },
                        child: const Text('重試'),
                      )
                    : Text(_label(item['retry_classification'])),
              ),
            ),
            const Divider(),
            Text('執行追蹤', style: Theme.of(dialogContext).textTheme.titleMedium),
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text('追蹤 ID ${detail['trace_id'] ?? '—'}'),
              subtitle: const Text('同一追蹤鏈的舊執行保持不可變更'),
            ),
            for (final related
                in (((detail['lineage'] as Map?)?['executions'] as List?) ??
                    const []))
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text('${related['execution_id'] ?? '—'}'),
                subtitle: Text(
                  '${_label(related['status'])} · ${related['requested_at'] ?? '—'}',
                ),
              ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(dialogContext, false),
          child: const Text('關閉'),
        ),
      ],
    ),
  );
  return result == true;
}

class AdminWorkspace extends StatefulWidget {
  const AdminWorkspace({
    required this.api,
    required this.email,
    required this.onTheme,
    super.key,
  });
  final AdminApi api;
  final String email;
  final ValueChanged<ThemeMode> onTheme;

  @override
  State<AdminWorkspace> createState() => _AdminWorkspaceState();
}

class _AdminWorkspaceState extends State<AdminWorkspace> {
  int page = 0;

  static const destinations = [
    NavigationRailDestination(
      icon: Icon(Icons.dashboard_outlined),
      label: Text('總覽'),
    ),
    NavigationRailDestination(
      icon: Icon(Icons.view_list_outlined),
      label: Text('批次'),
    ),
    NavigationRailDestination(icon: Icon(Icons.search), label: Text('個股')),
    NavigationRailDestination(
      icon: Icon(Icons.bar_chart_outlined),
      label: Text('市場資訊'),
    ),
    NavigationRailDestination(
      icon: Icon(Icons.psychology_outlined),
      label: Text('AI 分析'),
    ),
    NavigationRailDestination(
      icon: Icon(Icons.settings_outlined),
      label: Text('資料治理'),
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final pages = [
      AdminOverviewPage(widget.api),
      AdminBatchPage(widget.api),
      AdminStockWorkbench(widget.api),
      AdminMarketUniversePage(widget.api),
      const _PendingPage(title: 'AI 分析', message: '等待 WBS-5 五角色與 CIO 契約完成後啟用。'),
      AdminGovernancePage(widget.api),
    ];
    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= 900;
        return Scaffold(
          appBar: AppBar(
            title: Text(
              '資料營運中心 · ${destinations[page].label is Text ? (destinations[page].label as Text).data : ''}',
            ),
            actions: [
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Center(child: Text(widget.email)),
              ),
            ],
          ),
          drawer: wide
              ? null
              : NavigationDrawer(
                  selectedIndex: page,
                  onDestinationSelected: (value) {
                    setState(() => page = value);
                    Navigator.pop(context);
                  },
                  children: const [
                    Padding(
                      padding: EdgeInsets.fromLTRB(28, 20, 16, 12),
                      child: Text('資料營運中心'),
                    ),
                    NavigationDrawerDestination(
                      icon: Icon(Icons.dashboard_outlined),
                      label: Text('總覽'),
                    ),
                    NavigationDrawerDestination(
                      icon: Icon(Icons.view_list_outlined),
                      label: Text('批次'),
                    ),
                    NavigationDrawerDestination(
                      icon: Icon(Icons.search),
                      label: Text('個股'),
                    ),
                    NavigationDrawerDestination(
                      icon: Icon(Icons.bar_chart_outlined),
                      label: Text('市場資訊'),
                    ),
                    NavigationDrawerDestination(
                      icon: Icon(Icons.psychology_outlined),
                      label: Text('AI 分析'),
                    ),
                    NavigationDrawerDestination(
                      icon: Icon(Icons.settings_outlined),
                      label: Text('資料治理'),
                    ),
                  ],
                ),
          body: Row(
            children: [
              if (wide)
                NavigationRail(
                  selectedIndex: page,
                  labelType: NavigationRailLabelType.all,
                  onDestinationSelected: (value) =>
                      setState(() => page = value),
                  destinations: destinations,
                ),
              Expanded(child: SafeArea(child: pages[page])),
            ],
          ),
        );
      },
    );
  }
}

class AdminOverviewPage extends StatefulWidget {
  const AdminOverviewPage(this.api, {super.key});
  final AdminApi api;

  @override
  State<AdminOverviewPage> createState() => _AdminOverviewPageState();
}

class _AdminOverviewPageState extends State<AdminOverviewPage> {
  late Future<List<dynamic>> data;

  @override
  void initState() {
    super.initState();
    data = _load();
  }

  Future<List<dynamic>> _load() => Future.wait([
        widget.api.get('/api/v1/admin/executions?limit=50'),
        widget.api.get('/api/v1/admin/source-health?limit=200'),
        widget.api.get('/api/v1/admin/mart-reports?limit=50'),
        widget.api
            .get('/api/v1/admin/settings/data_supplement_quality')
            .catchError(
              (_) => {
                'value': {'status': 'unavailable'}
              },
            ),
      ]);

  void _reload() => setState(() {
        data = _load();
      });

  @override
  Widget build(BuildContext context) => _AdminPage(
        title: '需要處理的事項',
        action: IconButton(
          tooltip: '重新整理',
          onPressed: _reload,
          icon: const Icon(Icons.refresh),
        ),
        child: FutureBuilder<List<dynamic>>(
          future: data,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.hasError) return const _Message('營運摘要暫時無法使用');
            final executions = _items(snapshot.data![0]);
            final sources = _items(snapshot.data![1]);
            final reports = _items(snapshot.data![2]);
            final attentionExecutions = executions
                .where(_executionNeedsAttention)
                .toList()
              ..sort(
                  (a, b) => _executionOrder(a).compareTo(_executionOrder(b)));
            final attentionSources = sources
                .where(
                  (value) =>
                      !{'success', 'succeeded'}.contains(value['last_state']),
                )
                .toList();
            final attentionReports = reports
                .where(
                  (value) =>
                      {'blocked', 'review_required', 'invalid'}.contains(
                        value['publication_status'],
                      ) ||
                      {
                        'invalid',
                        'review_required',
                        'risk_blocked',
                        'insufficient_data'
                      }.contains(value['analysis_outcome']),
                )
                .toList();
            final total = attentionExecutions.length +
                attentionSources.length +
                attentionReports.length;
            return ListView(
              children: [
                _DataQualityCard(widget.api,
                    snapshot.data![3]['value'] as Map<String, dynamic>?),
                Wrap(
                  spacing: 12,
                  runSpacing: 12,
                  children: [
                    _IssueCard('Core', attentionSources.length,
                        Icons.storage_outlined),
                    _IssueCard('Mart', attentionReports.length,
                        Icons.analytics_outlined),
                    const _IssueCard('AI 分析', null, Icons.psychology_outlined),
                    _IssueCard(
                      '失敗／部分完成',
                      attentionExecutions.length,
                      Icons.error_outline,
                    ),
                  ],
                ),
                const SizedBox(height: 20),
                Text('優先處理', style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 4),
                const Text('正常 execution 不會佔用此區塊'),
                const SizedBox(height: 8),
                if (sources.isEmpty)
                  const Card(
                    child: ListTile(
                      leading: Icon(Icons.help_outline),
                      title: Text('尚無資料源健康紀錄，無法判定 Core 狀態'),
                    ),
                  ),
                if (total == 0 && sources.isNotEmpty)
                  const Card(
                    child: ListTile(
                      leading: Icon(Icons.check_circle_outline),
                      title: Text('今日沒有需要處理的事項'),
                      subtitle: Text('成功的執行紀錄仍可在「批次」查閱。'),
                    ),
                  ),
                for (final execution in attentionExecutions)
                  Card(
                    child: ListTile(
                      leading: Icon(
                        execution['status'] == 'failed'
                            ? Icons.error_outline
                            : Icons.warning_amber_outlined,
                      ),
                      title: Text(
                        '${execution['config_id'] ?? '—'} · ${_label(execution['status'])}',
                      ),
                      subtitle: Text(
                        '${_label(execution['trigger_type'])} · ${execution['requested_at'] ?? '—'}',
                      ),
                      trailing: TextButton(
                        onPressed: () async {
                          final retried = await _showExecutionDetails(
                            context,
                            widget.api,
                            execution['execution_id'].toString(),
                          );
                          if (retried && mounted) _reload();
                        },
                        child: const Text('查看與處理'),
                      ),
                    ),
                  ),
                for (final source in attentionSources)
                  Card(
                    child: ListTile(
                      leading: const Icon(Icons.storage_outlined),
                      title: Text(
                        '${source['source_id'] ?? '—'} · ${source['dataset_id'] ?? '—'}',
                      ),
                      subtitle: Text(
                        '${_label(source['last_state'])} · 最後取得 ${source['last_fetched_at'] ?? source['updated_at'] ?? '—'}',
                      ),
                      trailing: const Text('Core'),
                    ),
                  ),
                for (final report in attentionReports)
                  Card(
                    child: ListTile(
                      leading: const Icon(Icons.analytics_outlined),
                      title: Text(
                        '${report['scope_id'] ?? report['scope_type'] ?? '—'} · ${_label(report['publication_status'] ?? report['analysis_outcome'])}',
                      ),
                      subtitle: Text(
                        '${_label(report['analysis_outcome'])} · 分析日 ${report['analysis_as_of'] ?? '—'}',
                      ),
                      trailing: const Text('Mart'),
                    ),
                  ),
              ],
            );
          },
        ),
      );
}

class _DataQualityCard extends StatelessWidget {
  const _DataQualityCard(this.api, this.result);
  final AdminApi api;
  final Map<String, dynamic>? result;

  @override
  Widget build(BuildContext context) => Card(
        child: ListTile(
          leading: const Icon(Icons.fact_check_outlined),
          title: Text(
              '週六資料品質 · ${result == null ? '尚未檢查' : _label(result!['status'])}'),
          subtitle: Text(result == null
              ? '最近檢查時間尚無紀錄'
              : '最近檢查 ${result!['checked_at'] ?? '—'}\n'
                  '${result!['needs_daily_schedule_adjustment'] == true ? '需要檢視並調整每日補資料' : result!['status'] == 'passed' ? '目前不需調整每日補資料' : '每日補資料狀態未知'}'),
          trailing: TextButton(
            child: const Text('結果與檢核文件'),
            onPressed: () => showDialog<void>(
              context: context,
              builder: (dialogContext) => AlertDialog(
                title: const Text('資料品質檢核'),
                content: SizedBox(
                  width: 700,
                  child: ListView(shrinkWrap: true, children: [
                    if (result == null) const Text('尚未檢查'),
                    for (final issue in (result?['issues'] as List? ?? []))
                      ListTile(
                        title: Text(
                            '${issue['symbol'] ?? '—'} · ${issue['dataset'] ?? '—'} · ${issue['period'] ?? '—'}'),
                        subtitle: Text(
                            '${issue['field'] ?? '—'} · ${_label(issue['reason'])}'),
                      ),
                    if (result?['status'] == 'execution_failed')
                      Text(
                          '檢查執行失敗：${result?['error_code'] ?? '未知原因'}，不能判定資料正常。'),
                    for (final entry
                        in (result?['coverage'] as Map<String, dynamic>? ?? {})
                            .entries)
                      ListTile(
                        title: Text(entry.key),
                        subtitle: Text(
                            '財報 ${entry.value['financial_quarters'] ?? '—'} 季 · '
                            '營收 ${entry.value['revenue_months'] ?? '—'} 月 · '
                            '行情 ${entry.value['price_trading_dates'] ?? '—'} 交易日'),
                      ),
                    const Text(
                        '歷史公告時間與原始版次尚未完整證明，保留 unknown；檢查通過不代表歷史 PIT 已還原。'),
                    const Divider(),
                    FutureBuilder<dynamic>(
                      future: api.get('/api/v1/admin/data-quality/runbook'),
                      builder: (context, snapshot) => snapshot.hasError
                          ? const Text('檢核文件暫時無法載入')
                          : snapshot.hasData
                              ? SelectableText(
                                  snapshot.data['content'] as String)
                              : const CircularProgressIndicator(),
                    ),
                  ]),
                ),
                actions: [
                  TextButton(
                      onPressed: () => Navigator.pop(dialogContext),
                      child: const Text('關閉'))
                ],
              ),
            ),
          ),
        ),
      );
}

class _IssueCard extends StatelessWidget {
  const _IssueCard(this.title, this.count, this.icon);
  final String title;
  final int? count;
  final IconData icon;

  @override
  Widget build(BuildContext context) => SizedBox(
        width: 220,
        child: Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(icon),
                const SizedBox(height: 16),
                Text(title, style: Theme.of(context).textTheme.titleMedium),
                Text(
                  count == null ? '待 WBS-5' : '$count 項',
                  style: Theme.of(context).textTheme.headlineMedium,
                ),
              ],
            ),
          ),
        ),
      );
}

class AdminBatchPage extends StatefulWidget {
  const AdminBatchPage(this.api, {super.key});
  final AdminApi api;

  @override
  State<AdminBatchPage> createState() => _AdminBatchPageState();
}

class _AdminBatchPageState extends State<AdminBatchPage> {
  late Future<dynamic> executions;
  bool controller = true;

  @override
  void initState() {
    super.initState();
    executions = _load();
  }

  Future<dynamic> _load() =>
      widget.api.get('/api/v1/admin/executions?limit=50');

  void _reload() => setState(() {
        executions = _load();
      });

  Future<void> _queue() async {
    final config = TextEditingController(text: 'ohlcv');
    final symbols = TextEditingController();
    var analysis = false;
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('建立批次'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: config,
                decoration: const InputDecoration(labelText: '設定 ID'),
              ),
              TextField(
                controller: symbols,
                decoration: const InputDecoration(labelText: '股票代號（逗號分隔）'),
              ),
              SwitchListTile(
                value: analysis,
                onChanged: (value) => setDialogState(() => analysis = value),
                title: const Text('分析批次'),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('取消'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, {
                'analysis': analysis,
                'config_id': config.text.trim(),
                'symbols': symbols.text
                    .split(',')
                    .map((value) => value.trim().toUpperCase())
                    .where((value) => value.isNotEmpty)
                    .toList(),
              }),
              child: const Text('加入佇列'),
            ),
          ],
        ),
      ),
    );
    config.dispose();
    symbols.dispose();
    if (result == null || (result['config_id'] as String).isEmpty) return;
    try {
      await widget.api.post(
        result['analysis'] == true
            ? '/api/v1/admin/executions/analysis'
            : '/api/v1/admin/executions/collection',
        {'config_id': result['config_id'], 'symbols': result['symbols']},
      );
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('批次無法加入佇列，請檢查設定與權限')),
        );
      }
      return;
    }
    if (!mounted) return;
    _reload();
    ScaffoldMessenger.of(context)
        .showSnackBar(const SnackBar(content: Text('批次已加入佇列')));
  }

  Future<void> _details(String id) async {
    final retried = await _showExecutionDetails(context, widget.api, id);
    if (retried && mounted) {
      _reload();
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('重試已建立新的執行紀錄')));
    }
  }

  @override
  Widget build(BuildContext context) => _AdminPage(
        title: '批次與執行紀錄',
        action: FilledButton.icon(
          onPressed: _queue,
          icon: const Icon(Icons.add),
          label: const Text('建立批次'),
        ),
        child: Column(children: [
          SegmentedButton<bool>(
              segments: const [
                ButtonSegment(value: true, label: Text('排程批次')),
                ButtonSegment(value: false, label: Text('逐項執行')),
              ],
              selected: {
                controller
              },
              onSelectionChanged: (value) =>
                  setState(() => controller = value.first)),
          Expanded(
              child: controller
                  ? AdminEffectiveBatches(widget.api)
                  : FutureBuilder<dynamic>(
                      future: executions,
                      builder: (context, snapshot) {
                        if (snapshot.connectionState != ConnectionState.done) {
                          return const Center(
                              child: CircularProgressIndicator());
                        }
                        if (snapshot.hasError)
                          return const _Message('執行紀錄暫時無法使用');
                        final values = _items(snapshot.data).toList()
                          ..sort((a, b) {
                            final order = _executionOrder(a)
                                .compareTo(_executionOrder(b));
                            if (order != 0) return order;
                            return (b['requested_at'] ?? '')
                                .toString()
                                .compareTo(
                                    (a['requested_at'] ?? '').toString());
                          });
                        if (values.isEmpty) return const _Message('目前沒有執行紀錄');
                        final attention =
                            values.where(_executionNeedsAttention).length;
                        final active = values
                            .where((value) =>
                                {'queued', 'running'}.contains(value['status']))
                            .length;
                        final completed = values
                            .where((value) => value['status'] == 'succeeded')
                            .length;
                        return Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Wrap(
                              spacing: 8,
                              runSpacing: 8,
                              children: [
                                Chip(label: Text('需要處理 $attention')),
                                Chip(label: Text('執行中 $active')),
                                Chip(label: Text('已完成 $completed')),
                              ],
                            ),
                            const SizedBox(height: 12),
                            const Text('部分完成仍列為需要處理，不會視為成功。'),
                            const SizedBox(height: 8),
                            Expanded(
                              child: ListView.separated(
                                itemCount: values.length,
                                separatorBuilder: (_, __) =>
                                    const Divider(height: 1),
                                itemBuilder: (context, index) {
                                  final value = values[index];
                                  final attention =
                                      _executionNeedsAttention(value);
                                  return ListTile(
                                    leading: Icon(
                                      attention
                                          ? Icons.warning_amber_outlined
                                          : value['status'] == 'succeeded'
                                              ? Icons.check_circle_outline
                                              : Icons.playlist_play,
                                    ),
                                    title: Text(
                                      '${value['config_id']} · ${_label(value['trigger_type'])}',
                                    ),
                                    subtitle: Text(
                                      '${_label(value['status'])} · ${value['requested_at'] ?? '—'}',
                                    ),
                                    trailing: TextButton(
                                      onPressed: () => _details(
                                          value['execution_id'].toString()),
                                      child: const Text('查看'),
                                    ),
                                  );
                                },
                              ),
                            ),
                          ],
                        );
                      },
                    )),
        ]),
      );
}

class AdminEffectiveBatches extends StatefulWidget {
  const AdminEffectiveBatches(this.api, {super.key});
  final AdminApi api;
  @override
  State<AdminEffectiveBatches> createState() => _AdminEffectiveBatchesState();
}

class _AdminEffectiveBatchesState extends State<AdminEffectiveBatches> {
  String? until;
  String? beforeId;
  late Future<dynamic> data = load();
  Future<dynamic> load() =>
      widget.api.get(Uri(path: '/api/v1/admin/batches', queryParameters: {
        'days': '3',
        if (until != null) 'until': until!,
        if (beforeId != null) 'before_id': beforeId!,
      }).toString());
  @override
  Widget build(BuildContext context) => FutureBuilder<dynamic>(
      future: data,
      builder: (context, snapshot) {
        if (snapshot.hasError)
          return Column(children: [
            const Text('排程批次暫時無法使用'),
            TextButton(
                onPressed: () => setState(() => data = load()),
                child: const Text('重試'))
          ]);
        if (!snapshot.hasData)
          return const Center(child: CircularProgressIndicator());
        final root = snapshot.data as Map;
        final rows = _items(root);
        return ListView(children: [
          const ListTile(
              title: Text('最近 3 天'),
              subtitle: Text('已定義、已部署與執行成功分別判定；派送不代表完成。')),
          for (final definition in (root['definitions'] as List? ?? []))
            ExpansionTile(
                title: Text('${definition['name']}'),
                subtitle: Text(
                    '台北時間 ${(definition['hours'] as List).map((hour) => "${hour.toString().padLeft(2, '0')}:${definition['minute'].toString().padLeft(2, '0')}").join('、')} · 部署 ${_label(definition['deployment_status'])}'),
                children: [
                  ListTile(
                      title: Text(
                          '依賴 ${(definition['dependencies'] as List).join('、')}'),
                      subtitle: Text(
                          '星期 ${(definition['weekdays'] as List).map((day) => day + 1).join('、')} · 月日 ${(definition['month_days'] as List).isEmpty ? '每日' : (definition['month_days'] as List).join('、')}'))
                ]),
          const Divider(),
          if (rows.isEmpty) const ListTile(title: Text('此期間尚無批次紀錄')),
          for (final row in rows)
            ListTile(
                title: Text('${row['batch']} · ${_label(row['status'])}'),
                subtitle: Text(
                    '排程 ${row['scheduled_at']}\n更新 ${row['updated_at']} · 結束 ${row['completion_time'] ?? '尚未完成'}'),
                trailing: IconButton(
                    icon: const Icon(Icons.info_outline),
                    tooltip: '查看',
                    onPressed: () => showDialog<void>(
                        context: context,
                        builder: (context) => AlertDialog(
                                title: Text('${row['batch']}'),
                                content: Text(
                                    '批次 ${row['occurrence_id']}\n${row['reason'] ?? '沒有失敗原因'}'),
                                actions: [
                                  TextButton(
                                      onPressed: () => Navigator.pop(context),
                                      child: const Text('關閉'))
                                ])))),
          TextButton(
              onPressed: () => setState(() {
                    beforeId = root['next_before_id']?.toString();
                    until = root['next_until']?.toString() ??
                        root['since']?.toString();
                    data = load();
                  }),
              child: const Text('更早紀錄')),
        ]);
      });
}

class AdminGovernancePage extends StatefulWidget {
  const AdminGovernancePage(this.api, {super.key});
  final AdminApi api;
  @override
  State<AdminGovernancePage> createState() => _AdminGovernancePageState();
}

class _AdminGovernancePageState extends State<AdminGovernancePage> {
  late Future<dynamic> data = widget.api.get('/api/v1/admin/data-governance');
  @override
  Widget build(BuildContext context) => _AdminPage(
      title: '資料治理',
      child: FutureBuilder<dynamic>(
          future: data,
          builder: (context, snapshot) {
            if (snapshot.hasError) return const _Message('資料治理暫時無法使用');
            if (!snapshot.hasData)
              return const Center(child: CircularProgressIndicator());
            return ListView(children: [
              const ListTile(
                  title: Text('容量與保留政策'),
                  subtitle: Text('使用已持久化營運證據；未知不補零。Private 不套用公開清理政策。')),
              for (final row in _items(snapshot.data))
                Card(
                    child: ListTile(
                        title: Text('${row['layer']}'),
                        subtitle: Text(
                            '保留 ${row['retention'] ?? '未定義'}\n最後維護 ${row['maintenance_at'] ?? '未知'}\n'
                            '有效物件 ${row['live_objects'] ?? '未知'} · 有效 bytes ${row['active_bytes'] ?? '未知'}\n'
                            '非當前版本 bytes ${row['noncurrent_bytes'] ?? '未知'} · soft-deleted bytes ${row['soft_deleted_bytes'] ?? '未知'}\n'
                            '計費 bytes ${row['billable_bytes'] ?? '未知'}'))),
            ]);
          }));
}

class AdminStockWorkbench extends StatefulWidget {
  const AdminStockWorkbench(this.api, {super.key});
  final AdminApi api;

  @override
  State<AdminStockWorkbench> createState() => _AdminStockWorkbenchState();
}

class _AdminStockWorkbenchState extends State<AdminStockWorkbench> {
  final query = TextEditingController();
  late Future<dynamic> stocks;
  Map<String, dynamic>? selected;
  Future<List<dynamic>>? detail;

  @override
  void initState() {
    super.initState();
    stocks = _search();
  }

  @override
  void dispose() {
    query.dispose();
    super.dispose();
  }

  Future<dynamic> _search() => widget.api.get(
        '/api/v1/admin/stocks?q=${Uri.encodeQueryComponent(query.text.trim())}&limit=10',
      );

  void _select(Map<String, dynamic> stock) => setState(() {
        selected = stock;
        final symbol = Uri.encodeComponent(stock['symbol'].toString());
        detail = Future.wait([
          widget.api.get('/api/v1/admin/stocks/$symbol/status'),
          widget.api.get(
            '/api/v1/admin/mart-reports?scope_type=symbol&scope_id=$symbol&limit=50',
          ),
        ]);
      });

  static int _intValue(Object? value) {
    if (value is int) return value;
    return int.tryParse(value?.toString() ?? '') ?? 0;
  }

  static String _joined(Object? value) {
    if (value is List && value.isNotEmpty) return value.join('、');
    return '—';
  }

  static bool _needsGapRepair(Map<String, dynamic> value) {
    final status = value['status']?.toString();
    final received = _intValue(value['received_symbols']);
    final requested = _intValue(value['requested_symbols']);
    return {'missing', 'unavailable', 'stale', 'partial'}.contains(status) ||
        (requested > 0 && received < requested);
  }

  static String _healthState(Map<String, dynamic> value) {
    final status = value['status']?.toString();
    final received = _intValue(value['received_symbols']);
    final requested = _intValue(value['requested_symbols']);
    final warnings = _intValue(value['dq_warning_count']);
    if (status == 'unavailable') return '無法使用';
    if (status == 'missing') return '缺資料';
    if (requested > 0 && received < requested) {
      return '缺口 ${requested - received}';
    }
    if (warnings > 0) return '$warnings 個警示';
    return '正常';
  }

  Future<List<Map<String, dynamic>>> _repairOptions(String datasetId) async {
    final catalog =
        await widget.api.get('/api/v1/admin/source-catalog?limit=200');
    final options = _items(catalog)
        .where(
          (config) =>
              config['dataset_id'] == datasetId &&
              config['enabled'] == true &&
              config['collection_enabled'] == true &&
              {'official', 'approved_fallback'}
                  .contains(config['authorization_status']),
        )
        .toList()
      ..sort((a, b) =>
          a['config_id'].toString().compareTo(b['config_id'].toString()));
    return options;
  }

  Future<void> _repair(Map<String, dynamic> health) async {
    if (selected == null) return;
    final datasetId = health['dataset_id'].toString();
    late final List<Map<String, dynamic>> options;
    try {
      options = await _repairOptions(datasetId);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('無法讀取已核准的修復設定')),
        );
      }
      return;
    }
    if (!mounted) return;
    if (options.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('$datasetId 沒有可用的已核准收集設定')),
      );
      return;
    }

    String? configId;
    if (options.length == 1) {
      configId = options.single['config_id'].toString();
    } else {
      configId = await showDialog<String>(
        context: context,
        builder: (dialogContext) => SimpleDialog(
          title: Text('選擇 $datasetId 修復設定'),
          children: [
            for (final option in options)
              SimpleDialogOption(
                onPressed: () => Navigator.pop(
                  dialogContext,
                  option['config_id'].toString(),
                ),
                child: ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(option['config_id'].toString()),
                  subtitle: Text(
                    '${_label(option['authorization_status'])} · ${_joined(option['source_ids'])}',
                  ),
                ),
              ),
          ],
        ),
      );
    }
    if (configId == null || configId.isEmpty || !mounted) return;

    try {
      await widget.api.post(
        '/api/v1/admin/executions/collection',
        {
          'config_id': configId,
          'symbols': [selected!['symbol']]
        },
      );
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('無法建立缺口修復批次，請檢查設定與權限')),
        );
      }
      return;
    }
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('已建立 $datasetId 缺口修復批次（$configId）')),
    );
  }

  @override
  Widget build(BuildContext context) => _AdminPage(
        title: '個股工作台',
        child: Column(
          children: [
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: query,
                    decoration: const InputDecoration(
                      labelText: '代號或中文名稱',
                      prefixIcon: Icon(Icons.search),
                    ),
                    onSubmitted: (_) => setState(() {
                      stocks = _search();
                    }),
                  ),
                ),
                const SizedBox(width: 8),
                FilledButton(
                  onPressed: () => setState(() {
                    stocks = _search();
                  }),
                  child: const Text('搜尋'),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Expanded(
              child: LayoutBuilder(
                builder: (context, constraints) {
                  final list = FutureBuilder<dynamic>(
                    future: stocks,
                    builder: (context, snapshot) {
                      if (snapshot.connectionState != ConnectionState.done) {
                        return const Center(child: CircularProgressIndicator());
                      }
                      if (snapshot.hasError) {
                        return const _Message('股票資料暫時無法使用');
                      }
                      final values = _items(snapshot.data);
                      if (values.isEmpty) return const _Message('找不到符合條件的股票');
                      return ListView(
                        children: values
                            .map(
                              (stock) => ListTile(
                                selected:
                                    selected?['symbol'] == stock['symbol'],
                                title: Text(
                                  '${stock['symbol']} ${stock['name'] ?? ''}',
                                ),
                                subtitle: Text(
                                  '${stock['market'] ?? '—'} · ${stock['enabled'] == true ? '已啟用' : '已停用'}',
                                ),
                                onTap: () => _select(stock),
                              ),
                            )
                            .toList(),
                      );
                    },
                  );
                  final details = selected == null
                      ? const _Message('選擇股票以查看資料健康與修復缺口')
                      : FutureBuilder<List<dynamic>>(
                          future: detail,
                          builder: (context, snapshot) {
                            if (snapshot.connectionState !=
                                ConnectionState.done) {
                              return const Center(
                                child: CircularProgressIndicator(),
                              );
                            }
                            if (snapshot.hasError) {
                              return const _Message('個股資料暫時無法使用');
                            }
                            final health = _items(snapshot.data![0]);
                            final reports = _items(snapshot.data![1]);
                            return ListView(
                              children: [
                                Card(
                                  child: ListTile(
                                    leading: const Icon(Icons.lock_outline),
                                    title: const Text('AI 五角色／CIO 尚未啟用'),
                                    subtitle: const Text(
                                      'Fact Pack、AI role 與 CIO contracts 完成前，個股工作台不提供 role rerun 或歷史角色操作。',
                                    ),
                                  ),
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  '資料健康',
                                  style:
                                      Theme.of(context).textTheme.titleMedium,
                                ),
                                if (health.isEmpty) const Text('目前沒有 Core 資料'),
                                ...health.map((value) {
                                  final received =
                                      _intValue(value['received_symbols']);
                                  final requested =
                                      _intValue(value['requested_symbols']);
                                  final gap = requested > received
                                      ? requested - received
                                      : 0;
                                  final repairable = _needsGapRepair(value);
                                  return Card(
                                    child: ListTile(
                                      dense: true,
                                      title:
                                          Text(value['dataset_id'].toString()),
                                      subtitle: Text(
                                        '筆數 ${value['row_count'] ?? '—'} · 覆蓋 $received/$requested${gap > 0 ? ' · 缺口 $gap' : ''}\n'
                                        '資料日 ${value['latest_date'] ?? '—'}',
                                      ),
                                      trailing: Wrap(
                                        spacing: 8,
                                        crossAxisAlignment:
                                            WrapCrossAlignment.center,
                                        children: [
                                          Text(_healthState(value)),
                                          if (repairable)
                                            FilledButton.tonal(
                                              onPressed: () => _repair(value),
                                              child: const Text('修復'),
                                            ),
                                        ],
                                      ),
                                    ),
                                  );
                                }),
                                ExpansionTile(
                                  title: const Text('技術追蹤（唯讀）'),
                                  subtitle:
                                      const Text('舊 execution／snapshot 保持不可變更'),
                                  children: [
                                    for (final value in health)
                                      ListTile(
                                        title: Text(
                                          value['dataset_id'].toString(),
                                        ),
                                        subtitle: Text(
                                          '來源 ${_joined(value['source_ids'])}\n'
                                          'execution ${_joined(value['execution_ids'])}\n'
                                          'snapshot ${_joined(value['snapshot_ids'])}\n'
                                          'provenance ${_joined(value['provenance_ids'])}\n'
                                          'freshness ${value['freshness'] ?? '—'} · 更新 ${value['updated_at'] ?? '—'}',
                                        ),
                                      ),
                                  ],
                                ),
                                const Divider(),
                                Text(
                                  '歷史分析',
                                  style:
                                      Theme.of(context).textTheme.titleMedium,
                                ),
                                const Text(
                                  '僅顯示既有 persisted Mart 紀錄；不代表五角色、CIO 或 role rerun 已可用。',
                                ),
                                if (reports.isEmpty) const Text('目前沒有已持久化分析'),
                                ...reports.map(
                                  (value) => ListTile(
                                    dense: true,
                                    title: Text(
                                      '${value['analysis_as_of'] ?? '—'} · ${_label(value['analysis_outcome'])}',
                                    ),
                                    subtitle: Text(
                                      '版本 ${value['prompt_version'] ?? '—'} · ${_label(value['publication_status'])}',
                                    ),
                                  ),
                                ),
                              ],
                            );
                          },
                        );
                  if (constraints.maxWidth < 760) {
                    return Column(
                      children: [
                        Expanded(flex: 2, child: list),
                        const Divider(),
                        Expanded(flex: 3, child: details),
                      ],
                    );
                  }
                  return Row(
                    children: [
                      SizedBox(width: 300, child: list),
                      const VerticalDivider(),
                      Expanded(child: details),
                    ],
                  );
                },
              ),
            ),
          ],
        ),
      );
}

class AdminMarketUniversePage extends StatefulWidget {
  const AdminMarketUniversePage(this.api, {super.key});
  final AdminApi api;

  @override
  State<AdminMarketUniversePage> createState() =>
      _AdminMarketUniversePageState();
}

class _AdminMarketUniversePageState extends State<AdminMarketUniversePage> {
  late Future<dynamic> data;
  final search = TextEditingController();
  final remove = TextEditingController();
  final add = TextEditingController();
  final reason = TextEditingController();
  bool saving = false;
  bool showUpcoming = true;

  @override
  void initState() {
    super.initState();
    data = widget.api.get('/api/v1/admin/market-universe');
  }

  @override
  void dispose() {
    search.dispose();
    remove.dispose();
    add.dispose();
    reason.dispose();
    super.dispose();
  }

  void reload() => setState(() {
        data = widget.api.get('/api/v1/admin/market-universe');
      });

  Future<void> swap(int version) async {
    setState(() => saving = true);
    try {
      await widget.api.post('/api/v1/admin/market-universe/swap', {
        'remove_symbol': remove.text.trim(),
        'add_symbol': add.text.trim(),
        'reason': reason.text.trim(),
        'expected_version': version,
      });
      if (!mounted) return;
      remove.clear();
      add.clear();
      reason.clear();
      reload();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('市場資訊名單已更新')),
      );
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('無法更新名單，請重新整理並確認代號與原因')),
      );
    } finally {
      if (mounted) setState(() => saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => _AdminPage(
        title: '市場資訊 · 每週成交量前 500 檔',
        action: IconButton(
          tooltip: '重新整理市場資訊',
          onPressed: reload,
          icon: const Icon(Icons.refresh),
        ),
        child: FutureBuilder<dynamic>(
          future: data,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.hasError) return const _Message('市場資訊暫時無法使用');
            final snapshots = snapshot.data as Map<String, dynamic>;
            final current = snapshots['current'] as Map<String, dynamic>;
            final upcoming = snapshots['upcoming'] as Map<String, dynamic>;
            final hasUpcoming = upcoming['status'] == 'available';
            final value = showUpcoming && hasUpcoming ? upcoming : current;
            if (value['status'] != 'available' && !hasUpcoming) {
              return const _Message('尚無通過完整交易週檢查的 500 檔名單');
            }
            final items = _items(value);
            final query = search.text.trim().toLowerCase();
            final visible = items
                .where((item) =>
                    query.isEmpty ||
                    item['symbol'].toString().toLowerCase().contains(query) ||
                    item['name'].toString().toLowerCase().contains(query))
                .toList();
            final entered = (value['entered'] as List? ?? const []).join('、');
            final exited = (value['exited'] as List? ?? const []).join('、');
            return ListView(
              children: [
                Wrap(spacing: 8, children: [
                  ChoiceChip(
                    label: const Text('目前有效名單'),
                    selected: !showUpcoming || !hasUpcoming,
                    onSelected: (_) => setState(() => showUpcoming = false),
                  ),
                  ChoiceChip(
                    label: const Text('即將生效名單'),
                    selected: showUpcoming && hasUpcoming,
                    onSelected: hasUpcoming
                        ? (_) => setState(() => showUpcoming = true)
                        : null,
                  ),
                ]),
                if (value['status'] != 'available')
                  const Card(child: ListTile(title: Text('目前尚無有效名單')))
                else ...[
                  Card(
                      child: ListTile(
                    title: Text(
                        '${showUpcoming && hasUpcoming ? '即將生效' : '目前有效'} · 第 ${value['version']} 版 · ${items.length} 檔'),
                    subtitle: Text(
                        '週別 ${value['week_start']} · 生效 ${value['effective_from']}'),
                  )),
                  Card(
                      child: Column(children: [
                    ListTile(
                        title: const Text('進入'),
                        subtitle: Text(entered.isEmpty ? '首版／無變動' : entered)),
                    ListTile(
                        title: const Text('退出'),
                        subtitle: Text(exited.isEmpty ? '無變動' : exited)),
                  ])),
                  if (showUpcoming && hasUpcoming || !hasUpcoming)
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              Text('手動換股',
                                  style:
                                      Theme.of(context).textTheme.titleMedium),
                              const SizedBox(height: 8),
                              TextField(
                                  controller: remove,
                                  decoration:
                                      const InputDecoration(labelText: '移出代號')),
                              TextField(
                                  controller: add,
                                  decoration:
                                      const InputDecoration(labelText: '納入代號')),
                              TextField(
                                  controller: reason,
                                  decoration:
                                      const InputDecoration(labelText: '調整原因')),
                              const SizedBox(height: 12),
                              Align(
                                  alignment: Alignment.centerLeft,
                                  child: FilledButton(
                                    onPressed: saving
                                        ? null
                                        : () => swap(value['version'] as int),
                                    child: const Text('儲存換股'),
                                  )),
                            ]),
                      ),
                    ),
                  TextField(
                    controller: search,
                    decoration: const InputDecoration(
                        labelText: '搜尋代號或名稱', prefixIcon: Icon(Icons.search)),
                    onChanged: (_) => setState(() {}),
                  ),
                  for (final item in visible)
                    ListTile(
                      dense: true,
                      title: Text(
                          '${item['rank']}. ${item['name']} ${item['symbol']}'),
                      subtitle: Text(
                          '${item['market']} · 當週成交股數 ${item['volume_shares'] ?? '人工調整'}'),
                      trailing: item['manual_override'] == true
                          ? const Text('人工')
                          : null,
                    ),
                ],
              ],
            );
          },
        ),
      );
}

class _AdminPage extends StatelessWidget {
  const _AdminPage({required this.title, required this.child, this.action});
  final String title;
  final Widget child;
  final Widget? action;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    title,
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                ),
                if (action != null) action!,
              ],
            ),
            const SizedBox(height: 16),
            Expanded(child: child),
          ],
        ),
      );
}

class _Message extends StatelessWidget {
  const _Message(this.value);
  final String value;
  @override
  Widget build(BuildContext context) => Center(child: Text(value));
}

class _PendingPage extends StatelessWidget {
  const _PendingPage({required this.title, required this.message});
  final String title;
  final String message;
  @override
  Widget build(BuildContext context) => _AdminPage(
        title: title,
        child: Align(
          alignment: Alignment.topLeft,
          child: Card(
            child: Padding(
                padding: const EdgeInsets.all(20), child: Text(message)),
          ),
        ),
      );
}
