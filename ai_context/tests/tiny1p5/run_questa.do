transcript on
vlib work
vlog -sv tiny1p5/rtl/fpst_sync_bit.sv tiny1p5/rtl/fpst_sync_rise_pulse.sv tiny1p5/rtl/fpst_ms_tick.sv tiny1p5/rtl/fpst_debounce_active_low.sv tiny1p5/rtl/fpst_heartbeat_watchdog.sv tiny1p5/rtl/fpst_supervisor_core.sv tiny1p5/rtl/supervisor_top.sv ai_context/testbenches/supervisor/tb_fpst_heartbeat_watchdog.sv ai_context/testbenches/supervisor/tb_fpst_debounce_active_low.sv ai_context/testbenches/supervisor/tb_fpst_supervisor_core.sv ai_context/testbenches/supervisor/tb_supervisor_top_open_drain.sv
vsim -c tb_fpst_heartbeat_watchdog -do "run -all; quit -f"
vsim -c tb_fpst_debounce_active_low -do "run -all; quit -f"
vsim -c tb_fpst_supervisor_core -do "run -all; quit -f"
vsim -c tb_supervisor_top_open_drain -do "run -all; quit -f"
