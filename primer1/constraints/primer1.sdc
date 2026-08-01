create_clock -name sys_clk_27m -period 37.037 [get_ports {sys_clk_i}]
# SPI and Tiny controls enter explicit two-flop synchronizers in sys_clk_i domain.
set_false_path -from [get_ports {spi_sck_i spi_mosi_i spi_cs_ni fatal_latched_i secure_enable_i zeroize_ni}] -to [all_registers]
