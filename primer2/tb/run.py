#!/usr/bin/env python3
"""Run Primer #2 reference checks and self-checking RTL regression."""
from __future__ import annotations
import shutil, subprocess, sys, tempfile
from pathlib import Path

def run(cmd:list[str],cwd:Path)->None:
    result=subprocess.run(cmd,cwd=cwd,text=True,capture_output=True,check=False)
    if result.stdout: print(result.stdout,end="")
    if result.stderr: print(result.stderr,end="",file=sys.stderr)
    if result.returncode: raise SystemExit(result.returncode)

def main()->int:
    root=Path(__file__).resolve().parents[1];repo=root.parent
    run([sys.executable,str(root/'scripts/static_rtl_checks.py')],repo)
    run([sys.executable,str(root/'scripts/reference_checks.py')],repo)
    if not shutil.which('iverilog') or not shutil.which('vvp'):
        print('ERROR: iverilog and vvp are required',file=sys.stderr);return 2
    sources=[root/line.strip() for line in (root/'sources.f').read_text().splitlines() if line.strip()]
    tops=['tb_ascon_aead128_decrypt','tb_uart_rx_byte','tb_uart_frame_receiver','tb_spi_packet_endpoint','tb_primer2_command_core','tb_primer2_top']
    failures=[]
    with tempfile.TemporaryDirectory(prefix='primer2-rtl-') as td:
      for top in tops:
        out=Path(td)/(top+'.vvp')
        cmd=['iverilog','-g2012','-Wall','-Wno-timescale','-I',str(root/'rtl/core'),'-s',top,'-o',str(out),*(str(x) for x in sources),str(root/'tb'/(top+'.sv'))]
        print(f'\n=== COMPILE {top} ===');r=subprocess.run(cmd,cwd=repo,text=True,capture_output=True)
        if r.stdout:print(r.stdout,end='')
        if r.stderr:print(r.stderr,end='',file=sys.stderr)
        if r.returncode:failures.append(top+': compile');continue
        print(f'=== RUN {top} ===');r=subprocess.run(['vvp',str(out)],cwd=repo,text=True,capture_output=True)
        if r.stdout:print(r.stdout,end='')
        if r.stderr:print(r.stderr,end='',file=sys.stderr)
        if r.returncode:failures.append(top+': simulation')
    if failures:
      print('\nPRIMER2 RTL REGRESSION FAIL');[print('FAIL '+x) for x in failures];return 1
    print('\nPRIMER2 RTL REGRESSION PASS');return 0
if __name__=='__main__':raise SystemExit(main())
