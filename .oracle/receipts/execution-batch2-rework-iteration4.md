schema: arnold.batch2.rework.execution_receipt.v4
candidate_code_commit: 5c74f0c6155deedf22b911bc588d5c8a79e12390
parent_checkpoint: 5da26ec5be4d13559948fe4256a114ad7626482b
workspace: /Users/peteromalley/Documents/Arnold-batch2-rework
interpreter: /Users/peteromalley/.pyenv/versions/3.11.11/bin/python
python_version: 3.11.11
omp_rpc_source: /Users/peteromalley/Documents/oh-my-pi/python/omp-rpc/src
omp_rpc_package: /Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/omp_rpc/__init__.py
path: /Users/peteromalley/.pyenv/versions/3.11.11/bin:/opt/homebrew/bin:/usr/local/bin:/usr/sbin:/usr/bin:/bin
nbf02_result: 246 passed in 107.29s (0:01:47)
nbf03_result: 52 passed in 24.18s
auto_result: 29 passed in 4.62s
authority_checker: PASS; diagnostics=[]
compile_and_diff_check: PASS
probe_result: valid ACCEPT; forged-start REJECT; forged-boot REJECT; dead REJECT

raw_streams:
  nbf02_stdout: .oracle/evidence/iteration4-nbf02.stdout
  nbf02_stdout_sha256: 048f096bd8852a87680c9bb156605f0c59bf1ed8817d8e2f1ccc9ebabe54498f
  nbf02_stderr: .oracle/evidence/iteration4-nbf02.stderr
  nbf02_stderr_sha256: 01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b
  nbf03_stdout: .oracle/evidence/iteration4-nbf03.stdout
  nbf03_stdout_sha256: 65c18eed0555a3bf9c86dc9c19656632ec2ea7209c7b50d2b5d56e7957cb103f
  nbf03_stderr: .oracle/evidence/iteration4-nbf03.stderr
  nbf03_stderr_sha256: 01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b
  auto_stdout: .oracle/evidence/iteration4-auto.stdout
  auto_stdout_sha256: 7844a1a29d317a8dd5b4ea410933fc459db45dfd928a025076f5acdf9e1805bf
  auto_stderr: .oracle/evidence/iteration4-auto.stderr
  auto_stderr_sha256: 01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b

evidence_note: source code and tests are committed separately from this receipt; no merge, push, or Batch 3 action was performed.
