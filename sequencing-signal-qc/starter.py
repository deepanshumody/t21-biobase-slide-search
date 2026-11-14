"""CPU teaching baselines. Reads only a route's participant files. No network calls."""
import argparse, collections, datetime as dt, json, math, pathlib, re, statistics
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from data_io import load_data,text_for
LEVELS=[.01,.025,.05,.1,.15,.2,.25,.3,.35,.4,.45,.5,.55,.6,.65,.7,.75,.8,.85,.9,.95,.975,.99]
def tokens(s):return set(re.findall(r'\w+',s.lower()))-{'vehicle','ingredient'}
def quantile(v,q):
    v=sorted(v);return v[min(len(v)-1,max(0,math.ceil(q*len(v))-1))]
def forecast_quantile(values,q):
    values=sorted(values);position=(len(values)-1)*q;lo=math.floor(position);hi=math.ceil(position);return values[lo]+(position-lo)*(values[hi]-values[lo])

def run(route,data,model='baseline'):
    if any('target' in r or 'gold_spans' in r or 'label' in r for r in data['cases']):raise ValueError('Outcome fields forbidden in final cases')
    train=data.get('train',[]);validation=data.get('validation',[]);cases=data['cases'];result=[]
    kind=route.split('-')[0]
    allowed={'01':{'baseline','seasonal','fallback'},'02':{'baseline','fallback'},'03':{'baseline','abundance','fallback'},'04':{'baseline','fallback'},'05':{'baseline','ridge','fallback'},'06':{'baseline','logistic','fallback'},'07':{'baseline','ridge','domain','fallback'},'08':{'baseline','ridge','fallback'},'09':{'baseline','logistic','fallback'},'10':{'baseline','ridge','fallback'},'11':{'baseline','fallback'},'12':{'baseline','fallback'}}
    if kind not in allowed or model not in allowed[kind]:raise ValueError('Unsupported route/model combination')
    forbidden={'target','gold_spans','label','counter_efficacy','counter_pass','reliability_group','BD_mean(gcm-1)'}
    for c in cases:
        if forbidden & set(c):raise ValueError('Forbidden outcome/stage fields in final input')
        if kind=='02' and not (c['vehicle'].strip() or c['ingredient'].strip()):raise ValueError('Food description missing')
        if kind=='01':
            issue=dt.date.fromisoformat(c['issue']);reference=issue+dt.timedelta(days=3);dates=[x['date'] for x in c['history']]
            if len(dates)<2 or dates!=sorted(set(dates)) or max(dates)>str(issue-dt.timedelta(days=4)) or c['horizon'] not in [0,1,2] or c['reference_date']!=str(reference) or c['target_end_date']!=str(reference+dt.timedelta(days=7*c['horizon'])):raise ValueError('Invalid forecast availability/date boundary')
        if kind=='03':
            if not all(isinstance(c[x],(int,float)) and not isinstance(c[x],bool) and math.isfinite(c[x]) and c[x]>=0 for x in ['sample_mass','control_mass']):raise ValueError('Invalid signal mass')
            if c['control_count']!=len(c['control_signals']) or c['sample_count']!=len(c['sample_signals']):raise ValueError('Control/sample membership mismatch')

        if kind=='04' and (not text_for(data,c).strip() or any(not c[x].strip() for x in ['intervention','comparator','outcome'])):raise ValueError('Missing comparison or article')
        if kind in ['05','06','08']:
            n={'05':8,'06':8,'08':3}[kind]
            if len(c['features'])!=n or not all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in c['features']):raise ValueError('Invalid numeric feature contract')
        if kind=='06' and (c['primary_activity']<50 or c['features'][0]!=c['primary_activity']):raise ValueError('Ineligible primary hit')
        if kind=='08' and (not 0<=c['sensor_mean']<=1 or c['sensor_count'] not in [1,2,3] or c['features']!=[c['sensor_mean'],c['sensor_sd'],float(c['sensor_count'])]):raise ValueError('Invalid sensor count')
        if kind=='09' and c['last_input_date']>str(dt.date.fromisoformat(c['date'])-dt.timedelta(days=3)):raise ValueError('Future station input')
        if kind=='10' and (len(c['sequence'])!=len(data['reference']) or not set(c['sequence'])<=set('ACDEFGHIKLMNPQRSTVWY')):raise ValueError('Invalid aligned protein sequence')
    if kind=='04':
        from trial_model import predict
        rows,hyper=predict(data,fallback=model=='fallback')
        return {'packet_version':'0.5.0-internal','route':route,'model':model,'provenance':{'training':'bundled train only, hyperparameters selected on validation','external_models':[],'hyperparameters':hyper,'pre_event_work':'disclose reused work'},'rows':rows}
    ridge_predictions=None
    if model=='domain':
        if kind!='07':raise ValueError('domain model supports wheat only')
        from wheat_model import predict_domain
        ridge_predictions,domain_lower,domain_upper,domain_hyper=predict_domain(data);residual_low=residual_high=0
    elif model=='ridge':
        if kind not in ['05','07','08','10']:raise ValueError('ridge supported only for numeric/sequence routes')
        import numpy as np
        from sklearn.linear_model import Ridge
        from sklearn.preprocessing import OneHotEncoder,StandardScaler
        from threadpoolctl import threadpool_limits
        threadpool_limits(2)
        if kind=='10':
            encoder=OneHotEncoder(handle_unknown='ignore');X=encoder.fit_transform([list(r['sequence']) for r in train]);V=encoder.transform([list(r['sequence']) for r in validation]);T=encoder.transform([list(r['sequence']) for r in cases])
        else:
            features=lambda row:row['features'][:1024] if kind=='07' else row['features']
            encoder=StandardScaler();X=encoder.fit_transform([features(r) for r in train]);V=encoder.transform([features(r) for r in validation]);T=encoder.transform([features(r) for r in cases])
        y=np.array([r['target'] for r in train]);vy=np.array([r['target'] for r in validation]);grid=[]
        for alpha in ([10,100,1000,10000] if kind=='07' else [0.1,1,10,100]):
            estimator=Ridge(alpha=alpha,solver='auto' if kind=='07' else 'lsqr').fit(X,y);pv=estimator.predict(V)
            if kind=='07':pv=np.maximum(0,pv)
            if kind=='10':
                cut=sorted(pv,reverse=True)[min(50,len(pv))-1];above=pv>cut;at=pv==cut;k=min(50,len(pv));metric=-(vy[above].sum()+(k-above.sum())*vy[at].mean())/k
            elif kind=='07':
                groups=collections.defaultdict(list)
                for validation_row,observed,estimate in zip(validation,vy,pv):groups[validation_row['domain']].append(abs(observed-max(0,estimate)))
                metric=statistics.mean(statistics.mean(v) for v in groups.values())
            else:metric=float(np.mean(abs(vy-pv)))
            grid.append((metric,alpha,estimator,pv))
        _,alpha,estimator,pv=min(grid,key=lambda z:(z[0],z[1]));ridge_predictions=list(estimator.predict(T));width=quantile(list(abs(vy-pv)),.9)
        if kind=='07':
            from wheat_calibration import calibrate
            radius,calibration=calibrate(list(vy),list(pv),[r['domain'] for r in validation]);residual_low,residual_high=-radius,radius
    elif kind in ['05','06','07','08','10']:
        ys=[r['target'] for r in train];center=statistics.mean(ys);width=quantile([abs(r['target']-center) for r in validation],.9) if validation else 0
        if kind=='08':
            xs=[r['sensor_mean'] for r in train];xm=statistics.mean(xs);den=sum((x-xm)**2 for x in xs);slope=sum((x-xm)*(y-center) for x,y in zip(xs,ys))/den if den else 0;intercept=center-slope*xm
            width=quantile([abs(r['target']-(intercept+slope*r['sensor_mean'])) for r in validation],.9)
        if kind=='10':
            reference=''.join(collections.Counter(r['sequence'][i] for r in train).most_common(1)[0][0] for i in range(len(train[0]['sequence'])))
            effects=collections.defaultdict(list)
            for r in train:
                for i,(a,b) in enumerate(zip(r['sequence'],reference)):
                    if a!=b:effects[i,a].append(r['target'])
            def additive(r,shrink):return sum((statistics.mean(effects[i,a])-center)*len(effects[i,a])/(len(effects[i,a])+shrink) for i,(a,b) in enumerate(zip(r['sequence'],reference)) if a!=b and effects[i,a])
            def val_score(s):
                pairs=[(additive(r,s),r['target']) for r in validation];k=min(50,len(pairs));cut=sorted([p for p,y in pairs],reverse=True)[k-1];above=[y for p,y in pairs if p>cut];tie=[y for p,y in pairs if p==cut];return (sum(above)+(k-len(above))*statistics.mean(tie))/k
            shrink=max([5,20,50],key=val_score)
    if model=='logistic':
        if kind not in ['06','09']:raise ValueError('logistic supports counterscreen and freeze only')
        import numpy as np
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        from threadpoolctl import threadpool_limits
        threadpool_limits(2)
        scaler=StandardScaler();X=scaler.fit_transform([r['features'] for r in train]);V=scaler.transform([r['features'] for r in validation]);T=scaler.transform([r['features'] for r in cases]);y=np.array([r['target'] for r in train]);vy=np.array([r['target'] for r in validation]);options=[]
        if kind=='09':
            from sklearn.preprocessing import OneHotEncoder
            from scipy.sparse import hstack
            encoder=OneHotEncoder(handle_unknown='ignore');X=hstack([X,encoder.fit_transform([[r['station']] for r in train])]).tocsr();V=hstack([V,encoder.transform([[r['station']] for r in validation])]).tocsr();T=hstack([T,encoder.transform([[r['station']] for r in cases])]).tocsr()
        for c in [.01,.1,1,10]:
            estimator=LogisticRegression(C=c,max_iter=1000,random_state=0).fit(X,y);pv=estimator.predict_proba(V)[:,1];metric=float(np.mean((vy-pv)**2));options.append((metric,c,estimator))
        _,selected_c,estimator=min(options,key=lambda x:(x[0],x[1]));prob_predictions=list(estimator.predict_proba(T)[:,1])
    else:prob_predictions=None
    if kind=='02':
        classes=data['classes'];prior=collections.Counter(r['target'] for r in train);den=sum(prior.values())+len(classes);train_tokens=[tokens(r['text']) for r in train]
    if kind=='09':
        station_targets=collections.defaultdict(list)
        for row in train:station_targets[row['station']].append(row['target'])
        station_rates={st:statistics.mean(ys) for st,ys in station_targets.items()};global_rate=statistics.mean(r['target'] for r in train)
    if kind=='07':feature_center=[statistics.mean(col) for col in zip(*(r['features'][:1024] for r in train))]
    for index,r in enumerate(cases):
        row={'id':r['id']}
        if kind=='01':
            vals=r['history'];observations={dt.date.fromisoformat(v['date']):v['value'] for v in vals};lag=dt.timedelta(weeks=r['horizon']+1);res=[math.log1p(y)-math.log1p(observations[d-lag]) for d,y in observations.items() if d-lag in observations];last=vals[-1]['value'];
            if model=='seasonal' or r['stale']:
                prior=dt.date.fromisoformat(r['target_end_date'])-dt.timedelta(days=364);last=observations[prior];res=[math.log1p(y)-math.log1p(observations[d-dt.timedelta(days=364)]) for d,y in observations.items() if d-dt.timedelta(days=364) in observations]
            row.update(quantiles=[max(0,math.expm1(math.log1p(last)+forecast_quantile(res,q)-statistics.median(res))) for q in LEVELS],reference_date=r['reference_date'],horizon=r['horizon'],target_end_date=r['target_end_date'],last_input_date=vals[-1]['date'],status='stale' if r.get('stale') else 'ok')
        elif kind=='02':
            # Training-only nearest description; mix with a smoothed prior to avoid zero-probability classes.
            query=tokens(r['text']);best,nearest=max(zip(train,train_tokens),key=lambda pair:len(query&pair[1])/max(1,len(query|pair[1])));supported=bool(query&nearest);probs={c:(.2*(prior[c]+1)/den+.8*(c==best['target'])) if supported else (prior[c]+1)/den for c in classes};row.update(probabilities=probs,label=max(probs,key=probs.get),evidence=best['id'] if supported else None,status='ok' if supported else 'unknown_description',review=False)
        elif kind=='03':
            if not r['control_count']:row.update(keep=True,ratio=None,status='missing_controls')
            else:
                ratio=r['control_mass']/max(r['sample_mass'],1e-12);row.update(keep=(r['sample_mass']>=.005 if model=='abundance' else ratio<1),ratio=ratio,status='ok')
        elif kind in ['05','06','07','08','10']:
            pred=float(ridge_predictions[index]) if ridge_predictions is not None else center
            if kind=='08' and ridge_predictions is None:pred=intercept+slope*r['sensor_mean']
            if kind=='10' and ridge_predictions is None:pred=additive(r,shrink)
            if kind=='06':row.update(probability=float(prob_predictions[index]) if prob_predictions is not None else min(1,max(0,pred)),review=False,status='ok')
            elif kind=='10':
                ref=data['reference'];row.update(prediction=pred,sequence=r['sequence'],mutations=[f'{b}{i+1}{a}' for i,(a,b) in enumerate(zip(r['sequence'],ref)) if a!=b],review=False,status='assayed_library_only')
            else:
                if kind=='07':
                    pred=max(0,pred)
                    if ridge_predictions is None:residual_low,residual_high=-width,width
                row.update(prediction=pred,lower=max(0,pred+residual_low) if kind=='07' else pred-width,upper=max(max(0,pred+residual_low),pred+residual_high) if kind=='07' else pred+width,review=False,status='low_sensor_count' if kind=='08' and r['sensor_count']<2 else 'ok',correction=None)
        elif kind=='09':
            # Train climatology per station; unseen station falls back to pooled training rate.
            local=r['station'] in station_rates;prob=station_rates.get(r['station'],global_rate);row.update(probability=float(prob_predictions[index]) if prob_predictions is not None and local else prob,review=False,status='ok' if local else 'unknown_station_manual_review',last_input_date=r['last_input_date'])
        elif kind=='11':
            role=r['role'];allowed=[x for x in r['catalog'] if role in x['roles']];matches=[x['id'] for x in allowed if x['marker']==r['marker']];findings=[{'record_id':x['id'],'field':'marker','evidence':x['text']} for x in allowed if not x['marker']];ranking=sorted(allowed,key=lambda x:sum((a-b)**2 for a,b in zip(x['embedding'],r['query_embedding'])));row.update(cohort_ids=matches,count=len(matches),denied_ids=[x['id'] for x in r['catalog'] if role not in x['roles']],findings=findings,morphology_ids=[x['id'] for x in ranking],status='authored_fixture_only')
        elif kind=='12':
            hit=next((s for s in r['sections'] if r['search_term'].lower() in s['text'].lower()),None);row.update(answer=hit['text'] if hit else None,section=hit['id'] if hit else None,quote=hit['text'] if hit else '',status='supported' if hit else 'absent')
        if kind=='07' and model=='domain':row['lower']=domain_lower[index];row['upper']=domain_upper[index]
        if kind=='07':row['correction_image_sha256']=None;row['review_priority']=sum((v-m)**2 for v,m in zip(r['features'][:1024],feature_center))/len(feature_center) if r['image'] else -1.0
        if kind=='08':
            for field in ['prediction','lower','upper']:row[field]=min(1,max(0,row[field]))
            row['review_priority']=r['sensor_sd']
        result.append(row)
    if kind in ['02','05','06','07','08','10']:
        rank=sorted(result,key=lambda x:(-(1-max(x['probabilities'].values())) if kind=='02' else x['prediction'] if kind=='05' else -x.get('probability',x.get('prediction',0)),x['id']))
        if kind=='07':rank=sorted(result,key=lambda x:(-x['review_priority'],x['id']))
        if kind=='08':rank=sorted(result,key=lambda x:(-x['review_priority'],x['id']))
        for row in rank[:data['budget']]:row['review']=True
    if kind=='09':
        by_date=collections.defaultdict(list);lookup={r['id']:r for r in result}
        for r in cases:by_date[r['date']].append(lookup[r['id']])
        for date,rows in by_date.items():
            for row in sorted(rows,key=lambda x:(-x['probability'],x['id']))[:math.ceil(.2*len(rows))]:row['review']=True
    hyperparameters={'method':'mean abundance' if model=='abundance' else 'control ratio','threshold':.005 if model=='abundance' else 1} if kind=='03' else {'C':selected_c,'selection':'validation Brier, fixed .01/.1/1/10 grid'} if model=='logistic' else {'alpha':alpha,'selection':'validation macro-domain MAE; grid 10,100,1000,10000' if kind=='07' else 'validation only; fixed grid 0.1,1,10,100'} if model=='ridge' else {'shrinkage':shrink,'selection':'validation top-50 only; fixed grid 5,20,50'} if kind=='10' else {}
    if kind=='07' and model=='ridge':hyperparameters['calibration']=calibration
    if model=='domain':hyperparameters=domain_hyper
    external_models=[{'id': 'timm/mobilenetv3_small_100.lamb_in1k', 'revision': '1824797e7887cbec1990e4adbd6675960a36c589', 'weights_sha256': '46d2c063b18125884c48937afa4c49e18128869e52e8db96df48bf0a4d7ff697', 'use': 'Frozen generic ImageNet feature extraction only; no wheat benchmark training'}] if model=='domain' else []
    return {'packet_version':'0.5.0-internal','route':route,'model':model,'provenance':{'training':'participant data.json train only','external_models':external_models,'hyperparameters':hyperparameters,'pre_event_work':'disclose before judged submission'},'rows':result}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--route',required=True);ap.add_argument('--output',type=pathlib.Path,required=True);ap.add_argument('--fixture',action='store_true');ap.add_argument('--model',choices=['baseline','ridge','logistic','fallback','abundance','seasonal','domain'],default='baseline');args=ap.parse_args();p=pathlib.Path(__file__).resolve().parent/args.route
    data=load_data(p,args.fixture);out=run(args.route,data,args.model);args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n');print(f'{args.route}: {len(out["rows"])} rows exported to {args.output}')
if __name__=='__main__':main()
