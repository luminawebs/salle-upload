import re

with open('frontend/src/components/GlobalSettingsPanel.jsx', 'r', encoding='utf-8') as f:
    js_content = f.read()

with open('main.py', 'r', encoding='utf-8') as f:
    py_content = f.read()

js_keys = set(re.findall(r"key:\s*'([^']+)'", js_content))
py_keys = set(re.findall(r'getattr\(Config,\s*"([^"]+)"', py_content))

print('In JS but not in PY:')
for k in js_keys - py_keys:
    print('  ', k)

print('\nIn PY but not in JS:')
for k in py_keys - js_keys:
    print('  ', k)
