import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:http/http.dart' as http;

const portfolioPendingMessage = '交易已儲存，等待投資組合批次更新';

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
        home: LoginPage(onTheme: (value) => setState(() => mode = value)),
      );
}

class Api {
  Api(this.token);
  final String token;
  static const base = String.fromEnvironment('JANUS_API_BASE_URL');
  Map<String, String> get headers =>
      {'Authorization': 'Bearer $token', 'Content-Type': 'application/json'};
  Future<dynamic> get(String path) => _send('GET', path);
  Future<dynamic> post(String path, Map<String, dynamic> body) =>
      _send('POST', path, body);
  Future<dynamic> put(String path, Map<String, dynamic> body) =>
      _send('PUT', path, body);
  Future<dynamic> delete(String path) => _send('DELETE', path);
  Future<List<Map<String, dynamic>>> events(String thread, int cursor) async {
    final request = http.Request(
        'GET',
        Uri.parse(
            '$base/api/v1/me/chats/threads/$thread/events?cursor=$cursor&limit=200'))
      ..headers.addAll(headers);
    final response = await request.send();
    if (response.statusCode < 200 || response.statusCode >= 300)
      throw Exception('事件串流暫時無法使用');
    final result = <Map<String, dynamic>>[];
    String? event;
    String? id;
    final data = StringBuffer();
    void flush() {
      if (data.length == 0) return;
      final value = jsonDecode(data.toString()) as Map<String, dynamic>;
      result.add({
        ...value,
        'event_type': event,
        'seq': int.tryParse(id ?? '') ?? cursor
      });
      event = null;
      id = null;
      data.clear();
    }

    await for (final line in response.stream
        .transform(utf8.decoder)
        .transform(const LineSplitter())) {
      if (line.isEmpty) {
        flush();
      } else if (line.startsWith('event: ')) {
        event = line.substring(7);
      } else if (line.startsWith('id: ')) {
        id = line.substring(4);
      } else if (line.startsWith('data: ')) {
        data.write(line.substring(6));
      }
    }
    flush();
    return result;
  }

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
  const LoginPage({required this.onTheme, super.key});
  final ValueChanged<ThemeMode> onTheme;
  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  bool busy = false;
  String? error;
  Future<void> login() async {
    setState(() {
      busy = true;
      error = null;
    });
    try {
      const client = String.fromEnvironment('GOOGLE_USER_CLIENT_ID');
      final account = await GoogleSignIn(clientId: client).signIn();
      final auth = await account?.authentication;
      final token = auth?.idToken ?? auth?.accessToken;
      if (account == null || token == null) return;
      if (mounted)
        Navigator.of(context).pushReplacement(MaterialPageRoute(
            builder: (_) => Workspace(
                api: Api(token),
                email: account.email,
                onTheme: widget.onTheme)));
    } catch (_) {
      if (mounted) setState(() => error = '登入失敗，請再試一次');
    } finally {
      if (mounted) setState(() => busy = false);
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
                    const Text('你的私人投資工作台'),
                    const SizedBox(height: 24),
                    FilledButton.icon(
                        onPressed: busy ? null : login,
                        icon: busy
                            ? const SizedBox.square(
                                dimension: 18,
                                child:
                                    CircularProgressIndicator(strokeWidth: 2))
                            : const Icon(Icons.login),
                        label: const Text('使用 Google 登入')),
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
  void openStock(String symbol) => Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => StockDetailPage(
          api: widget.api,
          symbol: symbol,
          onAskAi: () {
            Navigator.of(context).pop();
            setState(() => page = 3);
          })));

