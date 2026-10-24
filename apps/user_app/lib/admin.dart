import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'admin_analysis.dart';
import 'usage.dart';
import 'admin_usage.dart';

/// Admin-only decimal MB formatting. Missing byte counts stay unknown.
String formatAdminStorageMb(Object? bytes) {
  if (bytes is! num || !bytes.isFinite || bytes < 0) return '未知';
  final parts = (bytes / 1000000).toStringAsFixed(2).split(".");
  return '${_groupAdminDigits(parts[0])}.${parts[1]} MB';
}

String formatAdminStorageCount(Object? count) =>
    count is int && count >= 0 ? _groupAdminDigits(count.toString()) : '未知';

String _groupAdminDigits(String digits) {
  final out = StringBuffer();
  for (var i = 0; i < digits.length; ++i) {
    if (i > 0 && (digits.length - i) % 3 == 0) out.write(',');
    out.write(digits[i]);
  }
  return out.toString();
}

int? adminStorageTotalBytes(Object? totals) {
  if (totals is! Map) return null;
  final values = [
    totals['current_bytes'],
    totals['noncurrent_bytes'],
    totals['soft_deleted_bytes']
  ];
  if (values.any((v) => v is! int || v < 0)) return null;
  return values.cast<int>().reduce((a, b) => a + b);
}

abstract class AdminApi {
  Future<dynamic> get(String path);
  Future<dynamic> post(String path, Map<String, dynamic> body);
  Future<dynamic> put(String path, Map<String, dynamic> body);
  Future<dynamic> patch(String path, Map<String, dynamic> body);
}

class AdminSections extends StatefulWidget {
  const AdminSections(
      {required this.api,
      required this.title,
      required this.labels,
      required this.pages,
      this.initialSection = 0,
      this.onSection,
      super.key});
  final AdminApi api;
  final String title;
  final List<String> labels;
  final List<Widget Function()> pages;
  final int initialSection;
  final ValueChanged<int>? onSection;
  @override
  State<AdminSections> createState() => _AdminSectionsState();
}

class _AdminSectionsState extends State<AdminSections> {
  late int selected = widget.initialSection;
  @override
  Widget build(BuildContext context) => Column(children: [
        Padding(
            padding: const EdgeInsets.all(12),
            child: DropdownButtonFormField<int>(
              initialValue: selected,
              decoration: InputDecoration(labelText: widget.title),
              items: [
                for (var i = 0; i < widget.labels.length; i++)
                  DropdownMenuItem(value: i, child: Text(widget.labels[i]))
              ],
              onChanged: (value) {
                if (value != null) {
                  setState(() => selected = value);
                  widget.onSection?.call(value);
                }
              },
            )),
        Expanded(
            child: KeyedSubtree(
                key: ValueKey(selected), child: widget.pages[selected]())),
      ]);
}

class AdminSourceHealthPage extends StatefulWidget {
  const AdminSourceHealthPage(this.api, {super.key});
  final AdminApi api;
  @override
  State<AdminSourceHealthPage> createState() => _AdminSourceHealthPageState();
}

class AdminReadinessPage extends StatefulWidget {
  const AdminReadinessPage(this.api, {super.key});
  final AdminApi api;
  @override
  State<AdminReadinessPage> createState() => _AdminReadinessPageState();
}

class AdminStockPeriods extends StatefulWidget {
  const AdminStockPeriods(this.api, this.symbol, {super.key});
  final AdminApi api;
  final String symbol;
  @override
  State<AdminStockPeriods> createState() => _AdminStockPeriodsState();
}

class _AdminStockPeriodsState extends State<AdminStockPeriods> {
  late final data = Future.wait([
    for (final metric in ['eps', 'revenue'])
      widget.api
          .get(
              '/api/v1/public/stocks/${Uri.encodeComponent(widget.symbol)}/visual-series?metric=$metric&limit=120')
          .catchError((_) => <String, dynamic>{})
  ]);
  @override
  Widget build(BuildContext context) => FutureBuilder<List<dynamic>>(
      future: data,
      builder: (context, snapshot) {
        if (!snapshot.hasData) return const ListTile(title: Text('合法期別讀取中'));
        final eps = snapshot.data![0] as Map;
        final revenue = snapshot.data![1] as Map;
        final current = eps['eps_current_year'] as Map? ?? {};
        return ExpansionTile(title: const Text('財報與營收合法期別'), children: [
          ListTile(
              title: Text(
                  '${current['year'] ?? '本年度'} 官方單季 EPS · ${current['status'] ?? '尚未驗證'}'),
              subtitle: Text(
                  '應到季度 ${current['required_quarters'] ?? '未知'} · 已有季度 ${current['available_quarters'] ?? '未知'}\n歷史四連季／TTM ${current['trailing_four_quarter_status'] ?? '未認證'}')),
          ListTile(
              title: Text('營收資料日 ${revenue['data_as_of'] ?? '未知'}'),
              subtitle: Text(
                  '有效期數 ${revenue['usable_points'] ?? '未知'} · 來源 ${revenue['source_ids'] ?? '未知'}')),
        ]);
      });
}

class _AdminReadinessPageState extends State<AdminReadinessPage> {
  late final data =
      widget.api.get('/api/v1/admin/settings/data_readiness_ledger');
  @override
  Widget build(BuildContext context) => FutureBuilder<dynamic>(
      future: data,
      builder: (context, snapshot) {
        if (snapshot.hasError) return const _Message('資料可用性暫時無法讀取');
        if (!snapshot.hasData)
          return const Center(child: CircularProgressIndicator());
        final value = (snapshot.data as Map)['value'] as Map?;
        if (value == null)
          return const _Message('尚無持久化 Data Readiness Ledger；狀態未知');
        final markets = value['market_price_window'] as Map? ?? {};
        return ListView(children: [
          ListTile(
              title: Text('資料日 ${value['as_of'] ?? '未知'}'),
              subtitle: Text(
                  '檢查 ${value['checked_at'] ?? '未知'} · ${value['status'] ?? '未知'}')),
          const ListTile(
              title: Text('上市至少90%／上櫃至少70%'),
              subtitle: Text('股票與債券 ETF 分母分開；單股可用不等於整市場通過。')),
          for (final market in ['TWSE', 'TPEX'])
            ListTile(
                title: Text(market == 'TWSE' ? '上市價量' : '上櫃價量'),
                subtitle: Text(
                    '狀態 ${_label((markets[market] as Map?)?['status'] ?? 'unknown')} · 合格 ${(markets[market] as Map?)?['symbols_with_20_of_21_sessions'] ?? '未知'}／${(markets[market] as Map?)?['expected'] ?? '未知'}')),
          for (final entry in const {
            'focus_120d': '持股與關注股：120個交易日行情',
            'monthly_revenue_13': '營收13個有效月份',
            'eps_current_year': '本年度單季每股盈餘',
            'eps_4_comparable': '歷史四連季／TTM（不等於本年度 EPS）'
          }.entries)
            ListTile(
                title: Text(entry.value),
                subtitle: Text(
                    '狀態 ${_label((value[entry.key] as Map?)?['status'] ?? 'unknown')} · 合格 ${(value[entry.key] as Map?)?['qualified'] ?? '未知'}／${(value[entry.key] as Map?)?['expected'] ?? '未知'}')),
          const ListTile(
              title: Text('歷史 PIT／TTM 不自動認證'),
              subtitle: Text('缺合法期別、來源或完整歷史時維持未認證；不以當期 EPS 通過代替歷史 TTM。')),
          ExpansionTile(title: const Text('來源與快照'), children: [
            ListTile(
                title: Text('快照 ${value['snapshot_ids'] ?? '未知'}'),
                subtitle:
                    Text('母體版本 ${value['market_membership_version'] ?? '未知'}'))
          ]),
        ]);
      });
}

