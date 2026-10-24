"""Compara upload real via loopback, com ACK, processamento e hash de decisões."""
import asyncio
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import httpx
import websockets
PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
sys.path.insert(0, str(PROJECT))
from backend.application.sample_batches import iterar_linhas_lote_sintetico
from benchmarks.run_stream_benchmark import get_process_memory_mb_by_pid

async def measure(path, port):
    size = path.stat().st_size
    async with websockets.connect(f'ws://127.0.0.1:{port}/api/simulations/stream', max_size=16*1024*1024, compression=None) as ws:
        await ws.send(json.dumps({'type':'start','filename':'sintetico.csv','size_bytes':size,'protocol_version':1}))
        ready=json.loads(await ws.recv());assert ready['type']=='ready'
        acked=0; sent=0; changed=asyncio.Event(); complete=asyncio.Event(); envelope=None; upload_end=None
        started=time.perf_counter()
        async def receive():
            nonlocal acked, envelope, upload_end
            async for raw in ws:
                msg=json.loads(raw)
                if msg['type']=='error':raise RuntimeError(msg.get('codigo'))
                if msg['type']=='ack':
                    acked=msg['received_bytes'];changed.set()
                    if acked==size:upload_end=time.perf_counter()
                if msg['type']=='complete':envelope=msg['simulation'];complete.set();return
        task=asyncio.create_task(receive())
        with path.open('rb') as source:
            while chunk:=source.read(ready['chunk_bytes']):
                while sent-acked+len(chunk)>ready['window_bytes']:
                    changed.clear()
                    if task.done():task.result()
                    await asyncio.wait_for(changed.wait(),30)
                await ws.send(chunk);sent+=len(chunk)
        while acked<size:
            changed.clear()
            if task.done():task.result()
            await asyncio.wait_for(changed.wait(),30)
        await ws.send(json.dumps({'type':'finish'}))
        await asyncio.wait_for(complete.wait(),300);await task
        elapsed=time.perf_counter()-started
        await ws.send(json.dumps({'type':'audit','request_id':'audit'}))
        audit=json.loads(await ws.recv());assert audit['type']=='audit'
        await ws.send(json.dumps({'type':'close'}))
        return {'upload_ack_seconds':round(upload_end-started,4),'total_seconds':round(elapsed,4),
            'chunk_bytes':ready['chunk_bytes'],'window_bytes':ready['window_bytes'],
            'total_itens':envelope['total_itens'],'aprovados':envelope['aprovados'],'recusados':envelope['recusados'],
            'total_liquido':envelope['total_liquido'],'decisions_sha256':audit['decisions_sha256']}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--rows', type=int, nargs='+', default=[100000,500000])
    parser.add_argument('--profiles', nargs='+', choices=['baseline','fast'], default=['baseline','fast'])
    parser.add_argument('--output', default='upload-benchmark')
    args=parser.parse_args()
    out=PROJECT/'.data'/args.output;out.mkdir(exist_ok=True)
    report={'started_utc':datetime.now(timezone.utc).isoformat(),'python':sys.version,'platform':platform.platform(),
        'scope':'upload até ACK total; hash compara status, primeiro código de recusa, nominal e líquido por linha; não valida todos os motivos',
        'runs_per_case':1,'results':{}}
    for rows in args.rows:
        path=out/f'synthetic-{rows}.csv'
        with path.open('w',encoding='utf-8',newline='') as stream:
            stream.writelines(iterar_linhas_lote_sintetico(rows, seed_tag=f'UPLOAD{rows}'))
        cases={}
        for profile,chunk,window in [('baseline',256*1024,4*1024*1024),('fast',768*1024,12*1024*1024)]:
            if profile not in args.profiles: continue
            source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (PROJECT/'backend').rglob('*.py') if 'tests' not in p.parts}
            env=dict(os.environ,STREAM_CHUNK_BYTES=str(chunk),STREAM_WINDOW_BYTES=str(window),LOG_LEVEL='ERROR')
            with (out/f'{rows}-{profile}.log').open('w',encoding='utf-8') as log:
                process=subprocess.Popen([sys.executable,str(PROJECT/'qa/serve_portal_review.py'),'--port','8017'],cwd=ROOT,env=env,stdout=log,stderr=log,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                try:
                    for attempt in range(100):
                        try:
                            if httpx.get('http://127.0.0.1:8017/api/health',timeout=1).status_code==200:break
                        except httpx.HTTPError:pass
                        time.sleep(.1)
                    result=asyncio.run(measure(path,8017))
                    runtime_pid=int(subprocess.check_output(['powershell','-NoProfile','-Command','(Get-NetTCPConnection -LocalPort 8017 -State Listen).OwningProcess'],text=True).strip())
                    _,peak=get_process_memory_mb_by_pid(runtime_pid);result['server_peak_rss_mb']=peak
                    result['source_hashes']=source_hashes
                    cases[profile]=result
                    print(json.dumps({'rows':rows,'profile':profile,**{k:v for k,v in result.items() if k!='source_hashes'}}),flush=True)
                finally:
                    if os.name=='nt':
                        subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                    else: process.terminate()
                    process.wait(timeout=15)
        if 'baseline' in cases and 'fast' in cases:
            for key in ['decisions_sha256','total_itens','aprovados','recusados','total_liquido']:
                assert cases['baseline'][key]==cases['fast'][key],key
            cases['upload_speedup']=round(cases['baseline']['upload_ack_seconds']/cases['fast']['upload_ack_seconds'],3)
        cases['file_bytes']=path.stat().st_size
        cases['file_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        report['results'][str(rows)]=cases
        (out/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('RESULTADO '+str(out/'results.json'),flush=True)

if __name__=='__main__':main()
