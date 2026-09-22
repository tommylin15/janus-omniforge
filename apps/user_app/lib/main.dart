import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:http/http.dart' as http;

import 'sign_in_button.dart'
    if (dart.library.html) 'sign_in_button_web.dart'
    if (dart.library.js_util) 'sign_in_button_web.dart';
import 'admin.dart';

const portfolioPendingMessage = '交易已儲存，等待投資組合批次更新';

String uiLabel(Object? value) => const {
      'fundamental': '基本面',
      'valuation': '估值',
      'positioning': '籌碼與定位',
      'quant': '量化',
      'event_risk': '事件風險',
      'warming': '升溫',
      'cooling': '降溫',
      'available': '可用',
      'partial': '部分可用',
      'stale': '資料過期',
      'fallback': '備援',
      'success': '成功',
      'failed': '失敗',
      'insufficient_data': '資料不足',
    }[value?.toString()] ?? value?.toString() ?? '—';

String requireGoogleIdToken(String? token) =>
    token ?? (throw StateError('Google ID token is required'));

bool adminWorkspaceRequested(Uri uri,
        [String configured = const String.fromEnvironment('JANUS_WORKSPACE')]) =>
    configured == 'admin' || uri.pathSegments.contains('admin');

void main() => runApp(const JanusApp());

class JanusApp extends StatefulWidget {
  const JanusApp({super.key});
  @override
  State<JanusApp> createState() => _JanusAppState();
}

class _JanusAppState extends State<JanusApp> {
  ThemeMode mode = ThemeMode.system;
  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'Janus',
        themeMode: mode,
        theme: ThemeData(colorSchemeSeed: Colors.cyan, useMaterial3: true),
        darkTheme: ThemeData(
            colorSchemeSeed: Colors.cyan,
            brightness: Brightness.dark,
            useMaterial3: true),
        home: LoginPage(
            admin: adminWorkspaceRequested(Uri.base),
            onTheme: (value) => setState(() => mode = value)),
      );
}

class Api implements AdminApi {
  Api(this.token);
  final String token;
  static const base = String.fromEnvironment('JANUS_API_BASE_URL');
  Map<String, String> get headers =>
      {'Authorization': 'Bearer $token', 'Content-Type': 'application/json'};
  @override
  Future<dynamic> get(String path) => _send('GET', path);
  @override
  Future<dynamic> post(String path, Map<String, dynamic> body) =>
      _send('POST', path, body);
  @override
  Future<dynamic> put(String path, Map<String, dynamic> body) =>
      _send('PUT', path, body);
  @override
  Future<dynamic> patch(String path, Map<String, dynamic> body) =>
      _send('PATCH', path, body);
  Future<dynamic> delete(String path) => _send('DELETE', path);

  Future<dynamic> _send(String method, String path,
      [Map<String, dynamic>? body]) async {
    final request = http.Request(method, Uri.parse('$base$path'))
      ..headers.addAll(headers);
    if (method != 'GET')
      request.headers['Idempotency-Key'] =
          DateTime.now().microsecondsSinceEpoch.toString();
    if (body != null) request.body = jsonEncode(body);
    final response = await http.Response.fromStream(await request.send());
    if (response.statusCode < 200 || response.statusCode >= 300)
      throw Exception(jsonDecode(response.body)['detail'] ?? '服務暫時無法使用');
    return response.body.isEmpty ? null : jsonDecode(response.body);
  }
}

class LoginPage extends StatefulWidget {
  const LoginPage({required this.onTheme, this.admin = false, super.key});
  final ValueChanged<ThemeMode> onTheme;
  final bool admin;
  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  static const userClient = String.fromEnvironment('GOOGLE_USER_CLIENT_ID');
  static const adminClient = String.fromEnvironment('GOOGLE_ADMIN_CLIENT_ID');
  late final GoogleSignIn google = GoogleSignIn(
      clientId: widget.admin ? adminClient : userClient);
  late final StreamSubscription<GoogleSignInAccount?> accountChanges;
  bool busy = false;
  bool finishing = false;
  String? error;

  @override
  void initState() {
    super.initState();
    accountChanges = google.onCurrentUserChanged.listen((account) {
      if (account != null) unawaited(finishLogin(account));
    }, onError: (_) {
      if (mounted) setState(() => error = '登入失敗，請再試一次');
    });
    unawaited(restoreLogin());
  }

  Future<void> restoreLogin() async {
    try {
      final account = await google.signInSilently(reAuthenticate: true);
      if (account != null) await finishLogin(account);
    } catch (_) {
      // No saved Google session; keep showing the sign-in button.
    }
  }

  @override
  void dispose() {
    unawaited(accountChanges.cancel());
    super.dispose();
  }

  Future<void> login() async {
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await google.signIn();
    } catch (_) {
      if (mounted) setState(() => error = '登入失敗，請再試一次');
    } finally {
      if (mounted && !finishing) setState(() => busy = false);
    }
  }

  Future<void> finishLogin(GoogleSignInAccount account) async {
    if (finishing) return;
    finishing = true;
    if (mounted) {
      setState(() {
        busy = true;
        error = null;
      });
    }
    try {
      final token = requireGoogleIdToken((await account.authentication).idToken);
      if (mounted) {
        final api = Api(token);
        await Navigator.of(context).pushReplacement(MaterialPageRoute(
            builder: (_) => widget.admin
                ? AdminWorkspace(api: api, email: account.email, onTheme: widget.onTheme)
                : Workspace(api: api, email: account.email, onTheme: widget.onTheme)));
      }
    } catch (_) {
      finishing = false;
      if (mounted) {
        setState(() {
          busy = false;
          error = '登入憑證無效，請重新登入';
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      body: Center(
          child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 360),
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text('JANUS',
                        style: Theme.of(context).textTheme.headlineLarge),
                    const SizedBox(height: 12),
                    Text(widget.admin ? '資料營運中心' : '你的私人投資工作台'),
                    const SizedBox(height: 24),
                    buildGoogleSignInButton(onPressed: login, busy: busy),
                    if (error != null)
                      Padding(
                          padding: const EdgeInsets.only(top: 12),
                          child: Text(error!,
                              style: TextStyle(
                                  color: Theme.of(context).colorScheme.error)))
                  ],
                ),
              ))));
}

