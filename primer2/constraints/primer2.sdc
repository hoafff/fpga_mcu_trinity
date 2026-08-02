create_clock -name sys_clk_27m -period 37.037 [get_ports {sys_clk_i}]
# Cut only asynchronous input to the first explicit synchronizer stage.
set_false_path -from [get_ports {spi_sck_i}] -to [get_regs {*sck_meta*}]
set_false_path -from [get_ports {spi_mosi_i}] -to [get_regs {*mosi_meta*}]
set_false_path -from [get_ports {spi_cs_ni}] -to [get_regs {*cs_meta*}]
set_false_path -from [get_ports {uart_rx_i}] -to [get_regs {*rx_meta*}]
set_false_path -from [get_ports {fatal_latched_i}] -to [get_regs {*fatal_meta*}]
set_false_path -from [get_ports {secure_enable_i}] -to [get_regs {*secure_meta*}]
set_false_path -from [get_ports {zeroize_ni}] -to [get_regs {*zeroize_meta*}]
