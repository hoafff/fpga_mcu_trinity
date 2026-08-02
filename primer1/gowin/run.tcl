set_device -name GW2A-18C GW2A-LV18PG256C8/I7
add_file ../rtl/common/trinity_spi_pkg.sv
add_file ../rtl/crypto/mlkem_poly_accel.sv
add_file ../rtl/crypto/ascon_aead128_encrypt.sv
add_file ../rtl/io/spi_packet_endpoint.sv
add_file ../rtl/io/uart_tx_byte.sv
add_file ../rtl/io/uart_frame_tx.sv
add_file ../rtl/core/primer1_command_core.sv
add_file ../rtl/primer1_top.sv
add_file ../constraints/primer1.cst
add_file ../constraints/primer1.sdc
set_option -top_module primer1_top
set_option -verilog_std sysv2017
set_option -include_path {../rtl/core}
set_option -resource_sharing 1
set_option -replicate_resources 0
set_option -output_base_name trinity_primer1
run all
