import 'package:flutter/material.dart';

import 'admin.dart';
import 'final_visual_common.dart';
import 'main.dart' as legacy;
import 'final_analysis.dart';

class AdminAnalysisPage extends StatefulWidget {
  const AdminAnalysisPage(this.api, {super.key});
  final AdminApi api;
  @override
  State<AdminAnalysisPage> createState() => _AdminAnalysisPageState();
}

class _AdminAnalysisPageState extends State<AdminAnalysisPage> {
  late Future<dynamic> data = widget.api.get('/api/v1/admin/analysis');
  bool busy = false;
  final testSymbol = TextEditingController(text: '2330');
  Map<String, dynamic>? comparison;
  @override
  void dispose() {
    testSymbol.dispose();
    super.dispose();
  }

  void reload() =>
      setState(() => data = widget.api.get('/api/v1/admin/analysis'));

  Future<void> editCapability() async {
    final email = TextEditingController(), reason = TextEditingController();
    final version = TextEditingController(text: '0');
    final quota = TextEditingController(text: '50'),
        cooldown = TextEditingController(text: '300');
    bool enabled = false;
    final value = await showDialog<Map<String, dynamic>>(
        context: context,
        builder: (context) => StatefulBuilder(
            builder: (context, update) => AlertDialog(
                    title: const Text('CEO 使用權限'),
                    content: SingleChildScrollView(
                        child:
                            Column(mainAxisSize: MainAxisSize.min, children: [
                      TextField(
                          controller: email,
                          decoration: const InputDecoration(
                              labelText: '已登入使用者的 Google email')),
                      TextField(
                          controller: version,
                          decoration: const InputDecoration(
                              labelText: '目前權限版本（新授權為 0）'),
                          keyboardType: TextInputType.number),
                      SwitchListTile(
                          title: const Text('允許手動 CEO 分析'),
                          value: enabled,
                          onChanged: (v) => update(() => enabled = v)),
                      TextField(
                          controller: quota,
                          decoration:
                              const InputDecoration(labelText: '每日額度（0–50）'),
                          keyboardType: TextInputType.number),
                      TextField(
                          controller: cooldown,
                          decoration: const InputDecoration(
                              labelText: '冷卻秒數（60–86400）'),
                          keyboardType: TextInputType.number),
                      TextField(
                          controller: reason,
                          decoration: const InputDecoration(labelText: '稽核原因')),
                    ])),
                    actions: [
                      TextButton(
                          onPressed: () => Navigator.pop(context),
                          child: const Text('取消')),
                      FilledButton(
                          onPressed: () {
                            final v = int.tryParse(version.text),
                                q = int.tryParse(quota.text),
                                c = int.tryParse(cooldown.text);
                            if (email.text.trim().isEmpty ||
                                reason.text.trim().isEmpty ||
                                v == null ||
                                q == null || q < 0 || q > 50 ||
                                c == null || c < 60 || c > 86400) return;
                            Navigator.pop(context, {
                              'email': email.text.trim(),
                              'enabled': enabled,
                              'expected_version': v,
                              'daily_quota': q,
                              'cooldown_seconds': c,
                              'reason': reason.text.trim()
                            });
                          },
                          child: const Text('保存新版本')),
                    ])));
    for (final controller in [email, reason, version, quota, cooldown]) {
      controller.dispose();
    }
    if (value != null) await save('/api/v1/admin/analysis/capability', value);
  }

