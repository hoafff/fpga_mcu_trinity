# Authoritative reproducible build flow for Primer #2.
# The GUI stores synthesis process settings under generated impl/ state, so a
# clean exact-device build must recreate that state from this source-controlled
# script instead of inheriting a local Verilog 2001 process configuration.
if {[file exists impl]} {
    file delete -force impl
}

set_device -name GW2A-18C GW2A-LV18PG256C8/I7
add_file ../rtl/common/trinity_spi_pkg.sv
add_file ../rtl/crypto/ascon_aead128_decrypt.sv
add_file ../rtl/io/spi_packet_endpoint.sv
add_file ../rtl/io/uart_rx_byte.sv
add_file ../rtl/io/uart_frame_receiver.sv
add_file ../rtl/core/primer2_command_core.sv
add_file ../rtl/primer2_top.sv
add_file ../constraints/primer2.cst
add_file ../constraints/primer2.sdc
set_option -top_module primer2_top
set_option -verilog_std sysv2017
set_option -include_path {../rtl/core}
set_option -resource_sharing 1
set_option -replicate_resources 0
set_option -output_base_name trinity_primer2
run all