class Workspace extends StatefulWidget {
  const Workspace(
      {required this.api,
      required this.email,
      required this.onTheme,
      super.key});
  final Api api;
  final String email;
  final ValueChanged<ThemeMode> onTheme;
  @override
  State<Workspace> createState() => _WorkspaceState();
}

class _WorkspaceState extends State<Workspace> {
  int page = 0;
  Map<String, dynamic>? lastTransaction;
  void openStock(String symbol) => Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => StockDetailPage(
          api: widget.api,
          symbol: symbol)));

  @override
  Widget build(BuildContext context) {
    final pages = [
      TodayPage(widget.api, onOpenStock: openStock),
      WatchlistPage(widget.api, onOpenStock: openStock),
      JournalNotesPage(widget.api,
          initialTransaction: lastTransaction,
          onTransactionSaved: (value) => setState(() => lastTransaction = value)),
      ProfilePage(api: widget.api, email: widget.email, onTheme: widget.onTheme)
    ];
    const destinations = [
              NavigationDestination(
                  icon: Icon(Icons.today_outlined), label: '今日'),
              NavigationDestination(
                  icon: Icon(Icons.star_outline), label: '關注'),
              NavigationDestination(
                  icon: Icon(Icons.edit_note), label: '記帳／筆記'),
              NavigationDestination(
                  icon: Icon(Icons.person_outline), label: '我的')
            ];
    return LayoutBuilder(builder: (context, constraints) {
      final wide = constraints.maxWidth >= 900;
      return Scaffold(
          appBar: AppBar(title: const Text('Janus')),
          body: Row(children: [
            if (wide)
              NavigationRail(
                  selectedIndex: page,
                  labelType: NavigationRailLabelType.all,
                  onDestinationSelected: (value) => setState(() => page = value),
                  destinations: const [
                    NavigationRailDestination(icon: Icon(Icons.today_outlined), label: Text('今日')),
                    NavigationRailDestination(icon: Icon(Icons.star_outline), label: Text('關注')),
                    NavigationRailDestination(icon: Icon(Icons.edit_note), label: Text('記帳／筆記')),
                    NavigationRailDestination(icon: Icon(Icons.person_outline), label: Text('我的')),
                  ]),
            Expanded(child: pages[page])
          ]),
          bottomNavigationBar: wide ? null : NavigationBar(
              selectedIndex: page,
              onDestinationSelected: (value) => setState(() => page = value),
              destinations: destinations));
    });
  }
}


class WatchlistPage extends StatefulWidget {
  const WatchlistPage(this.api, {this.onOpenStock, super.key});
  final Api api;
  final ValueChanged<String>? onOpenStock;
  @override
  State<WatchlistPage> createState() => _WatchlistPageState();
}

class _WatchlistPageState extends State<WatchlistPage> {
  late Future<dynamic> items = widget.api.get('/api/v1/me/watchlist');
  void reload() =>
      setState(() => items = widget.api.get('/api/v1/me/watchlist'));
  Future<void> add() async {
    final symbol = await textDialog(context, '加入關注', '股票代號');
    if (symbol == null) return;
    if (!mounted) return;
    final target = await textDialog(context, '設定目標價', '可留空');
    try {
      await widget.api.post('/api/v1/me/watchlist', {
        'symbol': symbol.toUpperCase(),
        if (target?.isNotEmpty == true) 'target_price': target
      });
      reload();
    } catch (error) {
      if (mounted)
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text(error.toString().contains('deep-tracking symbol limit')
                ? '已達 50 個 distinct active symbols 深度追蹤上限'
                : error.toString().replaceFirst('Exception: ', ''))));
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      floatingActionButton:
          FloatingActionButton(onPressed: add, child: const Icon(Icons.add)),
      body: FutureBuilder(
          future: items,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done)
              return const Center(child: CircularProgressIndicator());
            if (snapshot.hasError)
              return ErrorView(snapshot.error.toString(), reload);
            final rows = (snapshot.data as List? ?? []);
            if (rows.isEmpty) return const Center(child: Text('尚未關注股票'));
            return ReorderableListView(
                children: [
                  for (final row in rows)
                    ListTile(
                        key: ValueKey(row['symbol']),
                        onTap: () => widget.onOpenStock?.call(row['symbol']),
                        title: Text(row['symbol']),
                        subtitle: Text(row['target_price'] == null
                            ? '尚未設定目標價'
                            : '目標價 ${row['target_price']}'),
                        trailing: IconButton(
                            icon: const Icon(Icons.delete_outline),
                            onPressed: () async {
                              await widget.api.delete(
                                  '/api/v1/me/watchlist/${row['symbol']}');
                              reload();
                            }))
                ],
                onReorderItem: (oldIndex, newIndex) async {
                  final reordered = List<dynamic>.from(rows);
                  final moved = reordered.removeAt(oldIndex);
                  reordered.insert(newIndex, moved);
                  final version = rows.fold<int>(
                      0,
                      (best, row) =>
                          row['version'] > best ? row['version'] : best);
                  await widget.api.put('/api/v1/me/watchlist/order', {
                    'symbols': [for (final row in reordered) row['symbol']],
                    'expected_version': version
                  });
                  reload();
                });
          }));
}

class TodayPage extends StatefulWidget {
  const TodayPage(this.api, {this.onOpenStock, super.key});
  final Api api;
  final ValueChanged<String>? onOpenStock;
  @override
  State<TodayPage> createState() => _TodayPageState();
}

class _TodayPageState extends State<TodayPage> {
  late Future<dynamic> brief = widget.api.get('/api/v1/public/daily-brief');
  void reload() => setState(() => brief = widget.api.get('/api/v1/public/daily-brief'));

