import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:janus_user_app/login_brand.dart';

void main() {
  test('web manifest pins Janus app scope and PNG install icons', () {
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
          icon['type'] == 'image/png' &&
          icon['purpose'] == 'any')),
    );
    expect(
      icons,
      contains(predicate<Map<String, dynamic>>((icon) =>
          icon['src'] == '/app/icons/Icon-512.png' &&
          icon['sizes'] == '512x512' &&
          icon['type'] == 'image/png' &&
          icon['purpose'] == 'any')),
    );
    expect(
      icons,
      contains(predicate<Map<String, dynamic>>((icon) =>
          icon['src'] == '/app/icons/maskable-512.png' &&
          icon['sizes'] == '512x512' &&
          icon['type'] == 'image/png' &&
          icon['purpose'] == 'maskable')),
    );
  });

  test('web entrypoint advertises dedicated install icons', () {
    final html = File('web/index.html').readAsStringSync();
    expect(html, contains('href="/app/manifest.json"'));
    expect(html, contains('href="/app/apple-touch-icon.png"'));
    expect(html, contains('href="/app/favicon.png"'));
    expect(html, contains('apple-mobile-web-app-capable'));
    expect(html, isNot(contains('Icon-512.webp')));
  });

  test('login branding keeps the detailed 512px WebP asset', () {
    expect(
      janusAppIconAsset,
      'assets/branding/janus_app_icon_512.webp',
    );
  });
}
