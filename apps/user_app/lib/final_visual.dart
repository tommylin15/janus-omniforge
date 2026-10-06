import 'dart:async';

import 'package:flutter/material.dart';
import 'package:google_sign_in/google_sign_in.dart';

import 'admin.dart';
import 'final_perf.dart';
import 'final_visual_pages.dart';
import 'main.dart' as legacy;
import 'sign_in_button.dart'
    if (dart.library.html) 'sign_in_button_web.dart'
    if (dart.library.js_util) 'sign_in_button_web.dart';

const _teal = Color(0xFF177F88);
const _ink = Color(0xFF16324A);
const _canvas = Color(0xFFF1F6F8);

void main() => runApp(const FinalJanusApp());

class FinalJanusApp extends StatefulWidget {
  const FinalJanusApp({super.key});

  @override
  State<FinalJanusApp> createState() => _FinalJanusAppState();
}

class _FinalJanusAppState extends State<FinalJanusApp> {
  ThemeMode mode = ThemeMode.system;

  ThemeData theme(Brightness brightness) {
    final scheme = ColorScheme.fromSeed(
      seedColor: _teal,
      brightness: brightness,
      surface: brightness == Brightness.light ? Colors.white : const Color(0xFF13242C),
    );
    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      colorScheme: scheme,
      scaffoldBackgroundColor:
          brightness == Brightness.light ? _canvas : const Color(0xFF0C171D),
      textTheme: ThemeData(brightness: brightness).textTheme.apply(
            bodyColor: brightness == Brightness.light ? _ink : null,
            displayColor: brightness == Brightness.light ? _ink : null,
          ),
      cardTheme: CardThemeData(
        color: brightness == Brightness.light ? Colors.white : scheme.surface,
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: brightness == Brightness.light
            ? const Color(0xFFF8FBFC)
            : scheme.surface,
        indicatorColor: brightness == Brightness.light
            ? const Color(0xFFD5ECEF)
            : scheme.primaryContainer,
        labelTextStyle: WidgetStateProperty.resolveWith((states) => TextStyle(
              color: states.contains(WidgetState.selected)
                  ? scheme.primary
                  : scheme.onSurfaceVariant,
              fontWeight: states.contains(WidgetState.selected)
                  ? FontWeight.w800
                  : FontWeight.w600,
              fontSize: 12,
            )),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'Janus',
        debugShowCheckedModeBanner: false,
        themeMode: mode,
        theme: theme(Brightness.light),
        darkTheme: theme(Brightness.dark),
        home: FinalLoginPage(
          admin: legacy.adminWorkspaceRequested(Uri.base),
          onTheme: (value) => setState(() => mode = value),
        ),
      );
}

class FinalLoginPage extends StatefulWidget {
  const FinalLoginPage({required this.onTheme, this.admin = false, super.key});
  final ValueChanged<ThemeMode> onTheme;
  final bool admin;

  @override
  State<FinalLoginPage> createState() => _FinalLoginPageState();
}

class _FinalLoginPageState extends State<FinalLoginPage> {
  static const userClient = String.fromEnvironment('GOOGLE_USER_CLIENT_ID');
  static const adminClient = String.fromEnvironment('GOOGLE_ADMIN_CLIENT_ID');
  late final GoogleSignIn google =
      GoogleSignIn(clientId: widget.admin ? adminClient : userClient);
  late final StreamSubscription<GoogleSignInAccount?> accountChanges;
  bool busy = false;
  bool finishing = false;
  String? error;

  @override
  void initState() {
    super.initState();
    accountChanges = google.onCurrentUserChanged.listen((account) {
      if (account != null) unawaited(finishLogin(account));
    }, onError: (_) {
      if (mounted) setState(() => error = '登入失敗，請再試一次');
    });
    unawaited(restoreLogin());
  }

  Future<void> restoreLogin() async {
    try {
      final account = await google.signInSilently(reAuthenticate: true);
      if (account != null) await finishLogin(account);
    } catch (_) {
      // No saved Google session; keep showing the sign-in button.
    }
  }

  @override
  void dispose() {
    unawaited(accountChanges.cancel());
    super.dispose();
  }

  Future<void> login() async {
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await google.signIn();
    } catch (_) {
      if (mounted) setState(() => error = '登入失敗，請再試一次');
    } finally {
      if (mounted && !finishing) setState(() => busy = false);
    }
  }

