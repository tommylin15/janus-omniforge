import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:http/http.dart' as http;

void main() => runApp(const JanusApp());

class JanusApp extends StatefulWidget {
  const JanusApp({super.key});
  @override State<JanusApp> createState() => _JanusAppState();
}

class _JanusAppState extends State<JanusApp> {
  ThemeMode mode = ThemeMode.system;
  @override Widget build(BuildContext context) => MaterialApp(
    title: 'Janus', themeMode: mode, theme: ThemeData(colorSchemeSeed: Colors.cyan, useMaterial3: true),
    darkTheme: ThemeData(colorSchemeSeed: Colors.cyan, brightness: Brightness.dark, useMaterial3: true),
    home: LoginPage(onTheme: (value) => setState(() => mode = value)),
  );
}

class Api {
  Api(this.token);
  final String token;
  static const base = String.fromEnvironment('JANUS_API_BASE_URL');
  Map<String,String> get headers => {'Authorization':'Bearer $token','Content-Type':'application/json'};
  Future<dynamic> get(String path) => _send('GET',path);
  Future<dynamic> post(String path,Map<String,dynamic> body) => _send('POST',path,body);
  Future<dynamic> put(String path,Map<String,dynamic> body) => _send('PUT',path,body);
  Future<dynamic> delete(String path) => _send('DELETE',path);
  Future<dynamic> _send(String method,String path,[Map<String,dynamic>? body]) async {
    final request=http.Request(method,Uri.parse('$base$path'))..headers.addAll(headers);
    if(method!='GET') request.headers['Idempotency-Key']=DateTime.now().microsecondsSinceEpoch.toString();
    if(body!=null) request.body=jsonEncode(body);
    final response=await http.Response.fromStream(await request.send());
    if(response.statusCode<200||response.statusCode>=300) throw Exception(jsonDecode(response.body)['detail']??'服務暫時無法使用');
    return response.body.isEmpty?null:jsonDecode(response.body);
  }
}

class LoginPage extends StatefulWidget {
  const LoginPage({required this.onTheme,super.key});
  final ValueChanged<ThemeMode> onTheme;
  @override State<LoginPage> createState()=>_LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  bool busy=false; String? error;
  Future<void> login() async {
    setState(() {busy=true;error=null;});
    try {
      const client=String.fromEnvironment('GOOGLE_USER_CLIENT_ID');
      final account=await GoogleSignIn(clientId:client,serverClientId:client).signIn();
      final token=(await account?.authentication)?.idToken;
      if(account==null||token==null) return;
      if(mounted) Navigator.of(context).pushReplacement(MaterialPageRoute(builder:(_)=>Workspace(api:Api(token),email:account.email,onTheme:widget.onTheme)));
    } catch (_) { if(mounted) setState(()=>error='登入失敗，請再試一次'); }
    finally { if(mounted) setState(()=>busy=false); }
  }
  @override Widget build(BuildContext context)=>Scaffold(body:Center(child:ConstrainedBox(constraints:const BoxConstraints(maxWidth:360),child:Padding(
    padding:const EdgeInsets.all(24),child:Column(mainAxisSize:MainAxisSize.min,children:[Text('JANUS',style:Theme.of(context).textTheme.headlineLarge),
      const SizedBox(height:12),const Text('你的私人投資工作台'),const SizedBox(height:24),FilledButton.icon(onPressed:busy?null:login,
      icon:busy?const SizedBox.square(dimension:18,child:CircularProgressIndicator(strokeWidth:2)):const Icon(Icons.login),label:const Text('使用 Google 登入')),
      if(error!=null) Padding(padding:const EdgeInsets.only(top:12),child:Text(error!,style:TextStyle(color:Theme.of(context).colorScheme.error)))],),))));
}

class Workspace extends StatefulWidget {
  const Workspace({required this.api,required this.email,required this.onTheme,super.key});
  final Api api; final String email; final ValueChanged<ThemeMode> onTheme;
  @override State<Workspace> createState()=>_WorkspaceState();
}

class _WorkspaceState extends State<Workspace> {
  int page=0;
  @override Widget build(BuildContext context) {
    final pages=[WatchlistPage(widget.api),JournalNotesPage(widget.api),ProfilePage(api:widget.api,email:widget.email,onTheme:widget.onTheme)];
    return Scaffold(appBar:AppBar(title:const Text('Janus')),body:pages[page],bottomNavigationBar:NavigationBar(selectedIndex:page,
      onDestinationSelected:(value)=>setState(()=>page=value),destinations:const [NavigationDestination(icon:Icon(Icons.star_outline),label:'關注'),
      NavigationDestination(icon:Icon(Icons.edit_note),label:'記帳／筆記'),NavigationDestination(icon:Icon(Icons.person_outline),label:'我的')]));
  }
}

