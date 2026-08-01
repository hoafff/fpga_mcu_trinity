module primer1_command_core #(
    parameter integer CLOCK_HZ = 27000000,
    parameter integer UART_BAUD = 115200,
    parameter logic [31:0] BUILD_ID = 32'h5031_0001
) (
    input  logic         clk_i,
    input  logic         rst_ni,
    input  logic         secure_enable_i,
    input  logic         zeroize_ni,
    input  logic         fatal_latched_i,

    input  logic         request_valid_i,
    input  logic [7:0]   request_command_i,
    input  logic [7:0]   request_flags_i,
    input  logic [15:0]  request_txid_i,
    input  logic [15:0]  request_payload_length_i,
    input  logic [527:0] request_payload_i,

    input  logic         transport_error_valid_i,
    input  logic [7:0]   transport_error_command_i,
    input  logic [15:0]  transport_error_txid_i,
    input  logic [15:0]  transport_error_code_i,

    output logic         response_commit_o,
    output logic [7:0]   response_command_o,
    output logic [7:0]   response_flags_o,
    output logic [15:0]  response_txid_o,
    output logic [15:0]  response_payload_length_o,
    output logic [527:0] response_payload_o,
    input  logic         response_ready_i,
    input  logic         mailbox_pending_i,

    output logic         retained_result_pending_o,
    output logic         irq_event_pending_o,
    output logic         uart_tx_o,
    output logic         heartbeat_o,
    output logic         fault_o,
    output logic [3:0]   session_state_o,
    output logic [2:0]   operation_state_o
);
  import trinity_spi_pkg::*;

  localparam logic [31:0] CAPABILITIES =
      CAP_SELF_TEST | CAP_ZEROIZE | CAP_TRANSACTION_RECONCILIATION |
      CAP_SESSION_STAGE_COMMIT | CAP_NTT | CAP_INTT | CAP_BASEMUL |
      CAP_ASCON_ENCRYPT | CAP_UART_TX | CAP_DIAGNOSTICS;
  localparam integer HEARTBEAT_CYCLES = CLOCK_HZ / 10;
  localparam logic [191:0] ASCON_KAT_CT =
      192'h64AE2CC0931A7A9101C4872B0A040525B17FC6E9FD6D89E6;
  localparam logic [127:0] ASCON_KAT_TAG =
      128'h4B9E81835266C56C0884E76F29D95FE8;

  typedef enum logic [4:0] {
    C_IDLE,
    C_WRITE_CHUNK,
    C_READ_PRIME,
    C_READ_CHUNK,
    C_READ_RESP,
    C_WAIT_POLY,
    C_WAIT_ASCON,
    C_WAIT_UART,
    C_ZEROIZE_WAIT,
    C_ST_ASCON_WAIT,
    C_ST_ZERO_WAIT,
    C_ST_NTT_WAIT,
    C_ST_NTT_SCAN,
    C_ST_INTT_WAIT,
    C_ST_INTT_SCAN,
    C_ST_BM_WAIT,
    C_ST_BM_SCAN
  } core_state_e;
  core_state_e core_state;

  session_state_e session_state;
  operation_state_e operation_state;
  logic self_test_pass;
  logic fault_latched;
  logic [31:0] diagnostic_summary;
  logic [15:0] last_error;
  logic [15:0] active_transaction_id;

  logic [31:0] staged_session_id, active_session_id;
  logic [127:0] staged_key, active_key;
  logic [63:0] staged_nonce_prefix, active_nonce_prefix;
  logic staged_valid, active_valid;
  logic [63:0] sequence_number;

  logic telemetry_loaded;
  logic [7:0] telemetry_message_type;
  logic [15:0] telemetry_flags, telemetry_source_id;
  logic [191:0] telemetry_plaintext;
  logic [255:0] telemetry_request_image;

  logic retained_valid;
  logic [15:0] retained_txid;
  logic [7:0] retained_command;
  logic [31:0] retained_fingerprint;
  transaction_state_e retained_state;
  logic [15:0] retained_code;
  logic [15:0] retained_data_length;
  logic [127:0] retained_data;

  logic [7:0] poly_operation;
  logic [7:0] poly_mask_a, poly_mask_b;
  logic [31:0] chunk_fingerprint_a [0:7];
  logic [31:0] chunk_fingerprint_b [0:7];
  logic [7:0] chunk_valid_a, chunk_valid_b;

  logic poly_load_we, poly_load_slot;
  logic [7:0] poly_load_addr;
  logic [15:0] poly_load_data;
  logic poly_read_slot;
  logic [7:0] poly_read_addr;
  logic [15:0] poly_read_data;
  logic poly_start;
  logic [1:0] poly_start_operation;
  logic poly_busy, poly_done, poly_error;
  logic poly_zeroize, poly_zeroize_busy, poly_zeroize_done;

  mlkem_poly_accel u_poly (
    .clk_i(clk_i), .rst_ni(rst_ni),
    .load_we_i(poly_load_we), .load_slot_i(poly_load_slot),
    .load_addr_i(poly_load_addr), .load_data_i(poly_load_data),
    .read_slot_i(poly_read_slot), .read_addr_i(poly_read_addr),
    .read_data_o(poly_read_data), .start_i(poly_start),
    .operation_i(poly_start_operation), .busy_o(poly_busy),
    .done_o(poly_done), .error_o(poly_error),
    .zeroize_i(poly_zeroize), .zeroize_busy_o(poly_zeroize_busy),
    .zeroize_done_o(poly_zeroize_done)
  );

  logic ascon_start, ascon_busy, ascon_done;
  logic crypto_abort;
  logic [127:0] ascon_key_input, ascon_nonce_input;
  logic [191:0] ascon_ad_input, ascon_pt_input;
  logic [191:0] ascon_ciphertext;
  logic [127:0] ascon_tag;

  ascon_aead128_encrypt u_ascon (
    .clk_i(clk_i), .rst_ni(rst_ni), .start_i(ascon_start), .abort_i(crypto_abort),
    .key_i(ascon_key_input), .nonce_i(ascon_nonce_input),
    .ad_i(ascon_ad_input), .plaintext_i(ascon_pt_input),
    .busy_o(ascon_busy), .done_o(ascon_done),
    .ciphertext_o(ascon_ciphertext), .tag_o(ascon_tag)
  );

  logic uart_start, uart_busy, uart_done;
  logic uart_abort;
  logic [527:0] uart_frame;
  uart_frame_tx #(.CLOCK_HZ(CLOCK_HZ), .BAUD(UART_BAUD)) u_uart (
    .clk_i(clk_i), .rst_ni(rst_ni), .start_i(uart_start), .abort_i(uart_abort),
    .frame_i(uart_frame), .tx_o(uart_tx_o), .busy_o(uart_busy), .done_o(uart_done)
  );

  logic [21:0] heartbeat_counter;
  logic [5:0] chunk_word_index;
  logic saved_chunk_slot;
  logic [2:0] saved_chunk_index;
  logic [31:0] saved_chunk_fingerprint;
  logic [511:0] saved_chunk_data;
  logic [5:0] read_word_index;
  logic saved_read_slot;
  logic [2:0] saved_read_chunk;
  logic [527:0] read_response_data;
  logic [7:0] selftest_index;
  logic zeroize_from_command;
  logic zeroize_due_to_fault;
  logic zeroize_memory_done;
  logic [191:0] crypto_ad_snapshot;

  function automatic logic [7:0] pbyte(input logic [527:0] p, input integer idx);
    pbyte = p[8*idx +: 8];
  endfunction

  function automatic logic [31:0] crc32c_byte(
      input logic [31:0] crc_in, input logic [7:0] data
  );
    logic [31:0] c;
    integer bi;
    begin
      c = crc_in ^ data;
      for (bi=0; bi<8; bi=bi+1)
        c = c[0] ? ((c >> 1) ^ 32'h82F63B78) : (c >> 1);
      crc32c_byte = c;
    end
  endfunction

  function automatic logic [31:0] request_fingerprint(
      input logic [7:0] command,
      input logic [7:0] flags,
      input logic [15:0] length,
      input logic [527:0] payload
  );
    logic [31:0] c;
    integer fi;
    begin
      c = 32'hFFFFFFFF;
      c = crc32c_byte(c,command);
      c = crc32c_byte(c,flags);
      c = crc32c_byte(c,length[15:8]);
      c = crc32c_byte(c,length[7:0]);
      for (fi=0; fi<SPI_MAX_PAYLOAD; fi=fi+1)
        if (fi < length) c = crc32c_byte(c,payload[8*fi +: 8]);
      request_fingerprint = ~c;
    end
  endfunction

  function automatic logic chunk_coefficients_valid(input logic [527:0] payload);
    integer vi;
    logic [15:0] coefficient;
    begin
      chunk_coefficients_valid = 1'b1;
      for (vi=0; vi<32; vi=vi+1) begin
        coefficient = {payload[8*(3+2*vi) +: 8],payload[8*(2+2*vi) +: 8]};
        if (coefficient > 16'd3328) chunk_coefficients_valid = 1'b0;
      end
    end
  endfunction

  function automatic logic is_retained_side_effect(input logic [7:0] command);
    begin
      case (command)
        CMD_RUN_SELF_TEST, CMD_ZEROIZE, CMD_COMMIT_SESSION,
        CMD_POLY_EXECUTE, CMD_ENCRYPT_AND_SEND: is_retained_side_effect = 1'b1;
        default: is_retained_side_effect = 1'b0;
      endcase
    end
  endfunction

  task automatic emit_response(
      input logic [7:0] command,
      input logic [15:0] txid,
      input logic [7:0] flags,
      input logic [15:0] length,
      input logic [527:0] data
  );
    begin
      response_command_o <= command;
      response_txid_o <= txid;
      response_flags_o <= flags;
      response_payload_length_o <= length;
      response_payload_o <= data;
      response_commit_o <= 1'b1;
    end
  endtask

  task automatic emit_empty_success(input logic [7:0] command, input logic [15:0] txid);
    begin
      emit_response(command,txid,FLAG_RESPONSE,16'd0,'0);
    end
  endtask

  task automatic emit_error(
      input logic [7:0] command,
      input logic [15:0] txid,
      input logic [15:0] code,
      input logic [15:0] detail
  );
    logic [527:0] ep;
    begin
      ep = '0;
      ep[7:0] = code[15:8]; ep[15:8] = code[7:0];
      ep[23:16] = {4'h0,session_state};
      ep[31:24] = {5'h0,operation_state};
      ep[39:32] = detail[15:8]; ep[47:40] = detail[7:0];
      emit_response(command,txid,FLAG_RESPONSE|FLAG_ERROR,16'd6,ep);
      last_error <= code;
    end
  endtask

  task automatic begin_retained(
      input logic [15:0] txid,
      input logic [7:0] command,
      input logic [31:0] fingerprint
  );
    begin
      retained_valid <= 1'b1;
      retained_txid <= txid;
      retained_command <= command;
      retained_fingerprint <= fingerprint;
      retained_state <= TXN_RUNNING;
      retained_code <= ERR_OK;
      retained_data_length <= 0;
      retained_data <= '0;
      active_transaction_id <= txid;
    end
  endtask

  task automatic complete_retained(
      input transaction_state_e final_state,
      input logic [15:0] code,
      input logic [15:0] length,
      input logic [127:0] data
  );
    begin
      retained_state <= final_state;
      retained_code <= code;
      retained_data_length <= length;
      retained_data <= data;
      active_transaction_id <= 0;
      if (code != ERR_OK) last_error <= code;
    end
  endtask

  logic [191:0] constructed_ad;
  logic [127:0] constructed_nonce;
  integer ai;
  always_comb begin
    constructed_ad = '0;
    constructed_ad[7:0] = PROTOCOL_VERSION;
    constructed_ad[15:8] = telemetry_message_type;
    constructed_ad[23:16] = telemetry_flags[15:8];
    constructed_ad[31:24] = telemetry_flags[7:0];
    constructed_ad[39:32] = active_session_id[31:24];
    constructed_ad[47:40] = active_session_id[23:16];
    constructed_ad[55:48] = active_session_id[15:8];
    constructed_ad[63:56] = active_session_id[7:0];
    for (ai=0; ai<8; ai=ai+1)
      constructed_ad[8*(8+ai) +: 8] = sequence_number[63-8*ai -: 8];
    constructed_ad[135:128] = 8'h00;
    constructed_ad[143:136] = 8'h18;
    constructed_ad[151:144] = telemetry_source_id[15:8];
    constructed_ad[159:152] = telemetry_source_id[7:0];

    constructed_nonce = '0;
    constructed_nonce[63:0] = active_nonce_prefix;
    for (ai=0; ai<8; ai=ai+1)
      constructed_nonce[8*(8+ai) +: 8] = sequence_number[63-8*ai -: 8];
  end

  assign crypto_abort = (session_state == SESSION_ZEROIZE_BUSY) || !zeroize_ni || fatal_latched_i;
  assign uart_abort = crypto_abort || !secure_enable_i;
  assign retained_result_pending_o = retained_valid;
  assign irq_event_pending_o = retained_valid;
  assign session_state_o = session_state;
  assign operation_state_o = operation_state;
  assign fault_o = fault_latched || (session_state == SESSION_FAULT_LOCKED);

  integer ci;
  logic [31:0] incoming_fingerprint;
  logic [527:0] rsp;
  logic [127:0] txn_data;
  logic [7:0] new_mask;

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      core_state <= C_IDLE;
      session_state <= SESSION_SELF_TEST_REQUIRED;
      operation_state <= OP_IDLE;
      self_test_pass <= 1'b0;
      fault_latched <= 1'b0;
      diagnostic_summary <= 0;
      last_error <= 0;
      active_transaction_id <= 0;
      staged_session_id <= 0; active_session_id <= 0;
      staged_key <= 0; active_key <= 0;
      staged_nonce_prefix <= 0; active_nonce_prefix <= 0;
      staged_valid <= 1'b0; active_valid <= 1'b0;
      sequence_number <= 64'd1;
      telemetry_loaded <= 1'b0;
      telemetry_message_type <= 0; telemetry_flags <= 0; telemetry_source_id <= 0;
      telemetry_plaintext <= 0; telemetry_request_image <= 0;
      retained_valid <= 1'b0; retained_txid <= 0; retained_command <= 0;
      retained_fingerprint <= 0; retained_state <= TXN_NONE; retained_code <= 0;
      retained_data_length <= 0; retained_data <= 0;
      poly_operation <= 0; poly_mask_a <= 0; poly_mask_b <= 0;
      chunk_valid_a <= 0; chunk_valid_b <= 0;
      for (ci=0; ci<8; ci=ci+1) begin
        chunk_fingerprint_a[ci] <= 0;
        chunk_fingerprint_b[ci] <= 0;
      end
      response_commit_o <= 1'b0; response_command_o <= 0; response_flags_o <= 0;
      response_txid_o <= 0; response_payload_length_o <= 0; response_payload_o <= 0;
      poly_load_we <= 1'b0; poly_load_slot <= 0; poly_load_addr <= 0; poly_load_data <= 0;
      poly_read_slot <= 0; poly_read_addr <= 0; poly_start <= 1'b0;
      poly_start_operation <= 0; poly_zeroize <= 1'b0;
      ascon_start <= 1'b0; ascon_key_input <= 0; ascon_nonce_input <= 0;
      ascon_ad_input <= 0; ascon_pt_input <= 0;
      uart_start <= 1'b0; uart_frame <= 0;
      heartbeat_counter <= 0; heartbeat_o <= 1'b0;
      chunk_word_index <= 0; saved_chunk_slot <= 0; saved_chunk_index <= 0;
      saved_chunk_fingerprint <= 0; saved_chunk_data <= 0;
      read_word_index <= 0; saved_read_slot <= 0; saved_read_chunk <= 0;
      read_response_data <= 0; selftest_index <= 0;
      zeroize_from_command <= 1'b0; zeroize_due_to_fault <= 1'b0;
      zeroize_memory_done <= 1'b0;
      crypto_ad_snapshot <= 0;
    end else begin
      response_commit_o <= 1'b0;
      poly_load_we <= 1'b0;
      poly_start <= 1'b0;
      poly_zeroize <= 1'b0;
      ascon_start <= 1'b0;
      uart_start <= 1'b0;

      if (heartbeat_counter == HEARTBEAT_CYCLES-1) begin
        heartbeat_counter <= 0;
        heartbeat_o <= ~heartbeat_o;
      end else heartbeat_counter <= heartbeat_counter + 1'b1;

      if (session_state == SESSION_COMMITTED_BLOCKED && secure_enable_i && !fatal_latched_i) begin
        session_state <= SESSION_ACTIVE;
      end

      if ((fatal_latched_i || !zeroize_ni ||
           (session_state == SESSION_ACTIVE && !secure_enable_i)) &&
          core_state != C_ZEROIZE_WAIT && session_state != SESSION_ZEROIZE_BUSY &&
          session_state != SESSION_FAULT_LOCKED) begin
        fault_latched <= fault_latched | fatal_latched_i;
        zeroize_due_to_fault <= fatal_latched_i;
        zeroize_from_command <= 1'b0;
        zeroize_memory_done <= 1'b0;
        session_state <= SESSION_ZEROIZE_BUSY;
        operation_state <= OP_IDLE;
        staged_key <= 0; active_key <= 0;
        staged_nonce_prefix <= 0; active_nonce_prefix <= 0;
        staged_session_id <= 0; active_session_id <= 0;
        staged_valid <= 1'b0; active_valid <= 1'b0;
        telemetry_loaded <= 1'b0; telemetry_plaintext <= 0;
        sequence_number <= 64'd1;
        retained_valid <= 1'b0;
        poly_zeroize <= 1'b1;
        core_state <= C_ZEROIZE_WAIT;
      end else begin
        case (core_state)
          C_IDLE: begin
            if (transport_error_valid_i && response_ready_i) begin
              if (transport_error_code_i == ERR_BAD_CRC)
                diagnostic_summary <= diagnostic_summary | DIAG_CRC;
              else
                diagnostic_summary <= diagnostic_summary | DIAG_TRANSPORT;
              emit_error(transport_error_command_i,transport_error_txid_i,
                         transport_error_code_i,16'd0);
            end else if (request_valid_i && response_ready_i) begin
              incoming_fingerprint = request_fingerprint(
                  request_command_i,request_flags_i,request_payload_length_i,request_payload_i);

              if (is_retained_side_effect(request_command_i) && retained_valid && request_command_i != CMD_ZEROIZE) begin
                if (request_txid_i == retained_txid &&
                    request_command_i == retained_command &&
                    incoming_fingerprint == retained_fingerprint) begin
                  emit_empty_success(request_command_i,request_txid_i);
                end else if (request_txid_i == retained_txid) begin
                  diagnostic_summary <= diagnostic_summary | DIAG_TRANSACTION_CONFLICT;
                  emit_error(request_command_i,request_txid_i,ERR_TRANSACTION_CONFLICT,0);
                end else begin
                  emit_error(request_command_i,request_txid_i,ERR_RESULT_PENDING,retained_txid);
                end
              end else begin
                case (request_command_i)
                  CMD_GET_INFO: begin
                    if (request_payload_length_i != 0) emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,0);
                    else begin
                      rsp = '0;
                      rsp[7:0] = TARGET_PRIMER1;
                      rsp[15:8] = PROTOCOL_VERSION;
                      rsp[23:16] = CAPABILITIES[31:24]; rsp[31:24] = CAPABILITIES[23:16];
                      rsp[39:32] = CAPABILITIES[15:8]; rsp[47:40] = CAPABILITIES[7:0];
                      rsp[55:48] = BUILD_ID[31:24]; rsp[63:56] = BUILD_ID[23:16];
                      rsp[71:64] = BUILD_ID[15:8]; rsp[79:72] = BUILD_ID[7:0];
                      emit_response(request_command_i,request_txid_i,FLAG_RESPONSE,16'd12,rsp);
                    end
                  end

                  CMD_GET_STATUS: begin
                    if (request_payload_length_i != 0) emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,0);
                    else begin
                      rsp = '0;
                      rsp[7:0] = {4'h0,session_state};
                      rsp[15:8] = {5'h0,operation_state};
                      rsp[23:16] = (mailbox_pending_i ? PENDING_RESPONSE_MAILBOX : 0) |
                                      (retained_valid ? PENDING_SIDE_EFFECT_RESULT : 0);
                      rsp[31:24] = (self_test_pass ? SECURE_SELF_TEST_PASS : 0) |
                                      (staged_valid ? SECURE_SESSION_STAGED : 0) |
                                      (secure_enable_i ? SECURE_ENABLE : 0) |
                                      ((session_state==SESSION_ZEROIZE_BUSY) ? SECURE_ZEROIZE_BUSY : 0) |
                                      (fault_o ? SECURE_FAULT_LOCKED : 0);
                      rsp[39:32]=active_session_id[31:24]; rsp[47:40]=active_session_id[23:16];
                      rsp[55:48]=active_session_id[15:8]; rsp[63:56]=active_session_id[7:0];
                      rsp[71:64]=last_error[15:8]; rsp[79:72]=last_error[7:0];
                      rsp[87:80]=active_transaction_id[15:8]; rsp[95:88]=active_transaction_id[7:0];
                      rsp[103:96]=diagnostic_summary[31:24]; rsp[111:104]=diagnostic_summary[23:16];
                      rsp[119:112]=diagnostic_summary[15:8]; rsp[127:120]=diagnostic_summary[7:0];
                      emit_response(request_command_i,request_txid_i,FLAG_RESPONSE,16'd16,rsp);
                    end
                  end

                  CMD_RUN_SELF_TEST: begin
                    if (request_payload_length_i != 4 || pbyte(request_payload_i,2)!=0 || pbyte(request_payload_i,3)!=0)
                      emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,0);
                    else if (session_state != SESSION_SELF_TEST_REQUIRED && session_state != SESSION_READY_NO_SESSION)
                      emit_error(request_command_i,request_txid_i,ERR_BAD_STATE,0);
                    else begin
                      begin_retained(request_txid_i,request_command_i,incoming_fingerprint);
                      session_state <= SESSION_SELF_TEST_RUNNING;
                      operation_state <= OP_EXECUTING;
                      ascon_key_input <= 0; ascon_nonce_input <= 0;
                      ascon_ad_input <= 0; ascon_pt_input <= 0;
                      ascon_start <= 1'b1;
                      emit_empty_success(request_command_i,request_txid_i);
                      core_state <= C_ST_ASCON_WAIT;
                    end
                  end

                  CMD_GET_TXN_RESULT: begin
                    if (request_payload_length_i != 2) emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,0);
                    else if (!retained_valid || {pbyte(request_payload_i,0),pbyte(request_payload_i,1)} != retained_txid)
                      emit_error(request_command_i,request_txid_i,ERR_RESULT_NOT_READY,0);
                    else begin
                      rsp='0;
                      rsp[7:0]=retained_txid[15:8]; rsp[15:8]=retained_txid[7:0];
                      rsp[23:16]={5'h0,retained_state}; rsp[31:24]=retained_command;
                      rsp[39:32]=retained_code[15:8]; rsp[47:40]=retained_code[7:0];
                      rsp[55:48]=retained_data_length[15:8]; rsp[63:56]=retained_data_length[7:0];
                      for (ci=0;ci<16;ci=ci+1)
                        if (ci<retained_data_length) rsp[8*(10+ci)+:8]=retained_data[8*ci+:8];
                      emit_response(request_command_i,request_txid_i,FLAG_RESPONSE,
                                    16'd10+retained_data_length,rsp);
                    end
                  end

                  CMD_RETIRE_TXN_RESULT: begin
                    if (request_payload_length_i != 2) emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,0);
                    else if (retained_valid && {pbyte(request_payload_i,0),pbyte(request_payload_i,1)}==retained_txid) begin
                      retained_valid<=1'b0; retained_state<=TXN_NONE; emit_empty_success(request_command_i,request_txid_i);
                    end else emit_empty_success(request_command_i,request_txid_i);
                  end

                  CMD_ZEROIZE: begin
                    if (request_payload_length_i != 4 || pbyte(request_payload_i,1)!=0 ||
                        pbyte(request_payload_i,2)!=0 || pbyte(request_payload_i,3)!=0)
                      emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,0);
                    else begin
                      begin_retained(request_txid_i,request_command_i,incoming_fingerprint);
                      zeroize_from_command <= 1'b1; zeroize_due_to_fault <= 1'b0;
                      zeroize_memory_done <= 1'b0;
                      session_state <= SESSION_ZEROIZE_BUSY; operation_state <= OP_IDLE;
                      staged_key<=0;active_key<=0;staged_nonce_prefix<=0;active_nonce_prefix<=0;
                      staged_session_id<=0;active_session_id<=0;staged_valid<=0;active_valid<=0;
                      telemetry_loaded<=0;telemetry_plaintext<=0;sequence_number<=64'd1;
                      poly_zeroize<=1'b1;
                      emit_empty_success(request_command_i,request_txid_i);
                      core_state<=C_ZEROIZE_WAIT;
                    end
                  end

                  CMD_STAGE_SESSION: begin
                    if (request_payload_length_i != 28) emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,0);
                    else if (!self_test_pass || (session_state!=SESSION_READY_NO_SESSION && session_state!=SESSION_STAGED))
                      emit_error(request_command_i,request_txid_i,ERR_BAD_STATE,0);
                    else begin
                      if (staged_valid && staged_session_id=={pbyte(request_payload_i,0),pbyte(request_payload_i,1),pbyte(request_payload_i,2),pbyte(request_payload_i,3)}) begin
                        if (staged_key==request_payload_i[8*4+:128] && staged_nonce_prefix==request_payload_i[8*20+:64])
                          emit_empty_success(request_command_i,request_txid_i);
                        else emit_error(request_command_i,request_txid_i,ERR_SESSION_ID_COLLISION,0);
                      end else if ((active_valid && active_session_id=={pbyte(request_payload_i,0),pbyte(request_payload_i,1),pbyte(request_payload_i,2),pbyte(request_payload_i,3)})) begin
                        emit_error(request_command_i,request_txid_i,ERR_SESSION_ID_COLLISION,0);
                      end else begin
                        staged_session_id<={pbyte(request_payload_i,0),pbyte(request_payload_i,1),pbyte(request_payload_i,2),pbyte(request_payload_i,3)};
                        staged_key<=request_payload_i[8*4+:128];
                        staged_nonce_prefix<=request_payload_i[8*20+:64];
                        staged_valid<=1'b1; session_state<=SESSION_STAGED;
                        emit_empty_success(request_command_i,request_txid_i);
                      end
                    end
                  end

                  CMD_COMMIT_SESSION: begin
                    if (request_payload_length_i != 4) emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,0);
                    else if (secure_enable_i)
                      emit_error(request_command_i,request_txid_i,ERR_COMMIT_REJECTED,0);
                    else if (!staged_valid || session_state!=SESSION_STAGED ||
                      {pbyte(request_payload_i,0),pbyte(request_payload_i,1),pbyte(request_payload_i,2),pbyte(request_payload_i,3)}!=staged_session_id)
                      emit_error(request_command_i,request_txid_i,ERR_BAD_SESSION,0);
                    else begin
                      begin_retained(request_txid_i,request_command_i,incoming_fingerprint);
                      active_session_id<=staged_session_id; active_key<=staged_key;
                      active_nonce_prefix<=staged_nonce_prefix; active_valid<=1'b1;
                      staged_key<=0; staged_nonce_prefix<=0; staged_valid<=1'b0;
                      sequence_number<=64'd1; session_state<=SESSION_COMMITTED_BLOCKED;
                      complete_retained(TXN_SUCCEEDED,ERR_OK,0,'0);
                      emit_empty_success(request_command_i,request_txid_i);
                    end
                  end

                  CMD_ABORT_SESSION: begin
                    if (request_payload_length_i != 4) emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,0);
                    else begin
                      staged_key<=0;active_key<=0;staged_nonce_prefix<=0;active_nonce_prefix<=0;
                      staged_session_id<=0;active_session_id<=0;staged_valid<=0;active_valid<=0;
                      telemetry_loaded<=0;telemetry_plaintext<=0;sequence_number<=64'd1;
                      session_state<=self_test_pass?SESSION_READY_NO_SESSION:SESSION_SELF_TEST_REQUIRED;
                      emit_empty_success(request_command_i,request_txid_i);
                    end
                  end

                  CMD_POLY_BEGIN: begin
                    if (request_payload_length_i!=4 || pbyte(request_payload_i,2)!=8 || pbyte(request_payload_i,3)!=0)
                      emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,0);
                    else if (operation_state==OP_EXECUTING)
                      emit_error(request_command_i,request_txid_i,ERR_BUSY,0);
                    else if ((pbyte(request_payload_i,0)==1 || pbyte(request_payload_i,0)==2) && pbyte(request_payload_i,1)!=1)
                      emit_error(request_command_i,request_txid_i,ERR_BAD_STATE,0);
                    else if (pbyte(request_payload_i,0)==3 && pbyte(request_payload_i,1)!=3)
                      emit_error(request_command_i,request_txid_i,ERR_BAD_STATE,0);
                    else if (pbyte(request_payload_i,0)<1 || pbyte(request_payload_i,0)>3)
                      emit_error(request_command_i,request_txid_i,ERR_BAD_COMMAND,0);
                    else begin
                      poly_operation<=pbyte(request_payload_i,0);
                      poly_mask_a<=0;poly_mask_b<=0;chunk_valid_a<=0;chunk_valid_b<=0;
                      operation_state<=OP_LOAD_INPUT;
                      emit_empty_success(request_command_i,request_txid_i);
                    end
                  end

                  CMD_POLY_WRITE_CHUNK: begin
                    if (request_payload_length_i!=66) emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,0);
                    else if (operation_state!=OP_LOAD_INPUT && operation_state!=OP_READY_TO_EXECUTE)
                      emit_error(request_command_i,request_txid_i,ERR_BAD_STATE,0);
                    else if (pbyte(request_payload_i,0)>1 || pbyte(request_payload_i,1)>7)
                      emit_error(request_command_i,request_txid_i,ERR_BAD_CHUNK_INDEX,0);
                    else if (!chunk_coefficients_valid(request_payload_i))
                      emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,16'h0D01);
                    else if ((pbyte(request_payload_i,0)==0 && chunk_valid_a[pbyte(request_payload_i,1)]) ||
                             (pbyte(request_payload_i,0)==1 && chunk_valid_b[pbyte(request_payload_i,1)])) begin
                      if ((pbyte(request_payload_i,0)==0 && chunk_fingerprint_a[pbyte(request_payload_i,1)]==incoming_fingerprint) ||
                          (pbyte(request_payload_i,0)==1 && chunk_fingerprint_b[pbyte(request_payload_i,1)]==incoming_fingerprint))
                        emit_empty_success(request_command_i,request_txid_i);
                      else emit_error(request_command_i,request_txid_i,ERR_CHUNK_CONFLICT,0);
                    end else begin
                      saved_chunk_slot<=pbyte(request_payload_i,0);
                      saved_chunk_index<=pbyte(request_payload_i,1);
                      saved_chunk_fingerprint<=incoming_fingerprint;
                      saved_chunk_data<=request_payload_i[8*2+:512];
                      chunk_word_index<=0;
                      response_command_o<=request_command_i; response_txid_o<=request_txid_i;
                      core_state<=C_WRITE_CHUNK;
                    end
                  end

                  CMD_POLY_EXECUTE: begin
                    if (request_payload_length_i!=2 || pbyte(request_payload_i,1)!=0 || pbyte(request_payload_i,0)!=poly_operation)
                      emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,0);
                    else if (operation_state!=OP_READY_TO_EXECUTE)
                      emit_error(request_command_i,request_txid_i,ERR_INCOMPLETE_INPUT,0);
                    else begin
                      begin_retained(request_txid_i,request_command_i,incoming_fingerprint);
                      poly_start_operation<=poly_operation[1:0]; poly_start<=1'b1;
                      operation_state<=OP_EXECUTING;
                      emit_empty_success(request_command_i,request_txid_i);
                      core_state<=C_WAIT_POLY;
                    end
                  end

                  CMD_POLY_READ_CHUNK: begin
                    if (request_payload_length_i!=2 || pbyte(request_payload_i,0)>1 || pbyte(request_payload_i,1)>7)
                      emit_error(request_command_i,request_txid_i,ERR_BAD_CHUNK_INDEX,0);
                    else if (operation_state!=OP_RESULT_READY)
                      emit_error(request_command_i,request_txid_i,ERR_RESULT_NOT_READY,0);
                    else begin
                      saved_read_slot<=pbyte(request_payload_i,0);
                      saved_read_chunk<=pbyte(request_payload_i,1);
                      read_word_index<=0;
                      poly_read_slot<=pbyte(request_payload_i,0);
                      poly_read_addr<={request_payload_i[10:8],5'b00000};
                      read_response_data<='0;
                      read_response_data[7:0]<=pbyte(request_payload_i,0);
                      read_response_data[15:8]<=pbyte(request_payload_i,1);
                      response_command_o<=request_command_i;response_txid_o<=request_txid_i;
                      core_state<=C_READ_PRIME;
                    end
                  end

                  CMD_POLY_RETIRE: begin
                    if (request_payload_length_i!=2 || pbyte(request_payload_i,1)!=0)
                      emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,0);
                    else begin
                      if ((pbyte(request_payload_i,0) & 8'h01) != 0) begin poly_mask_a<=0;chunk_valid_a<=0; end
                      if ((pbyte(request_payload_i,0) & 8'h02) != 0) begin poly_mask_b<=0;chunk_valid_b<=0; end
                      operation_state<=OP_IDLE;
                      emit_empty_success(request_command_i,request_txid_i);
                    end
                  end

                  CMD_LOAD_TELEMETRY: begin
                    if (request_payload_length_i!=32 || pbyte(request_payload_i,1)!=0 ||
                        pbyte(request_payload_i,6)!=0 || pbyte(request_payload_i,7)!=0)
                      emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,0);
                    else if (session_state!=SESSION_ACTIVE || !secure_enable_i || fault_o)
                      emit_error(request_command_i,request_txid_i,ERR_BAD_STATE,0);
                    else if (telemetry_loaded && telemetry_request_image!=request_payload_i[255:0])
                      emit_error(request_command_i,request_txid_i,ERR_TRANSACTION_CONFLICT,0);
                    else begin
                      telemetry_message_type<=pbyte(request_payload_i,0);
                      telemetry_flags<={pbyte(request_payload_i,2),pbyte(request_payload_i,3)};
                      telemetry_source_id<={pbyte(request_payload_i,4),pbyte(request_payload_i,5)};
                      telemetry_plaintext<=request_payload_i[8*8+:192];
                      telemetry_request_image<=request_payload_i[255:0];
                      telemetry_loaded<=1'b1;
                      emit_empty_success(request_command_i,request_txid_i);
                    end
                  end

                  CMD_ENCRYPT_AND_SEND: begin
                    if (request_payload_length_i!=0) emit_error(request_command_i,request_txid_i,ERR_BAD_LENGTH,0);
                    else if (session_state!=SESSION_ACTIVE || !active_valid || !secure_enable_i || fault_o || !telemetry_loaded)
                      emit_error(request_command_i,request_txid_i,ERR_BAD_STATE,0);
                    else begin
                      begin_retained(request_txid_i,request_command_i,incoming_fingerprint);
                      ascon_key_input<=active_key;ascon_nonce_input<=constructed_nonce;
                      ascon_ad_input<=constructed_ad;ascon_pt_input<=telemetry_plaintext;
                      crypto_ad_snapshot<=constructed_ad;
                      ascon_start<=1'b1;
                      operation_state<=OP_EXECUTING;
                      emit_empty_success(request_command_i,request_txid_i);
                      core_state<=C_WAIT_ASCON;
                    end
                  end

                  default: begin
                    diagnostic_summary<=diagnostic_summary|DIAG_BAD_COMMAND;
                    emit_error(request_command_i,request_txid_i,ERR_BAD_COMMAND,0);
                  end
                endcase
              end
            end
          end

          C_WRITE_CHUNK: begin
            poly_load_we<=1'b1;
            poly_load_slot<=saved_chunk_slot;
            poly_load_addr<={saved_chunk_index,5'b00000}+chunk_word_index;
            poly_load_data<={saved_chunk_data[8*(2*chunk_word_index+1)+:8],
                             saved_chunk_data[8*(2*chunk_word_index)+:8]};
            if (chunk_word_index==6'd31) begin
              if (saved_chunk_slot) begin
                poly_mask_b<=poly_mask_b|(8'b1<<saved_chunk_index);
                chunk_valid_b<=chunk_valid_b|(8'b1<<saved_chunk_index);
                chunk_fingerprint_b[saved_chunk_index]<=saved_chunk_fingerprint;
                new_mask=poly_mask_b|(8'b1<<saved_chunk_index);
                if ((poly_operation==3 && poly_mask_a==8'hFF && new_mask==8'hFF))
                  operation_state<=OP_READY_TO_EXECUTE;
              end else begin
                poly_mask_a<=poly_mask_a|(8'b1<<saved_chunk_index);
                chunk_valid_a<=chunk_valid_a|(8'b1<<saved_chunk_index);
                chunk_fingerprint_a[saved_chunk_index]<=saved_chunk_fingerprint;
                new_mask=poly_mask_a|(8'b1<<saved_chunk_index);
                if ((poly_operation!=3 && new_mask==8'hFF) ||
                    (poly_operation==3 && new_mask==8'hFF && poly_mask_b==8'hFF))
                  operation_state<=OP_READY_TO_EXECUTE;
              end
              emit_empty_success(response_command_o,response_txid_o);
              core_state<=C_IDLE;
            end else chunk_word_index<=chunk_word_index+1'b1;
          end

          C_READ_PRIME: begin
            core_state<=C_READ_CHUNK;
          end

          C_READ_CHUNK: begin
            read_response_data[8*(2+2*read_word_index)+:8]<=poly_read_data[7:0];
            read_response_data[8*(3+2*read_word_index)+:8]<=poly_read_data[15:8];
            if (read_word_index==6'd31) core_state<=C_READ_RESP;
            else begin
              read_word_index<=read_word_index+1'b1;
              poly_read_addr<={saved_read_chunk,5'b00000}+read_word_index+1'b1;
            end
          end

          C_READ_RESP: begin
            emit_response(response_command_o,response_txid_o,FLAG_RESPONSE,16'd66,read_response_data);
            core_state<=C_IDLE;
          end

          C_WAIT_POLY: begin
            if (poly_done) begin
              if (poly_error) begin
                operation_state<=OP_IDLE;
                complete_retained(TXN_FAILED,ERR_INTERNAL_FAULT,0,'0);
              end else begin
                operation_state<=OP_RESULT_READY;
                complete_retained(TXN_SUCCEEDED,ERR_OK,0,'0);
              end
              core_state<=C_IDLE;
            end
          end

          C_WAIT_ASCON: begin
            if (ascon_done) begin
              uart_frame<='0;
              uart_frame[7:0]<=8'hA5; uart_frame[15:8]<=8'h5A;
              uart_frame[8*2+:192]<=crypto_ad_snapshot;
              uart_frame[8*26+:192]<=ascon_ciphertext;
              uart_frame[8*50+:128]<=ascon_tag;
              uart_start<=1'b1;
              core_state<=C_WAIT_UART;
            end
          end

          C_WAIT_UART: begin
            if (uart_done) begin
              txn_data='0;
              txn_data[7:0]=active_session_id[31:24];txn_data[15:8]=active_session_id[23:16];
              txn_data[23:16]=active_session_id[15:8];txn_data[31:24]=active_session_id[7:0];
              for (ci=0;ci<8;ci=ci+1) txn_data[8*(4+ci)+:8]=sequence_number[63-8*ci-:8];
              txn_data[103:96]=8'h00;txn_data[111:104]=8'h42;
              complete_retained(TXN_SUCCEEDED,ERR_OK,16'd14,txn_data);
              sequence_number<=sequence_number+1'b1;
              telemetry_loaded<=1'b0;telemetry_plaintext<=0;
              operation_state<=OP_IDLE;
              core_state<=C_IDLE;
            end
          end

          C_ZEROIZE_WAIT: begin
            if (poly_zeroize_done) zeroize_memory_done <= 1'b1;
            if ((poly_zeroize_done || zeroize_memory_done) && zeroize_ni) begin
              if (zeroize_from_command) begin
                complete_retained(TXN_ZEROIZED,ERR_ZEROIZED,0,'0);
                session_state<=self_test_pass?SESSION_READY_NO_SESSION:SESSION_SELF_TEST_REQUIRED;
              end else if (zeroize_due_to_fault || fatal_latched_i || fault_latched) begin
                session_state<=SESSION_FAULT_LOCKED;
                diagnostic_summary<=diagnostic_summary|DIAG_HEARTBEAT_OR_FAULT;
              end else begin
                self_test_pass<=1'b0;
                session_state<=SESSION_SELF_TEST_REQUIRED;
              end
              zeroize_memory_done <= 1'b0;
              core_state<=C_IDLE;
            end
          end

          C_ST_ASCON_WAIT: begin
            if (ascon_done) begin
              if (ascon_ciphertext!=ASCON_KAT_CT || ascon_tag!=ASCON_KAT_TAG) begin
                diagnostic_summary<=diagnostic_summary|DIAG_SELF_TEST;
                fault_latched<=1'b1;session_state<=SESSION_FAULT_LOCKED;
                operation_state<=OP_IDLE;
                complete_retained(TXN_FAILED,ERR_SELF_TEST_FAILED,0,'0);
                core_state<=C_IDLE;
              end else begin
                poly_zeroize<=1'b1;
                core_state<=C_ST_ZERO_WAIT;
              end
            end
          end

          C_ST_ZERO_WAIT: begin
            if (poly_zeroize_done) begin
              poly_start_operation<=2'd1;poly_start<=1'b1;
              core_state<=C_ST_NTT_WAIT;
            end
          end

          C_ST_NTT_WAIT: begin
            if (poly_done) begin selftest_index<=0;poly_read_slot<=0;poly_read_addr<=0;core_state<=C_ST_NTT_SCAN;end
          end
          C_ST_NTT_SCAN: begin
            if (poly_read_data!=0) begin
              fault_latched<=1'b1;session_state<=SESSION_FAULT_LOCKED;operation_state<=OP_IDLE;
              complete_retained(TXN_FAILED,ERR_SELF_TEST_FAILED,0,'0);core_state<=C_IDLE;
            end else if (selftest_index==8'd255) begin
              poly_start_operation<=2'd2;poly_start<=1'b1;core_state<=C_ST_INTT_WAIT;
            end else begin selftest_index<=selftest_index+1'b1;poly_read_addr<=selftest_index+1'b1;end
          end
          C_ST_INTT_WAIT: begin
            if (poly_done) begin selftest_index<=0;poly_read_addr<=0;core_state<=C_ST_INTT_SCAN;end
          end
          C_ST_INTT_SCAN: begin
            if (poly_read_data!=0) begin
              fault_latched<=1'b1;session_state<=SESSION_FAULT_LOCKED;operation_state<=OP_IDLE;
              complete_retained(TXN_FAILED,ERR_SELF_TEST_FAILED,0,'0);core_state<=C_IDLE;
            end else if (selftest_index==8'd255) begin
              poly_start_operation<=2'd3;poly_start<=1'b1;core_state<=C_ST_BM_WAIT;
            end else begin selftest_index<=selftest_index+1'b1;poly_read_addr<=selftest_index+1'b1;end
          end
          C_ST_BM_WAIT: begin
            if (poly_done) begin selftest_index<=0;poly_read_addr<=0;core_state<=C_ST_BM_SCAN;end
          end
          C_ST_BM_SCAN: begin
            if (poly_read_data!=0) begin
              fault_latched<=1'b1;session_state<=SESSION_FAULT_LOCKED;operation_state<=OP_IDLE;
              complete_retained(TXN_FAILED,ERR_SELF_TEST_FAILED,0,'0);core_state<=C_IDLE;
            end else if (selftest_index==8'd255) begin
              self_test_pass<=1'b1;session_state<=SESSION_READY_NO_SESSION;operation_state<=OP_IDLE;
              txn_data='0;txn_data[7:0]=8'h01;txn_data[15:8]=8'h3E;
              complete_retained(TXN_SUCCEEDED,ERR_OK,16'd2,txn_data);core_state<=C_IDLE;
            end else begin selftest_index<=selftest_index+1'b1;poly_read_addr<=selftest_index+1'b1;end
          end
          default: core_state<=C_IDLE;
        endcase
      end
    end
  end
endmodule
