import 'package:flutter/services.dart';
// The production target is Flutter Web. Other targets can still copy a source.
Future<void> openResearchLink(String url) async {
  final uri = Uri.tryParse(url);
  if (uri == null || uri.scheme != 'https' || uri.host.isEmpty || uri.userInfo.isNotEmpty) return;
  await Clipboard.setData(ClipboardData(text: uri.toString()));
}
