import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:http/http.dart' as http;

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
      final account =
          await GoogleSignIn(clientId: client, serverClientId: client).signIn();
      final token = (await account?.authentication)?.idToken;
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
  @override
  Widget build(BuildContext context) {
    final pages = [
      WatchlistPage(widget.api),
      JournalNotesPage(widget.api),
      ChatPage(widget.api),
      ProfilePage(api: widget.api, email: widget.email, onTheme: widget.onTheme)
    ];
    return Scaffold(
        appBar: AppBar(title: const Text('Janus')),
        body: pages[page],
        bottomNavigationBar: NavigationBar(
            selectedIndex: page,
            onDestinationSelected: (value) => setState(() => page = value),
            destinations: const [
              NavigationDestination(
                  icon: Icon(Icons.star_outline), label: '關注'),
              NavigationDestination(
                  icon: Icon(Icons.edit_note), label: '記帳／筆記'),
              NavigationDestination(
                  icon: Icon(Icons.chat_bubble_outline), label: 'AI'),
              NavigationDestination(
                  icon: Icon(Icons.person_outline), label: '我的')
            ]));
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
  const WatchlistPage(this.api, {super.key});
  final Api api;
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
    await widget.api.post('/api/v1/me/watchlist', {
      'symbol': symbol.toUpperCase(),
      if (target?.isNotEmpty == true) 'target_price': target
    });
    reload();
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

class JournalNotesPage extends StatefulWidget {
  const JournalNotesPage(this.api, {super.key});
  final Api api;
  @override
  State<JournalNotesPage> createState() => _JournalNotesPageState();
}

class _JournalNotesPageState extends State<JournalNotesPage> {
  int segment = 0;
  late Future<dynamic> rows = load();
  Future<dynamic> load() => widget.api
      .get(segment == 0 ? '/api/v1/me/journal/history' : '/api/v1/me/notes');
  void reload() => setState(() => rows = load());
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
                final google =
                    GoogleSignIn(clientId: client, serverClientId: client);
                await google.signOut();
                final account = await google.signIn();
                final token = (await account?.authentication)?.idToken;
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
