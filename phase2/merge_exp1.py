import glob, json, os, collections
g = collections.defaultdict(list)
for p in sorted(glob.glob('results/g*/exp1_*.json')): g[os.path.basename(p)].append(json.load(open(p)))
for name, parts in g.items():
    out = parts[0]; out['runs'] = [r for d in parts for r in d['runs']]
    json.dump(out, open('results/' + name, 'w'), indent=1); print(name, len(out['runs']), 'runs merged')
