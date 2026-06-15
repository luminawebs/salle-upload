import json
with open('assets/4737/contenidos.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
for k, v in data.items():
    if 'actualidad' in v:
        print(f'{k} actualidad:')
        print(json.dumps(v['actualidad'], indent=2))
        break
