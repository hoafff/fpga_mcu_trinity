`timescale 1ns/1ps
module tb_primer2_top;
  logic clk=0,rst_n=0,sck=0,mosi=0,cs_n=1,uart_rx=1,fatal=0,secure=0,zeroize_n=1;
  wire miso; logic irq_n,fault,heartbeat; integer cycles; logic hb0;
  always #5 clk=~clk;
  primer2_top #(.CLOCK_HZ(1000),.UART_BAUD(100)) dut(
    .sys_clk_i(clk),.rst_ni(rst_n),.spi_sck_i(sck),.spi_mosi_i(mosi),.spi_miso_o(miso),
    .spi_cs_ni(cs_n),.irq_no(irq_n),.uart_rx_i(uart_rx),.fault_o(fault),
    .fatal_latched_i(fatal),.secure_enable_i(secure),.zeroize_ni(zeroize_n),.heartbeat_o(heartbeat));
  initial begin
    repeat(4)@(posedge clk);rst_n=1;repeat(5)@(posedge clk);
    if(miso!==1'bz)$fatal(1,"MISO not high-Z while deselected");
    if(!irq_n||fault)$fatal(1,"idle safety outputs invalid");
    cs_n=0;repeat(2)@(posedge clk);if(miso===1'bz)$fatal(1,"MISO disconnected while selected");cs_n=1;
    $display("PASS top_idle_miso_irq_safety");

    // Retained and authenticated application results are queried explicitly.
    // They must not hold the transport IRQ low after a mailbox is consumed.
    force dut.mailbox_pending=1'b0;
    force dut.retained_pending=1'b1;
    force dut.authenticated_pending=1'b1;
    force dut.event_pending=1'b1;
    #1;
    if(irq_n!==1'b1)$fatal(1,"retained/auth/event state incorrectly asserted IRQ_N");
    force dut.mailbox_pending=1'b1;
    #1;
    if(irq_n!==1'b0)$fatal(1,"response mailbox did not assert IRQ_N");
    release dut.mailbox_pending;
    release dut.retained_pending;
    release dut.authenticated_pending;
    release dut.event_pending;
    #1;
    $display("PASS top_irq_mailbox_only");

    hb0=heartbeat;repeat(120)@(posedge clk);if(heartbeat===hb0)$fatal(1,"heartbeat did not toggle");
    $display("PASS top_heartbeat");
    @(negedge clk);fatal=1;repeat(6)@(posedge clk);@(negedge clk);fatal=0;cycles=0;
    while((!fault||dut.session_state!=4'd8)&&cycles<100)begin @(posedge clk);cycles=cycles+1;end
    if(!fault||dut.session_state!=4'd8)$fatal(1,"fatal did not enter fault locked");
    $display("PASS top_fatal_fail_closed");
    $finish;
  end
endmodule
