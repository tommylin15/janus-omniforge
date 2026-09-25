import 'package:flutter/material.dart';
import 'package:google_sign_in_web/web_only.dart' as web;

import 'login_brand.dart';

Widget buildGoogleSignInButton({
  required VoidCallback onPressed,
  required bool busy,
}) =>
    Builder(
      builder: (context) => Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          buildLoginBranding(context),
          Semantics(
            button: true,
            label: '使用 Google 登入',
            child: web.renderButton(),
          ),
        ],
      ),
    );
