import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/login_brand.dart';

void main() {
  test('web manifest pins Janus app scope and install icons', () {
    final manifest = jsonDecode(File('web/manifest.json').readAsStringSync())
        as Map<String, dynamic>;

    expect(manifest['id'], '/app/');
    expect(manifest['start_url'], '/app/');
    expect(manifest['scope'], '/app/');
    expect(manifest['display'], 'standalone');

    final icons = (manifest['icons'] as List).cast<Map<String, dynamic>>();
    expect(
      icons,
      contains(predicate<Map<String, dynamic>>((icon) =>
          icon['src'] == '/app/icons/Icon-192.png' &&
          icon['sizes'] == '192x192' &&
          icon['type'] == 'image/png')),
    );
    expect(
      icons,
      contains(predicate<Map<String, dynamic>>((icon) =>
          icon['src'] == '/app/icons/Icon-512.webp' &&
          icon['sizes'] == '512x512' &&
          icon['type'] == 'image/webp')),
    );
  });

  test('web entrypoint advertises canonical install metadata', () {
    final html = File('web/index.html').readAsStringSync();
    expect(html, contains('href="/app/manifest.json"'));
    expect(html, contains('href="/app/icons/Icon-192.png"'));
    expect(html, contains('apple-mobile-web-app-capable'));
  });

  test('login branding uses the high-resolution asset', () {
    expect(
      janusAppIconAsset,
      'assets/branding/janus_app_icon_512.webp',
    );
  });
}