  @override
  Widget build(BuildContext context) => FutureBuilder<dynamic>(
      future: brief,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done)
          return const Center(child: CircularProgressIndicator());
        if (snapshot.hasError)
          return ListView(padding: const EdgeInsets.all(16), children: [
            const ListTile(leading: Icon(Icons.info_outline), title: Text('今日市場資料尚未就緒')),
            const Text('本服務提供研究資訊，不構成投資建議。')
          ]);
        final root = snapshot.data as Map?;
        final items = root?['items'] is List ? root!['items'] as List : const [];
        final report = items.isNotEmpty && items.first is Map ? items.first as Map : const {};
        final data = report['data'] is Map ? report['data'] as Map : report;
        final candidates = _asList(data['candidates']);
        final highlights = _asList(data['highlights']);
        final sectors = _asList(data['sector_rotation']);
        final rotations = [
          ...sectors.where((item) => item is Map && item['state'] == 'warming').take(3),
          ...sectors.where((item) => item is Map && item['state'] == 'cooling').take(3),
        ];
        final topics = _asList(data['topics']);
        final reportDate = report['analysis_as_of']?.toString() ?? '';
        final componentDates = data['component_dates'];
        final mixedDates = componentDates is Map && componentDates.values
            .where((value) => value != null).any((value) => value.toString() != reportDate);
        final partial = mixedDates || {'partial', 'stale', 'fallback'}
            .contains(data['data_status']?.toString());
        return ListView(padding: const EdgeInsets.all(16), children: [
          Text('今日', style: Theme.of(context).textTheme.headlineMedium),
          Text('資料日期：${reportDate.isEmpty ? '—' : reportDate}'),
          if (partial)
            const ListTile(leading: Icon(Icons.info_outline),
                title: Text('部分資料日期不一致，本頁只顯示同日可用內容')),
          const SizedBox(height: 12),
          Card(child: ListTile(
              leading: Icon(Icons.public, color: Theme.of(context).colorScheme.primary),
              title: Text(uiLabel(data['market_regime'] ??
                  data['market_status'] ?? '市場狀態')),
              subtitle: Text(data['summary']?.toString() ?? '今日公開研究摘要'))),
          const ListTile(title: Text('今日重點')),
          if (highlights.isEmpty)
            const Card(child: ListTile(title: Text('目前沒有可發布重點'))),
          for (final item in highlights.take(3))
            ListTile(leading: const Icon(Icons.bolt_outlined),
                title: Text(item is Map ? '${item['title'] ?? item['summary'] ?? '重點'}' : '$item'),
                subtitle: item is Map ? Text('支撐：${item['support'] ?? '—'} · 風險：${item['risk'] ?? '—'}') : null),
          const ListTile(title: Text('產業輪動')),
          if (rotations.isEmpty)
            const Card(child: ListTile(title: Text('目前沒有可發布產業輪動'))),
          for (final item in rotations)
            ListTile(leading: Icon(item is Map && item['state'] == 'cooling'
                ? Icons.south_east : Icons.north_east),
                title: Text(item is Map ? '${item['industry'] ?? item['name'] ?? '產業'}' : '$item'),
                trailing: item is Map ? Text(uiLabel(item['state'])) : null),
          if (topics.isNotEmpty) ...[
            const ListTile(title: Text('熱門話題')),
            for (final topic in topics.take(5))
              ListTile(leading: const Icon(Icons.trending_up),
                  title: Text(topic is Map ? '${topic['topic'] ?? topic['name'] ?? '話題'}' : '$topic'),
                  subtitle: topic is Map ? Text('來源 ${topic['source_count'] ?? '—'} · 不確定性 ${topic['uncertainty'] ?? '—'}') : null)
          ],
          const ListTile(title: Text('候選股健康')),
          if (candidates.isEmpty)
            const Card(child: ListTile(title: Text('目前沒有可發布候選股'))),
          for (final candidate in candidates.take(5))
            StockHealthCard(value: candidate is Map
                ? Map<String, dynamic>.from(candidate)
                : {'stock_id': candidate},
                onTap: candidate is Map
                    ? () => widget.onOpenStock?.call('${candidate['stock_id'] ?? candidate['symbol']}')
                    : null),
          Align(alignment: Alignment.centerLeft, child: FilledButton.tonalIcon(
              icon: const Icon(Icons.filter_alt_outlined),
              label: const Text('查看全市場篩選'),
              onPressed: () => Navigator.of(context).push(MaterialPageRoute(
                  builder: (_) => ScreeningPage(widget.api, onOpenStock: widget.onOpenStock))))),
          const SizedBox(height: 16),
          const Text('本服務提供研究資訊，不構成投資建議。')
        ]);
      });
}

class StockHealthCard extends StatelessWidget {
  const StockHealthCard({required this.value, this.onTap, super.key});
  final Map<String, dynamic> value;
  final VoidCallback? onTap;
  @override
  Widget build(BuildContext context) {
    final blocked = {'blocked', 'insufficient_data'}.contains(
        value['data_status']?.toString() ?? value['analysis_outcome']?.toString());
    final score = num.tryParse('${value['mart_health_score'] ?? ''}');
    final symbol = '${value['stock_id'] ?? '—'}';
    final scoreLabel = blocked || score == null ? '資料不足，暫不顯示分數' : '健康度 ${score.round()} 分';
    return Card(child: InkWell(onTap: onTap, child: Padding(padding: const EdgeInsets.all(14), child: Column(
        crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        if (!blocked && score != null)
          Semantics(label: scoreLabel, child: SizedBox.square(dimension: 48,
              child: CircularProgressIndicator(value: (score / 100).clamp(0, 1).toDouble(),
                  strokeWidth: 7))),
        if (!blocked && score != null) const SizedBox(width: 12),
        Expanded(child: Text('$symbol ${value['stock_name'] ?? ''}'.trim(),
            style: Theme.of(context).textTheme.titleLarge)),
        Chip(label: Text(uiLabel(value['chips_status'] ?? '籌碼狀態未提供')))
      ]),
      ListTile(contentPadding: EdgeInsets.zero, leading: const Icon(Icons.psychology),
          title: Text(value['ai_whitepaper_analysis']?.toString() ?? '白話摘要未提供'),
          subtitle: Text(scoreLabel)),
      const Text('信心度不是獲利機率。'),
      Text('資料日期：${value['analysis_as_of'] ?? '—'} · 風險：${value['risk'] ?? '—'}')
    ]))));
  }
}

