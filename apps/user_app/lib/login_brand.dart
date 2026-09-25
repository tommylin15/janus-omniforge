import 'package:flutter/material.dart';

const janusHeroAsset = 'assets/branding/janus_ui_hero_1200.webp';
const janusAppIconAsset = 'assets/branding/janus_app_icon_512.png';

Widget buildLoginBranding(BuildContext context) {
  if (Uri.base.pathSegments.contains('admin')) {
    return const SizedBox.shrink();
  }

  final viewportWidth = MediaQuery.sizeOf(context).width;
  final compact = viewportWidth < 600;
  final width = (viewportWidth - (compact ? 48.0 : 96.0)).clamp(240.0, 1120.0);

  return Padding(
    padding: const EdgeInsets.only(bottom: 24),
    child: SizedBox(
      height: compact ? 260 : 360,
      child: OverflowBox(
        alignment: Alignment.center,
        minWidth: 0,
        maxWidth: double.infinity,
        child: ClipRRect(
          borderRadius: BorderRadius.circular(compact ? 28 : 32),
          child: Image.asset(
            compact ? janusAppIconAsset : janusHeroAsset,
            width: compact ? 240 : width,
            height: compact ? 240 : 360,
            fit: BoxFit.cover,
            semanticLabel: compact
                ? 'Janus 雙生獸投資研究圖示'
                : 'Janus 投資研究入口主視覺',
          ),
        ),
      ),
    ),
  );
}
