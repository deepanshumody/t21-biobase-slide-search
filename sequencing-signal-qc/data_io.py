"""Read only bundled participant inputs. Compressed files keep full cohorts portable."""
import gzip,json,pathlib,hashlib

def load_data(folder,fixture=False):
    folder=pathlib.Path(folder);name='fallback' if fixture else 'data';plain=folder/(name+'.json');compressed=folder/(name+'.json.gz')
    if compressed.exists():
        with gzip.open(compressed,'rt') as stream:data=json.load(stream)
    else:data=json.loads(plain.read_text())
    docs=folder/('fallback-documents.json.gz' if fixture else 'documents.json.gz')
    if docs.exists():
        with gzip.open(docs,'rt') as stream:data['document_texts']=json.load(stream)
    if data.get('feature_cache'):
        import numpy as np
        cache=(folder/data['feature_cache']).resolve()
        if cache.parent!=folder.resolve() or hashlib.sha256(cache.read_bytes()).hexdigest()!=data['feature_cache_sha256']:raise ValueError('Feature cache identity mismatch')
        with np.load(cache,allow_pickle=False) as archive:
            if set(archive.files)!={'X'}:raise ValueError('Feature cache must contain features only')
            features=archive['X']
            if list(features.shape)!=data['feature_shape'] or not np.isfinite(features).all():raise ValueError('Feature cache shape/value mismatch')
            for group in ['train','validation','cases']:
                for row in data[group]:row['features']=features[row['feature_index']].tolist()
    return data

def text_for(data,row):
    if 'text' in row:return row['text']
    if row['article_id'] not in data.get('document_texts',{}):raise ValueError('Source article missing from permitted document set')
    return data['document_texts'][row['article_id']]
