import json
for n in ('ECU', 'WUSTL'):
    d = json.load(open(f'results/exp1_{n}_random.json'))
    r = max([x for x in d['runs'] if x['method'] == 'lirs'], key=lambda x: x['val']['accuracy'])
    json.dump(r['hp'], open(f'results/hp_{n}.json', 'w')); print(n, 'seed', r['seed'], 'val', round(r['val']['accuracy'], 4), r['hp'])