class _AdminSourceHealthPageState extends State<AdminSourceHealthPage> {
  late final data =
      widget.api.get('/api/v1/admin/source-health?limit=200&active_only=true');
  @override
  Widget build(BuildContext context) => FutureBuilder<dynamic>(
      future: data,
      builder: (context, snapshot) {
        if (snapshot.hasError) return const _Message('採集來源暫時無法讀取，請稍後重試');
        if (!snapshot.hasData)
          return const Center(child: CircularProgressIndicator());
        final rows = _items(snapshot.data);
        if (rows.isEmpty) return const _Message('尚無來源證據，狀態未知');
        return ListView(children: [
          const ListTile(
              title: Text('採集來源狀態'),
              subtitle: Text('查看最近資料是否取得成功。多個股票同時缺資料時，先檢查這裡。')),
          for (final row in rows)
            ListTile(
              title: Text(
                  '${_label(row['source_id'])} · ${_label(row['dataset_id'])}'),
              subtitle: Text(
                  '${_label(row['last_state'])} · ${row['last_fetched_at'] ?? row['updated_at'] ?? '未知'}'),
            )
        ]);
      });
}

List<Map<String, dynamic>> _items(dynamic value) =>
    ((value as Map<String, dynamic>?)?['items'] as List? ?? const [])
        .cast<Map<String, dynamic>>();

String _label(Object? value) =>
    const {
      'queued': '排隊中',
      'running': '執行中',
      'cancel_requested': '正在中止',
      'cancelled': '已中止',
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
      'unknown': '尚未確認',
      'TWSE': '上市',
      'TPEX': '上櫃',
      'already_queued': '已有同一筆執行請求，不會重複建立',
      'stop_requested': '已要求停止，等待雲端執行終態確認',
      'stop_not_confirmed': '未確認停止成功，請查看實際執行狀態與權限',
      'cannot_safely_stop': '無法確認安全停止條件，可暫停後續排程',
      'admin_stopped': '由管理者停止',
      'applied': '已套用',
      'stopped': '已停止',
      'no_eligible_slot': '尚無可執行的排程時段',
      'already_dispatched_cannot_stop': '工作已派送，無法用排隊停止操作中止',
      'reconcile': '更新實際執行結果',
      'dispatch_result': '派送結果',
      'dispatch_intent': '準備派送',
      'admin_control': '管理者操作已由總控處理',
      'stage': '暫存資料',
      'core': '市場原始資料',
      'research': '研究資料',
      'cloudbuild': '舊建置檔案',
      'duplicate_active_work': '已有同一支程式執行中，本次未重複啟動',
      'admin_stopped_before_dispatch': '已在派送前停止',
      'admin_paused': '已暫停後續排程',
      'queue_empty': '沒有待處理資料，不需執行',
      'market_holiday': '休市日不執行',
      'waiting_dependency': '等待上游工作完成',
      'job_busy': '等待其他共用工作完成',
      'upstream_ingestion_failed': '上游資料收集失敗，本次未執行',
      'schedule_superseded': '舊排程已被取代，本次略過',
      'cloud_run_operation_failed': '雲端執行失敗，請查看執行紀錄',
      'inspect_cloud_execution_before_manual_recovery': '執行結果不確定，需先確認再重試',
      'PASS': '達標',
      'FAIL': '未達標',
      'PARTIAL': '部分資料缺漏',
      'OBSERVED': '盤點完成',
      'KNOWN_BUCKETS_COMPLETE': '六桶盤點完成',
      'PARTIAL_NOT_TOTAL': '部分空間無法讀取，暫無合計',
      'BLOCKED': '無法讀取',
      'TRUNCATED': '尚未查完',
      'PENDING': '等待資料',
      'NOT_VERIFIED': '尚未確認',
      'ambiguous': '結果尚未確認',
      'dispatched': '已派送，尚未完成',
      'dispatching': '派送中',
      'pending': '等待執行',
      'skipped': '本次略過',
      'available': '可用',
      'missing': '缺資料',
      'stale': '資料尚未更新',
      'ohlcv': '每日股價與成交量',
      'financials': '財報',
      'revenue': '月營收',
      'monthly_revenue': '月營收',
      'valuation': '本益比與股價淨值比',
      'twse': '證交所',
      'tpex': '櫃買中心',
      'mops': '公開資訊觀測站',
      'ingestion': '定時收集資料',
      'data-supplement': '補齊缺漏資料',
      'market-screening': '全市場分析',
      'mart': '更新分析結果',
      'private': '更新個人損益',
      'ledger-backup': '交易資料備份',
      'data-quality': '每週資料檢查',
      'stage-cleanup': '清理過期暫存',
      'mobile-ledger': '處理記帳佇列',
      'iceberg-compaction': '整理資料檔案',
      'core-cleanup': '清理過期市場資料',
      'mart-cleanup': '清理過期分析結果',
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
    this.brokerProfile,
    required this.email,
    required this.onTheme,
    this.usage,
    super.key,
  });
  final AdminApi api;
  final Widget? brokerProfile;
  final String email;
  final ValueChanged<ThemeMode> onTheme;
  final UsageTracker? usage;

  @override
  State<AdminWorkspace> createState() => _AdminWorkspaceState();
}

