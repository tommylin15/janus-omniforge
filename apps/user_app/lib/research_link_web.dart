// Browser-only, explicit click. No remote images, HTML, scripts or tracking loads.
// ignore: deprecated_member_use, avoid_web_libraries_in_flutter
import 'dart:html' as html;
Future<void> openResearchLink(String value) async {
  final uri = Uri.tryParse(value);
  if (uri == null || uri.scheme != 'https' || uri.host.isEmpty || uri.userInfo.isNotEmpty) return;
  html.window.open(uri.toString(), '_blank', 'noopener,noreferrer');
}
