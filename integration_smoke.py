"""Local smoke only, no model/provider requests. Starts a pinned installed Bifrost binary."""
import json, pathlib, subprocess, tempfile, time, urllib.request
from preflight import scan
binary=pathlib.Path.home()/'.cache/bifrost/v2.5.1/bin/bifrost-http-0'
config={'providers':{},'config_store':{'enabled':False},'client':{'enable_logging':False,'disable_content_logging':True}}
result={'binary_version':'v2.5.1','provider_requests':0,'api_keys_used':0,'binding':'127.0.0.1','config_findings':scan(config)['findings']}
with tempfile.TemporaryDirectory() as d:
 pathlib.Path(d,'config.json').write_text(json.dumps(config))
 with open('integration-runtime.log','w') as log:
  proc=subprocess.Popen([str(binary),'-app-dir',d,'-host','127.0.0.1','-port','18347'],stdout=log,stderr=log)
  try:
   for i in range(40):
    if proc.poll() is not None:raise RuntimeError('Gateway exited; inspect local log.')
    try:
     with urllib.request.urlopen('http://127.0.0.1:18347/health',timeout=1) as r:
      result['health_status']=r.status; result['health_body']=r.read(2000).decode();break
    except OSError:time.sleep(.25)
   else:raise RuntimeError('No readiness within 10s')
   assert result['health_status']==200
  finally:
   proc.terminate()
   try:proc.wait(timeout=5)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
result['process_stopped']=True
pathlib.Path('integration-result.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