class _AdminWorkspaceState extends State<AdminWorkspace> {
  int page = 0;
  Map<String, dynamic>? repairTarget;
  final sections = <int, int>{};
  static const routes = ['overview', 'batches', 'quality', 'settings'];
  // Keep existing numeric bookmarks when removing the retired list preview.
  static const sectionRoutes = [
    [0, 1],
    [0, 1],
    [0, 2, 3, 4],
    [0, 1]
  ];
  void updateRoute() {
    SystemNavigator.routeInformationUpdated(
        uri: Uri.base.replace(
            fragment:
                'admin/${routes[page]}/${sectionRoutes[page][sections[page] ?? 0]}'));
  }

  @override
  void initState() {
    super.initState();
    final route = Uri.base.fragment.split('#').last.split('/');
    if (route.length >= 2 && route[0] == 'admin' && routes.contains(route[1])) {
      page = routes.indexOf(route[1]);
      final section = route.length >= 3 ? int.tryParse(route[2]) ?? 0 : 0;
      final index = sectionRoutes[page].indexOf(section);
      sections[page] = index >= 0 ? index : (page == 3 && section == 2 ? 1 : 0);
    }
    widget.usage?.feature = [
      'admin_overview',
      'admin_batches',
      'admin_quality',
      'admin_settings'
    ][page];
    if (widget.usage != null) unawaited(widget.usage!.start());
  }

  @override
  void dispose() {
    widget.usage?.dispose();
    super.dispose();
  }

  void selectPage(int value) {
    widget.usage?.select([
      'admin_overview',
      'admin_batches',
      'admin_quality',
      'admin_settings'
    ][value]);
    setState(() => page = value);
    updateRoute();
  }

  static const destinations = [
    NavigationRailDestination(
      icon: Icon(Icons.dashboard_outlined),
      label: Text('總覽'),
    ),
    NavigationRailDestination(
      icon: Icon(Icons.view_list_outlined),
      label: Text('批次'),
    ),
    NavigationRailDestination(
        icon: Icon(Icons.fact_check_outlined), label: Text('資料品質')),
    NavigationRailDestination(
        icon: Icon(Icons.settings_outlined), label: Text('系統設定')),
  ];

  @override
  Widget build(BuildContext context) {
    final pages = [
      AdminSections(
          key: const ValueKey('overview'),
          api: widget.api,
          title: '總覽',
          initialSection: sections[0] ?? 0,
          onSection: (value) {
            sections[0] = value;
            updateRoute();
          },
          labels: const [
            '待處理事項',
            '使用情況'
          ],
          pages: [
            () => AdminOverviewPage(widget.api, onOpen: (target, section) {
                  sections[target] = section;
                  selectPage(target);
                }),
            () => AdminUsagePage(widget.api),
          ]),
      AdminSections(
          key: const ValueKey('批次'),
          api: widget.api,
          title: '批次',
          initialSection: sections[1] ?? 0,
          onSection: (value) {
            sections[1] = value;
            updateRoute();
          },
          labels: const [
            '自動工作與紀錄',
            '損益重算'
          ],
          pages: [
            () => AdminBatchPage(widget.api, repairTarget: repairTarget),
            () => AdminGovernancePage(widget.api, section: 'operations'),
          ]),
      AdminSections(
          key: const ValueKey('資料品質'),
          api: widget.api,
          title: '資料品質',
          initialSection: sections[2] ?? 0,
          onSection: (value) {
            sections[2] = value;
            updateRoute();
          },
          labels: const [
            '全市場資料健康',
            '個股資料查修',
            '採集來源狀態',
            '儲存空間'
          ],
          pages: [
            () => AdminReadinessPage(widget.api),
            () => AdminStockWorkbench(widget.api, onRepair: (target) {
                  repairTarget = target;
                  sections[1] = 0;
                  selectPage(1);
                }),
            () => AdminSourceHealthPage(widget.api),
            () => AdminGovernancePage(widget.api, section: 'storage'),
          ]),
      AdminSections(
          key: const ValueKey('系統設定'),
          api: widget.api,
          title: '系統設定',
          initialSection: sections[3] ?? 0,
          onSection: (value) {
            sections[3] = value;
            updateRoute();
          },
          labels: const [
            '模型與報告管理',
            '券商與隱私設定'
          ],
          pages: [
            () => AdminAnalysisPage(widget.api),
            () => AdminGovernancePage(widget.api,
                section: 'settings',
                brokerProfile: widget.brokerProfile,
                usage: widget.usage),
          ]),
    ];
    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= 900;
        return Listener(
            onPointerDown: (_) => widget.usage?.interaction(),
            child: Focus(
                onKeyEvent: (_, __) {
                  widget.usage?.interaction();
                  return KeyEventResult.ignored;
                },
                child: Scaffold(
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
                            selectPage(value);
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
                                icon: Icon(Icons.fact_check_outlined),
                                label: Text('資料品質')),
                            NavigationDrawerDestination(
                                icon: Icon(Icons.settings_outlined),
                                label: Text('系統設定')),
                          ],
                        ),
                  body: Row(
                    children: [
                      if (wide)
                        NavigationRail(
                          selectedIndex: page,
                          labelType: NavigationRailLabelType.all,
                          onDestinationSelected: selectPage,
                          destinations: destinations,
                        ),
                      Expanded(child: SafeArea(child: pages[page])),
                    ],
                  ),
                )));
      },
    );
  }
}

