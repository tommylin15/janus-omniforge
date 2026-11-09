import 'package:flutter/material.dart';

import 'main.dart' as legacy;

const fvInk = Color(0xFF16324A);
const fvMuted = Color(0xFF5D7180);
const fvTeal = Color(0xFF177F88);
const fvCanvas = Color(0xFFF1F6F8);
const fvSoft = Color(0xFFE6F1F3);
const fvGain = Color(0xFFC62828);
const fvLoss = Color(0xFF16814F);

// Life-inspired pastel surfaces are presentation-only: never encode an
// investment recommendation, price direction or model confidence as a tint.
enum FvCardTone { mint, sky, peach, lavender }

BoxDecoration fvPastelDecoration({
  FvCardTone tone = FvCardTone.mint,
  double radius = 20,
}) {
  final colors = switch (tone) {
    FvCardTone.mint => const [Color(0xFFDDF2EF), Color(0xFFF7FCFB)],
    FvCardTone.sky => const [Color(0xFFE4F2F8), Color(0xFFFBFDFE)],
    FvCardTone.peach => const [Color(0xFFFFEEE1), Color(0xFFFFFBF7)],
    FvCardTone.lavender => const [Color(0xFFF1EAF8), Color(0xFFFCFAFE)],
  };
  return BoxDecoration(
    gradient: LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: colors,
    ),
    borderRadius: BorderRadius.circular(radius),
    border: Border.all(color: const Color(0xFFE0E9E9)),
  );
}

double? fvNumber(Object? value) => double.tryParse('${value ?? ''}');

Color fvSignedColor(Object? value) =>
    legacy.profitLossColor(value, neutral: fvMuted);

String fvSignedPercent(Object? value, {int decimals = 2}) {
  final ratio = fvNumber(value);
  if (ratio == null) return '—';
  final percent = ratio * 100;
  final sign = percent > 0 ? '+' : '';
  return '$sign${percent.toStringAsFixed(decimals)}%';
}

/// UI-only limit hint: exchange tick rounding matters (374 -> 411.0).
enum FvPriceLimit { none, up, down }

const fvLimitUpFill = Color(0xFFFFE8E8);
const fvLimitDownFill = Color(0xFFE3F3EA);
const fvLimitUpInk = Color(0xFFAD3232);
const fvLimitDownInk = Color(0xFF167149);

double _fvStockTick(double value) {
  if (value < 10) return 0.01;
  if (value < 50) return 0.05;
  if (value < 100) return 0.1;
  if (value < 500) return 0.5;
  if (value < 1000) return 1;
  return 5;
}

/// Only show an exchange limit where both current quote and reference are valid.
/// ETF limits vary by underlying; do not guess overseas/inverse ETF caps.
FvPriceLimit fvPriceLimitState(Map<String, dynamic> row) {
  if (row['currency'] != 'TWD' || row['price_status'] != 'available') {
    return FvPriceLimit.none;
  }
  if (!{'intraday', 'eod_final', 'closing_pending_eod'}
      .contains(row['quote_state'])) return FvPriceLimit.none;
  if (!{'official_previous_close', 'mis_previous_close', 'shioaji_previous_close'}
      .contains(row['previous_close_source'])) return FvPriceLimit.none;

  final price = fvNumber(row['market_price']);
  final basis = fvNumber(row['previous_close']);
  if (price == null || basis == null || !price.isFinite || !basis.isFinite ||
      price <= 0 || basis <= 0) return FvPriceLimit.none;

  final symbol = fvText(row['symbol'], missing: '');
  final kind = fvText(row['instrument_kind'], missing: '').toUpperCase();
  // 0050 is a known Taiwan-components ETF with a regular 10% price band.
  // Other ETFs require explicit exchange limit metadata before marking.
  final domesticEtf = kind == 'ETF' && symbol == '0050';
  final stock = kind == 'EQUITY' || kind == 'STOCK' ||
      (kind.isEmpty && RegExp(r'^[1-9][0-9]{3}$').hasMatch(symbol));
  if (!domesticEtf && !stock) return FvPriceLimit.none;

  double tick(double theoretical) => domesticEtf
      ? (theoretical < 50 ? 0.01 : 0.05)
      : _fvStockTick(theoretical);
  final theoreticalUp = basis * 1.10;
  final theoreticalDown = basis * 0.90;
  final upTick = tick(theoreticalUp);
  final downTick = tick(theoreticalDown);
  final upper = ((theoreticalUp / upTick) + 1e-8).floor() * upTick;
  final lower = ((theoreticalDown / downTick) - 1e-8).ceil() * downTick;
  if ((price - upper).abs() < 0.0001) return FvPriceLimit.up;
  if ((price - lower).abs() < 0.0001) return FvPriceLimit.down;
  return FvPriceLimit.none;
}

Widget fvLimitPriceText(Map<String, dynamic> row, String value, {
  Key? key,
  double fontSize = 13,
  Color ordinaryColor = fvInk,
}) {
  final state = fvPriceLimitState(row);
  final active = state != FvPriceLimit.none;
  final ink = state == FvPriceLimit.up ? fvLimitUpInk
      : state == FvPriceLimit.down ? fvLimitDownInk : ordinaryColor;
  final content = Container(
    padding: active
        ? const EdgeInsets.symmetric(horizontal: 5, vertical: 2)
        : EdgeInsets.zero,
    decoration: active ? BoxDecoration(
      color: state == FvPriceLimit.up ? fvLimitUpFill : fvLimitDownFill,
      borderRadius: BorderRadius.circular(6),
    ) : null,
    child: Text(value, key: key, maxLines: 1, overflow: TextOverflow.ellipsis,
      style: TextStyle(color: ink, fontSize: fontSize,
          fontWeight: FontWeight.w800)),
  );
  return !active ? content : Tooltip(
    message: state == FvPriceLimit.up ? '漲停價' : '跌停價',
    child: content,
  );
}