class WatchlistPage extends StatefulWidget { const WatchlistPage(this.api,{super.key}); final Api api; @override State<WatchlistPage> createState()=>_WatchlistPageState(); }
class _WatchlistPageState extends State<WatchlistPage> {
  late Future<dynamic> items=widget.api.get('/api/v1/me/watchlist');
  void reload()=>setState(()=>items=widget.api.get('/api/v1/me/watchlist'));
  Future<void> add() async { final symbol=await textDialog(context,'加入關注','股票代號'); if(symbol==null)return;
    if(!mounted)return;
    final target=await textDialog(context,'設定目標價','可留空');
    await widget.api.post('/api/v1/me/watchlist',{'symbol':symbol.toUpperCase(),if(target?.isNotEmpty==true)'target_price':target}); reload(); }
  @override Widget build(BuildContext context)=>Scaffold(floatingActionButton:FloatingActionButton(onPressed:add,child:const Icon(Icons.add)),body:FutureBuilder(
    future:items,builder:(context,snapshot){if(snapshot.connectionState!=ConnectionState.done)return const Center(child:CircularProgressIndicator());
      if(snapshot.hasError)return ErrorView(snapshot.error.toString(),reload); final rows=(snapshot.data as List? ?? []);
      if(rows.isEmpty)return const Center(child:Text('尚未關注股票'));
      return ReorderableListView(children:[for(final row in rows)ListTile(key:ValueKey(row['symbol']),title:Text(row['symbol']),
        subtitle:Text(row['target_price']==null?'尚未設定目標價':'目標價 ${row['target_price']}'),trailing:IconButton(icon:const Icon(Icons.delete_outline),
        onPressed:()async{await widget.api.delete('/api/v1/me/watchlist/${row['symbol']}');reload();}))],onReorderItem:(oldIndex,newIndex)async{
          final reordered=List<dynamic>.from(rows);final moved=reordered.removeAt(oldIndex);reordered.insert(newIndex,moved);
          final version=rows.fold<int>(0,(best,row)=>row['version']>best?row['version']:best);
          await widget.api.put('/api/v1/me/watchlist/order',{'symbols':[for(final row in reordered)row['symbol']],'expected_version':version});reload();}); }));
}

class JournalNotesPage extends StatefulWidget { const JournalNotesPage(this.api,{super.key}); final Api api; @override State<JournalNotesPage> createState()=>_JournalNotesPageState(); }
class _JournalNotesPageState extends State<JournalNotesPage> {
  int segment=0; late Future<dynamic> rows=load();
  Future<dynamic> load()=>widget.api.get(segment==0?'/api/v1/me/journal/history':'/api/v1/me/notes');
  void reload()=>setState(()=>rows=load());
  Future<void> add() async {
    if(segment==1){final body=await textDialog(context,'新增筆記','筆記內容');if(body!=null){await widget.api.post('/api/v1/me/notes',{'body':body});reload();}return;}
    final payload=await transactionDialog(context);if(payload!=null){await widget.api.post('/api/v1/me/journal/events',payload);reload();}
  }
  @override Widget build(BuildContext context)=>Scaffold(floatingActionButton:FloatingActionButton(onPressed:add,child:const Icon(Icons.add)),body:Column(children:[
    SummaryCards(widget.api),
    Padding(padding:const EdgeInsets.all(12),child:SegmentedButton<int>(segments:const [ButtonSegment(value:0,label:Text('記帳')),ButtonSegment(value:1,label:Text('筆記'))],
      selected:{segment},onSelectionChanged:(value)=>setState((){segment=value.first;rows=load();}))),Expanded(child:FutureBuilder(future:rows,builder:(context,snapshot){
      if(snapshot.connectionState!=ConnectionState.done)return const Center(child:CircularProgressIndicator());if(snapshot.hasError)return ErrorView(snapshot.error.toString(),reload);
      final values=(snapshot.data as List? ?? []);if(values.isEmpty)return Center(child:Text(segment==0?'尚無交易':'尚無筆記'));
      return ListView.builder(itemCount:values.length,itemBuilder:(context,index){final row=values[index];return ListTile(title:Text(segment==0?'${row['event_type']} ${row['symbol']}':row['body']??''),
        subtitle:Text(segment==0?'${row['trade_date']} · ${row['shares']??row['cash_amount']??''}':'${row['symbol']??'一般筆記'} · revision ${row['revision']}'),
        trailing:TextButton(onPressed:()async{if(segment==0){final replacement=await transactionDialog(context);if(replacement!=null){await widget.api.post('/api/v1/me/journal/events/${row['event_id']}/corrections',
          {'expected_version':row['record_version'],'replacement':replacement});reload();}}else{final body=await textDialog(context,'修改筆記','筆記內容',initial:row['body']??'');if(body!=null){await widget.api.put('/api/v1/me/notes/${row['note_id']}',
          {'body':body,'symbol':row['symbol'],'trade_event_id':row['trade_event_id'],'needs_follow_up':row['needs_follow_up'],'expected_version':row['revision']});reload();}}},child:Text(segment==0?'建立更正':'修改')));});}))]));
}

