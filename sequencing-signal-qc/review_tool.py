"""Filter review tool: compare the control-aware and abundance-only filters feature by feature.

Writes one self-contained, offline HTML report plus a per-feature CSV. Standard library only.

    python3 -I review_tool.py --route 03-qc --output review/report.html
    python3 -I review_tool.py --route 03-qc --fixture --output review/fixture-report.html
"""
import argparse, collections, csv, json, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from data_io import load_data  # noqa: E402
import starter  # noqa: E402

ABUNDANCE_THRESHOLD = .005   # starter.py abundance model
RATIO_THRESHOLD = 1          # starter.py control-aware (baseline) model
RECURRING = .3               # share of sample replicates with signal that counts as "recurring"

BUCKETS = {
    'rare_recurring': ('Rare, recurring', 'Control-aware keeps, abundance-only removes. Seen in many replicates, and weaker in controls than in samples. The rare real organism the abundance cutoff would lose.'),
    'rare_sparse': ('Rare, sparse', 'Control-aware keeps, abundance-only removes. Seen in only one or two replicates, so it could be noise or cross-talk.'),
    'control_flagged': ('Abundant but in controls', 'Control-aware removes, abundance-only keeps. Could be a reagent contaminant, or sample signal leaking into a control.'),
    'no_signal': ('No sample signal', 'Zero signal in every sample. The control-aware filter keeps it only because 0 divided by almost 0 passes.'),
    'agree_keep': ('Agree: keep', 'Both filters keep it.'),
    'agree_remove': ('Agree: remove', 'Both filters remove it.'),
    'no_controls': ('No controls', 'No control measurements, so the control-aware filter keeps it by default.'),
}
DISAGREE = ['rare_recurring', 'rare_sparse', 'control_flagged', 'no_signal']


def decisions(route, rows):
    """Run both starter filters so decisions match the official starter exactly."""
    data = {'cases': [{k: v for k, v in r.items() if k != 'target'} for r in rows]}
    ca = {r['id']: r for r in starter.run(route, data, 'baseline')['rows']}
    ab = {r['id']: r for r in starter.run(route, data, 'abundance')['rows']}
    return ca, ab


def bucket_of(r, ca_keep, ab_keep, prevalence):
    if not r['control_count']:
        return 'no_controls'
    if r['sample_mass'] == 0 and ca_keep:
        return 'no_signal'
    if ca_keep and ab_keep:
        return 'agree_keep'
    if not ca_keep and not ab_keep:
        return 'agree_remove'
    if ca_keep:
        return 'rare_recurring' if prevalence >= RECURRING else 'rare_sparse'
    return 'control_flagged'


def check_next(f):
    """Plain-language next steps a researcher would take before accepting a decision."""
    out = []
    b = f['bucket']
    if b == 'no_signal':
        out.append('No sample replicate has any signal. The control-aware keep is a divide-by-zero artifact, so removing it is safe.')
        return out
    if f['sample_hits'] <= 1:
        out.append('All the signal comes from one replicate. Check that well\'s raw read count and its plate neighbours for index hopping or cross-talk.')
    elif f['prevalence'] >= RECURRING:
        out.append(f"Signal recurs in {f['sample_hits']} of {f['sample_count']} replicates. That is hard to explain as random noise, so check whether the organism is expected in the mixture.")
    if f['control_hits']:
        out.append(f"Present in {f['control_hits']} of {f['control_count']} controls. Find out which control type and batch it came from (extraction blank or PCR blank).")
    if b == 'control_flagged':
        out.append('Abundant in samples yet present in controls. Compare against plate layout: high sample signal next to a blank suggests leakage into the control, not a contaminant.')
    if f['ratio'] is not None and .5 <= f['ratio'] < 2:
        out.append(f"Control ratio {f['ratio']:.2f} is close to the cutoff of 1. A single control replicate could flip this decision.")
    if f['sample_mass'] < ABUNDANCE_THRESHOLD:
        out.append(f"Mean sample signal is {f['sample_mass']/ABUNDANCE_THRESHOLD:.1%} of the abundance cutoff. Confirm with raw read counts before treating it as present.")
    out.append('Look up the sequence\'s taxonomy and compare it with known kit and reagent contaminants and with the expected mixture.')
    return out