List<dynamic> fvRows(dynamic value) {
  if (value is List) return value;
  if (value is Map && value['items'] is List) return value['items'] as List;
  if (value is Map && value['rows'] is List) return value['rows'] as List;
  return const [];
}

Map<String, dynamic> fvMap(dynamic value) => value is Map
    ? Map<String, dynamic>.from(value)
    : <String, dynamic>{};

DateTime? fvRowDate(Map<String, dynamic> row, List<String> fields) {
  for (final field in fields) {
    final date = DateTime.tryParse('${row[field] ?? ''}');
    if (date != null) return date;
  }
  return null;
}

// Sort a copy: presentation must not reorder a shared API response or a chart.
List<Map<String, dynamic>> fvNewestRows(List<dynamic> rows,
    {required List<String> fields, bool recentOnly = true, DateTime? now}) {
  final today = now ?? DateTime.now();
  final cutoff = DateTime(today.year - 2, today.month, today.day);
  final dated = rows.map(fvMap).where((row) {
    final date = fvRowDate(row, fields);
    return !recentOnly || date == null || !date.isBefore(cutoff);
  }).toList();
  dated.sort((a, b) {
    final left = fvRowDate(a, fields), right = fvRowDate(b, fields);
    if (left == null) return right == null ? 0 : 1;
    if (right == null) return -1;
    return right.compareTo(left);
  });
  return dated;
}

Color fvDatedRowColor(int index) => index.isEven ? fvSoft : Colors.white;

String fvText(Object? value, {String missing = '—'}) {
  final result = value?.toString().trim() ?? '';
  return result.isEmpty ? missing : result;
}

int fvInt(Object? value) => int.tryParse('${value ?? ''}') ?? 0;

Widget fvPageTitle(BuildContext context, String title, {String? subtitle}) =>
    Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                  color: fvInk,
                  fontWeight: FontWeight.w800,
                  letterSpacing: -.4,
                ),
          ),
          if (subtitle != null) ...[
            const SizedBox(height: 4),
            Text(
              subtitle,
              style: Theme.of(context)
                  .textTheme
                  .bodyMedium
                  ?.copyWith(color: fvMuted),
            ),
          ],
        ],
      ),
    );

Widget fvSectionTitle(BuildContext context, String title, {String? trailing}) =>
    Padding(
      padding: const EdgeInsets.fromLTRB(2, 14, 2, 8),
      child: Row(
        children: [
          Expanded(
            child: Text(
              title,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    color: fvInk,
                    fontWeight: FontWeight.w800,
                  ),
            ),
          ),
          if (trailing != null)
            Text(
              trailing,
              style: Theme.of(context)
                  .textTheme
                  .bodySmall
                  ?.copyWith(color: fvMuted),
            ),
        ],
      ),
    );

Widget fvPanel({required Widget child, EdgeInsetsGeometry? padding,
    Color color = Colors.white, FvCardTone? tone}) => Card(
      margin: const EdgeInsets.only(bottom: 10),
      color: color,
      elevation: 0,
      clipBehavior: Clip.antiAlias,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      child: Ink(
        decoration: tone == null ? null : fvPastelDecoration(tone: tone),
        child: Padding(
          padding: padding ?? const EdgeInsets.all(16),
          child: child,
        ),
      ),
    );

Widget fvBoundedState(String text, {IconData icon = Icons.info_outline}) =>
    fvPanel(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: fvTeal, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Text(text, style: const TextStyle(color: fvMuted)),
          ),
        ],
      ),
    );

Widget fvStatusPill(Object? value) {
  final label = legacy.uiLabel(value);
  return Container(
    padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
    decoration: BoxDecoration(
      color: fvSoft,
      borderRadius: BorderRadius.circular(999),
    ),
    child: Text(
      label,
      style: const TextStyle(
        color: fvTeal,
        fontSize: 12,
        fontWeight: FontWeight.w700,
      ),
    ),
  );
}

Widget fvTag(String text, {bool warning = false, Color? color, IconData? icon}) => Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(
        color: warning ? const Color(0xFFFFF2E2) : fvSoft,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        if (icon != null) ...[
          Icon(icon, size: 13,
            color: color ?? (warning ? const Color(0xFF9A5A10) : fvTeal)),
          const SizedBox(width: 4),
        ],
        Flexible(child: Text(
          text,
          style: TextStyle(
            color: color ?? (warning ? const Color(0xFF9A5A10) : fvTeal),
            fontSize: 11,
            fontWeight: FontWeight.w700,
          ),
        )),
      ]),
    );

Widget fvMetricTile(
  String label,
  String value, {
  String? detail,
  Color? valueColor,
  Color? detailColor,
}) => Container(
      height: 116,
      padding: const EdgeInsets.all(13),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: fvMuted,
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 7),
          Text(
            value,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              color: valueColor ?? fvInk,
              fontSize: 17,
              fontWeight: FontWeight.w800,
              height: 1.15,
            ),
          ),
          if (detail != null) ...[
            const SizedBox(height: 5),
            Text(
              detail,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                color: detailColor ?? fvMuted,
                fontSize: 10.5,
              ),
            ),
          ],
        ],
      ),
    );
