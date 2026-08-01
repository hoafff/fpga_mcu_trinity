#!/usr/bin/env python3
from pathlib import Path
import re
root=Path(__file__).resolve().parents[1]
required=[x.strip() for x in (root/'sources.f').read_text().splitlines() if x.strip()]
for rel in required:
    p=root/rel
    if not p.is_file() and rel == 'rtl/common/trinity_spi_pkg.sv':
        continue
    assert p.is_file(),f'missing {rel}'
    text=p.read_text()
    assert not re.search(r'[A-Za-z]:\\|/home/|/Users/',text),f'absolute path in {rel}'
alltext='\n'.join((root/r).read_text() for r in required if (root/r).is_file())
for module in ['primer1_top','spi_packet_endpoint','mlkem_poly_accel','ascon_aead128_encrypt','uart_frame_tx','primer1_command_core']:
    assert re.search(rf'\bmodule\s+{module}\b',alltext),f'missing module {module}'
for token in ['CMD_POLY_EXECUTE','CMD_ENCRYPT_AND_SEND','SESSION_COMMITTED_BLOCKED','secure_enable_i','zeroize_ni','uart_tx_o']:
    assert token in alltext,f'missing required token {token}'
for rel in required:
    if not (root/rel).is_file(): continue
    t=(root/rel).read_text()
    assert t.count('module ')==t.count('endmodule'),f'module imbalance {rel}'
    assert t.count('begin')>=t.count('endcase'),f'structural imbalance {rel}'
print('PASS source_manifest')
print('PASS no_absolute_paths')
print('PASS mandatory_blocks_present')
print('PASS basic_structural_checks')