class AdminOverviewPage extends StatefulWidget {
  const AdminOverviewPage(this.api, {this.onOpen, super.key});
  final AdminApi api;
  final void Function(int page, int section)? onOpen;

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
        widget.api
            .get('/api/v1/admin/source-health?limit=200&active_only=true'),
        widget.api.get('/api/v1/admin/mart-reports?limit=50'),
        widget.api
            .get('/api/v1/admin/operational-summary')
            .catchError((_) => <String, dynamic>{}),
        widget.api
            .get('/api/v1/admin/settings/data_readiness_ledger')
            .catchError((_) => <String, dynamic>{}),
        widget.api
            .get('/api/v1/admin/batches?days=1')
            .catchError((_) => <String, dynamic>{}),
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
                ExpansionTile(title: const Text('營運與部署詳細資訊'), children: [
                  ListTile(
                      title: Text(
                          'Private Mart 估值日 ${snapshot.data![3]['private_operations']?['valuation_date'] ?? '未知'}'),
                      subtitle: Text(
                          '快照資料日 ${snapshot.data![3]['snapshot']?['as_of_date'] ?? '未知'} · 更新 ${snapshot.data![3]['snapshot']?['updated_at'] ?? '未知'}')),
                  ListTile(
                      title: Text(
                          '目前回應 revision ${snapshot.data![3]['serving_revision'] ?? '未知'}'),
                      subtitle: Text(
                          'SHA ${snapshot.data![3]['serving_sha'] ?? '未知'}\n已驗證部署／digest：未知（不從目前回應版本推定）')),
                ]),
                Wrap(spacing: 12, runSpacing: 12, children: [
                  _DashboardCard(
                      title: '自動工作',
                      value: _items(snapshot.data![5]).isEmpty
                          ? '尚無最近一天的紀錄'
                          : _label(_items(snapshot.data![5]).first['status']),
                      detail: _items(snapshot.data![5]).isEmpty
                          ? '沒有紀錄不代表工作正常。'
                          : '最近一筆：${_label(_items(snapshot.data![5]).first['batch'])}\n更新 ${_items(snapshot.data![5]).first['updated_at'] ?? '時間未提供'}',
                      action: '查看自動工作',
                      onTap: () => widget.onOpen?.call(1, 0)),
                  _DashboardCard(
                      title: '全市場行情',
                      value: _marketReadinessSummary(snapshot.data![4]),
                      detail:
                          '資料日 ${(snapshot.data![4] as Map)['value']?['as_of'] ?? '尚未確認'}\n營收與財報的缺口另列。',
                      action: '查看資料缺口',
                      onTap: () => widget.onOpen?.call(2, 0)),
                  _DashboardCard(
                      title: '損益資料更新日',
                      value:
                          '${snapshot.data![3]['private_operations']?['valuation_date'] ?? '尚未確認'}',
                      detail: '已保存的估值日期；重算進度請查看批次。',
                      action: '查看損益重算',
                      onTap: () => widget.onOpen?.call(1, 1)),
                ]),
                TextButton.icon(
                    onPressed: () => widget.onOpen?.call(2, 3),
                    icon: const Icon(Icons.storage_outlined),
                    label: const Text('查看儲存空間與清理紀錄')),
                const SizedBox(height: 20),
                Text('優先處理', style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 4),
                const Text('以下是最近50筆執行、50筆報告與來源紀錄中的異常，不是全站待辦總數。'),
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
                      title: Text('目前查詢範圍內沒有異常'),
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
                        '${_label(execution['config_id'])} · ${_label(execution['status'])}',
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
                        '${_label(source['source_id'])} · ${_label(source['dataset_id'])}',
                      ),
                      subtitle: Text(
                        '${_label(source['last_state'])} · 最後取得 ${source['last_fetched_at'] ?? source['updated_at'] ?? '—'}',
                      ),
                      trailing: TextButton(
                          onPressed: () => widget.onOpen?.call(2, 2),
                          child: const Text('查看來源')),
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
                      trailing: TextButton(
                          onPressed: () => widget.onOpen?.call(3, 0),
                          child: const Text('查看報告')),
                    ),
                  ),
              ],
            );
          },
        ),
      );
}

String _marketReadinessSummary(dynamic data) {
  final markets = (data as Map)['value']?['market_price_window'] as Map?;
  return '上市：${_label(markets?['TWSE']?['status'] ?? 'unknown')}\n上櫃：${_label(markets?['TPEX']?['status'] ?? 'unknown')}';
}

class _DashboardCard extends StatelessWidget {
  const _DashboardCard(
      {required this.title,
      required this.value,
      required this.detail,
      required this.action,
      required this.onTap});
  final String title, value, detail, action;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => SizedBox(
      width: 280,
      child: Card(
          child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 8),
                    Text(value, style: Theme.of(context).textTheme.titleLarge),
                    Text(detail),
                    TextButton(onPressed: onTap, child: Text(action)),
                  ]))));
}

class AdminBatchPage extends StatefulWidget {
  const AdminBatchPage(this.api, {this.repairTarget, super.key});
  final Map<String, dynamic>? repairTarget;
  final AdminApi api;

  @override
  State<AdminBatchPage> createState() => _AdminBatchPageState();
}

class _AdminBatchPageState extends State<AdminBatchPage> {
  late Future<dynamic> executions;
  bool controller = true;
  bool creating = false;
  int revision = 0;

  @override
  void initState() {
    super.initState();
    executions = _load();
  }

  Future<dynamic> _load() =>
      widget.api.get('/api/v1/admin/executions?limit=50');

  void _reload() => setState(() {
        executions = _load();
        revision++;
      });

  Future<void> _queue() async {
    if (creating) return;
    setState(() => creating = true);
    try {
      await _createRequest();
    } finally {
      if (mounted) setState(() => creating = false);
    }
  }

