import 'package:flutter/material.dart';
import 'package:google_sign_in_web/web_only.dart' as web;

const _janusTwinBeastWebImage = '/app/og-image.jpg';

Widget buildGoogleSignInButton({
  required VoidCallback onPressed,
  required bool busy,
}) =>
    Builder(
      builder: (context) => Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            key: const Key('janus-twin-beast-brand'),
            margin: const EdgeInsets.only(bottom: 20),
            padding: const EdgeInsets.fromLTRB(20, 20, 20, 18),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(28),
              gradient: const LinearGradient(
                colors: [Color(0xFF061D55), Color(0xFF0B4FD6), Color(0xFF12C9F5)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              boxShadow: const [
                BoxShadow(
                  color: Color(0x33064FB8),
                  blurRadius: 24,
                  offset: Offset(0, 12),
                ),
              ],
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                ClipRRect(
                  borderRadius: BorderRadius.circular(28),
                  child: Image.network(
                    _janusTwinBeastWebImage,
                    width: 220,
                    height: 220,
                    fit: BoxFit.cover,
                    alignment: Alignment.centerRight,
                    semanticLabel: 'Janus 雙生獸投資研究圖示',
                    errorBuilder: (context, error, stackTrace) => Container(
                      width: 220,
                      height: 220,
                      alignment: Alignment.center,
                      decoration: BoxDecoration(
                        color: const Color(0x2200E5FF),
                        borderRadius: BorderRadius.circular(28),
                      ),
                      child: const Icon(
                        Icons.auto_awesome,
                        size: 64,
                        color: Color(0xFF8CF4FF),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 14),
                const Text(
                  'Janus · OmniForge',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 21,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 6),
                const Text(
                  '更聰明・更安心・更愉快',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: Color(0xFF8CF4FF),
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 4),
                const Text(
                  '多源資料 × AI 多分析師 × 個人化洞察',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: Color(0xFFDCEBFF),
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
          Semantics(
            button: true,
            label: '使用 Google 登入',
            child: web.renderButton(),
          ),
        ],
      ),
    );
