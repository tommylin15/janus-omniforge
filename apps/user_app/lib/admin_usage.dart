import 'package:flutter/material.dart';
import 'admin.dart';

class AdminUsagePage extends StatefulWidget {
  const AdminUsagePage(this.api, {super.key});
  final AdminApi api;
  @override
  State<AdminUsagePage> createState() => _AdminUsagePageState();
}

class _AdminUsagePageState extends State<AdminUsagePage> {
  int days = 7;
  String grain = 'day';
  String? userId;
  String? email;
  final query = TextEditingController();
  late Future<dynamic> data = load();
  Future<dynamic>? users, recent;
  Future<dynamic> load() => widget.api.get(userId == null
      ? '/api/v1/admin/usage/overview?days=$days&grain=$grain'
      : '/api/v1/admin/usage/users/${Uri.encodeComponent(userId!)}?days=$days&grain=$grain');
  @override
  void dispose() {
    query.dispose();
    super.dispose();
  }

  List rows(dynamic root) => (root as Map?)?['items'] as List? ?? [];
  @override
  Widget build(BuildContext context) =>
      ListView(padding: const EdgeInsets.all(16), children: [
        Text(email == null ? '全站使用分析' : '使用分析 · $email',
            style: Theme.of(context).textTheme.titleLarge),
        const Text('自願上報；遺失率未知。時間為估計活躍時間，不代表精確閱讀時間；無回報不等於零。'),
        DropdownButton<String>(
            value: grain,
            items: const [
              DropdownMenuItem(value: 'day', child: Text('按日')),
              DropdownMenuItem(value: 'week', child: Text('按週')),
              DropdownMenuItem(value: 'month', child: Text('按月'))
            ],
            onChanged: (value) {
              if (value != null)
                setState(() {
                  grain = value;
                  data = load();
                });
            }),
        Wrap(spacing: 8, children: [
          for (final period in [7, 30, 90])
            ChoiceChip(
                label: Text('$period 天'),
                selected: days == period,
                onSelected: (_) => setState(() {
                      days = period;
                      data = load();
                    })),
          if (userId != null)
            TextButton(
                onPressed: () => setState(() {
                      userId = null;
                      email = null;
                      recent = null;
                      data = load();
                    }),
                child: const Text('回全站')),
        ]),
        TextField(
            controller: query,
            maxLength: 100,
            decoration:
                const InputDecoration(labelText: '查詢使用者 Email 或 user ID'),
            onSubmitted: (_) => setState(() => users = widget.api.get(
                '/api/v1/admin/usage/users?q=${Uri.encodeQueryComponent(query.text)}'))),
        TextButton(
            onPressed: () => setState(() => users = widget.api.get(
                '/api/v1/admin/usage/users?q=${Uri.encodeQueryComponent(query.text)}')),
            child: const Text('查詢使用者')),
        if (users != null)
          FutureBuilder<dynamic>(
              future: users,
              builder: (context, snapshot) {
                if (snapshot.hasError) return const Text('使用者目錄暫時無法讀取');
                if (snapshot.connectionState != ConnectionState.done ||
                    !snapshot.hasData) return const LinearProgressIndicator();
                return Column(children: [
                  for (final row in rows(snapshot.data))
                    ListTile(
                      title: Text('${row['display_email'] ?? row['user_id']}'),
                      subtitle: Text(
                          '近7日操作 ${row['actions'] ?? '無回報'} · 最後活動 ${row['last_event_at'] ?? '未知'}'),
                      onTap: () => setState(() {
                        userId = '${row['user_id']}';
                        email = '${row['display_email'] ?? userId}';
                        data = load();
                        recent = widget.api.get(
                            '/api/v1/admin/usage/users/${Uri.encodeComponent(userId!)}/recent');
                      }),
                    )
                ]);
              }),
        FutureBuilder<dynamic>(
            future: data,
            builder: (context, snapshot) {
              if (snapshot.hasError) return const Text('使用分析暫時無法讀取');
              if (snapshot.connectionState != ConnectionState.done ||
                  !snapshot.hasData) return const LinearProgressIndicator();
              final values = rows(snapshot.data);
              final dau =
                  (snapshot.data as Map)['daily_active_users'] as List? ?? [];
              final rank = <String, num>{};
              for (final row in values) {
                final key = '${row['feature_id']}';
                rank[key] =
                    (rank[key] ?? 0) + (num.tryParse('${row['actions']}') ?? 0);
              }
              final ranked = rank.entries.toList()
                ..sort((a, b) => b.value.compareTo(a.value));
              if (values.isEmpty) return const Text('尚無資料；可能未開啟收集，不判定為零');
              return Column(children: [
                for (final row in dau)
                  ListTile(
                      title:
                          Text('${row['day']} · DAU ${row['active_users']}')),
                for (final entry in ranked)
                  ListTile(title: Text('${entry.key} · 操作 ${entry.value}')),
                for (final row in values)
                  ListTile(
                    title: Text('${row['day']} · ${row['feature_id']}'),
                    subtitle: Text(
                        '功能活躍人數 ${row['active_users']} · 開啟 ${row['page_views']} · 操作 ${row['actions']}\nsession ${row['sessions'] ?? '未知'} · 成功 ${row['successes']}／失敗 ${row['failures']} · 估計活躍 ${((num.tryParse('${row['active_duration_ms']}') ?? 0) / 1000).round()} 秒'),
                  )
              ]);
            }),
        if (recent != null) ...[
          const Text('最近7天時間線（最多100筆）'),
          FutureBuilder<dynamic>(
              future: recent,
              builder: (context, snapshot) {
                if (snapshot.hasError) return const Text('時間線暫時無法讀取');
                if (snapshot.connectionState != ConnectionState.done ||
                    !snapshot.hasData) return const LinearProgressIndicator();
                return Column(children: [
                  for (final row in rows(snapshot.data))
                    ListTile(
                      title:
                          Text('${row['client_time']} · ${row['feature_id']}'),
                      subtitle: Text(
                          '${row['event_type']} · ${row['action_key']} · ${row['outcome']}'),
                    )
                ]);
              }),
        ],
      ]);
}