  Future<void> _createRequest() async {
    late final List<Map<String, dynamic>> catalog;
    try {
      catalog =
          _items(await widget.api.get('/api/v1/admin/source-catalog?limit=200'))
              .where((item) =>
                  item['enabled'] == true &&
                  {'official', 'approved_fallback'}
                      .contains(item['authorization_status']))
              .toList();
    } catch (_) {
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('無法讀取已核准的工作設定，請稍後重試。')));
      return;
    }
    if (!mounted) return;
    final symbols =
        TextEditingController(text: '${widget.repairTarget?['symbol'] ?? ''}');
    var analysis = false;
    List<Map<String, dynamic>> choices() => catalog
        .where((item) =>
            item[analysis ? 'analysis_enabled' : 'collection_enabled'] == true)
        .toList();
    String? configId;
    final matching = choices().where(
        (item) => item['dataset_id'] == widget.repairTarget?['dataset_id']);
    if (matching.isNotEmpty)
      configId = '${matching.first['config_id']}';
    else if (choices().isNotEmpty) configId = '${choices().first['config_id']}';
    final result = await showDialog<Map<String, dynamic>>(
        context: context,
        builder: (context) => StatefulBuilder(
            builder: (context, update) => AlertDialog(
                    title: const Text('手動收集／分析'),
                    content: SingleChildScrollView(
                        child:
                            Column(mainAxisSize: MainAxisSize.min, children: [
                      SwitchListTile(
                          value: analysis,
                          title: const Text('使用已保存資料產生分析'),
                          onChanged: (value) => update(() {
                                analysis = value;
                                configId = choices().isEmpty
                                    ? null
                                    : '${choices().first['config_id']}';
                              })),
                      if (choices().isEmpty)
                        const Text('目前沒有已核准且已啟用的工作設定。')
                      else
                        DropdownButtonFormField<String>(
                            key: ValueKey(analysis),
                            initialValue: configId,
                            isExpanded: true,
                            decoration:
                                const InputDecoration(labelText: '要處理的資料'),
                            items: [
                              for (final item in choices())
                                DropdownMenuItem(
                                    value: '${item['config_id']}',
                                    child: Text(
                                        '${_label(item['dataset_id'])} · ${_label(item['market'])} · ${item['config_id']}',
                                        overflow: TextOverflow.ellipsis))
                            ],
                            onChanged: (value) =>
                                update(() => configId = value)),
                      TextField(
                          controller: symbols,
                          decoration: const InputDecoration(
                              labelText: '股票代號（逗號分隔）',
                              helperText: '留白使用該工作設定的範圍，不代表強制全市場。')),
                      const Text('加入同一總控佇列；會檢查依賴與重複執行，不代表立即完成。'),
                    ])),
                    actions: [
                      TextButton(
                          onPressed: () => Navigator.pop(context),
                          child: const Text('取消')),
                      FilledButton(
                          onPressed: configId == null
                              ? null
                              : () => Navigator.pop(context, {
                                    'analysis': analysis,
                                    'config_id': configId,
                                    'symbols': symbols.text
                                        .split(',')
                                        .map((value) =>
                                            value.trim().toUpperCase())
                                        .where((value) => value.isNotEmpty)
                                        .toList(),
                                  }),
                          child: const Text('加入佇列'))
                    ])));
    symbols.dispose();
    if (result == null) return;
    try {
      await widget.api.post(
          result['analysis'] == true
              ? '/api/v1/admin/executions/analysis'
              : '/api/v1/admin/executions/collection',
          {'config_id': result['config_id'], 'symbols': result['symbols']});
    } catch (_) {
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('工作尚未加入佇列，請檢查資料與權限。')));
      return;
    }
    if (!mounted) return;
    _reload();
    ScaffoldMessenger.of(context)
        .showSnackBar(const SnackBar(content: Text('工作已加入佇列，請重新整理查看實際執行結果。')));
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
        title: '自動工作與紀錄',
        action: FilledButton.icon(
          onPressed: creating ? null : _queue,
          icon: const Icon(Icons.add),
          label: Text(widget.repairTarget == null
              ? '手動收集／分析'
              : '補資料：${widget.repairTarget!['symbol']}'),
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
                  ? AdminEffectiveBatches(widget.api, key: ValueKey(revision))
                  : FutureBuilder<dynamic>(
                      future: executions,
                      builder: (context, snapshot) {
                        if (snapshot.connectionState != ConnectionState.done) {
                          return const Center(
                              child: CircularProgressIndicator());
                        }
                        if (snapshot.hasError)
                          return const _Message('執行紀錄暫時無法使用');
                        final values = _items(snapshot.data).where((row) {
                          final requested =
                              DateTime.tryParse('${row['requested_at']}');
                          return requested != null &&
                              !requested.isBefore(DateTime.now()
                                  .toUtc()
                                  .subtract(const Duration(days: 7)));
                        }).toList()
                          ..sort((a, b) => (b['requested_at'] ?? '')
                              .toString()
                              .compareTo((a['requested_at'] ?? '').toString()));
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
  late Future<dynamic> data = load();
  bool busy = false;
  Future<dynamic> load() => widget.api.get('/api/v1/admin/batch-dashboard');
  Future<void> act(Map row, String action) async {
    final label = {
      'start': '啟動一次',
      'stop': '停止本次',
      'pause': '暫停後續排程',
      'resume': '恢復排程'
    }[action]!;
    final accepted = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
                title: Text('$label：${row['title']}'),
                content: Text(action == 'pause'
                    ? '暫停後續自動執行；已在執行的工作會安全完成。'
                    : action == 'stop'
                        ? '只停止所選的這次執行；不回滾已保存資料，不影響其他工作。送出後仍需確認實際停止結果。'
                        : '由同一總控檢查依賴、重複執行與寫入保護後處理。'),
                actions: [
                  TextButton(
                      onPressed: () => Navigator.pop(context, false),
                      child: const Text('取消')),
                  FilledButton(
                      onPressed: () => Navigator.pop(context, true),
                      child: Text(label))
                ]));
    if (accepted != true || !mounted) return;
    setState(() => busy = true);
    try {
      final result = await widget.api.post(
          '/api/v1/admin/batches/${Uri.encodeComponent(row['name'] as String)}/actions',
          {
            'action': action,
            'expected_version': row['control_version'],
            if (action == 'stop')
              'occurrence_id': row['latest']['occurrence_id'],
          });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('${result['message'] ?? '請求已保存，等待總控處理'}')));
        setState(() => data = load());
      }
    } catch (_) {
      if (mounted)
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('尚未完成操作，請重新整理並確認工作狀態。')));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<dynamic>(
      future: data,
      builder: (context, snapshot) {
        if (snapshot.hasError)
          return Column(children: [
            const Text('批次狀況暫時無法讀取'),
            TextButton(
                onPressed: () => setState(() => data = load()),
                child: const Text('重新讀取'))
          ]);
        if (!snapshot.hasData)
          return const Center(child: CircularProgressIndicator());
        final root = snapshot.data as Map;
        final rows = _items(root);
        return ListView(children: [
          ListTile(
              title: const Text('自動工作與紀錄'),
              subtitle: const Text('每項只顯示最近7天內的最新一筆。啟動、停止及暫停都由總控處理。'),
              trailing: IconButton(
                  tooltip: '重新整理',
                  onPressed: busy ? null : () => setState(() => data = load()),
                  icon: const Icon(Icons.refresh))),
          if (root['controller_fresh'] != true)
            const ListTile(
                leading: Icon(Icons.warning_amber),
                title: Text('總控最近狀況尚未確認'),
                subtitle: Text('暫不能啟動工作或判斷逾期；請查看總控部署與最近執行。')),
          for (final group in const {
            'daily': '每日工作',
            'weekly': '每週工作',
            'monthly': '每月工作',
            'manual': '手動與資料修復'
          }.entries)
            ExpansionTile(
                initiallyExpanded: true,
                title: Text(group.value),
                children: [
                  for (final row
                      in rows.where((row) => row['cadence'] == group.key))
                    _batch(row),
                  if (!rows.any((row) => row['cadence'] == group.key))
                    const ListTile(title: Text('目前沒有已定義的工作')),
                ]),
        ]);
      });

  Widget _batch(Map row) {
    final latest = row['latest'] as Map?;
    final status = row['request_pending'] == true
        ? '已送出操作，等待總控確認'
        : row['enabled'] != true
            ? '尚未啟用'
            : row['paused'] == true
                ? '後續排程已暫停'
                : row['overdue'] == true
                    ? '逾期未執行'
                    : latest == null
                        ? '最近7天尚無紀錄'
                        : latest['reason'] == 'admin_stopped'
                            ? '已停止'
                            : _label(latest['status']);
    final schedule = row['schedule'] as Map?;
    return ExpansionTile(
        title: Text('${row['title']} · $status'),
        subtitle: Text(
            '${row['purpose']}\n最近開始：${_adminTime(latest?['start_time'])} · 耗時：${_adminDuration(latest?['duration_seconds'])}'),
        children: [
          if (schedule != null)
            ListTile(
                title: const Text('執行時間（台北）'),
                subtitle: Text(
                    '${(schedule['hours'] as List).map((hour) => "${hour.toString().padLeft(2, '0')}:${schedule['minute'].toString().padLeft(2, '0')}").join('、')}\n${row['conditional'] == true ? '有待處理資料才執行' : '依排程及上游資料狀態執行'}')),
          if (row['unavailable_reason'] != null)
            ListTile(title: Text('${row['unavailable_reason']}')),
          Wrap(spacing: 8, children: [
            FilledButton.tonal(
                onPressed: !busy && row['can_start'] == true
                    ? () => act(row, 'start')
                    : null,
                child: const Text('啟動一次')),
            OutlinedButton(
                onPressed: !busy && row['can_stop'] == true
                    ? () => act(row, 'stop')
                    : null,
                child: const Text('停止本次')),
            if (row['enabled'] == true)
              TextButton(
                  onPressed: busy
                      ? null
                      : () =>
                          act(row, row['paused'] == true ? 'resume' : 'pause'),
                  child: Text(row['paused'] == true ? '恢復排程' : '暫停後續排程')),
          ]),
          if (latest?['status'] == 'running' ||
              latest?['status'] == 'dispatching' ||
              latest?['status'] == 'ambiguous')
            ListTile(title: Text('${row['stop_note']}')),
          if (row['control_outcome'] != null)
            ListTile(title: Text('最近操作：${_label(row['control_outcome'])}')),
          ExpansionTile(title: const Text('最新總控 log'), children: [
            if (row['latest_log'] == null)
              const ListTile(title: Text('尚無與這次執行相符的 log'))
            else
              ListTile(
                  title: Text(_label(row['latest_log']['status'])),
                  subtitle: Text(
                      '時間：${_adminTime(row['latest_log']['at'])}\n${_label(row['latest_log']['action'])}\n${_label(row['latest_log']['reason'])}')),
          ]),
          ExpansionTile(title: const Text('最近一次執行紀錄'), children: [
            if (latest == null)
              const ListTile(title: Text('最近7天沒有可顯示的執行紀錄'))
            else
              ListTile(
                  title: Text(_label(latest['status'])),
                  subtitle: Text(
                      '預定：${_adminTime(latest['scheduled_at'])}\n開始：${_adminTime(latest['start_time'])}\n結束：${_adminTime(latest['completion_time'])}\n耗時：${_adminDuration(latest['duration_seconds'])}\n原因：${_label(latest['reason'])}\n執行識別：${latest['occurrence_id']}')),
          ]),
        ]);
  }
}

