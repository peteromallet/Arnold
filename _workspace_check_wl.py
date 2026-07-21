with open('arnold_pipelines/megaplan/observability/work_ledger.py','rb') as f:
    data = f.read()
idx = data.find(b'prompt_tokens=')
count = 0
while idx != -1 and count < 30:
    print(idx, repr(data[idx:idx+60]))
    idx = data.find(b'prompt_tokens=', idx+1)
    count += 1
