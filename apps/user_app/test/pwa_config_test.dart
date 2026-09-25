import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

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
          icon['src'] == 'icons/Icon-512.png' &&
          icon['sizes'] == '512x512' &&
          icon['type'] == 'image/png')),
    );
    expect(
      icons,
      contains(predicate<Map<String, dynamic>>((icon) =>
          icon['src'] == 'icons/maskable-512.png' &&
          icon['purpose'] == 'maskable')),
    );
  });

  test('web entrypoint advertises dedicated Apple touch icon', () {
    final html = File('web/index.html').readAsStringSync();
    expect(html, contains('apple-touch-icon.png'));
    expect(html, isNot(contains('Icon-512.webp')));
  });
}