class AnalysisFeedbackCard extends StatefulWidget {
  const AnalysisFeedbackCard({required this.api, required this.executionId,
      required this.scopeType, required this.scopeId, super.key});
  final Api api;
  final String executionId;
  final String scopeType;
  final String scopeId;
  @override
  State<AnalysisFeedbackCard> createState() => _AnalysisFeedbackCardState();
}

class _AnalysisFeedbackCardState extends State<AnalysisFeedbackCard> {
  String? selected;
  bool busy = true;
  String? error;

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final value = await widget.api.get(Uri(path: '/api/v1/me/analysis-feedback', queryParameters: {
        'analysis_execution_id': widget.executionId,
        'scope_type': widget.scopeType,
        'scope_id': widget.scopeId,
      }).toString());
      if (mounted) setState(() { selected = value is Map ? value['feedback']?.toString() : null; busy = false; });
    } catch (_) {
      if (mounted) setState(() { error = '回饋暫時無法載入'; busy = false; });
    }
  }

  Future<void> save(String value) async {
    setState(() { busy = true; error = null; });
    try {
      await widget.api.put('/api/v1/me/analysis-feedback', {
        'analysis_execution_id': widget.executionId,
        'scope_type': widget.scopeType,
        'scope_id': widget.scopeId,
        'feedback': value,
      });
      if (mounted) setState(() { selected = value; busy = false; });
    } catch (_) {
      if (mounted) setState(() { error = '回饋儲存失敗'; busy = false; });
    }
  }

  @override
  Widget build(BuildContext context) => Card(child: Padding(
      padding: const EdgeInsets.all(12),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('這份分析有幫助嗎？'),
        const SizedBox(height: 8),
        SegmentedButton<String>(
          segments: const [
            ButtonSegment(value: 'useful', label: Text('有幫助'), icon: Icon(Icons.thumb_up_outlined)),
            ButtonSegment(value: 'neutral', label: Text('普通'), icon: Icon(Icons.horizontal_rule)),
            ButtonSegment(value: 'misleading', label: Text('可能誤導'), icon: Icon(Icons.report_outlined)),
          ],
          selected: selected == null ? const {} : {selected!},
          emptySelectionAllowed: true,
          onSelectionChanged: busy ? null : (values) { if (values.isNotEmpty) save(values.first); },
        ),
        if (busy) const LinearProgressIndicator(),
        if (error != null) Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
      ])));
}

List<dynamic> _asList(dynamic value) => value is List ? value : const [];

class ScreeningPage extends StatelessWidget {
  const ScreeningPage(this.api, {this.onOpenStock, super.key});
  final Api api;
  final ValueChanged<String>? onOpenStock;
  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(title: const Text('全市場篩選')),
      body: FutureBuilder<dynamic>(future: api.get('/api/v1/public/candidates'), builder: (context, snapshot) {
        if (snapshot.hasError) return ErrorView(snapshot.error.toString(), () {});
        if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());
        final root = snapshot.data as Map?;
        final reports = _asList(root?['items']);
        final report = reports.isNotEmpty && reports.first is Map ? reports.first as Map : const {};
        final data = report['data'] is Map ? report['data'] as Map : const {};
        final rows = _asList(data['candidates']);
        return ListView(padding: const EdgeInsets.all(16), children: [
          Text('涵蓋 ${data['coverage'] ?? rows.length} 檔 · 資料日期 ${report['analysis_as_of'] ?? '—'}'),
          Text('來源健康：${data['source_health'] ?? '—'} · 完整度 ${report['completeness'] ?? '—'}'),
          if (rows.isEmpty) const Card(child: ListTile(title: Text('資料不足，暫無篩選結果'))),
          for (final row in rows)
            StockHealthCard(value: row is Map ? Map<String, dynamic>.from(row) : {'stock_id': row},
                onTap: row is Map ? () => onOpenStock?.call('${row['stock_id'] ?? row['symbol']}') : null)
        ]);
      }));
}

