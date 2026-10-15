#!/usr/bin/env python3
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
protocol=json.loads((HERE/'protocol.json').read_text())
source=output/'sources';source.mkdir()
names=['protocol.json','benchmark.php','test_harness.php','run.py','summarize.py','README.md','test_publication.py']
hashes={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in names}
for name in names:shutil.copy2(HERE/name,source/name)
manifest={'status':'running','protocol':protocol,'sourceSha256':hashes,'startedAt':datetime.now(timezone.utc).isoformat(),'plannedMeasuredSamples':90,'plannedWarmupSamples':18,'scope':'Synthetic same-engine query/index remediation, not version migration','command':['docker','run','--network','none','--platform','linux/arm64','--cpus','2','--memory','1g',protocol['image']]}
def save(): (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
save()
base=['docker','run','--rm','--network','none','--platform','linux/arm64','--cpus','2','--memory','1g','-v',f'{source}:/lab:ro',protocol['image'],'php','-d','memory_limit=768M']
try:
    test=subprocess.run(base+['/lab/test_harness.php'],text=True,capture_output=True,check=True)
    (output/'test-harness.txt').write_text(test.stdout+test.stderr)
    with (output/'raw.jsonl').open('w') as raw, (output/'stderr.txt').open('w') as stderr:
        subprocess.run(base+['/lab/benchmark.php'],check=True,stdout=raw,stderr=stderr)
    subprocess.run([sys.executable,str(source/'summarize.py'),'--directory',str(output)],check=True)
    manifest['status']='completed'
except Exception as error:
    manifest['status']='failed';manifest['failure']=str(error);raise
finally:
    manifest['finishedAt']=datetime.now(timezone.utc).isoformat();save()
    if manifest['status']=='completed':
        (output/'SHA256.json').write_text(json.dumps({str(p.relative_to(output)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.rglob('*')) if p.is_file() and p.name!='SHA256.json'},indent=2)+'\n')
