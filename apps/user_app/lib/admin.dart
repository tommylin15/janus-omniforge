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
    }[value?.toString()] ??
    value?.toString() ??
    '—';

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
      icon: Icon(Icons.psychology_outlined),
      label: Text('AI 分析'),
    ),
    NavigationRailDestination(
      icon: Icon(Icons.settings_outlined),
      label: Text('進階管理'),
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final pages = [
      AdminOverviewPage(widget.api),
      AdminBatchPage(widget.api),
      AdminStockWorkbench(widget.api),
      const _PendingPage(title: 'AI 分析', message: '等待 WBS-5 五角色與 CIO 契約完成後啟用。'),
      const _PendingPage(title: '進階管理', message: '資料源、排程與治理仍由既有資料營運中心提供。'),
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
                      icon: Icon(Icons.psychology_outlined),
                      label: Text('AI 分析'),
                    ),
                    NavigationDrawerDestination(
                      icon: Icon(Icons.settings_outlined),
                      label: Text('進階管理'),
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
  ]);

  @override
  Widget build(BuildContext context) => _AdminPage(
    title: '需要處理的事項',
    action: IconButton(
      tooltip: '重新整理',
      onPressed: () => setState(() { data = _load(); }),
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
        final failed = executions
            .where(
              (value) =>
                  {'failed', 'partial', 'retrying'}.contains(value['status']),
            )
            .length;
        final core = sources
            .where(
              (value) => !{'success', 'succeeded'}.contains(value['state']),
            )
            .length;
        final mart = reports
            .where(
              (value) => {'blocked', 'review_required', 'invalid'}.contains(
                value['publication_status'] ?? value['analysis_outcome'],
              ),
            )
            .length;
        final total = failed + core + mart;
        return ListView(
          children: [
            if (sources.isEmpty)
              const Card(child: ListTile(title: Text('尚無資料源健康紀錄，無法判定 Core 狀態'))),
            if (total == 0 && sources.isNotEmpty)
              const Card(
                child: ListTile(
                  leading: Icon(Icons.check_circle_outline),
                  title: Text('今日沒有需要處理的事項'),
                ),
              ),
            Wrap(
              spacing: 12,
              runSpacing: 12,
              children: [
                _IssueCard('Core', core, Icons.storage_outlined),
                _IssueCard('Mart', mart, Icons.analytics_outlined),
                const _IssueCard('AI 分析', null, Icons.psychology_outlined),
                _IssueCard('失敗／阻擋', failed, Icons.error_outline),
              ],
            ),
          ],
        );
      },
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
            Text(count == null ? '待 WBS-5' : '$count 項',
                style: Theme.of(context).textTheme.headlineMedium),
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

  @override
  void initState() {
    super.initState();
    executions = _load();
  }

  Future<dynamic> _load() =>
      widget.api.get('/api/v1/admin/executions?limit=50');

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
            const SnackBar(content: Text('批次無法加入佇列，請檢查設定與權限')));
      }
      return;
    }
    if (!mounted) return;
    setState(() { executions = _load(); });
    ScaffoldMessenger.of(context)
        .showSnackBar(const SnackBar(content: Text('批次已加入佇列')));
  }

  Future<void> _details(String id) async {
    late final Map<String, dynamic> detail;
    try {
      detail = await widget.api.get(
        '/api/v1/admin/executions/${Uri.encodeComponent(id)}',
      ) as Map<String, dynamic>;
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('執行明細暫時無法使用')));
      }
      return;
    }
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('執行 ${detail['status'] ?? '—'}'),
        content: SizedBox(
          width: 640,
          child: ListView(
            shrinkWrap: true,
            children: _items(detail)
                .map(
                  (item) => ListTile(
                    title: Text('${item['dataset_id']} · ${item['source_id']}'),
                    subtitle: Text(
                      '${_label(item['state'])} · ${item['safe_message'] ?? '—'}',
                    ),
                    trailing: item['retry_classification'] == 'retryable'
                        ? FilledButton.tonal(
                            onPressed: () async {
                              try {
                                await widget.api.post(
                                  '/api/v1/admin/executions/${Uri.encodeComponent(id)}/items/${Uri.encodeComponent(item['item_key'].toString())}/retry',
                                  const {},
                                );
                              } catch (_) {
                                if (context.mounted) {
                                  ScaffoldMessenger.of(context).showSnackBar(
                                      const SnackBar(content: Text('此項目目前無法重試')));
                                }
                                return;
                              }
                              if (context.mounted) Navigator.pop(context);
                            },
                            child: const Text('重試'),
                          )
                        : Text(_label(item['retry_classification'])),
                  ),
                )
                .toList(),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('關閉'),
          ),
        ],
      ),
    );
    if (mounted) setState(() { executions = _load(); });
  }

  @override
  Widget build(BuildContext context) => _AdminPage(
    title: '批次與執行紀錄',
    action: FilledButton.icon(
      onPressed: _queue,
      icon: const Icon(Icons.add),
      label: const Text('建立批次'),
    ),
    child: FutureBuilder<dynamic>(
      future: executions,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) return const _Message('執行紀錄暫時無法使用');
        final values = _items(snapshot.data);
        if (values.isEmpty) return const _Message('目前沒有執行紀錄');
        return ListView.separated(
          itemCount: values.length,
          separatorBuilder: (_, __) => const Divider(height: 1),
          itemBuilder: (context, index) {
            final value = values[index];
            return ListTile(
              leading: const Icon(Icons.playlist_play),
              title: Text(
                '${value['config_id']} · ${_label(value['trigger_type'])}',
              ),
              subtitle: Text(
                '${_label(value['status'])} · ${value['requested_at'] ?? '—'}',
              ),
              trailing: TextButton(
                onPressed: () => _details(value['execution_id'].toString()),
                child: const Text('查看'),
              ),
            );
          },
        );
      },
    ),
  );
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

  Future<void> _queue(bool analysis) async {
    final config = TextEditingController(text: 'ohlcv');
    final value = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(analysis ? '建立分析批次' : '修復資料缺口'),
        content: TextField(
          controller: config,
          decoration: const InputDecoration(labelText: '設定 ID'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, config.text.trim()),
            child: const Text('加入佇列'),
          ),
        ],
      ),
    );
    config.dispose();
    if (value == null || value.isEmpty || selected == null) return;
    try {
      await widget.api.post(
        analysis
            ? '/api/v1/admin/executions/analysis'
            : '/api/v1/admin/executions/collection',
        {'config_id': value, 'symbols': [selected!['symbol']]},
      );
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('無法建立執行紀錄，請檢查設定與權限')));
      }
      return;
    }
    if (mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('已建立新的執行紀錄')));
    }
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
                onSubmitted: (_) => setState(() { stocks = _search(); }),
              ),
            ),
            const SizedBox(width: 8),
            FilledButton(
              onPressed: () => setState(() { stocks = _search(); }),
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
                            selected: selected?['symbol'] == stock['symbol'],
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
                  ? const _Message('選擇股票以查看資料健康與歷史分析')
                  : FutureBuilder<List<dynamic>>(
                      future: detail,
                      builder: (context, snapshot) {
                        if (snapshot.connectionState != ConnectionState.done) {
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
                            Wrap(
                              spacing: 8,
                              children: [
                                FilledButton.tonal(
                                  onPressed: () => _queue(false),
                                  child: const Text('修復資料缺口'),
                                ),
                                FilledButton.tonal(
                                  onPressed: () => _queue(true),
                                  child: const Text('重新分析'),
                                ),
                              ],
                            ),
                            const SizedBox(height: 12),
                            Text(
                              '資料健康',
                              style: Theme.of(context).textTheme.titleMedium,
                            ),
                            if (health.isEmpty) const Text('目前沒有 Core 資料'),
                            ...health.map(
                              (value) => ListTile(
                                dense: true,
                                title: Text(value['dataset_id'].toString()),
                                subtitle: Text(
                                  '筆數 ${value['row_count'] ?? '—'} · 覆蓋 ${value['received_symbols'] ?? '—'}/${value['requested_symbols'] ?? '—'}',
                                ),
                                trailing: Text(
                                  value['dq_warning_count'] == 0
                                      ? '正常'
                                      : '${value['dq_warning_count']} 個警示',
                                ),
                              ),
                            ),
                            const Divider(),
                            Text(
                              '歷史分析',
                              style: Theme.of(context).textTheme.titleMedium,
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
        child: Padding(padding: const EdgeInsets.all(20), child: Text(message)),
      ),
    ),
  );
}