  @override
  Widget build(BuildContext context) {
    final pages = [
      TodayPage(widget.api, onOpenStock: openStock),
      WatchlistPage(widget.api, onOpenStock: openStock),
      JournalNotesPage(widget.api),
      ChatPage(widget.api),
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
                  icon: Icon(Icons.chat_bubble_outline), label: 'AI'),
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
                    NavigationRailDestination(icon: Icon(Icons.chat_bubble_outline), label: Text('AI')),
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

class ChatPage extends StatefulWidget {
  const ChatPage(this.api, {super.key});
  final Api api;
  @override
  State<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends State<ChatPage> {
  late Future<dynamic> threads = widget.api.get('/api/v1/me/chats/threads');
  Map<String, dynamic>? thread;
  final input = TextEditingController();
  final events = <String, Map<String, dynamic>>{};
  final lockedApprovals = <String>{};
  int cursor = -1;
  bool busy = false;
  String connection = 'idle';
  String runtime = 'gemini';
  String model = 'gemini-2.5-flash';
  @override
  void dispose() {
    input.dispose();
    super.dispose();
  }

  void reload() =>
      setState(() => threads = widget.api.get('/api/v1/me/chats/threads'));
  Future<void> createThread() async {
    final value = await widget.api.post('/api/v1/me/chats/threads',
        {'runtime': runtime, 'model': model, 'assistant_profile': 'default'});
    setState(() {
      thread = value;
      events.clear();
      cursor = -1;
    });
    reload();
  }

  Future<void> select(Map<String, dynamic> value) async {
    setState(() {
      thread = value;
      events.clear();
      cursor = -1;
      busy = true;
      connection = 'connecting';
    });
    try {
      for (final event in await widget.api.events(value['thread_id'], -1)) {
        _merge(event);
      }
      if (mounted) setState(() => connection = 'connected');
    } catch (_) {
      if (mounted) setState(() => connection = 'disconnected');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  void _merge(Map<String, dynamic> event) {
    final seq = event['seq'] as int? ?? -1;
    final id = event['event_id']?.toString() ?? '$seq';
    if (events.containsKey(id)) return;
    if (seq <= cursor) return;
    if (seq > cursor) cursor = seq;
    final item = event['item_id']?.toString() ?? id;
    final type = event['event_type']?.toString();
    if (type == 'item_upsert')
      events[item] = {...events[item] ?? {}, ...event};
    else
      events[id] = event;
  }

  Future<void> _poll(String threadId, {int attempts = 10}) async {
    for (var attempt = 0; attempt < attempts; attempt++) {
      try {
        for (final event in await widget.api.events(threadId, cursor)) {
          _merge(event);
        }
        if (mounted) setState(() => connection = 'connected');
      } catch (_) {
        if (mounted) setState(() => connection = 'disconnected');
        break;
      }
      if (events.values.any((e) => [
            'turn_completed',
            'turn_error',
            'turn_cancelled'
          ].contains(e['event_type']))) break;
      await Future<void>.delayed(const Duration(milliseconds: 300));
    }
  }

  Future<void> send() async {
    final value = input.text.trim();
    if (value.isEmpty || thread == null || busy) return;
    input.clear();
    setState(() {
      busy = true;
      connection = 'connecting';
    });
    try {
      final response = await widget.api.post(
          '/api/v1/me/chats/threads/${thread!['thread_id']}/messages',
          {'content': value});
      await _poll(thread!['thread_id'],
          attempts: response['turn']?['status'] == 'RUNNING' ? 10 : 1);
    } catch (_) {
      if (mounted) {
        setState(() => connection = 'disconnected');
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('訊息送出失敗，請稍後重試')));
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> approval(Map<String, dynamic> event, bool approved) async {
    final payload = Map<String, dynamic>.from(event['payload'] as Map? ?? {});
    final id =
        payload['request_id']?.toString() ?? payload['requestId']?.toString();
    final turn = event['turn_id']?.toString();
    final digest = payload['params_digest']?.toString() ??
        payload['paramsDigest']?.toString();
    final key = id ?? event['event_id']?.toString();
    if (id == null ||
        turn == null ||
        digest == null ||
        key == null ||
        lockedApprovals.contains(key)) return;
    setState(() => lockedApprovals.add(key));
    try {
      await widget.api.post(
          '/api/v1/me/chats/threads/${thread!['thread_id']}/turns/$turn/approvals/$id',
          {'approved': approved, 'params_digest': digest});
      await _poll(thread!['thread_id']);
    } catch (_) {
      if (mounted) setState(() => connection = 'disconnected');
    }
  }

  @override
  Widget build(BuildContext context) => LayoutBuilder(
      builder: (context, box) => Row(children: [
            SizedBox(
                width: box.maxWidth < 700 ? 150 : 230, child: _ThreadList()),
            Expanded(
                child: thread == null
                    ? _StartChat(onCreate: createThread)
                    : _Room(
                        onSend: send,
                        onApproval: approval,
                        input: input,
                        busy: busy,
                        events: events.values.toList(),
                        runtime: runtime,
                        model: model,
                        connection: connection,
                        lockedApprovals: lockedApprovals,
                        onRuntime: (v) {
                          setState(() {
                            runtime = v;
                            model = v == 'gemini'
                                ? 'gemini-2.5-flash'
                                : v == 'openrouter'
                                    ? 'openai/gpt-4o-mini'
                                    : 'gpt-5';
                          });
                        },
                        onTools: () => showModalBottomSheet(
                            context: context,
                            builder: (_) => AssistantControls(widget.api))))
          ]));
  Widget _ThreadList() => Column(children: [
        Padding(
            padding: const EdgeInsets.all(8),
            child: FilledButton.icon(
                onPressed: createThread,
                icon: const Icon(Icons.add),
                label: const Text('新對話'))),
        Expanded(
            child: FutureBuilder(
                future: threads,
                builder: (context, snapshot) {
                  if (!snapshot.hasData)
                    return const Center(child: CircularProgressIndicator());
                  final data = snapshot.data;
                  final values =
                      (data is Map ? data['items'] as List? : null) ?? [];
                  return ListView(children: [
                    for (final value in values)
                      ListTile(
                          selected: value['thread_id'] == thread?['thread_id'],
                          title:
                              Text('${value['runtime']} · ${value['model']}'),
                          subtitle: Text(value['thread_id']),
                          onTap: () => select(Map<String, dynamic>.from(value)))
                  ]);
                }))
      ]);
}

class _StartChat extends StatelessWidget {
  const _StartChat({required this.onCreate});
  final VoidCallback onCreate;
  @override
  Widget build(BuildContext context) => Center(
      child: FilledButton.icon(
          onPressed: onCreate,
          icon: const Icon(Icons.chat),
          label: const Text('建立私人助理對話')));
}

class _Room extends StatelessWidget {
  const _Room(
      {required this.onSend,
      required this.onApproval,
      required this.input,
      required this.busy,
      required this.events,
      required this.runtime,
      required this.model,
      required this.connection,
      required this.lockedApprovals,
      required this.onRuntime,
      required this.onTools});
  final VoidCallback onSend;
  final Future<void> Function(Map<String, dynamic>, bool) onApproval;
  final TextEditingController input;
  final bool busy;
  final List<Map<String, dynamic>> events;
  final String runtime, model, connection;
  final Set<String> lockedApprovals;
  final ValueChanged<String> onRuntime;
  final VoidCallback onTools;
  @override
  Widget build(BuildContext context) => Column(children: [
        Padding(
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
            child: Row(children: [
              Expanded(
                  child: DropdownButtonFormField<String>(
                      initialValue: runtime,
                      decoration: InputDecoration(
                          labelText: 'Runtime',
                          helperText: connection == 'disconnected'
                              ? '連線中斷，可重新載入事件'
                              : null),
                      items: const [
                        DropdownMenuItem(
                            value: 'gemini', child: Text('Gemini API')),
                        DropdownMenuItem(
                            value: 'openrouter', child: Text('OpenRouter')),
                        DropdownMenuItem(value: 'codex', child: Text('Codex'))
                      ],
                      onChanged: (v) {
                        if (v != null) onRuntime(v);
                      })),
              const SizedBox(width: 8),
              IconButton(
                  tooltip: 'MCP／Skills／資料源',
                  onPressed: onTools,
                  icon: const Icon(Icons.tune))
            ])),
        Expanded(
            child: events.isEmpty
                ? const Center(child: Text('開始輸入訊息'))
                : ListView(padding: const EdgeInsets.all(12), children: [
                    for (final event in events)
                      _EventCard(event, onApproval, lockedApprovals)
                  ])),
        SafeArea(
            top: false,
            child: Padding(
                padding: const EdgeInsets.all(12),
                child:
                    Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
                  Expanded(
                      child: TextField(
                          controller: input,
                          minLines: 1,
                          maxLines: 5,
                          decoration: const InputDecoration(
                              hintText: '詢問私人助理…',
                              border: OutlineInputBorder()))),
                  const SizedBox(width: 8),
                  IconButton(
                      onPressed: busy ? null : onSend,
                      icon: busy
                          ? const SizedBox.square(
                              dimension: 22,
                              child: CircularProgressIndicator(strokeWidth: 2))
                          : const Icon(Icons.send))
                ])))
      ]);
}

class _EventCard extends StatelessWidget {
  const _EventCard(this.event, this.onApproval, this.lockedApprovals);
  final Map<String, dynamic> event;
  final Future<void> Function(Map<String, dynamic>, bool) onApproval;
  final Set<String> lockedApprovals;
  @override
  Widget build(BuildContext context) {
    final payload = Map<String, dynamic>.from(event['payload'] as Map? ?? {});
    final type = event['event_type']?.toString() ?? '';
    final content = payload['content']?.toString() ??
        payload['text']?.toString() ??
        payload['message']?.toString() ??
        payload.toString();
    final role = payload['role']?.toString();
    if (type == 'approval_request') {
      final id = payload['request_id']?.toString() ??
          payload['requestId']?.toString() ??
          event['event_id']?.toString() ??
          '';
      final command = payload['command'];
      final details = [
        '命令：${command is List ? jsonEncode(command) : command ?? '未提供'}',
        '原因：${payload['reason'] ?? '未提供'}',
        '範圍：${payload['scope'] ?? '未提供'}',
        '到期：${payload['expires_at'] ?? payload['expiresAt'] ?? '未提供'}'
      ].join('\n');
      final locked = lockedApprovals.contains(id);
      return Card(
          color: Theme.of(context).colorScheme.secondaryContainer,
          child: ListTile(
              leading: const Icon(Icons.lock_outline),
              title: Text(locked ? '已送出核准決策' : '需要核准的操作'),
              subtitle: Text(details),
              trailing: Wrap(children: [
                TextButton(
                    onPressed: locked ? null : () => onApproval(event, false),
                    child: const Text('拒絕')),
                FilledButton(
                    onPressed: locked ? null : () => onApproval(event, true),
                    child: const Text('允許'))
              ])));
    }
    if (type == 'approval_resolved')
      return ListTile(
          leading: const Icon(Icons.verified_outlined),
          title: Text({
                'accept': '已批准',
                'decline': '已拒絕',
                'expired': '已過期',
                'cancel': '已取消',
                'cleared': '已處理'
              }[payload['decision']?.toString()] ??
              '核准狀態已更新'));
    if (type == 'turn_completed' ||
        type == 'turn_cancelled' ||
        type == 'turn_error')
      return Padding(
          padding: const EdgeInsets.all(8),
          child: Text(type == 'turn_completed'
              ? '已完成'
              : type == 'turn_cancelled'
                  ? '已取消'
                  : payload['code'] == 'gateway_handle_unavailable'
                      ? '連線中斷，無法恢復原生工作階段'
                      : '執行失敗'));
    return Align(
        alignment:
            role == 'user' ? Alignment.centerRight : Alignment.centerLeft,
        child: Card(
            child: Padding(
                padding: const EdgeInsets.all(12),
                child: MarkdownText(content))));
  }
}

class MarkdownText extends StatelessWidget {
  const MarkdownText(this.value, {super.key});
  final String value;
  @override
  Widget build(BuildContext context) {
    var code = false;
    final children = <Widget>[];
    for (final line in value.split('\n')) {
      if (line.startsWith('```')) {
        code = !code;
        continue;
      }
      children.add(Padding(
          padding: const EdgeInsets.only(bottom: 4),
          child: line.startsWith('# ')
              ? Text(line.substring(2),
                  style: Theme.of(context).textTheme.titleLarge)
              : line.startsWith('**') && line.endsWith('**')
                  ? Text(line.substring(2, line.length - 2),
                      style: const TextStyle(fontWeight: FontWeight.bold))
                  : code
                      ? Container(
                          width: double.infinity,
                          color: Theme.of(context)
                              .colorScheme
                              .surfaceContainerHighest,
                          padding: const EdgeInsets.all(8),
                          child: Text(line,
                              style: const TextStyle(
                                  fontFamily: 'monospace', color: Colors.cyan)))
                      : Text(line)));
    }
    return Column(
        crossAxisAlignment: CrossAxisAlignment.start, children: children);
  }
}

class AssistantControls extends StatefulWidget {
  const AssistantControls(this.api, {super.key});
  final Api api;
  @override
  State<AssistantControls> createState() => _AssistantControlsState();
}

class _AssistantControlsState extends State<AssistantControls> {
  late Future<dynamic> mcp = widget.api.get('/api/v1/me/mcp/servers'),
      skills = widget.api.get('/api/v1/me/skills');
  Future<void> toggleSkill(Map<String, dynamic> value, bool enabled) async {
    await widget.api.put('/api/v1/me/skills/${value['skill_id']}/state',
        {'enabled': enabled, 'revision': value['revision']});
    setState(() => skills = widget.api.get('/api/v1/me/skills'));
  }

  @override
  Widget build(BuildContext context) => SafeArea(
          child: ListView(
              padding: const EdgeInsets.all(16),
              shrinkWrap: true,
              children: [
            Text('資料源、MCP 與 Skills',
                style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 8),
            _Panel(
                'MCP Servers',
                mcp,
                (v) =>
                    '${v['server_id']} · ${v['enabled'] == true ? '已啟用' : '未啟用'}'),
            _TogglePanel(
                'Skills',
                skills,
                (v) => '${v['skill_id']} · revision ${v['revision']}',
                toggleSkill),
            const ListTile(
                leading: Icon(Icons.info_outline),
                title: Text('私人資料須逐項選取'),
                subtitle: Text('API key、Codex auth 與資料庫憑證不會進入裝置。'))
          ]));
}

class _Panel extends StatelessWidget {
  const _Panel(this.title, this.future, this.label);
  final String title;
  final Future<dynamic> future;
  final String Function(Map<String, dynamic>) label;
  @override
  Widget build(BuildContext context) => FutureBuilder(
      future: future,
      builder: (context, snapshot) {
        final data = snapshot.data;
        final values = (data is Map ? data['items'] as List? : null) ?? [];
        return ExpansionTile(
            title: Text(title),
            children: values.isEmpty
                ? [const ListTile(title: Text('目前沒有設定'))]
                : [
                    for (final value in values)
                      ListTile(
                          title: Text(label(Map<String, dynamic>.from(value))))
                  ]);
      });
}

class _TogglePanel extends StatelessWidget {
  const _TogglePanel(this.title, this.future, this.label, this.onToggle);
  final String title;
  final Future<dynamic> future;
  final String Function(Map<String, dynamic>) label;
  final Future<void> Function(Map<String, dynamic>, bool) onToggle;
  @override
  Widget build(BuildContext context) => FutureBuilder(
      future: future,
      builder: (context, snapshot) {
        final data = snapshot.data;
        final values = (data is Map ? data['items'] as List? : null) ?? [];
        final children = values.map((raw) {
          final value = Map<String, dynamic>.from(raw);
          return SwitchListTile(
              title: Text(label(value)),
              value: value['enabled'] == true,
              onChanged: (enabled) => onToggle(value, enabled));
        }).toList();
        return ExpansionTile(
            title: Text(title),
            children: children.isEmpty
                ? [const ListTile(title: Text('目前沒有設定'))]
                : children);
      });
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
        if (snapshot.hasError) return ErrorView(snapshot.error.toString(), reload);
        if (snapshot.connectionState != ConnectionState.done)
          return const Center(child: CircularProgressIndicator());
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
              title: Text(data['market_regime']?.toString() ??
                  data['market_status']?.toString() ?? '市場狀態'),
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
                trailing: item is Map ? Text('${item['state'] ?? '—'}') : null),
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
        Chip(label: Text(value['chips_status']?.toString() ?? '籌碼狀態未提供'))
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
  const StockDetailPage({required this.api, required this.symbol, required this.onAskAi, super.key});
  final Api api;
  final String symbol;
  final VoidCallback onAskAi;
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
              ListTile(title: Text(role is Map ? '${role['role'] ?? '角色'}' : '$role'),
                  subtitle: role is Map ? Text('${role['summary'] ?? role['outcome'] ?? '—'}') : null),
            ListTile(title: const Text('來源與版本'), subtitle: Text(
                '來源 ${provenance['source_id'] ?? '—'} · schema ${provenance['schema_version'] ?? report['schema_version'] ?? '—'} · model ${provenance['model_version'] ?? report['model_version'] ?? '—'}')),
          ]),
          FilledButton.icon(onPressed: onAskAi, icon: const Icon(Icons.chat_bubble_outline), label: const Text('針對這檔問 AI')),
          const SizedBox(height: 12),
          const Text('信心度不是獲利機率；本服務提供研究資訊，不構成投資建議。')
        ]);
      }));
}