class StockDetailPage extends StatelessWidget {
  const StockDetailPage({required this.api, required this.symbol, super.key});
  final Api api;
  final String symbol;
  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(title: Text(symbol)),
      body: FutureBuilder<List<dynamic>>(future: Future.wait([
        api.get('/api/v1/public/stock-health/$symbol'),
        api.get('/api/v1/me/journal/positions'),
        api.get('/api/v1/me/notes?symbol=$symbol'),
        api.get('/api/v1/public/kline/$symbol'),
        api.get('/api/v1/public/events/$symbol'),
      ]), builder: (context, snapshot) {
        if (snapshot.hasError) return ErrorView(snapshot.error.toString(), () {});
        if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());
        final result = snapshot.data!;
        final report = result[0] is Map ? result[0] as Map : const {};
        final data = report['data'] is Map ? Map<String, dynamic>.from(report['data']) : <String, dynamic>{};
        data.putIfAbsent('stock_id', () => symbol);
        data.putIfAbsent('analysis_as_of', () => report['analysis_as_of']);
        data.putIfAbsent('data_status', () => report['data_status']);
        final positions = _asList(result[1]).where((row) => row is Map && row['symbol'] == symbol).toList();
        final notes = _asList(result[2]);
        final kline = result[3] is Map ? _asList((result[3] as Map)['rows']) : const [];
        final events = result[4] is Map ? _asList((result[4] as Map)['rows']) : const [];
        final roles = _asList(data['role_analyses']);
        final position = positions.isNotEmpty && positions.first is Map ? positions.first as Map : const {};
        final metrics = data['metrics'] is Map ? data['metrics'] as Map : const {};
        final provenance = data['provenance'] is Map ? data['provenance'] as Map : const {};
        final evidence = _asList(data['evidence_refs']);
        return ListView(padding: const EdgeInsets.all(16), children: [
          Text('$symbol ${data['stock_name'] ?? ''}'.trim(), style: Theme.of(context).textTheme.headlineMedium),
          ListTile(title: const Text('持股摘要'), subtitle: Text(positions.isEmpty ? '目前無持股' :
              '${position['shares'] ?? position['quantity'] ?? '—'} 股 · 成本 ${position['average_cost'] ?? '—'} · 損益 ${position['unrealized_pnl'] ?? '—'}')),
          ListTile(title: const Text('我的筆記'), subtitle: Text(notes.isEmpty ? '尚無筆記' : '${notes.first['body']}')),
          StockHealthCard(value: data),
          if (report['execution_id'] != null)
            AnalysisFeedbackCard(api: api, executionId: '${report['execution_id']}',
                scopeType: '${report['scope_type'] ?? 'symbol'}', scopeId: '${report['scope_id'] ?? symbol}'),
          ListTile(title: const Text('為什麼'), subtitle: Text('${data['why'] ?? '尚無可發布說明'}')),
          ListTile(title: const Text('主要風險'), subtitle: Text('${data['risks'] ?? data['risk'] ?? '—'}')),
          ListTile(title: const Text('籌碼'), subtitle: Text('${data['chips_status'] ?? '—'}')),
          const ListTile(title: Text('事件')),
          if (events.isEmpty) const ListTile(title: Text('目前沒有事件')),
          for (final event in events.take(5))
            ListTile(title: Text(event is Map ? '${event['title'] ?? event['event_type'] ?? '事件'}' : '$event'),
                subtitle: event is Map ? Text('${event['published_at'] ?? event['event_date'] ?? '—'}') : null),
          const ListTile(title: Text('證據')),
          if (evidence.isEmpty) const ListTile(title: Text('目前沒有可公開證據')),
          for (final item in evidence.take(5))
            ListTile(title: Text(item is Map ? '${item['label'] ?? item['source_id'] ?? '證據'}' : '$item')),
          ExpansionTile(title: const Text('進階資料'), children: [
            const ListTile(title: Text('K 線／OHLCV')),
            if (kline.isEmpty) const ListTile(title: Text('資料等待中')),
            for (final row in kline.take(5))
              ListTile(title: Text(row is Map ? '${row['trade_date'] ?? '—'}' : '$row'),
                  subtitle: row is Map ? Text('O ${row['open'] ?? '—'} · H ${row['high'] ?? '—'} · L ${row['low'] ?? '—'} · C ${row['close'] ?? '—'} · V ${row['volume_shares'] ?? '—'}') : null),
            const ListTile(title: Text('指標')),
            if (metrics.isEmpty) const ListTile(title: Text('目前沒有指標')),
            for (final metric in metrics.entries.take(8))
              ListTile(title: Text('${metric.key}'), trailing: Text('${metric.value ?? '—'}')),
            const ListTile(title: Text('五角色分析')),
            if (roles.isEmpty) const ListTile(title: Text('目前沒有角色分析')),
            for (final role in roles.take(5))
              ListTile(title: Text(role is Map ? uiLabel(role['role'] ?? '角色') : '$role'),
                  subtitle: role is Map ? Text('${role['summary'] ?? role['outcome'] ?? '—'}') : null),
            ListTile(title: const Text('來源與版本'), subtitle: Text(
                '來源 ${provenance['source_id'] ?? '—'} · schema ${provenance['schema_version'] ?? report['schema_version'] ?? '—'} · model ${provenance['model_version'] ?? report['model_version'] ?? '—'}')),
          ]),
          const SizedBox(height: 12),
          const Text('信心度不是獲利機率；本服務提供研究資訊，不構成投資建議。')
        ]);
      }));
}

class JournalNotesPage extends StatefulWidget {
  const JournalNotesPage(this.api,
      {this.initialTransaction, this.onTransactionSaved, super.key});
  final Api api;
  final Map<String, dynamic>? initialTransaction;
  final ValueChanged<Map<String, dynamic>>? onTransactionSaved;
  @override
  State<JournalNotesPage> createState() => _JournalNotesPageState();
}

