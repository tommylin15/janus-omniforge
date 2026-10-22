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
    final predicted = _fraction(data['future_20d_volatility_annualized']);
    final recent = _fraction(data['recent_20d_volatility_annualized']);
    final validated = specialist['model_status'] == 'oos_validated' &&
        specialist['baseline_status'] == 'available' &&
        freshness == 'current' &&
        predicted != null && recent != null && recent > 0 &&
        (specialist['model_version'] ?? '').toString().startsWith('risk-xgboost');
    final stale = freshness == 'stale';
    final double? ratio = validated ? predicted / recent : null;
    final increasing = ratio != null && ratio >= 1.20;
    final easing = ratio != null && ratio <= 0.80;
    final state = stale ? '資料已過期' : !validated ? '模型尚待驗證'
        : increasing ? '波動風險升高'
        : easing ? '波動風險相對緩和' : '波動風險接近近期';
    // Risk colors indicate forward volatility, NOT Taiwan stock price direction.
    final color = stale || !validated ? Colors.blueGrey
        : increasing ? Colors.deepOrange
        : easing ? Colors.teal : Colors.blueGrey;
    final asOf = specialist['analysis_as_of']?.toString() ?? '尚未取得';
    final model = validated ? specialist['model_version'].toString() : '未啟用預測模型';
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
              ? '目前顯示已保存的風險基準；XGBoost 預測尚未完成正式驗收，不提供未驗證風險方向。'
              : increasing
                ? '預期未來 20 個交易日的波動高於近期，請留意跳空、流動性與風險控管。'
                : easing
                  ? '預期未來 20 個交易日波動較近期緩和；低波動不代表股價將上漲。'
                  : '預期未來 20 個交易日波動與近期相近，仍需留意市場突然變化。'),
            if (validated) ...[
              const SizedBox(height: 6),
              Text('近期年化波動 ${(recent * 100).toStringAsFixed(1)}% → 預測 ${(predicted * 100).toStringAsFixed(1)}%',
                style: TextStyle(color: color, fontWeight: FontWeight.w600)),
            ],
            const SizedBox(height: 8),
            Text('行情資料日 $asOf · 更新頻率：交易日盤後',
              style: const TextStyle(color: Colors.blueGrey, fontSize: 11)),
            Text('模型 $model · 模型評估：每月，重訓檢討：每季',
              style: const TextStyle(color: Colors.blueGrey, fontSize: 11)),
            const Text('波動是風險幅度，不是漲跌方向或買賣建議。',
              style: TextStyle(color: Colors.blueGrey, fontSize: 11)),
          ]),
        ),
      ),
    );
  }
}