  Future<void> editProfile(
      Map<String, dynamic> profile, Map<String, dynamic> options) async {
    final reason = TextEditingController();
    bool approve = profile['approved'] == true;
    final models = fvMap(fvMap(profile['route_json'])['models']);
    for (final item in options.entries) {
      models.putIfAbsent(item.key, () => fvRows(item.value).first);
    }
    var providers =
        fvRows(fvMap(profile['route_json'])['providers']).cast<String>();
    final value = await showDialog<Map<String, dynamic>>(
        context: context,
        builder: (context) => StatefulBuilder(
            builder: (context, update) => AlertDialog(
                    title: const Text('CEO profile／模型／順序'),
                    content: SingleChildScrollView(
                        child:
                            Column(mainAxisSize: MainAxisSize.min, children: [
                      const Text(
                          '核准前須確認 provider 登入、免費或已授權費用與真實執行證據。核准本身不代表驗收通過。'),
                      SwitchListTile(
                          title: const Text('核准此版本執行'),
                          value: approve,
                          onChanged: (v) => update(() => approve = v)),
                      DropdownButtonFormField<String>(
                          initialValue: providers.first,
                          decoration:
                              const InputDecoration(labelText: '第一順位 provider'),
                          items: providers
                              .map((p) =>
                                  DropdownMenuItem(value: p, child: Text(p)))
                              .toList(),
                          onChanged: (v) {
                            if (v != null)
                              update(() => providers = [
                                    v,
                                    ...providers.where((p) => p != v)
                                  ]);
                          }),
                      for (final item in options.entries)
                        DropdownButtonFormField<String>(
                            initialValue: models[item.key] as String?,
                            decoration:
                                InputDecoration(labelText: '${item.key} 已核准模型'),
                            items: fvRows(item.value)
                                .map((m) => DropdownMenuItem(
                                    value: m as String, child: Text(m)))
                                .toList(),
                            onChanged: (v) {
                              if (v != null) update(() => models[item.key] = v);
                            }),
                      TextField(
                          controller: reason,
                          decoration:
                              const InputDecoration(labelText: '原因／證據')),
                    ])),
                    actions: [
                      TextButton(
                          onPressed: () => Navigator.pop(context),
                          child: const Text('取消')),
                      FilledButton(
                          onPressed: () {
                            if (reason.text.trim().isNotEmpty) {
                              Navigator.pop(context, {
                                'approved': approve,
                                'expected_version': profile['version'],
                                'providers': providers,
                                'models': models,
                                'reason': reason.text.trim()
                              });
                            }
                          },
                          child: const Text('保存新版本')),
                    ])));
    reason.dispose();
    if (value != null) {
      await save(
          '/api/v1/admin/analysis/profiles/${profile['profile_id']}', value);
    }
  }

  Future<void> save(String path, Map<String, dynamic> value) async {
    setState(() => busy = true);
    try {
      await widget.api.put(path, value);
      if (mounted) reload();
    } catch (_) {
      if (mounted)
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('保存未完成；請核對版本、使用者與輸入後重試')));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> restoreProfile(
      Map<String, dynamic> previous, int currentVersion) async {
    final reason = TextEditingController();
    final value = await showDialog<String>(
        context: context,
        builder: (context) => AlertDialog(
                title: Text('還原 profile v${previous['version']} 的設定'),
                content: TextField(
                    controller: reason,
                    decoration: const InputDecoration(labelText: '還原原因／證據')),
                actions: [
                  TextButton(
                      onPressed: () => Navigator.pop(context),
                      child: const Text('取消')),
                  FilledButton(
                      onPressed: () {
                        if (reason.text.trim().isNotEmpty)
                          Navigator.pop(context, reason.text.trim());
                      },
                      child: const Text('另存新版本'))
                ]));
    reason.dispose();
    if (value != null) {
      await save('/api/v1/admin/analysis/profiles/${previous['profile_id']}', {
        'approved': previous['approved'],
        'expected_version': currentVersion,
        'providers': fvMap(previous['route_json'])['providers'],
        if (fvMap(previous['route_json'])['models'] != null)
          'models': fvMap(previous['route_json'])['models'],
        'reason': '還原 v${previous['version']}：$value'
      });
    }
  }

