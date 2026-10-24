"""Compare 4 vs 5 factors on exactly the same five-factor complete 2024-26 rows."""
from pathlib import Path
import argparse,json
import pandas as pd
from valuation_research_train import FOUR,FIVE,group_model,sha

def run(v26output,ablationoutput):
 v26output=Path(v26output);ablationoutput=Path(ablationoutput);ablationoutput.mkdir(parents=True,exist_ok=True)
 pane=pd.read_csv(v26output/'study_XY_panel.csv.gz',dtype={'symbol':str},parse_dates=['trade_date']);pane=pane.dropna(subset=FIVE)
 splits={'fold_2025h2':(('2024-07','2025-06'),('2025-07','2025-09'),('2025-10','2025-12')),
              'fold_2026':(('2024-07','2025-09'),('2025-10','2025-12'),('2026-01','2026-09'))}
 ref=json.loads((v26output/'report.json').read_text())
 result={'state':'FAIR_SAME_ROWS_ABLATION','publication_allowed':False,'features_four':FOUR,'features_five':FIVE,'rows_five_complete':len(pane),'folds':{}}
 for fold,(train,val,test) in splits.items():
  d=lambda a,b:pane[(pane.month>=a)&(pane.month<=b)]
  tr,va,te=d(*train),d(*val),d(*test)
  result['folds'][fold]={}
  for branch in ('pe','pb'):
   four,_=group_model(tr,va,te,FOUR,branch,ablationoutput,fold)
   five=ref['folds'][fold][branch]
   if four.get('status')!='RESEARCH_NON_PIT_FITTED' or five.get('status')!='RESEARCH_NON_PIT_FITTED':
    raise ValueError('EXPECTED_FITTED_FOR_COMPARISON')
   if four['split']!=five['split']:raise ValueError('ABLATED_ROW_SET_MISMATCH')
   entry={'four':{k:v['test']['log_mae'] for k,v in four['metrics'].items()},'five':{k:v['test']['log_mae'] for k,v in five['metrics'].items()},
          'delta_xgb_test_mae_five_minus_four':five['metrics']['xgboost']['test']['log_mae']-four['metrics']['xgboost']['test']['log_mae'],
          'four_validation_xgb_mae':four['metrics']['xgboost']['validation']['log_mae'],
          'five_validation_xgb_mae':five['metrics']['xgboost']['validation']['log_mae'],
          'test_months':five['split']['test']['months'],'test_rows':five['split']['test']['rows']}
   result['folds'][fold][branch]=entry
 (ablationoutput/'report.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf8')
 (ablationoutput/'artifact_manifest.json').write_text(json.dumps({'publication_allowed':False,'sha256':{str(p.relative_to(ablationoutput)):sha(p) for p in ablationoutput.rglob('*') if p.is_file() and p.name!='artifact_manifest.json'}},indent=2),encoding='utf8')
 return result
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--v26',type=Path,required=True);a.add_argument('--out',type=Path,required=True);p=a.parse_args();x=run(p.v26,p.out);print(json.dumps(x['folds'],indent=2))
