`timescale 1ns/1ps
module tb_uart_frame_receiver;
  logic clk=0,rst_n=0,abort=0,accept=1,pending=0;
  logic byte_valid=0,framing=0; logic [7:0] byte_in=0;
  logic frame_valid,timeout,error,pending_drop,blocked; logic [511:0] body; logic [2:0] state;
  integer i, pulses;
  always #5 clk=~clk;
  uart_frame_receiver #(.CLOCK_HZ(1000000),.INTERBYTE_TIMEOUT_MS(1),.INTERFRAME_IDLE_US(10)) dut(
    .clk_i(clk),.rst_ni(rst_n),.abort_i(abort),.accept_enable_i(accept),
    .result_pending_i(pending),.byte_valid_i(byte_valid),.byte_i(byte_in),
    .framing_error_i(framing),.frame_valid_o(frame_valid),.frame_body_o(body),
    .frame_timeout_o(timeout),.framing_error_o(error),.pending_drop_o(pending_drop),
    .blocked_frame_o(blocked),.rx_state_o(state));
  task automatic push(input [7:0] b); begin @(negedge clk);byte_in=b;byte_valid=1;@(negedge clk);byte_valid=0; end endtask
  task automatic idle_gap; begin repeat(12)@(posedge clk); end endtask
  initial begin
    repeat(4)@(posedge clk);rst_n=1;idle_gap();
    push(8'hA5);push(8'h5A);
    for(i=0;i<64;i=i+1) begin
      if(i==10) push(8'hA5); else if(i==11) push(8'h5A); else push(i[7:0]);
    end
    wait(frame_valid); if(body[8*10+:8]!=8'hA5 || body[8*11+:8]!=8'h5A)$fatal(1,"body resync corruption");
    $display("PASS frame_66_bytes_body_sync_not_resync");
    idle_gap();push(8'hA5);push(8'h5A);push(8'h01);wait(timeout);
    $display("PASS frame_interbyte_timeout_drop");
    idle_gap();push(8'hA5);push(8'h5A);push(8'h01);@(negedge clk);framing=1;@(negedge clk);framing=0;wait(error);
    $display("PASS frame_uart_error_drop");
    idle_gap();accept=0;pending=1;pulses=0;
    fork begin repeat(3)begin push(8'hA5);push(8'h5A);end end begin repeat(100)begin @(posedge clk);if(pending_drop)pulses=pulses+1;end end join
    if(pulses!=1)$fatal(1,"pending drop counted %0d times",pulses);
    $display("PASS result_pending_drop_once_per_candidate_window");
    pending=0; idle_gap(); push(8'hA5);push(8'h5A);wait(blocked);
    $display("PASS inactive_session_frame_blocked");
    $finish;
  end
endmodule
