import 'package:flutter/material.dart';

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
          FilledButton.icon(
            onPressed: busy ? null : onPressed,
            icon: busy
                ? const SizedBox.square(
                    dimension: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.login),
            label: const Text('使用 Google 登入'),
          ),
        ],
      ),
    );