def build(route, data):
    feats = []
    for split in ('cases', 'train'):
        rows = data.get(split, [])
        if not rows:
            continue
        ca, ab = decisions(route, rows)
        for r in rows:
            s = [x['signal'] for x in r['sample_signals']]
            c = [x['signal'] for x in r['control_signals']]
            ca_keep, ab_keep = ca[r['id']]['keep'], ab[r['id']]['keep']
            hits = sum(v > 0 for v in s)
            prevalence = hits / len(s) if s else 0
            mass = sum(s)  # same formula as workflow.py retained/removed mass
            f = dict(
                id=r['id'], split=split, cohort=r['cohort'], target=r.get('target'),
                sample_mass=r['sample_mass'], control_mass=r['control_mass'],
                sample_count=r['sample_count'], control_count=r['control_count'],
                ratio=ca[r['id']]['ratio'], status=ca[r['id']]['status'],
                ca_keep=ca_keep, ab_keep=ab_keep, low_abundance=r['sample_mass'] < ABUNDANCE_THRESHOLD,
                signal_mass=mass,
                ca_retained=mass if ca_keep else 0, ca_removed=0 if ca_keep else mass,
                ab_retained=mass if ab_keep else 0, ab_removed=0 if ab_keep else mass,
                sample_hits=hits, control_hits=sum(v > 0 for v in c), prevalence=prevalence,
                samples=s, controls=c,
            )
            f['bucket'] = bucket_of(r, ca_keep, ab_keep, prevalence)
            f['disagree'] = f['bucket'] in DISAGREE
            # Review priority: disagreements first, then replicate support, then signal.
            f['priority'] = (2 if f['disagree'] and f['bucket'] != 'no_signal' else 1 if f['disagree'] else 0) * 10 + prevalence + min(1, r['sample_mass'] / ABUNDANCE_THRESHOLD)
            f['check_next'] = check_next(f)
            feats.append(f)
    return feats


def labeled_accuracy(feats):
    table = collections.OrderedDict()
    for key in list(BUCKETS) + ['all']:
        rows = [f for f in feats if f['split'] == 'train' and (key == 'all' or f['bucket'] == key)]
        if not rows:
            continue
        table[key] = dict(
            n=len(rows), real=sum(bool(f['target']) for f in rows),
            ca_right=sum(f['ca_keep'] == f['target'] for f in rows),
            ab_right=sum(f['ab_keep'] == f['target'] for f in rows),
        )
    return table


def signal_summary(feats, split='cases'):
    out = collections.OrderedDict()
    for f in feats:
        if f['split'] != split:
            continue
        o = out.setdefault(f['cohort'], collections.Counter())
        for k in ('signal_mass', 'ca_retained', 'ca_removed', 'ab_retained', 'ab_removed'):
            o[k] += f[k]
        o['features'] += 1
        o['disagree'] += f['disagree']
    return {k: dict(v) for k, v in out.items()}


def write_csv(feats, path):
    cols = ['id', 'split', 'cohort', 'bucket', 'disagree', 'ca_keep', 'ab_keep', 'status', 'ratio', 'sample_mass',
            'control_mass', 'sample_hits', 'sample_count', 'control_hits', 'control_count', 'low_abundance',
            'ca_retained', 'ca_removed', 'ab_retained', 'ab_removed', 'priority', 'target']
    with path.open('w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        for f in sorted(feats, key=lambda f: (f['split'], -f['priority'], f['id'])):
            w.writerow(f)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--route', default='03-qc')
    ap.add_argument('--fixture', action='store_true', help='use the 50-case fallback set')
    ap.add_argument('--output', type=pathlib.Path, default=pathlib.Path('review/report.html'))
    args = ap.parse_args()
    data = load_data(HERE / args.route, args.fixture)
    feats = build(args.route, data)
    payload = dict(
        features=feats, buckets=BUCKETS, disagree=DISAGREE, accuracy=labeled_accuracy(feats),
        summary=signal_summary(feats), thresholds=dict(abundance=ABUNDANCE_THRESHOLD, ratio=RATIO_THRESHOLD, recurring=RECURRING),
        source='fixture (50 cases)' if args.fixture else 'full held-out set',
    )
    template = (HERE / 'review_template.html').read_text()
    blob = json.dumps(payload, separators=(',', ':'), allow_nan=False).replace('</', '<\\/')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(template.replace('/*__DATA__*/null', blob))
    write_csv(feats, args.output.with_name(args.output.stem + '-features.csv'))
    cases = [f for f in feats if f['split'] == 'cases']
    counts = collections.Counter(f['bucket'] for f in cases)
    print(f'{len(cases)} held-out features, {sum(f["disagree"] for f in cases)} disagreements')
    for k in BUCKETS:
        if counts[k]:
            print(f'  {BUCKETS[k][0]:<26}{counts[k]:>6}')
    print(f'Report: {args.output}')


if __name__ == '__main__':
    main()