  Future<void> finishLogin(GoogleSignInAccount account) async {
    if (finishing) return;
    finishing = true;
    if (mounted) {
      setState(() {
        busy = true;
        error = null;
      });
    }
    try {
      final token = legacy.requireGoogleIdToken((await account.authentication).idToken);
      if (!mounted) return;
      final api = legacy.Api(token);
      await Navigator.of(context).pushReplacement(MaterialPageRoute(
        builder: (_) => widget.admin
            ? AdminWorkspace(api: api, email: account.email, onTheme: widget.onTheme)
            : FinalWorkspace(api: api, email: account.email, onTheme: widget.onTheme),
      ));
    } catch (_) {
      finishing = false;
      if (mounted) {
        setState(() {
          busy = false;
          error = '登入憑證無效，請重新登入';
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        body: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text('JANUS',
                      style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                            color: _ink,
                            fontWeight: FontWeight.w900,
                            letterSpacing: 2,
                          )),
                  const SizedBox(height: 8),
                  Text(widget.admin ? '資料營運中心' : '你的私人投資研究工作台',
                      style: Theme.of(context)
                          .textTheme
                          .bodyMedium
                          ?.copyWith(color: const Color(0xFF5D7180))),
                  const SizedBox(height: 22),
                  buildGoogleSignInButton(onPressed: login, busy: busy),
                  if (error != null) ...[
                    const SizedBox(height: 12),
                    Text(error!,
                        style: TextStyle(color: Theme.of(context).colorScheme.error)),
                  ],
                ],
              ),
            ),
          ),
        ),
      );
}

class FinalWorkspace extends StatefulWidget {
  const FinalWorkspace({
    required this.api,
    required this.email,
    required this.onTheme,
    super.key,
  });
  final legacy.Api api;
  final String email;
  final ValueChanged<ThemeMode> onTheme;

  @override
  State<FinalWorkspace> createState() => _FinalWorkspaceState();
}

class _FinalWorkspaceState extends State<FinalWorkspace> {
  int page = 0;
  final visited = <int>{0};

  void selectPage(int value) {
    final restoring = value != page && visited.contains(value);
    final stopwatch = restoring ? (Stopwatch()..start()) : null;
    setState(() {
      page = value;
      visited.add(value);
    });
    if (stopwatch != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        stopwatch.stop();
        FinalPerf.recordRestore(stopwatch.elapsed);
      });
    }
  }

  @override
  void didUpdateWidget(FinalWorkspace oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.api != widget.api) {
      page = 0;
      visited
        ..clear()
        ..add(0);
    }
  }

  void openStock(String symbol) => Navigator.of(context).push(MaterialPageRoute(
        builder: (_) => FinalStockDetailPage(api: widget.api, symbol: symbol),
      ));

  @override
  Widget build(BuildContext context) {
    final pages = <Widget>[
      FinalTodayPage(widget.api, active: page == 0, onOpenStock: openStock),
      FinalWatchlistPage(widget.api, active: page == 1, onOpenStock: openStock),
      FinalLedgerPage(widget.api, active: page == 2, onOpenStock: openStock),
      legacy.ProfilePage(api: widget.api, email: widget.email, onTheme: widget.onTheme),
    ];
    const destinations = [
      NavigationDestination(icon: Icon(Icons.today_outlined), selectedIcon: Icon(Icons.today), label: '今日'),
      NavigationDestination(icon: Icon(Icons.star_outline), selectedIcon: Icon(Icons.star), label: '關注'),
      NavigationDestination(icon: Icon(Icons.edit_note_outlined), selectedIcon: Icon(Icons.edit_note), label: '記帳／筆記'),
      NavigationDestination(icon: Icon(Icons.person_outline), selectedIcon: Icon(Icons.person), label: '我的'),
    ];
    return LayoutBuilder(builder: (context, constraints) {
      final wide = constraints.maxWidth >= 900;
      return Scaffold(
        body: Stack(
          children: [
            Row(children: [
          if (wide)
            NavigationRail(
              selectedIndex: page,
              labelType: NavigationRailLabelType.all,
              onDestinationSelected: selectPage,
              destinations: const [
                NavigationRailDestination(icon: Icon(Icons.today_outlined), selectedIcon: Icon(Icons.today), label: Text('今日')),
                NavigationRailDestination(icon: Icon(Icons.star_outline), selectedIcon: Icon(Icons.star), label: Text('關注')),
                NavigationRailDestination(icon: Icon(Icons.edit_note_outlined), selectedIcon: Icon(Icons.edit_note), label: Text('記帳／筆記')),
                NavigationRailDestination(icon: Icon(Icons.person_outline), selectedIcon: Icon(Icons.person), label: Text('我的')),
              ],
            ),
          Expanded(
            child: IndexedStack(
              index: page,
              children: [
                for (var index = 0; index < pages.length; index++)
                  KeyedSubtree(
                    key: ValueKey('${identityHashCode(widget.api)}:$index'),
                    child: visited.contains(index) ? pages[index] : const SizedBox.shrink(),
                  ),
              ],
            ),
          ),
        ]),
            if (FinalPerf.enabled)
              const Positioned(
                right: 8,
                top: 8,
                child: IgnorePointer(child: FinalPerfBadge()),
              ),
          ],
        ),
        bottomNavigationBar: wide
            ? null
            : NavigationBar(
                height: 72,
                selectedIndex: page,
                onDestinationSelected: selectPage,
                destinations: destinations,
              ),
      );
    });
  }
}
