#!/usr/bin/env python3
"""Conservative source-policy and lexical checks used before vendor compilation."""
from __future__ import annotations
import re, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SV=list((ROOT/'rtl').rglob('*.sv'))
INCLUDE_RE=re.compile(r'^\s*`include\s+"([^"]+)"\s*$',re.M)

def read_expanded(path:Path, seen:tuple[Path,...]=())->str:
    path=path.resolve()
    if path in seen: raise RuntimeError(f'cyclic include: {path}')
    text=path.read_text()
    def repl(match:re.Match[str])->str:
        return read_expanded(path.parent/match.group(1), seen+(path,))
    return INCLUDE_RE.sub(repl,text)
PAIR={'begin':'end','case':'endcase','module':'endmodule','function':'endfunction','task':'endtask','package':'endpackage','generate':'endgenerate'}
CLOSERS=set(PAIR.values())

def strip(text:str)->str:
    text=re.sub(r'/\*.*?\*/',' ',text,flags=re.S)
    text=re.sub(r'//[^\n]*',' ',text)
    text=re.sub(r'"(?:\\.|[^"\\])*"','""',text)
    return text

def check_file(path:Path)->list[str]:
    text=read_expanded(path)
    clean=strip(text)
    errors=[]
    stack=[]
    # Parentheses/brackets/braces.
    pairs={')':'(',']':'[','}':'{'}
    chars=[]
    for n,ch in enumerate(clean):
        if ch in '([{':chars.append((ch,n))
        elif ch in pairs:
            if not chars or chars[-1][0]!=pairs[ch]:errors.append(f'{path}: unmatched {ch} at {n}')
            else:chars.pop()
    if chars:errors.append(f'{path}: unclosed delimiters {chars[-3:]}')
    # Block keywords. Treat fork/join separately and ignore end labels.
    toks=re.findall(r'\b(?:module|endmodule|package|endpackage|function|endfunction|task|endtask|generate|endgenerate|case|casez|casex|endcase|begin|end|fork|join|join_any|join_none)\b',clean)
    for tok in toks:
        if tok in ('casez','casex'):tok='case'
        if tok=='fork':stack.append('join')
        elif tok in ('join','join_any','join_none'):
            if not stack or stack[-1]!='join':errors.append(f'{path}: unmatched {tok}')
            else:stack.pop()
        elif tok in PAIR:stack.append(PAIR[tok])
        elif tok in CLOSERS:
            if not stack or stack[-1]!=tok:errors.append(f'{path}: unmatched {tok}, expected {stack[-1] if stack else None}')
            else:stack.pop()
    if stack:errors.append(f'{path}: unclosed blocks {stack[-8:]}')
    if '\t' in text:errors.append(f'{path}: tab character')
    for i,line in enumerate(text.splitlines(),1):
        if line.rstrip()!=line:errors.append(f'{path}:{i}: trailing whitespace')
    return errors

def main()->int:
    errors=[]
    for path in SV:errors.extend(check_file(path))
    joined='\n'.join(read_expanded(p).lower() for p in SV)
    for bad in ('placeholder','bypass tag','todo','fixme'):
        if bad in joined:errors.append(f'forbidden deployment marker: {bad}')
    top=(ROOT/'rtl/primer2_top.sv').read_text()
    for port in ('heartbeat_o','fault_o','irq_no','secure_enable_i','zeroize_ni','fatal_latched_i','uart_rx_i'):
        if port not in top:errors.append(f'missing safety/deployment port {port}')

    core=read_expanded(ROOT/'rtl/core/primer2_command_core.sv')
    decrypt=(ROOT/'rtl/crypto/ascon_aead128_decrypt.sv').read_text()
    receiver=(ROOT/'rtl/io/uart_frame_receiver.sv').read_text()
    required_core_fragments=(
        "fbyte(candidate_frame,1) != 8'h02",
        "last_accepted_sequence <= candidate_sequence",
        "candidate_sequence != last_accepted_sequence + 1'b1",
        "auth_result_plaintext <= decrypt_plaintext",
        "decrypt_abort <= 1'b1",
    )
    for fragment in required_core_fragments:
        if fragment not in core:errors.append(f'missing fail-closed core invariant: {fragment}')
    for secret in ("k0 <= '0", "k1 <= '0", "ad_reg <= '0", "ct_reg <= '0",
                   "tag_reg <= '0", "plaintext_o <= '0"):
        if decrypt.count(secret) < 2:
            errors.append(f'Ascon secret scrub is not present on reset/abort: {secret}')
    if "((x3 ^ k0) == tag_reg[63:0])" not in decrypt or        "((x4 ^ k1) == tag_reg[127:64])" not in decrypt:
        errors.append('full 128-bit Ascon tag comparison not found')
    if "RX_HUNT_SYNC" not in receiver or "RX_RECEIVE_BODY" not in receiver:
        errors.append('UART receiver sync/body separation not found')

    # Exact-device project contract. These checks do not claim a vendor build;
    # they prevent the committed deployment project from silently drifting away
    # from the qualified Primer #1 device/tool conventions.
    gowin_tcl=(ROOT/'gowin/run.tcl').read_text()
    gowin_project=(ROOT/'gowin/trinity_primer2.gprj').read_text()
    sdc=(ROOT/'constraints/primer2.sdc').read_text()
    cst=(ROOT/'constraints/primer2.cst').read_text()
    required_tcl_fragments=(
        'set_device -name GW2A-18C GW2A-LV18PG256C8/I7',
        'set_option -top_module primer2_top',
        'set_option -verilog_std sysv2017',
        'set_option -include_path {../rtl/core}',
        'set_option -output_base_name trinity_primer2',
        'run all',
    )
    for fragment in required_tcl_fragments:
        if fragment not in gowin_tcl:
            errors.append(f'missing Gowin deployment option: {fragment}')
    for fragment in ('name="GW2A-18C"', 'pn="GW2A-LV18PG256C8/I7"',
                     '>gw2a18c-011</Device>', 'primer2_top.sv',
                     'primer2.cst', 'primer2.sdc'):
        if fragment not in gowin_project:
            errors.append(f'missing exact-device project fragment: {fragment}')
    if 'create_clock -name sys_clk_27m -period 37.037' not in sdc:
        errors.append('27 MHz primary clock constraint missing')
    for port in ('sys_clk_i','rst_ni','spi_sck_i','spi_mosi_i','spi_miso_o',
                 'spi_cs_ni','irq_no','uart_rx_i','fault_o','fatal_latched_i',
                 'secure_enable_i','zeroize_ni','heartbeat_o'):
        if f'IO_LOC "{port}"' not in cst:
            errors.append(f'missing CST location for {port}')
    if errors:
        print('STATIC RTL CHECK FAIL');print('\n'.join(errors));return 1
    print(f'STATIC RTL CHECK PASS ({len(SV)} files)');return 0
if __name__=='__main__':raise SystemExit(main())