String _adminTime(Object? raw) {
  final value = DateTime.tryParse('$raw');
  if (value == null) return '尚未取得';
  final local = value.toUtc().add(const Duration(hours: 8));
  return '${local.year}-${local.month.toString().padLeft(2, '0')}-${local.day.toString().padLeft(2, '0')} ${local.hour.toString().padLeft(2, '0')}:${local.minute.toString().padLeft(2, '0')}';
}

String _adminDuration(Object? raw) => raw is num && raw >= 0
    ? raw < 60
        ? '${raw.toStringAsFixed(1)}秒'
        : '${(raw / 60).toStringAsFixed(1)}分鐘'
    : '尚未取得';

class AdminGovernancePage extends StatefulWidget {
  const AdminGovernancePage(this.api,
      {this.brokerProfile, this.usage, this.section = 'all', super.key});
  final UsageTracker? usage;
  final String section;
  final Widget? brokerProfile;
  final AdminApi api;
  @override
  State<AdminGovernancePage> createState() => _AdminGovernancePageState();
}

class _AdminGovernancePageState extends State<AdminGovernancePage> {
  late Future<List<dynamic>> data = _load();
  Timer? refreshTimer;
  int? selectedWorkers;
  Map<String, dynamic>? gcsScan;
  bool gcsScanning = false;
  String? gcsScanError;

  Future<List<dynamic>> _load() => Future.wait([
        widget.api.get('/api/v1/admin/data-governance'),
        if (widget.section == 'all' || widget.section == 'operations')
          widget.api.get('/api/v1/admin/private-recalculations?limit=50')
        else
          Future.value(<String, dynamic>{}),
        if (widget.section == 'all' || widget.section == 'operations')
          widget.api.get('/api/v1/admin/settings/private_recalc_workers')
        else
          Future.value(<String, dynamic>{}),
      ]);

  @override
  void initState() {
    super.initState();
    if (widget.section == 'all' || widget.section == 'operations')
      refreshTimer = Timer.periodic(const Duration(seconds: 5), (_) {
        if (mounted) _reload();
      });
  }

  @override
  void dispose() {
    refreshTimer?.cancel();
    super.dispose();
  }

  void _reload() => setState(() => data = _load());

  Future<void> _scanGcs() async {
    if (gcsScanning) return;
    setState(() {
      gcsScanning = true;
      gcsScanError = null;
    });
    try {
      final result = await widget.api
          .post('/api/v1/admin/gcs-storage/inspect', const <String, dynamic>{});
      if (!mounted) return;
      setState(() {
        gcsScan = (result as Map).cast<String, dynamic>();
        gcsScanError = null;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        gcsScan = null;
        gcsScanError = 'GCS 盤點失敗，請檢查讀取權限或稍後重試。';
      });
    } finally {
      if (mounted) setState(() => gcsScanning = false);
    }
  }