class JournalNotesPage extends StatefulWidget {
  const JournalNotesPage(this.api, {super.key});
  final Api api;
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
    final payload = await transactionDialog(context);
    if (payload != null) {
      await widget.api.post('/api/v1/me/journal/events', payload);
      if (mounted) showPortfolioPending();
      reload();
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      floatingActionButton:
          FloatingActionButton(onPressed: add, child: const Icon(Icons.add)),
      body: Column(children: [
        SummaryCards(widget.api),
        Padding(
            padding: const EdgeInsets.all(12),
            child: SegmentedButton<int>(
                segments: const [
                  ButtonSegment(value: 0, label: Text('記帳')),
                  ButtonSegment(value: 1, label: Text('筆記'))
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
            ActionChip(label: Text(symbolFilter == null ? '股票：全部' : '股票：$symbolFilter'),
                onPressed: () async {
                  final value = await textDialog(context, '歷史篩選', '股票代號，可留空');
                  if (value != null) setState(() {
                    symbolFilter = value.trim().isEmpty ? null : value.trim().toUpperCase();
                    rows = load();
                  });
                }),
            DropdownButton<int>(value: yearFilter ?? 0, items: [
              const DropdownMenuItem(value: 0, child: Text('年度：全部')),
              for (var year = DateTime.now().year; year >= DateTime.now().year - 5; year--)
                DropdownMenuItem(value: year, child: Text('年度：$year'))
            ], onChanged: (value) => setState(() {
              yearFilter = value == 0 ? null : value;
              rows = load();
            }))
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
                                : '${row['symbol'] ?? '一般筆記'} · revision ${row['revision']}'),
                            trailing: TextButton(
                                onPressed: () async {
                                  if (segment == 0) {
                                    final replacement =
                                        await transactionDialog(context);
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
          title: const Text('允許我主動選取投資屬性作為 AI 對話 context'),
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
                final token = auth?.idToken ?? auth?.accessToken;
                if (token != null)
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

Future<Map<String, dynamic>?> transactionDialog(BuildContext context) async {
  final type = await showDialog<String>(
      context: context,
      builder: (context) => SimpleDialog(title: const Text('交易類型'), children: [
            for (final item in const {
              'BUY': '買進',
              'SELL': '賣出',
              'CASH_DIV': '現金股利',
              'STOCK_DIV': '股票股利'
            }.entries)
              SimpleDialogOption(
                  onPressed: () => Navigator.pop(context, item.key),
                  child: Text(item.value))
          ]));
  if (type == null || !context.mounted) return null;
  final day = await showDatePicker(
      context: context,
      firstDate: DateTime(2000),
      lastDate: DateTime.now(),
      initialDate: DateTime.now());
  if (day == null || !context.mounted) return null;
  final symbol = await textDialog(context, '交易內容', '股票代號');
  if (symbol == null || !context.mounted) return null;
  final payload = <String, dynamic>{
    'event_type': type,
    'trade_date': day.toIso8601String().substring(0, 10),
    'symbol': symbol.toUpperCase(),
    'currency': 'TWD'
  };
  if (type == 'CASH_DIV') {
    final amount = await textDialog(context, '交易內容', '股利金額');
    if (amount == null) return null;
    payload['cash_amount'] = amount;
  } else {
    final shares = await textDialog(context, '交易內容', '股數');
    if (shares == null) return null;
    payload['shares'] = shares;
    if ((type == 'BUY' || type == 'SELL') && context.mounted) {
      final price = await textDialog(context, '交易內容', '成交單價');
      if (price == null) return null;
      payload['price'] = price;
    }
  }
  return payload;
}