  Future<void> compareSymbol() async {
    final symbol = testSymbol.text.trim();
    if (!RegExp(r'^[A-Za-z0-9.-]{1,20}$').hasMatch(symbol)) return;
    setState(() => busy = true);
    try {
      final value = await widget.api.get(
          '/api/v1/admin/analysis/compare?symbol=${Uri.encodeQueryComponent(symbol)}');
      if (mounted) setState(() => comparison = fvMap(value));
    } catch (_) {
      if (mounted)
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('測試股號的版本比較暫時不可用')));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<dynamic>(
      future: data,
      builder: (context, snapshot) {
        if (snapshot.hasError)
          return Center(
              child: OutlinedButton(
                  onPressed: reload, child: const Text('分析管理暫時無法使用，重新讀取')));
        if (!snapshot.hasData)
          return const Center(child: CircularProgressIndicator());
        final value = fvMap(snapshot.data);
        return ListView(padding: const EdgeInsets.all(16), children: [
          Row(children: [
            const Expanded(
                child: Text('分析管理',
                    style:
                        TextStyle(fontSize: 22, fontWeight: FontWeight.bold))),
            IconButton(onPressed: reload, icon: const Icon(Icons.refresh))
          ]),
          const Text('基準可用與模型品質分開呈現；尚未驗證的模型不能升級。'),
          const Text('Provider auth／health 未取得即時證據時維持 NOT VERIFIED；未知成本不顯示 0。'),
          for (final item in fvRows(value['profiles']))
            Card(
                child: ListTile(
                    title: Text(
                        '${fvMap(item)['profile_id']} · v${fvMap(item)['version']} · ${fvMap(item)['approved'] == true ? '已核准' : '未核准'}'),
                    subtitle: Text(
                        '${fvMap(item)['route_json']}\n${fvMap(item)['reason']}'),
                    trailing: TextButton(
                        onPressed: busy
                            ? null
                            : () => editProfile(
                                fvMap(item), fvMap(value['model_options'])),
                        child: const Text('變更核准')))),
          ExpansionTile(title: const Text('Profile 不可變版本／還原'), children: [
            for (final item in fvRows(value['profile_history']))
              ListTile(
                  title: Text(
                      '${fvMap(item)['profile_id']} · v${fvMap(item)['version']}'),
                  subtitle: Text(
                      '${fvMap(item)['route_json']}\n${fvMap(item)['actor']} · ${fvMap(item)['reason']}'),
                  trailing: TextButton(
                      onPressed: busy
                          ? null
                          : () {
                              final current = fvRows(value['profiles'])
                                  .map(fvMap)
                                  .firstWhere((p) =>
                                      p['profile_id'] ==
                                      fvMap(item)['profile_id']);
                              restoreProfile(
                                  fvMap(item), current['version'] as int);
                            },
                      child: const Text('還原設定'))),
          ]),
          OutlinedButton(
              onPressed: busy ? null : editCapability,
              child: const Text('設定 CEO 使用權限／額度')),
          for (final item in fvRows(value['capabilities']))
            ListTile(
                title: Text(
                    '${fvMap(item)['display_email'] ?? fvMap(item)['user_id']} · v${fvMap(item)['version']}'),
                subtitle: Text(
                    '${fvMap(item)['enabled'] == true ? '啟用' : '停用'} · 每日 ${fvMap(item)['daily_quota']} · 冷卻 ${fvMap(item)['cooldown_seconds']} 秒')),
          const Divider(),
          const Text('Specialist persisted 基準／版本'),
          TextField(
              controller: testSymbol,
              decoration:
                  const InputDecoration(labelText: '測試股號（比較已保存的前後基準，不呼叫模型）')),
          OutlinedButton(
              onPressed: busy ? null : compareSymbol,
              child: const Text('比較版本')),
          if (comparison != null) ...[
            Text(comparison!['comparison_status'] == 'available'
                ? '已保存版本比較'
                : '尚無足夠版本可比較'),
            for (final version in fvRows(comparison!['versions']))
              ExpansionTile(
                  title: Text(
                      '${fvMap(version)['analysis_as_of']} · ${fvMap(version)['execution_id']}'),
                  children: [
                    for (final role in fvRows(fvMap(version)['specialists']))
                      ListTile(
                          title: Text(
                              '${legacy.uiLabel(fvMap(role)['role'])} · ${fvMap(role)['engine_version']}'),
                          subtitle: Text(
                              '${fvMap(role)['metrics']}\n${fvMap(role)['plain_language']}')),
                  ]),
          ],
          for (final item in fvRows(value['specialists']))
            ExpansionTile(
                title: Text(
                    '${fvMap(item)['symbol']} · ${fvMap(item)['analysis_as_of']}'),
                subtitle: const Text('模型品質 NOT VERIFIED；無自動 promotion'),
                children: [
                  for (final role in fvRows(
                      fvMap(fvMap(item)['payload_json'])['specialists']))
                    ListTile(
                        title: Text(
                            '${legacy.uiLabel(fvMap(role)['role'])} · ${fvMap(role)['baseline_status']}'),
                        subtitle: Text(
                            '${fvMap(role)['plain_language']}\n${fvMap(role)['engine_version']} / ${fvMap(role)['model_version']}')),
                ]),
          const Divider(),
          const Text('CEO 執行／usage／cost audit（不含私人交易內容）'),
          for (final item in fvRows(value['executions']))
            ExpansionTile(
                title: Text(
                    '${fvMap(item)['symbol']} · ${analysisState(fvMap(item)['status'])}'),
                subtitle: Text(
                    '${fvMap(item)['requested_at']} · profile v${fvMap(item)['profile_version']}'),
                children: [
                  for (final attempt
                      in fvRows(fvMap(fvMap(item)['audit_json'])['attempts']))
                    ListTile(
                        title: Text(
                            '${fvMap(attempt)['provider']} / ${fvMap(attempt)['model']} · ${fvMap(attempt)['status']}'),
                        subtitle: Text(
                            'usage ${fvMap(attempt)['usage'] ?? 'unknown'} · USD ${fvMap(attempt)['actual_cost_usd'] ?? 'unknown'}')),
                ]),
        ]);
      });
}
