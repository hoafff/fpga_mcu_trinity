package trinity_spi_pkg;
  localparam logic [7:0] PROTOCOL_VERSION = 8'h01;
  localparam logic [7:0] SPI_MAGIC = 8'hA5;
  localparam int unsigned SPI_HEADER_SIZE = 8;
  localparam int unsigned SPI_CRC_SIZE = 2;
  localparam int unsigned SPI_MAX_POLYNOMIAL_DATA = 64;
  localparam int unsigned SPI_MAX_PAYLOAD = 66;
  localparam int unsigned SPI_MAX_PACKET = 76;

  localparam logic [7:0] FLAG_RESPONSE = 8'h01;
  localparam logic [7:0] FLAG_ERROR = 8'h02;
  localparam logic [7:0] FLAG_MORE = 8'h04;
  localparam logic [7:0] FLAG_EVENT = 8'h08;
  localparam logic [7:0] FLAG_ALLOWED_MASK = 8'h0F;

  localparam logic [7:0] CMD_GET_INFO = 8'h01;
  localparam logic [7:0] CMD_GET_STATUS = 8'h02;
  localparam logic [7:0] CMD_RUN_SELF_TEST = 8'h03;
  localparam logic [7:0] CMD_GET_TXN_RESULT = 8'h04;
  localparam logic [7:0] CMD_RETIRE_TXN_RESULT = 8'h05;
  localparam logic [7:0] CMD_ZEROIZE = 8'h06;
  localparam logic [7:0] CMD_STAGE_SESSION = 8'h07;
  localparam logic [7:0] CMD_COMMIT_SESSION = 8'h08;
  localparam logic [7:0] CMD_ABORT_SESSION = 8'h09;
  localparam logic [7:0] CMD_POLY_BEGIN = 8'h20;
  localparam logic [7:0] CMD_POLY_WRITE_CHUNK = 8'h21;
  localparam logic [7:0] CMD_POLY_EXECUTE = 8'h22;
  localparam logic [7:0] CMD_POLY_READ_CHUNK = 8'h23;
  localparam logic [7:0] CMD_POLY_RETIRE = 8'h24;
  localparam logic [7:0] CMD_LOAD_TELEMETRY = 8'h30;
  localparam logic [7:0] CMD_ENCRYPT_AND_SEND = 8'h31;
  localparam logic [7:0] CMD_GET_RX_STATUS = 8'h40;
  localparam logic [7:0] CMD_READ_AUTH_RESULT = 8'h41;
  localparam logic [7:0] CMD_ACK_AUTH_RESULT = 8'h42;
  localparam logic [7:0] CMD_CLEAR_DIAGNOSTIC_COUNTERS = 8'h43;

  localparam logic [15:0] ERR_OK = 16'h0000;
  localparam logic [15:0] ERR_BAD_MAGIC = 16'h0101;
  localparam logic [15:0] ERR_BAD_VERSION = 16'h0102;
  localparam logic [15:0] ERR_BAD_LENGTH = 16'h0103;
  localparam logic [15:0] ERR_BAD_CRC = 16'h0104;
  localparam logic [15:0] ERR_BAD_FLAGS = 16'h0105;
  localparam logic [15:0] ERR_BAD_COMMAND = 16'h0201;
  localparam logic [15:0] ERR_BAD_STATE = 16'h0202;
  localparam logic [15:0] ERR_BUSY = 16'h0203;
  localparam logic [15:0] ERR_RESULT_PENDING = 16'h0204;
  localparam logic [15:0] ERR_TRANSACTION_CONFLICT = 16'h0205;
  localparam logic [15:0] ERR_OUTCOME_UNKNOWN_TARGET_RESET = 16'h0206;
  localparam logic [15:0] ERR_BAD_CHUNK_INDEX = 16'h0301;
  localparam logic [15:0] ERR_CHUNK_CONFLICT = 16'h0302;
  localparam logic [15:0] ERR_INCOMPLETE_INPUT = 16'h0303;
  localparam logic [15:0] ERR_RESULT_NOT_READY = 16'h0304;
  localparam logic [15:0] ERR_SELF_TEST_FAILED = 16'h0305;
  localparam logic [15:0] ERR_MLKEM_SHARED_SECRET_MISMATCH = 16'h0306;
  localparam logic [15:0] ERR_SESSION_ID_COLLISION = 16'h0401;
  localparam logic [15:0] ERR_BAD_SESSION = 16'h0402;
  localparam logic [15:0] ERR_ZEROIZED = 16'h0403;
  localparam logic [15:0] ERR_REPLAY = 16'h0501;
  localparam logic [15:0] ERR_STALE_SEQUENCE = 16'h0502;
  localparam logic [15:0] ERR_BAD_TAG = 16'h0503;
  localparam logic [15:0] ERR_MALFORMED_FRAME = 16'h0504;
  localparam logic [15:0] ERR_FRAME_TIMEOUT = 16'h0505;
  localparam logic [15:0] ERR_RESULT_PENDING_DROP = 16'h0506;
  localparam logic [15:0] ERR_AUTH_THRESHOLD = 16'h0601;
  localparam logic [15:0] ERR_COMMIT_REJECTED = 16'h0602;
  localparam logic [15:0] ERR_SESSION_COMMIT_FAILED = 16'h0603;
  localparam logic [15:0] ERR_HEARTBEAT_TIMEOUT = 16'h0604;
  localparam logic [15:0] ERR_FAULT_LOCKED = 16'h0605;
  localparam logic [15:0] ERR_INTERNAL_FAULT = 16'h0701;
  localparam logic [15:0] ERR_NOT_SUPPORTED = 16'h0702;

  localparam logic [7:0] TARGET_PRIMER1 = 8'h01;
  localparam logic [7:0] TARGET_PRIMER2 = 8'h02;

  typedef enum logic [3:0] {
    SESSION_BOOT = 4'd0,
    SESSION_SELF_TEST_REQUIRED = 4'd1,
    SESSION_SELF_TEST_RUNNING = 4'd2,
    SESSION_READY_NO_SESSION = 4'd3,
    SESSION_STAGED = 4'd4,
    SESSION_COMMITTED_BLOCKED = 4'd5,
    SESSION_ACTIVE = 4'd6,
    SESSION_ZEROIZE_BUSY = 4'd7,
    SESSION_FAULT_LOCKED = 4'd8
  } session_state_e;

  typedef enum logic [2:0] {
    OP_IDLE = 3'd0,
    OP_LOAD_INPUT = 3'd1,
    OP_READY_TO_EXECUTE = 3'd2,
    OP_EXECUTING = 3'd3,
    OP_RESULT_READY = 3'd4
  } operation_state_e;

  typedef enum logic [2:0] {
    TXN_NONE = 3'd0,
    TXN_ACCEPTED = 3'd1,
    TXN_RUNNING = 3'd2,
    TXN_SUCCEEDED = 3'd3,
    TXN_FAILED = 3'd4,
    TXN_ZEROIZED = 3'd5,
    TXN_OUTCOME_UNKNOWN = 3'd6
  } transaction_state_e;

  typedef enum logic [2:0] {
    RX_HUNT_SYNC = 3'd0,
    RX_RECEIVE_BODY = 3'd1,
    RX_VALIDATE = 3'd2,
    RX_VERIFY_TAG = 3'd3,
    RX_RESULT_PENDING = 3'd4
  } rx_state_e;

  typedef enum logic [1:0] {
    TEST_PROFILE_QUICK = 2'd0,
    TEST_PROFILE_FULL = 2'd1,
    TEST_PROFILE_KAT = 2'd2,
    TEST_PROFILE_DIAGNOSTIC = 2'd3
  } test_profile_e;

  localparam logic [7:0] PENDING_RESPONSE_MAILBOX = 8'h01;
  localparam logic [7:0] PENDING_SIDE_EFFECT_RESULT = 8'h02;
  localparam logic [7:0] PENDING_AUTHENTICATED_RESULT = 8'h04;

  localparam logic [7:0] SECURE_SELF_TEST_PASS = 8'h01;
  localparam logic [7:0] SECURE_SESSION_STAGED = 8'h02;
  localparam logic [7:0] SECURE_ENABLE = 8'h04;
  localparam logic [7:0] SECURE_ZEROIZE_BUSY = 8'h08;
  localparam logic [7:0] SECURE_FAULT_LOCKED = 8'h10;

  localparam logic [31:0] CAP_SELF_TEST = 32'h00000001;
  localparam logic [31:0] CAP_ZEROIZE = 32'h00000002;
  localparam logic [31:0] CAP_TRANSACTION_RECONCILIATION = 32'h00000004;
  localparam logic [31:0] CAP_SESSION_STAGE_COMMIT = 32'h00000008;
  localparam logic [31:0] CAP_NTT = 32'h00000010;
  localparam logic [31:0] CAP_INTT = 32'h00000020;
  localparam logic [31:0] CAP_BASEMUL = 32'h00000040;
  localparam logic [31:0] CAP_ASCON_ENCRYPT = 32'h00000080;
  localparam logic [31:0] CAP_UART_TX = 32'h00000100;
  localparam logic [31:0] CAP_ASCON_DECRYPT = 32'h00000200;
  localparam logic [31:0] CAP_REPLAY_FILTER = 32'h00000400;
  localparam logic [31:0] CAP_AUTH_RESULT_BUFFER = 32'h00000800;
  localparam logic [31:0] CAP_DIAGNOSTICS = 32'h00001000;

  localparam logic [15:0] TEST_PROTOCOL = 16'h0001;
  localparam logic [15:0] TEST_MEMORY = 16'h0002;
  localparam logic [15:0] TEST_NTT = 16'h0004;
  localparam logic [15:0] TEST_INTT = 16'h0008;
  localparam logic [15:0] TEST_BASEMUL = 16'h0010;
  localparam logic [15:0] TEST_ASCON = 16'h0020;
  localparam logic [15:0] TEST_UART = 16'h0040;
  localparam logic [15:0] TEST_SESSION = 16'h0080;
  localparam logic [15:0] TEST_ZEROIZE = 16'h0100;
  localparam logic [15:0] TEST_HEARTBEAT = 16'h0200;

  localparam logic [7:0] ZEROIZE_ACTIVE_SESSION = 8'h01;
  localparam logic [7:0] ZEROIZE_STAGED_SESSION = 8'h02;
  localparam logic [7:0] ZEROIZE_POLYNOMIAL_BUFFERS = 8'h04;
  localparam logic [7:0] ZEROIZE_TELEMETRY_OR_AUTH_RESULT = 8'h08;
  localparam logic [7:0] ZEROIZE_TRANSACTION_STATE = 8'h10;
  localparam logic [7:0] ZEROIZE_DIAGNOSTIC_TRANSIENT = 8'h20;
  localparam logic [7:0] ZEROIZE_ALL = 8'hFF;

  localparam logic [31:0] DIAG_TRANSPORT = 32'h00000001;
  localparam logic [31:0] DIAG_CRC = 32'h00000002;
  localparam logic [31:0] DIAG_BAD_COMMAND = 32'h00000004;
  localparam logic [31:0] DIAG_TRANSACTION_CONFLICT = 32'h00000008;
  localparam logic [31:0] DIAG_BAD_TAG = 32'h00000010;
  localparam logic [31:0] DIAG_REPLAY_OR_STALE = 32'h00000020;
  localparam logic [31:0] DIAG_FRAME_ERROR = 32'h00000040;
  localparam logic [31:0] DIAG_RESULT_PENDING_DROP = 32'h00000080;
  localparam logic [31:0] DIAG_HEARTBEAT_OR_FAULT = 32'h00000100;
  localparam logic [31:0] DIAG_SELF_TEST = 32'h00000200;
  localparam logic [31:0] DIAG_ALL = 32'hFFFFFFFF;

  function automatic logic flags_valid(input logic [7:0] flags);
    flags_valid = ((flags & ~FLAG_ALLOWED_MASK) == 8'h00);
  endfunction

  function automatic logic [15:0] crc16_update_byte(
      input logic [15:0] crc_in,
      input logic [7:0] data
  );
    logic [15:0] crc;
    integer i;
    begin
      crc = crc_in ^ {data, 8'h00};
      for (i = 0; i < 8; i = i + 1) begin
        if (crc[15])
          crc = (crc << 1) ^ 16'h1021;
        else
          crc = crc << 1;
      end
      crc16_update_byte = crc;
    end
  endfunction
endpackage
