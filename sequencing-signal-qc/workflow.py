"""Export inspectable scientific worklists and exercise file round trips without organizer keys."""
import argparse,collections,csv,datetime,gzip,json,math,pathlib,statistics,hashlib
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from data_io import load_data,text_for
from check_submission import validate

def export(route,data,submission,output,corrections=None,image_directory=None):
    validate(route,data,submission);output.mkdir(parents=True,exist_ok=True);kind=route[:2];cases={r['id']:r for r in data['cases']};rows=[];summary={'route':route,'packet_version':'0.5.0-internal','scientific_limit':'See route README. Exports are model/review artifacts, not real-world biological outcomes.'}
    summary['source_notice']=(pathlib.Path(__file__).resolve().parent/route/'NOTICE.md').read_text()
    if kind=='05':
        from rdkit import Chem,DataStructs
        from rdkit.Chem import rdFingerprintGenerator
        generator=rdFingerprintGenerator.GetMorganGenerator(radius=2,fpSize=1024)
        training_fingerprints=[generator.GetFingerprint(Chem.MolFromSmiles(r['smiles'])) for r in data['train']]
    for pred in submission['rows']:

        c=cases[pred['id']];row={'id':pred['id']}
        if kind=='01':row.update(location=c['location'],issue=c['issue'],target=c['target_end_date'],horizon=c['horizon'],median=pred['quantiles'][11],lower90=pred['quantiles'][2],upper90=pred['quantiles'][20],last_input_date=pred['last_input_date'],status=pred['status'])
        elif kind=='02':row.update(source_text=c['text'],label=pred['label'],confidence=max(pred['probabilities'].values()),training_source=pred['evidence'],review=pred['review'],status=pred['status'])
        elif kind=='03':
            mass=sum(x['signal'] for x in c['sample_signals']);row.update(cohort=c['cohort'],retained_mass=mass if pred['keep'] else 0,removed_mass=0 if pred['keep'] else mass,control_ratio=pred['ratio'],status=pred['status'],low_abundance=c['sample_mass']<.005,abundance_alternative_keep=c['sample_mass']>=.005)
        elif kind=='04':
            source=data['article_sources'][c['article_id']];row.update(intervention=c['intervention'],comparator=c['comparator'],outcome=c['outcome'],direction=pred['direction'],start=pred['start'],end=pred['end'],quote=pred['quote'],source=source['source_url'],title=source['title'],authors='; '.join(source['authors']),license_urls='; '.join(source['license_urls']),source_text_sha256=hashlib.sha256(text_for(data,c).encode()).hexdigest(),status=pred['status'])
        elif kind=='05':
            query=generator.GetFingerprint(Chem.MolFromSmiles(c['smiles']));similarities=DataStructs.BulkTanimotoSimilarity(query,training_fingerprints);indices=sorted(range(len(similarities)),key=lambda i:(-similarities[i],data['train'][i]['id']))[:3];analogue=[data['train'][i]['id'] for i in indices];similarity=[float(similarities[i]) for i in indices]
            row.update(smiles=c['smiles'],logS=pred['prediction'],lower90=pred['lower'],upper90=pred['upper'],measurement_selected=pred['review'],Morgan_training_neighbours=','.join(analogue),Tanimoto_similarities=','.join(f'{v:.6f}' for v in similarity),units='log10 mol/L',domain='frozen verified structure domain',neighbour_warning='weak fingerprint support' if max(similarity)<.3 else 'inspect analogue conditions')
        elif kind=='06':row.update(smiles=c['smiles'],primary_activity=c['primary_activity'],counter_pass_probability=pred['probability'],follow_up=pred['review'],stage_reason='primary >=50; counter outcome withheld, no target-binding claim')
        elif kind=='07':
            correction=corrections.get(pred['id']) if corrections else pred['correction'];row.update(image=c['image'],domain=c['domain'],prediction=pred['prediction'],lower90=pred['lower'],upper90=pred['upper'],review=pred['review'],review_priority=pred['review_priority'],correction=correction)
            if correction is not None:
                image=pathlib.Path(image_directory)/f"{pred['id']}.jpg" if image_directory else pathlib.Path(__file__).resolve().parent/'07-wheat'/c['image'] if c['image'] else None
                if image is None or not image.is_file() or hashlib.sha256(image.read_bytes()).hexdigest()!=c['image_sha256']:raise ValueError('Correction image missing or changed')
                if not math.isfinite(correction) or correction<0:raise ValueError('Invalid correction')
                pred['correction']=correction;pred['correction_image_sha256']=c['image_sha256'];row['correction_image_sha256']=c['image_sha256']

        elif kind=='08':
            date=str(datetime.date(1899,12,30)+datetime.timedelta(days=float(c['sample_date'])));row.update(device=c['device'],source_date=c['sample_date'],display_date=date,raw_manufacturer=c['sensor_mean'],calibrated=pred['prediction'],lower90=pred['lower'],upper90=pred['upper'],sensor_count=c['sensor_count'],warning=pred['status'],remeasure=pred['review'],review_priority=pred['review_priority'],units='m3/m3')
        elif kind=='09':row.update(station=c['station'],target_date=c['date'],last_input_date=pred['last_input_date'],freeze_probability=pred['probability'],local_verification=pred['review'],status=pred['status'],source_vintage='finalized current archive; not issuance vintage')
        elif kind=='10':row.update(sequence=pred['sequence'],prediction=pred['prediction'],mutations=','.join(pred['mutations']),hypothetical_assay=pred['review'],status=pred['status'])
        else:row.update(pred)
        rows.append(row)
    validate(route,data,submission)
    if kind=='07':(output/'corrected-submission.json').write_text(json.dumps(submission,indent=2,allow_nan=False)+'\n')
    if kind=='02':summary['predicted_categories_in_this_fixed_corpus']=dict(collections.Counter(r['label'] for r in rows));summary['inference_limit']='Descriptive corpus coding, not population incidence.'
    if kind=='03':
        by_cohort=collections.defaultdict(lambda:{'retained':0,'removed':0})
        for r in rows:by_cohort[r['cohort']]['retained']+=r['retained_mass'];by_cohort[r['cohort']]['removed']+=r['removed_mass']
        summary['signal_mass']=dict(by_cohort)
    if kind=='10':summary['selected_assayed_sequences']=sum(r['hypothetical_assay'] for r in rows);summary['prospective_performance']='unknown; no new assay run'
    (output/'review.json').write_text(json.dumps(rows,indent=2,allow_nan=False)+'\n');(output/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    with (output/'review.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for row in rows for k in row)));writer.writeheader();writer.writerows(rows)
    with (output/'review.csv').open(newline='') as f:readback=list(csv.DictReader(f))
    if len(readback)!=len(rows) or {r['id'] for r in readback}!=set(cases):raise ValueError('Export round trip lost case identity')
    return rows

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--route',required=True);ap.add_argument('--submission',type=pathlib.Path,required=True);ap.add_argument('--output',type=pathlib.Path,required=True);ap.add_argument('--corrections',type=pathlib.Path);ap.add_argument('--image-directory',type=pathlib.Path);args=ap.parse_args();p=pathlib.Path(__file__).resolve().parent;data=load_data(p/args.route);sub=json.loads(args.submission.read_text());corrections=None
    if args.corrections:
        with args.corrections.open(newline='') as f:source=list(csv.DictReader(f))
        corrections={r['id']:float(r['correction']) for r in source}
        if len(corrections)!=len(source) or not set(corrections)<={r['id'] for r in data['cases']}:raise ValueError('Duplicate or unknown correction IDs')
    rows=export(args.route,data,sub,args.output,corrections,args.image_directory);print(f'{len(rows)} rows exported and CSV/JSON identities verified')
if __name__=='__main__':main()