  Future<void> _saveWorkers(int currentVersion) async {
    final workers = selectedWorkers;
    if (workers == null) return;
    try {
      await widget.api.put(
        '/api/v1/admin/settings/private_recalc_workers',
        {
          'value': {'workers': workers},
          'expected_version': currentVersion
        },
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('已改為同時重算 $workers 筆，下次執行生效')),
      );
      _reload();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('無法更新重算並行數，請重新整理後再試')),
        );
      }
    }
  }

  Future<void> _cancel(String requestId) async {
    try {
      await widget.api.post(
        '/api/v1/admin/private-recalculations/${Uri.encodeComponent(requestId)}/cancel',
        const {'reason': '管理員從 Admin UI 要求中止'},
      );
      if (!mounted) return;
      _reload();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('無法中止此重算工作')),
        );
      }
    }
  }

  Future<void> _forceFail(String requestId) async {
    final controller = TextEditingController();
    final reason = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('強制標記失敗'),
        content: TextField(
          controller: controller,
          maxLength: 300,
          autofocus: true,
          decoration: const InputDecoration(
            labelText: 'User 可見原因',
            hintText: '例如：Private Mart 寫入失敗，已由管理員終止',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () {
              final value = controller.text.trim();
              if (value.isNotEmpty) Navigator.pop(dialogContext, value);
            },
            child: const Text('回寫失敗'),
          ),
        ],
      ),
    );
    controller.dispose();
    if (reason == null || !mounted) return;
    try {
      await widget.api.post(
        '/api/v1/admin/private-recalculations/${Uri.encodeComponent(requestId)}/fail',
        {'reason': reason},
      );
      if (!mounted) return;
      _reload();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('無法回寫失敗狀態')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) => _AdminPage(
        title: widget.section == 'settings'
            ? '券商與隱私設定'
            : widget.section == 'operations'
                ? '損益重算'
                : '儲存空間',
        action: IconButton(
          tooltip: '重新整理',
          onPressed: _reload,
          icon: const Icon(Icons.refresh),
        ),
        child: FutureBuilder<List<dynamic>>(
          future: data,
          builder: (context, snapshot) {
            if (snapshot.hasError) return const _Message('資料治理暫時無法使用');
            if (!snapshot.hasData) {
              return const Center(child: CircularProgressIndicator());
            }
            final root = snapshot.data![0] as Map<String, dynamic>;
            final queue = snapshot.data![1] as Map<String, dynamic>;
            final setting = snapshot.data![2] as Map<String, dynamic>;
            final privateOperations =
                (root['private_operations'] as Map?)?.cast<String, dynamic>() ??
                    const <String, dynamic>{};
            final settingValue =
                (setting['value'] as Map?)?.cast<String, dynamic>() ??
                    const <String, dynamic>{};
            final configuredWorkers = (settingValue['workers'] as int?) ??
                (queue['workers'] as int?) ??
                2;
            final workerChoice = selectedWorkers ?? configuredWorkers;
            final active = _items(queue)
                .where((row) => {'QUEUED', 'RUNNING', 'CANCEL_REQUESTED'}
                    .contains(row['status']))
                .toList();
            final history = _items(queue)
                .where((row) => !active.contains(row))
                .take(10)
                .toList();

            return ListView(children: [
              if (widget.brokerProfile != null) widget.brokerProfile!,
              if (widget.section == 'settings') ...[
                const ListTile(
                    title: Text('操作權限'),
                    subtitle: Text('每次操作都會驗證管理者權限；變更與重試保留紀錄。')),
                if (widget.usage != null) UsagePrivacy(widget.usage!),
              ],
              if (widget.section == 'all' ||
                  widget.section == 'operations') ...[
                const ListTile(
                  title: Text('損益更新狀況'),
                  subtitle: Text('查看損益資料更新與重算進度；不顯示交易或持股內容。'),
                ),
                Card(
                    child: ExpansionTile(
                        title: Text(
                            '損益更新 · ${_label(privateOperations['last_result'] ?? 'unknown')}'),
                        subtitle: Text(
                            '估值日 ${privateOperations['valuation_date'] ?? '尚未確認'} · 待處理 ${privateOperations['pending_changes'] ?? '尚未確認'}筆'),
                        children: [
                      ListTile(
                          title: const Text('詳細追蹤'),
                          subtitle: Text(
                              'checkpoint ${privateOperations['checkpoint_change_id'] ?? '未知'} · 最新 change ${privateOperations['latest_change_id'] ?? '未知'} · 待處理 ${privateOperations['pending_changes'] ?? '未知'}\n最新 ledger version ${privateOperations['latest_ledger_version'] ?? '未知'} · 估值日 ${privateOperations['valuation_date'] ?? '未知'} · lag ${privateOperations['valuation_lag_days'] ?? '未知'} 天\n最後更新 ${privateOperations['updated_at'] ?? '未知'}\nexecution ${privateOperations['execution_name'] ?? '未知'}')),
                    ])),
                const SizedBox(height: 12),
              ],
              if (widget.section == 'all' ||
                  widget.section == 'operations') ...[
                Text('同時處理的損益重算數',
                    style: Theme.of(context).textTheme.titleMedium),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Wrap(
                      spacing: 12,
                      runSpacing: 10,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        Text(
                            '執行中 ${queue['running'] ?? '尚未確認'} · 排隊 ${queue['queued'] ?? '尚未確認'}'),
                        DropdownButton<int>(
                          key: const Key('private-recalc-workers'),
                          value: workerChoice,
                          items: [
                            for (var value = 2; value <= 8; value++)
                              DropdownMenuItem(
                                value: value,
                                child: Text('同時 $value 筆'),
                              ),
                          ],
                          onChanged: (value) =>
                              setState(() => selectedWorkers = value),
                        ),
                        FilledButton.tonal(
                          onPressed: workerChoice == configuredWorkers
                              ? null
                              : () =>
                                  _saveWorkers(setting['version'] as int? ?? 0),
                          child: const Text('套用並行數'),
                        ),
                        const Text('同時處理2–8筆；下次執行生效，最後寫入仍會依序完成。'),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 12),
              ],
              if (widget.section == 'all' ||
                  widget.section == 'operations') ...[
                Text('正在處理與排隊的重算',
                    style: Theme.of(context).textTheme.titleMedium),
                if (active.isEmpty)
                  const Card(
                    child: ListTile(
                      title: Text('目前沒有個人重算工作'),
                      subtitle: Text('同一 owner 在完成或失敗前不會接受第二筆 active request。'),
                    ),
                  ),
                for (final row in active)
                  Card(
                    child: ListTile(
                      leading: const Icon(Icons.memory_outlined),
                      title: Text(
                        'owner ${row['owner_ref']} · ${_label(row['status'].toString().toLowerCase())}',
                      ),
                      subtitle: Text(
                        'ledger v${row['requested_ledger_version']} · request ${row['request_id']}\n'
                        'execution ${row['worker_execution'] ?? '尚未啟動'} · worker ${row['worker_task_index'] ?? '—'}\n'
                        '${row['safe_message'] ?? '沒有錯誤訊息'}',
                      ),
                      trailing: Wrap(
                        spacing: 6,
                        children: [
                          TextButton(
                            onPressed: row['status'] == 'CANCEL_REQUESTED'
                                ? null
                                : () => _cancel(row['request_id'].toString()),
                            child: const Text('中止'),
                          ),
                          FilledButton.tonal(
                            onPressed: () =>
                                _forceFail(row['request_id'].toString()),
                            child: const Text('回寫失敗'),
                          ),
                        ],
                      ),
                    ),
                  ),
                const SizedBox(height: 12),
                Text('最近終態', style: Theme.of(context).textTheme.titleMedium),
                for (final row in history)
                  ListTile(
                    title: Text(
                      'owner ${row['owner_ref']} · ${_label(row['status'].toString().toLowerCase())}',
                    ),
                    subtitle: Text(
                      '${row['finished_at'] ?? row['updated_at'] ?? '—'} · '
                      '${row['safe_message'] ?? row['error_code'] ?? '完成'}',
                    ),
                  ),
              ],
              if (widget.section == 'all' || widget.section == 'storage') ...[
                const Divider(),
                const ListTile(
                  title: Text('容量與保留政策'),
                  subtitle: Text('使用已持久化營運證據；未知不補零。Private 不套用公開清理政策。'),
                ),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        FilledButton.tonalIcon(
                          key: const ValueKey('admin-gcs-inventory-button'),
                          onPressed: gcsScanning ? null : _scanGcs,
                          icon: const Icon(Icons.cloud_outlined),
                          label:
                              Text(gcsScanning ? 'GCS 盤點中…' : '一鍵盤點 GCS 六桶容量'),
                        ),
                        const SizedBox(height: 8),
                        const Text(
                            '僅讀取六個已核准 Bucket 的物件 metadata，不下載原始資料、不刪檔。數據為盤點當下的儲存量，非 GCP 帳單。'),
                        if (gcsScanning) const LinearProgressIndicator(),
                        if (gcsScanError != null)
                          Text(gcsScanError!,
                              key: const ValueKey('admin-gcs-inventory-error')),
                        if (gcsScan != null) ...[
                          Text(
                              '${_label(gcsScan!['status'])} · 盤點時間：${_adminTime(gcsScan!['observed_at_utc'])}'),
                          Text(gcsScan!['totals'] == null
                              ? '結果不完整，不計算六桶總量'
                              : '六桶合計：${formatAdminStorageMb(adminStorageTotalBytes(gcsScan!['totals']))}'
                                  ' · 使用中：${formatAdminStorageMb((gcsScan!['totals'] as Map)['current_bytes'])}'
                                  ' · 物件：${formatAdminStorageCount((gcsScan!['totals'] as Map)['current_objects'])} 件'),
                          for (final item
                              in (gcsScan!['buckets'] as List<dynamic>? ??
                                  const []))
                            ListTile(
                              dense: true,
                              title: Text(
                                  '${_storageName((item as Map)['role'])} · ${_label(item['status'])}'
                                  '${item['http_status'] is int ? ' · HTTP ${item['http_status']}' : ''}'
                                  '${item['failure_step'] is String ? ' · ${item['failure_step']}' : ''}'),
                              subtitle: Text(
                                  '使用中 ${formatAdminStorageMb(item['current_bytes'])}'
                                  ' ／ ${formatAdminStorageCount(item['current_objects'])} 件\n'
                                  '歷史版本 ${formatAdminStorageMb(item['noncurrent_bytes'])}'
                                  ' · 待到期刪除 ${formatAdminStorageMb(item['soft_deleted_bytes'])}'
                                  '${item['role'] == 'stage' ? ' · MD5 疑似重複 ${formatAdminStorageMb(item['possible_same_md5_extra_bytes'])}（不可直接刪除）' : ''}'),
                            ),
                        ],
                      ],
                    ),
                  ),
                ),
                ExpansionTile(
                    title: const Text('保留政策與上次維護紀錄（非即時容量）'),
                    children: [
                      for (final row in _items(root))
                        Card(
                          child: ListTile(
                            title: Text('${row['layer']}'),
                            subtitle: Text(
                              '保留 ${row['retention'] ?? '未定義'}\n最後維護 ${row['maintenance_at'] ?? '未知'}\n'
                              '有效物件 ${formatAdminStorageCount(row['live_objects'])} 件 · 有效 ${formatAdminStorageMb(row['active_bytes'])}\n'
                              '非當前版本 ${formatAdminStorageMb(row['noncurrent_bytes'])} · soft-deleted ${formatAdminStorageMb(row['soft_deleted_bytes'])}\n'
                              '計費容量 ${formatAdminStorageMb(row['billable_bytes'])}',
                            ),
                          ),
                        ),
                    ]),
              ],
            ]);
          },
        ),
      );
}

