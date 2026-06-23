import re

def parse_activity_number(val):
    if val.isdigit(): return int(val)
    roman = {'i':1,'v':5,'x':10,'l':50,'c':100,'d':500,'m':1000}
    res = 0
    val = val.lower()
    for i in range(len(val)):
        if i + 1 < len(val) and roman.get(val[i], 0) < roman.get(val[i+1], 0):
            res -= roman.get(val[i], 0)
        else:
            res += roman.get(val[i], 0)
    return res

def match(search, name):
    if search in name: return True
    sm = re.search(r'^actividad\s+([\divxlcdm]+)', search)
    nm = re.search(r'^actividad\s+([\divxlcdm]+)', name)
    if sm and nm:
        return parse_activity_number(sm.group(1)) == parse_activity_number(nm.group(1))
    return False

print(match('actividad 2', 'actividad ii: ¿cómo usar...'))
print(match('actividad 5', 'actividad v ( power point)'))