class _JournalNotesPageState extends State<JournalNotesPage> {
  int segment = 0;
  String? symbolFilter;
  int? yearFilter;
  late Future<dynamic> rows = load();
  Future<dynamic> load() {
    if (segment != 0) return widget.api.get('/api/v1/me/notes');
    return widget.api.get(Uri(path: '/api/v1/me/journal/history', queryParameters: {
      if (symbolFilter?.isNotEmpty == true) 'symbol': symbolFilter,
      if (yearFilter != null) 'year': '$yearFilter',
    }).toString());
  }
  void reload() => setState(() => rows = load());
  void showPortfolioPending() => ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text(portfolioPendingMessage)));
  Future<void> add() async {
    if (segment == 1) {
      final body = await textDialog(context, '新增筆記', '筆記內容');
      if (body != null) {
        await widget.api.post('/api/v1/me/notes', {'body': body});
        reload();
      }
      return;
    }
    final payload = await transactionDialog(context,
        initial: widget.initialTransaction);
    if (payload != null) {
      await widget.api.post('/api/v1/me/journal/events', payload);
      widget.onTransactionSaved?.call(Map<String, dynamic>.from(payload));
      if (mounted) showPortfolioPending();
      reload();
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      floatingActionButton: FloatingActionButton.extended(
          onPressed: add,
          icon: const Icon(Icons.add),
          label: Text(segment == 0 ? '新增交易' : '新增筆記')),
      body: Column(children: [
        SummaryCards(widget.api),
        Padding(
            padding: const EdgeInsets.all(12),
            child: SegmentedButton<int>(
                showSelectedIcon: false,
                segments: const [
                  ButtonSegment(value: 0, label: Text('交易紀錄')),
                  ButtonSegment(value: 1, label: Text('投資筆記'))
                ],
                selected: {
                  segment
                },
                onSelectionChanged: (value) => setState(() {
                      segment = value.first;
                      rows = load();
                    }))),
        if (segment == 0)
          Padding(padding: const EdgeInsets.symmetric(horizontal: 12), child: Wrap(spacing: 8, children: [
            OutlinedButton(
                onPressed: () async {
                  final value = await textDialog(context, '歷史篩選', '股票代號，可留空');
                  if (value != null) setState(() {
                    symbolFilter = value.trim().isEmpty ? null : value.trim().toUpperCase();
                    rows = load();
                  });
                },
                child: Row(mainAxisSize: MainAxisSize.min, children: [
                  Text(symbolFilter == null ? '股票：全部' : '股票：$symbolFilter'),
                  const Icon(Icons.arrow_drop_down)
                ])),
            MenuAnchor(
                builder: (context, controller, child) => OutlinedButton(
                    onPressed: () => controller.isOpen ? controller.close() : controller.open(),
                    child: Row(mainAxisSize: MainAxisSize.min, children: [
                      Text(yearFilter == null ? '年度：全部' : '年度：$yearFilter'),
                      const Icon(Icons.arrow_drop_down)
                    ])),
                menuChildren: [
                  MenuItemButton(onPressed: () => setState(() {
                    yearFilter = null;
                    rows = load();
                  }), child: const Text('全部年度')),
                  for (var year = DateTime.now().year; year >= DateTime.now().year - 5; year--)
                    MenuItemButton(onPressed: () => setState(() {
                      yearFilter = year;
                      rows = load();
                    }), child: Text('$year'))
                ])
          ])),
        Expanded(
            child: FutureBuilder(
                future: rows,
                builder: (context, snapshot) {
                  if (snapshot.connectionState != ConnectionState.done)
                    return const Center(child: CircularProgressIndicator());
                  if (snapshot.hasError)
                    return ErrorView(snapshot.error.toString(), reload);
                  final values = (snapshot.data as List? ?? []);
                  if (values.isEmpty)
                    return Center(child: Text(segment == 0 ? '尚無交易' : '尚無筆記'));
                  return ListView.builder(
                      itemCount: values.length,
                      itemBuilder: (context, index) {
                        final row = values[index];
                        return ListTile(
                            title: Text(segment == 0
                                ? '${row['event_type']} ${row['symbol']}'
                                : row['body'] ?? ''),
                            subtitle: Text(segment == 0
                                ? '${row['trade_date']} · ${row['shares'] ?? row['cash_amount'] ?? ''}'
                                : '${row['symbol'] ?? '一般筆記'} · 版本 ${row['revision']}'),
                            trailing: TextButton(
                                onPressed: () async {
                                  if (segment == 0) {
                                    final replacement = await transactionDialog(
                                        context,
                                        initial:
                                            Map<String, dynamic>.from(row),
                                        title: '建立更正');
                                    if (replacement != null) {
                                      await widget.api.post(
                                          '/api/v1/me/journal/events/${row['event_id']}/corrections',
                                          {
                                            'expected_version':
                                                row['record_version'],
                                            'replacement': replacement
                                          });
                                      if (mounted) showPortfolioPending();
                                      reload();
                                    }
                                  } else {
                                    final body = await textDialog(
                                        context, '修改筆記', '筆記內容',
                                        initial: row['body'] ?? '');
                                    if (body != null) {
                                      await widget.api.put(
                                          '/api/v1/me/notes/${row['note_id']}',
                                          {
                                            'body': body,
                                            'symbol': row['symbol'],
                                            'trade_event_id':
                                                row['trade_event_id'],
                                            'needs_follow_up':
                                                row['needs_follow_up'],
                                            'expected_version': row['revision']
                                          });
                                      reload();
                                    }
                                  }
                                },
                                child: Text(segment == 0 ? '建立更正' : '修改')));
                      });
                }))
      ]));
}

class SummaryCards extends StatelessWidget {
  const SummaryCards(this.api, {super.key});
  final Api api;
  @override
  Widget build(BuildContext context) => FutureBuilder<List<dynamic>>(
      future: Future.wait([
        api.get('/api/v1/me/journal/positions'),
        api.get('/api/v1/me/journal/pnl?year=${DateTime.now().year}'),
        api.get('/api/v1/me/notes')
      ]),
      builder: (context, snapshot) {
        if (!snapshot.hasData)
          return const SizedBox(
              height: 88, child: Center(child: CircularProgressIndicator()));
        final data = snapshot.data!;
        final pnl = data[1] as List;
        final pnlText = pnl.isEmpty
            ? '—'
            : pnl.length == 1
                ? '${pnl.first['currency']} ${pnl.first['realized_pnl']}'
                : '多幣別';
        final pending = (data[2] as List)
            .where((row) => row['needs_follow_up'] == true)
            .length;
        return SizedBox(
            height: 88,
            child: ListView(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.all(8),
                children: [
                  summary('目前持股', '${(data[0] as List).length} 檔'),
                  summary('本年已實現損益', pnlText),
                  summary('待完成筆記', '$pending 則')
                ]));
      });
  Widget summary(String title, String value) => Card(
      child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(children: [Text(title), Text(value)])));
}

class PortfolioDashboard extends StatefulWidget {
  const PortfolioDashboard(this.api, {super.key});
  final Api api;
  @override
  State<PortfolioDashboard> createState() => _PortfolioDashboardState();
}

class _PortfolioDashboardState extends State<PortfolioDashboard> {
  Map<String, dynamic>? profile;
  List<dynamic> summary = [], exposure = [], performance = [], stress = [];
  String risk = 'moderate', horizon = 'medium', goal = 'growth';
  double minimumCash = .1;
  bool aiContext = false, busy = false;
  Object? error;

  @override
  void initState() { super.initState(); load(); }

  Future<void> load() async {
    setState(() { busy = true; error = null; });
    try {
      final year = DateTime.now().year;
      final values = await Future.wait([
        widget.api.get('/api/v1/me/investment-profile'),
        widget.api.get('/api/v1/me/portfolio/summary'),
        widget.api.get('/api/v1/me/portfolio/exposure'),
        widget.api.get('/api/v1/me/portfolio/performance?year=$year'),
        widget.api.get('/api/v1/me/portfolio/stress-tests')
      ]);
      if (!mounted) return;
      final next = values[0] as Map<String, dynamic>;
      setState(() {
        profile = next;
        risk = next['risk_tolerance'] ?? 'moderate';
        horizon = next['investment_horizon'] ?? 'medium';
        goal = next['primary_goal'] ?? 'growth';
        minimumCash = double.tryParse('${next['minimum_cash_ratio'] ?? .1}') ?? .1;
        aiContext = next['ai_context_opt_in'] == true;
        summary = (values[1] as Map<String, dynamic>)['items'] as List<dynamic>;
        exposure = (values[2] as Map<String, dynamic>)['items'] as List<dynamic>;
        performance = (values[3] as Map<String, dynamic>)['items'] as List<dynamic>;
        stress = (values[4] as Map<String, dynamic>)['items'] as List<dynamic>;
      });
    } catch (value) { if (mounted) setState(() => error = value); }
    finally { if (mounted) setState(() => busy = false); }
  }

