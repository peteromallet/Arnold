with open('arnold_pipelines/megaplan/observability/work_ledger.py','rb') as f:
    data = f.read()
print('len', len(data))
for off in [13590, 14613, 15432]:
    print('---', off)
    print(repr(data[off-5:off+80]))
