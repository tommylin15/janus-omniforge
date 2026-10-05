import 'package:flutter/material.dart';

import 'main.dart' as legacy;

const fvInk = Color(0xFF16324A);
const fvMuted = Color(0xFF5D7180);
const fvTeal = Color(0xFF177F88);
const fvCanvas = Color(0xFFF1F6F8);
const fvSoft = Color(0xFFE6F1F3);

List<dynamic> fvRows(dynamic value) {
  if (value is List) return value;
  if (value is Map && value['items'] is List) return value['items'] as List;
  if (value is Map && value['rows'] is List) return value['rows'] as List;
  return const [];
}

Map<String, dynamic> fvMap(dynamic value) => value is Map
    ? Map<String, dynamic>.from(value)
    : <String, dynamic>{};

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

Widget fvPanel({required Widget child, EdgeInsetsGeometry? padding}) => Card(
      margin: const EdgeInsets.only(bottom: 10),
      color: Colors.white,
      elevation: 0,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      child: Padding(
        padding: padding ?? const EdgeInsets.all(16),
        child: child,
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

Widget fvTag(String text, {bool warning = false}) => Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(
        color: warning ? const Color(0xFFFFF2E2) : fvSoft,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        text,
        style: TextStyle(
          color: warning ? const Color(0xFF9A5A10) : fvTeal,
          fontSize: 11,
          fontWeight: FontWeight.w700,
        ),
      ),
    );

Widget fvMetricTile(String label, String value, {String? detail}) => Container(
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
            style: const TextStyle(
              color: fvInk,
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
              style: const TextStyle(color: fvMuted, fontSize: 10.5),
            ),
          ],
        ],
      ),
    );