  Future<void> save() async {
    setState(() => busy = true);
    try {
      await widget.api.put('/api/v1/me/investment-profile', {
        'risk_tolerance': risk, 'investment_horizon': horizon,
        'primary_goal': goal, 'minimum_cash_ratio': minimumCash,
        'ai_context_opt_in': aiContext, 'expected_version': profile?['version'] ?? 0
      });
      await load();
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('投資屬性已儲存')));
    } catch (value) { if (mounted) setState(() { error = value; busy = false; }); }
  }

  String money(dynamic value) => value == null ? '資料不足' : '${double.tryParse('$value')?.toStringAsFixed(0) ?? value}';

  @override
  Widget build(BuildContext context) {
    if (busy && profile == null) return const Center(child: CircularProgressIndicator());
    return Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Text('資產與風險', style: Theme.of(context).textTheme.titleLarge),
        if (error != null) Text('資料暫時無法使用', style: TextStyle(color: Theme.of(context).colorScheme.error)),
        const SizedBox(height: 12),
        Wrap(spacing: 12, runSpacing: 12, children: [
          SizedBox(width: 210, child: DropdownButtonFormField<String>(initialValue: risk,
            decoration: const InputDecoration(labelText: '風險承受度'),
            items: const {'conservative':'保守','moderate':'穩健','aggressive':'積極'}.entries
              .map((item) => DropdownMenuItem(value: item.key, child: Text(item.value))).toList(),
            onChanged: (value) { if (value != null) setState(() => risk = value); })),
          SizedBox(width: 210, child: DropdownButtonFormField<String>(initialValue: horizon,
            decoration: const InputDecoration(labelText: '投資期間'),
            items: const {'short':'短期','medium':'中期','long':'長期'}.entries
              .map((item) => DropdownMenuItem(value: item.key, child: Text(item.value))).toList(),
            onChanged: (value) { if (value != null) setState(() => horizon = value); })),
          SizedBox(width: 210, child: DropdownButtonFormField<String>(initialValue: goal,
            decoration: const InputDecoration(labelText: '主要目標'),
            items: const {'capital_preservation':'保本','income':'現金流','growth':'成長','retirement':'退休'}.entries
              .map((item) => DropdownMenuItem(value: item.key, child: Text(item.value))).toList(),
            onChanged: (value) { if (value != null) setState(() => goal = value); }))
        ]),
        Semantics(label: '最低現金比例 ${(minimumCash * 100).round()}%', child: Slider(
          value: minimumCash, divisions: 20, label: '${(minimumCash * 100).round()}%',
          onChanged: (value) => setState(() => minimumCash = value))),
        SwitchListTile(contentPadding: EdgeInsets.zero, value: aiContext,
          title: const Text('允許外部助理使用我明確選取的投資屬性'),
          onChanged: (value) => setState(() => aiContext = value)),
        Align(alignment: Alignment.centerLeft, child: FilledButton.icon(
          onPressed: busy ? null : save, icon: const Icon(Icons.save_outlined), label: const Text('儲存投資屬性'))),
        const Divider(height: 32),
        for (final row in summary.cast<Map<String, dynamic>>())
          ListTile(title: Text('${row['currency']} 投資組合'),
            subtitle: Text('市值 ${money(row['market_value'])}・未實現 ${money(row['unrealized_pnl'])}'),
            trailing: Text(row['cash_safety_status'] == 'insufficient_data' ? '現金資料不足' : '${row['cash_ratio']}')),
        ExpansionTile(title: const Text('產業曝險'), children: [
          for (final row in exposure.cast<Map<String, dynamic>>())
            ListTile(title: Text('${row['industry']}'), trailing: Text('${money(row['portfolio_ratio'] == null ? null : double.parse('${row['portfolio_ratio']}') * 100)}%'))
        ]),
        ExpansionTile(title: const Text('年度 XIRR'), children: [
          for (final row in performance.cast<Map<String, dynamic>>())
            ListTile(title: Text('${row['year']} ${row['currency']}'), trailing: Text(row['xirr_status'] == 'available' ? '${(double.parse('${row['xirr']}') * 100).toStringAsFixed(2)}%' : '資料不足'))
        ]),
        ExpansionTile(title: const Text('壓力測試'), children: [
          for (final row in stress.cast<Map<String, dynamic>>())
            ListTile(title: Text('${row['scenario_id']}'), trailing: Text(money(row['loss'])))
        ]),
        const Text('壓力測試為固定情境估算，不構成投資建議；AI 不會改寫計算結果。')
      ])));
  }
}

class ProfilePage extends StatelessWidget {
  const ProfilePage(
      {required this.api,
      required this.email,
      required this.onTheme,
      super.key});
  final Api api;
  final String email;
  final ValueChanged<ThemeMode> onTheme;
  @override
  Widget build(BuildContext context) =>
      ListView(padding: const EdgeInsets.all(16), children: [
        ListTile(
            leading: const Icon(Icons.account_circle),
            title: Text(email),
            subtitle: const Text('Google 帳號')),
        PortfolioDashboard(api),
        const Divider(),
        const ListTile(title: Text('外觀')),
        DropdownButtonFormField<ThemeMode>(
            initialValue: ThemeMode.system,
            items: const [
              DropdownMenuItem(value: ThemeMode.system, child: Text('跟隨系統')),
              DropdownMenuItem(value: ThemeMode.light, child: Text('淺色')),
              DropdownMenuItem(value: ThemeMode.dark, child: Text('深色'))
            ],
            onChanged: (value) {
              if (value != null) onTheme(value);
            }),
        const Divider(),
        ListTile(
            leading: const Icon(Icons.download_outlined),
            title: const Text('匯出我的私人資料'),
            onTap: () => api.get('/api/v1/me/export')),
        ListTile(
            leading: Icon(Icons.warning_amber,
                color: Theme.of(context).colorScheme.error),
            title: const Text('永久刪除私人資料'),
            subtitle: const Text('涵蓋交易、筆記、關注股與衍生資料'),
            onTap: () async {
              final answer =
                  await textDialog(context, '永久刪除私人資料', '輸入 DELETE 確認');
              if (answer == 'DELETE' && context.mounted) {
                const client = String.fromEnvironment('GOOGLE_USER_CLIENT_ID');
                final google = GoogleSignIn(clientId: client);
                await google.signOut();
                final account = await google.signIn();
                final auth = await account?.authentication;
                final token = requireGoogleIdToken(auth?.idToken);
                await Api(token).delete('/api/v1/me/private-data');
                if (context.mounted)
                  ScaffoldMessenger.of(context)
                      .showSnackBar(const SnackBar(content: Text('刪除要求已排入處理')));
              }
            })
      ]);
}

