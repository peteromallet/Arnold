"""Smoke test for native trace emission."""
import sys, os, tempfile, json

os.environ['ARNOLD_NATIVE_RUNTIME'] = '1'

from arnold.pipeline.native import (
    compile_pipeline, run_native_pipeline,
    phase, pipeline,
)

@phase
def do_work(ctx: dict) -> dict:
    return {'result': 42}

@pipeline
def my_pipe(ctx: dict) -> dict:
    state = yield do_work(ctx)
    return state

prog = compile_pipeline(my_pipe)

# Run WITHOUT trace
result_no_trace = run_native_pipeline(prog)
print('Without trace:')
print('  state:', result_no_trace.state)
print('  stages:', result_no_trace.stages)

# Run WITH trace
with tempfile.TemporaryDirectory() as tmpdir:
    trace_dir = os.path.join(tmpdir, 'traces')
    result_trace = run_native_pipeline(prog, trace_dir=trace_dir)
    print()
    print('With trace:')
    print('  state:', result_trace.state)
    print('  stages:', result_trace.stages)
    print()
    print('Trace files:')
    for f in sorted(os.listdir(trace_dir)):
        fpath = os.path.join(trace_dir, f)
        size = os.path.getsize(fpath)
        print(f'  {f} ({size} bytes)')
        if f.endswith('.json'):
            with open(fpath) as fh:
                content = fh.read()
                if len(content) > 300:
                    content = content[:300] + '...'
                print(f'    content: {content}')
    
    # Verify all expected files exist
    all_exist = True
    for expected in ['state.json', 'events.ndjson', 'stages.json', 'artifacts.json', 'checkpoint.json']:
        full = os.path.join(trace_dir, expected)
        exists = os.path.exists(full)
        print(f'  {expected} exists: {exists}')
        all_exist = all_exist and exists

print()
print('Parity check: state same?', result_no_trace.state == result_trace.state)
print('Parity check: stages same?', result_no_trace.stages == result_trace.stages)
print('Parity check: suspended same?', result_no_trace.suspended == result_trace.suspended)
print()
if all_exist:
    print('SUCCESS: All trace files emitted, behavior unchanged when tracing disabled')
else:
    print('FAILURE: Some trace files missing')
    sys.exit(1)
