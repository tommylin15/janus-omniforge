import 'package:flutter/widgets.dart';
import 'package:google_sign_in_web/web_only.dart' as web;

Widget buildGoogleSignInButton({
  required VoidCallback onPressed,
  required bool busy,
}) =>
    Semantics(
        button: true,
        label: '使用 Google 登入',
        child: web.renderButton());