class SummaryCards extends StatelessWidget { const SummaryCards(this.api,{super.key});final Api api;
  @override Widget build(BuildContext context)=>FutureBuilder<List<dynamic>>(future:Future.wait([api.get('/api/v1/me/journal/positions'),
    api.get('/api/v1/me/journal/pnl?year=${DateTime.now().year}'),api.get('/api/v1/me/notes')]),builder:(context,snapshot){
      if(!snapshot.hasData)return const SizedBox(height:88,child:Center(child:CircularProgressIndicator()));final data=snapshot.data!;
      final pnl=data[1] as List;final pnlText=pnl.isEmpty?'—':pnl.length==1?'${pnl.first['currency']} ${pnl.first['realized_pnl']}':'多幣別';
      final pending=(data[2] as List).where((row)=>row['needs_follow_up']==true).length;
      return SizedBox(height:88,child:ListView(scrollDirection:Axis.horizontal,padding:const EdgeInsets.all(8),children:[
        summary('目前持股','${(data[0] as List).length} 檔'),summary('本年已實現損益',pnlText),summary('待完成筆記','$pending 則')]));});
  Widget summary(String title,String value)=>Card(child:Padding(padding:const EdgeInsets.all(12),child:Column(children:[Text(title),Text(value)])));
}

class ProfilePage extends StatelessWidget { const ProfilePage({required this.api,required this.email,required this.onTheme,super.key}); final Api api;final String email; final ValueChanged<ThemeMode> onTheme;
  @override Widget build(BuildContext context)=>ListView(padding:const EdgeInsets.all(16),children:[ListTile(leading:const Icon(Icons.account_circle),title:Text(email),subtitle:const Text('Google 帳號')),
    const Divider(),const ListTile(title:Text('外觀')),DropdownButtonFormField<ThemeMode>(initialValue:ThemeMode.system,items:const [DropdownMenuItem(value:ThemeMode.system,child:Text('跟隨系統')),
      DropdownMenuItem(value:ThemeMode.light,child:Text('淺色')),DropdownMenuItem(value:ThemeMode.dark,child:Text('深色'))],onChanged:(value){if(value!=null)onTheme(value);}),
    const Divider(),ListTile(leading:const Icon(Icons.download_outlined),title:const Text('匯出我的私人資料'),onTap:()=>api.get('/api/v1/me/export')),
    ListTile(leading:Icon(Icons.warning_amber,color:Theme.of(context).colorScheme.error),title:const Text('永久刪除私人資料'),subtitle:const Text('涵蓋交易、筆記、關注股與衍生資料'),
      onTap:()async{final answer=await textDialog(context,'永久刪除私人資料','輸入 DELETE 確認');if(answer=='DELETE'&&context.mounted){
        const client=String.fromEnvironment('GOOGLE_USER_CLIENT_ID');final google=GoogleSignIn(clientId:client,serverClientId:client);await google.signOut();final account=await google.signIn();
        final token=(await account?.authentication)?.idToken;if(token!=null)await Api(token).delete('/api/v1/me/private-data');
        if(context.mounted)ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content:Text('刪除要求已排入處理')));}})]); }

class ErrorView extends StatelessWidget { const ErrorView(this.message,this.retry,{super.key});final String message;final VoidCallback retry;
  @override Widget build(BuildContext context)=>Center(child:Column(mainAxisSize:MainAxisSize.min,children:[const Text('服務暫時發生問題'),const SizedBox(height:8),OutlinedButton(onPressed:retry,child:const Text('重試'))]));}

Future<String?> textDialog(BuildContext context,String title,String label,{String initial=''}){final controller=TextEditingController(text:initial);return showDialog<String>(context:context,builder:(context)=>AlertDialog(
  title:Text(title),content:TextField(controller:controller,autofocus:true,decoration:InputDecoration(labelText:label)),actions:[TextButton(onPressed:()=>Navigator.pop(context),child:const Text('取消')),
  FilledButton(onPressed:()=>Navigator.pop(context,controller.text.trim()),child:const Text('儲存'))]));}

Future<Map<String,dynamic>?> transactionDialog(BuildContext context) async {
  final type=await showDialog<String>(context:context,builder:(context)=>SimpleDialog(title:const Text('交易類型'),children:[for(final item in const {
    'BUY':'買進','SELL':'賣出','CASH_DIV':'現金股利','STOCK_DIV':'股票股利'}.entries)SimpleDialogOption(onPressed:()=>Navigator.pop(context,item.key),child:Text(item.value))]));
  if(type==null||!context.mounted)return null;
  final day=await showDatePicker(context:context,firstDate:DateTime(2000),lastDate:DateTime.now(),initialDate:DateTime.now());
  if(day==null||!context.mounted)return null;
  final symbol=await textDialog(context,'交易內容','股票代號');if(symbol==null||!context.mounted)return null;
  final payload=<String,dynamic>{'event_type':type,'trade_date':day.toIso8601String().substring(0,10),'symbol':symbol.toUpperCase(),'currency':'TWD'};
  if(type=='CASH_DIV'){final amount=await textDialog(context,'交易內容','股利金額');if(amount==null)return null;payload['cash_amount']=amount;}
  else {final shares=await textDialog(context,'交易內容','股數');if(shares==null)return null;payload['shares']=shares;
    if((type=='BUY'||type=='SELL')&&context.mounted){final price=await textDialog(context,'交易內容','成交單價');if(price==null)return null;payload['price']=price;}}
  return payload;
}
