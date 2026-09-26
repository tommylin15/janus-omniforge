import 'dart:math' as math;

import 'package:flutter/material.dart';

const janusAppIconAsset = 'assets/branding/janus_app_icon_512.webp';

Widget buildLoginBranding(BuildContext context) {
  if (Uri.base.pathSegments.contains('admin')) {
    return const SizedBox.shrink();
  }

  return LayoutBuilder(
    builder: (context, constraints) {
      final viewportWidth = MediaQuery.sizeOf(context).width;
      final parentWidth = constraints.hasBoundedWidth
          ? constraints.maxWidth
          : viewportWidth;
      final availableWidth = math.min(viewportWidth, parentWidth);
      final compact = availableWidth < 720;

      if (compact) {
        final iconSize = (availableWidth - 48).clamp(120.0, 220.0).toDouble();
        return Padding(
          padding: const EdgeInsets.only(bottom: 20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(32),
                child: Image.asset(
                  janusAppIconAsset,
                  width: iconSize,
                  height: iconSize,
                  fit: BoxFit.cover,
                  semanticLabel: 'Janus 雙生獸投資研究圖示',
                ),
              ),
              const SizedBox(height: 16),
              Text(
                '更聰明・更安心・更愉快',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
              ),
              const SizedBox(height: 6),
              Text(
                '多源資料 × AI 多分析師 × 個人化洞察',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        );
      }

      final heroWidth = math.min(960.0, availableWidth - 48.0);
      final narrow = heroWidth < 820;
      final iconSize = narrow ? 180.0 : 235.0;
      final horizontalPadding = narrow ? 28.0 : 42.0;
      final gap = narrow ? 20.0 : 28.0;
      final headlineSize = narrow ? 24.0 : 28.0;
      final promiseSize = narrow ? 25.0 : 30.0;
      final detailSize = narrow ? 13.0 : 15.0;
      final textRightInset = horizontalPadding + iconSize + gap;

      return Padding(
        padding: const EdgeInsets.only(bottom: 24),
        child: Center(
          child: Container(
            width: heroWidth,
            height: 300,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(32),
              gradient: const LinearGradient(
                colors: [
                  Color(0xFF061D55),
                  Color(0xFF0B4FD6),
                  Color(0xFF12C9F5),
                ],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              boxShadow: const [
                BoxShadow(
                  color: Color(0x33064FB8),
                  blurRadius: 30,
                  offset: Offset(0, 14),
                ),
              ],
            ),
            child: Stack(
              children: [
                Positioned.fill(
                  child: Padding(
                    padding: EdgeInsets.fromLTRB(
                      horizontalPadding,
                      34,
                      textRightInset,
                      34,
                    ),
                    child: Align(
                      alignment: Alignment.centerLeft,
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '讓投資研究',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: headlineSize,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            '更聰明・更安心・更愉快',
                            style: TextStyle(
                              color: const Color(0xFF8CF4FF),
                              fontSize: promiseSize,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          const SizedBox(height: 14),
                          Text(
                            '市場洞察  ·  風險控管  ·  策略研究  ·  長期累積',
                            style: TextStyle(
                              color: const Color(0xFFDCEBFF),
                              fontSize: detailSize,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
                Positioned(
                  right: horizontalPadding,
                  top: (300 - iconSize) / 2,
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(34),
                    child: Image.asset(
                      janusAppIconAsset,
                      width: iconSize,
                      height: iconSize,
                      fit: BoxFit.cover,
                      semanticLabel: 'Janus 雙生獸投資研究圖示',
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      );
    },
  );
}