class ErrorView extends StatelessWidget {
  const ErrorView(this.message, this.retry, {super.key});
  final String message;
  final VoidCallback retry;
  @override
  Widget build(BuildContext context) => Center(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
        const Text('服務暫時發生問題'),
        const SizedBox(height: 8),
        OutlinedButton(onPressed: retry, child: const Text('重試'))
      ]));
}

Future<String?> textDialog(BuildContext context, String title, String label,
    {String initial = ''}) {
  final controller = TextEditingController(text: initial);
  return showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
              title: Text(title),
              content: TextField(
                  controller: controller,
                  autofocus: true,
                  decoration: InputDecoration(labelText: label)),
              actions: [
                TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('取消')),
                FilledButton(
                    onPressed: () =>
                        Navigator.pop(context, controller.text.trim()),
                    child: const Text('儲存'))
              ]));
}

Future<Map<String, dynamic>?> transactionDialog(BuildContext context,
    {Map<String, dynamic>? initial, String title = '新增交易'}) async {
  const types = {
    'BUY': '買進',
    'SELL': '賣出',
    'CASH_DIV': '現金股利',
    'STOCK_DIV': '股票股利'
  };
  var type = '${initial?['event_type'] ?? 'BUY'}';
  if (!types.containsKey(type)) type = 'BUY';
  final form = GlobalKey<FormState>();
  var day =
      '${initial?['trade_date'] ?? DateTime.now().toIso8601String().substring(0, 10)}';
  var symbol = '${initial?['symbol'] ?? ''}';
  var shares = '${initial?['shares'] ?? ''}';
  var price = '${initial?['price'] ?? ''}';
  var amount = '${initial?['cash_amount'] ?? ''}';

  String? requiredText(String? value) =>
      value == null || value.trim().isEmpty ? '必填' : null;
  String? positiveNumber(String? value) {
    final number = num.tryParse(value?.trim() ?? '');
    return number == null || number <= 0 ? '請輸入大於 0 的數字' : null;
  }

  final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
          builder: (context, setDialogState) => AlertDialog(
                  title: Text(title),
                  content: SizedBox(
                      width: 420,
                      child: SingleChildScrollView(
                          child: Form(
                              key: form,
                              child: Column(mainAxisSize: MainAxisSize.min, children: [
                                DropdownButtonFormField<String>(
                                    initialValue: type,
                                    decoration: const InputDecoration(labelText: '交易類型'),
                                    items: [
                                      for (final item in types.entries)
                                        DropdownMenuItem(value: item.key, child: Text(item.value))
                                    ],
                                    onChanged: (value) {
                                      if (value != null) setDialogState(() => type = value);
                                    }),
                                TextFormField(
                                    initialValue: day,
                                    onChanged: (value) => day = value,
                                    decoration: const InputDecoration(
                                        labelText: '交易日期', hintText: 'YYYY-MM-DD'),
                                    validator: (value) {
                                      final text = value?.trim() ?? '';
                                      final date = DateTime.tryParse(text);
                                      if (date == null ||
                                          date.toIso8601String().substring(0, 10) != text) {
                                        return '請輸入正確日期';
                                      }
                                      final today = DateTime.now();
                                      if (date.isBefore(DateTime(2000)) ||
                                          date.isAfter(DateTime(today.year, today.month, today.day))) {
                                        return '日期需介於 2000-01-01 至今天';
                                      }
                                      return null;
                                    }),
                                TextFormField(
                                    initialValue: symbol,
                                    onChanged: (value) => symbol = value,
                                    autofocus: true,
                                    textCapitalization: TextCapitalization.characters,
                                    decoration: const InputDecoration(labelText: '股票代號'),
                                    validator: requiredText),
                                if (type != 'CASH_DIV')
                                  TextFormField(
                                      initialValue: shares,
                                      onChanged: (value) => shares = value,
                                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                                      decoration: const InputDecoration(labelText: '股數'),
                                      validator: positiveNumber),
                                if (type == 'BUY' || type == 'SELL')
                                  TextFormField(
                                      initialValue: price,
                                      onChanged: (value) => price = value,
                                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                                      decoration: const InputDecoration(labelText: '成交單價'),
                                      validator: positiveNumber),
                                if (type == 'CASH_DIV')
                                  TextFormField(
                                      initialValue: amount,
                                      onChanged: (value) => amount = value,
                                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                                      decoration: const InputDecoration(labelText: '股利金額'),
                                      validator: positiveNumber),
                                const TextField(
                                    enabled: false,
                                    decoration: InputDecoration(labelText: '幣別', hintText: 'TWD'))
                              ])))),
                  actions: [
                    TextButton(
                        onPressed: () => Navigator.pop(dialogContext),
                        child: const Text('取消')),
                    FilledButton(
                        onPressed: () {
                          if (form.currentState?.validate() != true) return;
                          Navigator.pop(dialogContext, <String, dynamic>{
                            'event_type': type,
                            'trade_date': day.trim(),
                            'symbol': symbol.trim().toUpperCase(),
                            'currency': 'TWD',
                            if (type != 'CASH_DIV') 'shares': shares.trim(),
                            if (type == 'BUY' || type == 'SELL') 'price': price.trim(),
                            if (type == 'CASH_DIV') 'cash_amount': amount.trim()
                          });
                        },
                        child: const Text('儲存'))
                  ])));
  return result;
}
