import 'package:flutter/material.dart';

const janusAppIconAsset = 'assets/branding/janus_app_icon_512.webp';

Widget buildLoginBranding(BuildContext context) {
  if (Uri.base.pathSegments.contains('admin')) {
    return const SizedBox.shrink();
  }

  final viewportWidth = MediaQuery.sizeOf(context).width;
  final compact = viewportWidth < 600;

  if (compact) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(32),
            child: Image.asset(
              janusAppIconAsset,
              width: 220,
              height: 220,
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

  final width = (viewportWidth - 96).clamp(680.0, 960.0).toDouble();
  return Padding(
    padding: const EdgeInsets.only(bottom: 24),
    child: SizedBox(
      height: 320,
      child: OverflowBox(
        alignment: Alignment.center,
        minWidth: 0,
        maxWidth: double.infinity,
        child: Container(
          width: width,
          height: 300,
          padding: const EdgeInsets.fromLTRB(42, 34, 34, 34),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(32),
            gradient: const LinearGradient(
              colors: [Color(0xFF061D55), Color(0xFF0B4FD6), Color(0xFF12C9F5)],
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
          child: Row(
            children: [
              const Expanded(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '讓投資研究',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 28,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    SizedBox(height: 8),
                    Text(
                      '更聰明・更安心・更愉快',
                      style: TextStyle(
                        color: Color(0xFF8CF4FF),
                        fontSize: 30,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    SizedBox(height: 14),
                    Text(
                      '市場洞察  ·  風險控管  ·  策略研究  ·  長期累積',
                      style: TextStyle(
                        color: Color(0xFFDCEBFF),
                        fontSize: 15,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 28),
              ClipRRect(
                borderRadius: BorderRadius.circular(34),
                child: Image.asset(
                  janusAppIconAsset,
                  width: 235,
                  height: 235,
                  fit: BoxFit.cover,
                  semanticLabel: 'Janus 雙生獸投資研究圖示',
                ),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}