class AdminStockWorkbench extends StatefulWidget {
  const AdminStockWorkbench(this.api, {this.onRepair, super.key});
  final ValueChanged<Map<String, dynamic>>? onRepair;
  final AdminApi api;

  @override
  State<AdminStockWorkbench> createState() => _AdminStockWorkbenchState();
}

class _AdminStockWorkbenchState extends State<AdminStockWorkbench> {
  final query = TextEditingController();
  late Future<dynamic> stocks;
  Map<String, dynamic>? selected;
  Future<dynamic>? detail;

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
        detail = widget.api.get('/api/v1/admin/stocks/$symbol/status');
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

  @override
  Widget build(BuildContext context) => _AdminPage(
        title: '個股資料查修',
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
                      : FutureBuilder<dynamic>(
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
                            final health = _items(snapshot.data);
                            return ListView(
                              children: [
                                AdminStockPeriods(
                                    widget.api, selected!['symbol'].toString(),
                                    key: ValueKey(selected!['symbol'])),
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
                                      title: Text(_label(value['dataset_id'])),
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
                                              onPressed: widget.onRepair == null
                                                  ? null
                                                  : () => widget.onRepair!({
                                                        'symbol':
                                                            selected!['symbol'],
                                                        'dataset_id':
                                                            value['dataset_id']
                                                      }),
                                              child: const Text('到批次補資料'),
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

String _storageName(Object? role) =>
    const {
      'stage': '暫存資料',
      'core': '市場原始資料',
      'mart': '分析結果',
      'private': '私人資料與備份',
      'research': '研究資料',
      'cloudbuild': '舊建置檔案'
    }[role] ??
    '其他儲存空間';
