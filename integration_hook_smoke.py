"""Author-only real pre-commit runner smoke in a disposable local Git repository."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parent

def main():
    runner=shutil.which('pre-commit')
    if not runner:
        raise SystemExit('Install pre-commit in a local environment first.')
    version=subprocess.check_output([runner,'--version'],text=True).strip()
    with tempfile.TemporaryDirectory(prefix='bifrost-hook-smoke-') as tmp:
        root=Path(tmp)
        subprocess.run(['git','init','-q',tmp],check=True)
        target=root/'tools'/'bifrost-preflight'
        target.mkdir(parents=True)
        for f in ('preflight.py','precommit_entry.py','upstream-schema.json'):
            shutil.copy2(ROOT/f,target/f)
        shutil.copy2(ROOT/'precommit-example.yaml',root/'.pre-commit-config.yaml')
        (root/'good').mkdir()
        shutil.copy2(ROOT/'examples'/'reference-only.json',root/'good'/'config.json')
        subprocess.run(['git','add','.'],cwd=tmp,check=True)
        def run():
            return subprocess.run([runner,'run','--all-files'],cwd=tmp,capture_output=True,text=True)
        good=run()
        (root/'bypass').mkdir()
        config=json.loads((ROOT/'examples'/'reference-only.json').read_text())
        config.setdefault('governance',{}).setdefault('auth_config',{})['disable_auth_on_inference']=True
        (root/'bypass'/'config.json').write_text(json.dumps(config))
        subprocess.run(['git','add','.'],cwd=tmp,check=True)
        mixed=run()
        result={'runner':version,'good_exit':good.returncode,'mixed_exit':mixed.returncode,
                'good_hook_passed':'Passed' in good.stdout,'mixed_hook_failed':'Failed' in mixed.stdout,
                'bypass_reported':'INFERENCE_AUTH_BYPASS' in mixed.stdout,
                'temporary_repository_only':True,'network_model_calls':0}
        assert result['good_exit']==0 and result['mixed_exit']==1 and result['good_hook_passed'] and result['mixed_hook_failed'] and result['bypass_reported'],result
        print(json.dumps(result,indent=2))

if __name__=='__main__':main()
