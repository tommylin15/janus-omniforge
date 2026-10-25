import 'package:flutter/material.dart';

/// Read-only product signal. No model fitting or inferred numbers in Flutter.
/// All percentages are annualized volatility fractions, never price returns.
class RiskSignalCard extends StatelessWidget {
  const RiskSignalCard({super.key, required this.specialist, required this.freshness});
  final Map<String, dynamic> specialist;
  final String freshness;

  static double? _fraction(Object? v) {
    if (v is! num || !v.isFinite || v < 0 || v > 10) return null;
    return v.toDouble();
  }

  @override
  Widget build(BuildContext context) {
    final metrics = specialist['metrics'];
    final data = metrics is Map ? metrics : const <String, dynamic>{};
    final servingSource = specialist['seq08_native_model'];
    final serving = servingSource is Map ? servingSource : const <String, dynamic>{};
    final predicted = _fraction(serving['prediction']);
    final recent = _fraction(data['recent_20d_volatility_annualized']);
    final validated = const {'ACTIVE_PREDICTED', 'ACTIVE_CACHED'}.contains(serving['status']) &&
        freshness == 'current' && predicted != null &&
        (serving['model_version'] ?? '').toString().startsWith('risk-xgb12-') &&
        serving['input_as_of'] != null;
    final stale = freshness == 'stale';
    final double? ratio = validated && recent != null && recent > 0
        ? predicted / recent : null;
    final increasing = ratio != null && ratio >= 1.20;
    final easing = ratio != null && ratio <= 0.80;
    final state = stale ? '資料已過期' : !validated ? '模型尚待驗證'
        : increasing ? '波動風險升高'
        : easing ? '波動風險相對緩和' : ratio == null ? '風險預測可用' : '波動風險接近近期';
    // Risk colors indicate forward volatility, NOT Taiwan stock price direction.
    final color = stale || !validated ? Colors.blueGrey
        : increasing ? Colors.deepOrange
        : easing ? Colors.teal : Colors.blueGrey;
    final asOf = specialist['analysis_as_of']?.toString() ?? '尚未取得';
    final model = validated ? serving['model_version'].toString() : '未啟用新版預測模型';
    return Semantics(
      label: 'Risk 分析師，$state，資料日 $asOf，交易日盤後更新',
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              const Expanded(child: Text('Risk 分析師｜個股風險',
                  style: TextStyle(fontWeight: FontWeight.w800))),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
                decoration: BoxDecoration(color: color.withValues(alpha: .10),
                    borderRadius: BorderRadius.circular(20)),
                child: Text(state, style: TextStyle(color: color, fontWeight: FontWeight.w700, fontSize: 12)),
              ),
            ]),
            const SizedBox(height: 9),
            Text(!validated
              ? '新版 Risk12 尚無可用正式推論；僅保留觀測事實，不顯示舊 Risk8 或替代預測。'
              : increasing
                ? '預期未來 20 個交易日的波動高於近期，請留意跳空、流動性與風險控管。'
                : easing
                  ? '預期未來 20 個交易日波動較近期緩和；低波動不代表股價將上漲。'
                  : ratio == null
                    ? '未來 20 個交易日風險波動預測可用；近期波動比較值尚不足。'
                    : '預期未來 20 個交易日波動與近期相近，仍需留意市場突然變化。'),
            if (validated) ...[
              const SizedBox(height: 6),
              Text(recent != null && recent > 0
                 ? '近期年化波動 ${(recent * 100).toStringAsFixed(1)}% → 預測 ${(predicted * 100).toStringAsFixed(1)}%'
                 : '未來 20 交易日年化 RMS 波動預測 ${(predicted * 100).toStringAsFixed(1)}%',
                style: TextStyle(color: color, fontWeight: FontWeight.w600)),
            ],
            const SizedBox(height: 8),
            Text('行情資料日 $asOf · 更新頻率：交易日盤後',
              style: const TextStyle(color: Colors.blueGrey, fontSize: 11)),
            Text('模型 $model · 模型評估：每月，重訓檢討：每季',
              style: const TextStyle(color: Colors.blueGrey, fontSize: 11)),
            if (validated)
              const Text('模型為歷史研究定版，前瞻結果仍需持續驗證；不是保證預測。',
                style: TextStyle(color: Colors.blueGrey, fontSize: 11)),
            const Text('波動是風險幅度，不是漲跌方向或買賣建議。',
              style: TextStyle(color: Colors.blueGrey, fontSize: 11)),
          ]),
        ),
      ),
    );
  }
}
