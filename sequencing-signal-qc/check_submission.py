"""Offline participant submission contract checker; contains no answer keys."""
import argparse,json,math,pathlib
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from data_io import load_data,text_for

def validate(route,data,submission):
    if not isinstance(submission,dict) or set(submission)!={'packet_version','route','model','provenance','rows'}:raise ValueError('Invalid submission envelope')
    if not isinstance(submission['model'],str) or not submission['model'].strip():raise ValueError('Model declaration required')
    provenance=submission['provenance']
    if not isinstance(provenance,dict) or not {'training','external_models','hyperparameters','pre_event_work'}<=set(provenance):raise ValueError('Provenance declaration incomplete')
    if not isinstance(provenance['training'],str) or not isinstance(provenance['external_models'],list) or not isinstance(provenance['hyperparameters'],dict) or not isinstance(provenance['pre_event_work'],str):raise ValueError('Invalid provenance types')
    if not isinstance(submission['rows'],list) or not all(isinstance(r,dict) and isinstance(r.get('id'),str) for r in submission['rows']):raise ValueError('Invalid result rows')
    if submission.get('packet_version')!='0.5.0-internal' or submission.get('route')!=route:raise ValueError('Wrong packet or route')
    if not isinstance(submission.get('provenance'),dict):raise ValueError('Missing provenance')
    rows=submission['rows'];ids=[r['id'] for r in rows];expected={r['id'] for r in data['cases']}
    if len(set(ids))!=len(ids) or set(ids)!=expected:raise ValueError('Duplicate/missing/foreign case IDs')
    kind=route[:2];lookup={r['id']:r for r in data['cases']}
    contracts={
        '01':{'quantiles','reference_date','horizon','target_end_date','last_input_date','status'},
        '02':{'probabilities','label','evidence','review','status'},'03':{'keep','ratio','status'},
        '04':{'direction','start','end','quote','status'},
        '05':{'prediction','lower','upper','review','status','correction'},
        '06':{'probability','review','status'},'07':{'prediction','lower','upper','review','status','correction','correction_image_sha256','review_priority'},
        '08':{'prediction','lower','upper','review','status','correction','review_priority'},'09':{'probability','review','status','last_input_date'},
        '10':{'prediction','sequence','mutations','review','status'},
        '11':{'cohort_ids','count','denied_ids','findings','morphology_ids','status'},'12':{'answer','section','quote','status'}}
    for r in rows:
        if set(r)!=contracts[kind]|{'id'}:raise ValueError('Missing or unknown output fields')
        if 'status' in r and not isinstance(r['status'],str):raise ValueError('Status must be text')
        if 'correction' in r and r['correction'] is not None and (isinstance(r['correction'],bool) or not isinstance(r['correction'],(int,float)) or not math.isfinite(r['correction']) or r['correction']<0):raise ValueError('Invalid correction')
        if kind=='08' and (any(not 0<=r[k]<=1 for k in ['prediction','lower','upper','review_priority']) or not r['lower']<=r['prediction']<=r['upper']):raise ValueError('Soil values/risk must satisfy the original 0..1 and interval contract')
        if kind in ['05','08'] and r['correction'] is not None:raise ValueError('Correction is reserved and must be null for this route')
        if kind=='10':
            c=lookup[r['id']];reference=data['reference'];mutations=[f'{b}{i+1}{a}' for i,(a,b) in enumerate(zip(c['sequence'],reference)) if a!=b]
            if r['mutations']!=mutations:raise ValueError('Mutation audit mismatch')
        if kind=='11':
            if not all(isinstance(r[k],list) for k in ['cohort_ids','denied_ids','findings','morphology_ids']) or not isinstance(r['count'],int) or r['count']!=len(r['cohort_ids']):raise ValueError('Invalid partner export')
            c=lookup[r['id']];allowed={x['id'] for x in c['catalog'] if c['role'] in x['roles']}
            disclosed=set(r['cohort_ids'])|set(r['morphology_ids'])|{f['record_id'] for f in r['findings']}
            if not disclosed<=allowed:raise ValueError('Unauthorized fixture output')
        if kind=='12':
            if r['status']=='absent':
                if r['answer'] is not None or r['section'] is not None or r['quote']!='':raise ValueError('Absent answer must be empty')
            elif r['status']=='supported':
                c=lookup[r['id']];sections={x['id']:x['text'] for x in c['sections']}
                if r['section'] not in sections or not isinstance(r['quote'],str) or not r['quote'] or r['quote'] not in sections[r['section']]:raise ValueError('Unsupported citation')
            else:raise ValueError('Unknown document status')

    for r in rows:
        c=lookup[r['id']]
        if kind=='01':
            q=r['quantiles']
            if len(q)!=23 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 for v in q) or sorted(q)!=q:raise ValueError('Invalid quantiles')
            if any(r[k]!=c[k] for k in ['reference_date','horizon','target_end_date']):raise ValueError('Forecast date/horizon changed')
            if r['last_input_date']!=c['history'][-1]['date']:raise ValueError('Input date changed')
        if kind=='02':
            probs=r['probabilities']
            if set(probs)!=set(data['classes']) or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=1 for v in probs.values()) or abs(sum(probs.values())-1)>1e-6 or r['label'] not in probs:raise ValueError('Invalid category probabilities')
        if kind=='03' and not isinstance(r['keep'],bool):raise ValueError('Keep must be boolean')
        if kind=='04':
            s,e=r['start'],r['end']
            if type(r['direction']) is not int or r['direction'] not in [-1,0,1] or isinstance(s,bool) or isinstance(e,bool) or not isinstance(s,int) or not isinstance(e,int) or not 0<=s<e<=len(text_for(data,c)) or r['quote']!=text_for(data,c)[s:e] or len(r['quote'].split())>160:raise ValueError('Invalid evidence card')
        for col in (['probability'] if kind in ['06','09'] else ['prediction','lower','upper','review_priority'] if kind in ['07','08'] else ['prediction','lower','upper'] if kind=='05' else ['prediction'] if kind=='10' else []):
            v=r[col]
            if isinstance(v,bool) or isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):raise ValueError('Nonfinite numeric output')
        if kind in ['06','09'] and not 0<=r['probability']<=1:raise ValueError('Probability outside [0,1]')
        if kind in ['05','07','08'] and r['lower']>r['upper']:raise ValueError('Inverted interval')
        if kind=='10' and r['sequence']!=c['sequence']:raise ValueError('Candidate sequence changed')
        if kind in ['02','05','06','07','08','09','10'] and not isinstance(r['review'],bool):raise ValueError('Review must be boolean')
    if kind in ['02','05','06','07','08','10'] and sum(r['review'] for r in rows)!=data['budget']:raise ValueError('Wrong queue capacity')
    # Ranking tasks must submit a queue consistent with their declared score, including cutoff ties.
    if kind in ['05','06','07','08','10']:
        score=lambda r:-r['prediction'] if kind=='05' else r['review_priority'] if kind in ['07','08'] else r.get('probability',r.get('prediction'))
        selected=[score(r) for r in rows if r['review']];omitted=[score(r) for r in rows if not r['review']]
        if selected and omitted and min(selected)<max(omitted):raise ValueError('Queue is inconsistent with submitted ranking')
    if kind=='09':
        groups={};output={r['id']:r for r in rows}
        for c in data['cases']:groups.setdefault(c['date'],[]).append(output[c['id']])
        for group in groups.values():
            chosen=[r['probability'] for r in group if r['review']];other=[r['probability'] for r in group if not r['review']]
            if len(chosen)!=math.ceil(.2*len(group)):raise ValueError('Wrong daily queue capacity')
            if chosen and other and min(chosen)<max(other):raise ValueError('Daily queue inconsistent with ranking')
    if kind=='02':
        train_ids={r['id'] for r in data['train']}
        for r in rows:
            if r['status'] not in ['ok','unknown_description'] or (r['status']=='ok' and r['evidence'] not in train_ids) or (r['status']=='unknown_description' and r['evidence'] is not None) or r['probabilities'][r['label']]!=max(r['probabilities'].values()):raise ValueError('Unknown training source or label/probability mismatch')
    if kind=='03':
        for r in rows:
            c=lookup[r['id']]
            if not c['control_count']:
                if r['status']!='missing_controls' or r['ratio'] is not None:raise ValueError('Missing controls must be explicit')
            elif isinstance(r['ratio'],bool) or not isinstance(r['ratio'],(int,float)) or not math.isfinite(r['ratio']) or r['ratio']<0:raise ValueError('Invalid control ratio')
    if kind=='07':
        for r in rows:
            if r['prediction']<0 or r['lower']<0:raise ValueError('Negative visible-head count')
            if r['correction'] is not None and r['correction_image_sha256']!=lookup[r['id']]['image_sha256']:raise ValueError('Correction must name the exact supplied/retrieved image hash')
            if r['correction'] is None and r['correction_image_sha256'] is not None:raise ValueError('Image attestation without correction')
    return rows


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--route',required=True);ap.add_argument('--submission',type=pathlib.Path,required=True);ap.add_argument('--fixture',action='store_true');args=ap.parse_args();p=pathlib.Path(__file__).resolve().parent;data=load_data(p/args.route,args.fixture);rows=validate(args.route,data,json.loads(args.submission.read_text()));print(f'valid: {len(rows)} rows; scientific correctness and provenance require separate evaluation')
if __name__=='__main__':main()
