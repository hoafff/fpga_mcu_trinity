create_clock -name sys_clk_27m -period 37.037 [get_ports {sys_clk_i}]

# These six inputs are asynchronous to sys_clk_i and enter explicit two-flop
# synchronizers. Cut only each input-to-first-stage (*_meta) arc. The
# first-stage-to-second-stage (*_sync) paths and all functional logic remain timed.
set_false_path -from [get_ports {spi_sck_i}] -to [get_regs {*sck_meta*}]
set_false_path -from [get_ports {spi_mosi_i}] -to [get_regs {*mosi_meta*}]
set_false_path -from [get_ports {spi_cs_ni}] -to [get_regs {*cs_meta*}]
set_false_path -from [get_ports {fatal_latched_i}] -to [get_regs {*fatal_meta*}]
set_false_path -from [get_ports {secure_enable_i}] -to [get_regs {*secure_meta*}]
set_false_path -from [get_ports {zeroize_ni}] -to [get_regs {*zeroize_meta*}]
