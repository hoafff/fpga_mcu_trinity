module mlkem_poly_accel (
    input  logic        clk_i,
    input  logic        rst_ni,
    input  logic        load_we_i,
    input  logic        load_slot_i,
    input  logic [7:0]  load_addr_i,
    input  logic [15:0] load_data_i,
    input  logic        read_slot_i,
    input  logic [7:0]  read_addr_i,
    output logic [15:0] read_data_o,
    input  logic        start_i,
    input  logic [1:0]  operation_i,
    output logic        busy_o,
    output logic        done_o,
    output logic        error_o,
    input  logic        zeroize_i,
    output logic        zeroize_busy_o,
    output logic        zeroize_done_o
);
  localparam integer Q = 3329;

  // Two 256x16 true-dual-port memories. All arithmetic is scheduled around
  // these two ports so Gowin can keep both polynomials in BSRAM.
  (* ram_style = "block", syn_ramstyle = "block_ram" *) logic signed [15:0] poly_a [0:255];
  (* ram_style = "block", syn_ramstyle = "block_ram" *) logic signed [15:0] poly_b [0:255];

  logic [7:0] a_addr0, a_addr1, b_addr0, b_addr1;
  logic a_we0, a_we1, b_we0, b_we1;
  logic signed [15:0] a_din0, a_din1, b_din0, b_din1;
  logic signed [15:0] a_q0, a_q1, b_q0, b_q1;

  always_ff @(posedge clk_i) begin
    if (a_we0) poly_a[a_addr0] <= a_din0;
    if (a_we1) poly_a[a_addr1] <= a_din1;
    if (b_we0) poly_b[b_addr0] <= b_din0;
    if (b_we1) poly_b[b_addr1] <= b_din1;
    a_q0 <= poly_a[a_addr0];
    a_q1 <= poly_a[a_addr1];
    b_q0 <= poly_b[b_addr0];
    b_q1 <= poly_b[b_addr1];
  end

  // One Montgomery multiplier/reducer is shared by NTT, INTT, scaling and all
  // seven BaseMul sub-operations. This is intentionally iterative to preserve
  // functionality while creating a large LUT margin on GW2A-LV18.
  logic signed [15:0] mul_lhs, mul_rhs;
  logic signed [31:0] mul_product;
  logic signed [15:0] mul_result;

  function automatic logic signed [15:0] montgomery_reduce(
      input logic signed [31:0] value
  );
    logic signed [31:0] qinv_product;
    logic signed [15:0] qinv_low;
    logic signed [31:0] reduced;
    begin
      qinv_product = $signed(value[15:0]) * -16'sd3327;
      qinv_low = qinv_product[15:0];
      reduced = (value - ($signed(qinv_low) * 32'sd3329)) >>> 16;
      montgomery_reduce = reduced[15:0];
    end
  endfunction

  always_comb begin
    mul_product = $signed(mul_lhs) * $signed(mul_rhs);
    mul_result = montgomery_reduce(mul_product);
  end

  function automatic logic signed [15:0] barrett_reduce(
      input logic signed [16:0] value
  );
    logic signed [31:0] extended_value;
    logic signed [31:0] quotient;
    logic signed [31:0] reduced;
    begin
      extended_value = {{15{value[16]}}, value};
      quotient = ((32'sd20159 * extended_value) + 32'sd33554432) >>> 26;
      reduced = extended_value - (quotient * 32'sd3329);
      barrett_reduce = reduced[15:0];
    end
  endfunction

  function automatic logic [15:0] canonical(input logic signed [17:0] value);
    integer v;
    integer ci;
    begin
      v = value;
      for (ci = 0; ci < 8; ci = ci + 1) begin
        if (v < 0) v = v + Q;
        if (v >= Q) v = v - Q;
      end
      canonical = v[15:0];
    end
  endfunction

  function automatic logic signed [15:0] zeta(input logic [7:0] index);
    begin
      case (index)
        0:zeta=-1044; 1:zeta=-758; 2:zeta=-359; 3:zeta=-1517;
        4:zeta=1493; 5:zeta=1422; 6:zeta=287; 7:zeta=202;
        8:zeta=-171; 9:zeta=622; 10:zeta=1577; 11:zeta=182;
        12:zeta=962; 13:zeta=-1202; 14:zeta=-1474; 15:zeta=1468;
        16:zeta=573; 17:zeta=-1325; 18:zeta=264; 19:zeta=383;
        20:zeta=-829; 21:zeta=1458; 22:zeta=-1602; 23:zeta=-130;
        24:zeta=-681; 25:zeta=1017; 26:zeta=732; 27:zeta=608;
        28:zeta=-1542; 29:zeta=411; 30:zeta=-205; 31:zeta=-1571;
        32:zeta=1223; 33:zeta=652; 34:zeta=-552; 35:zeta=1015;
        36:zeta=-1293; 37:zeta=1491; 38:zeta=-282; 39:zeta=-1544;
        40:zeta=516; 41:zeta=-8; 42:zeta=-320; 43:zeta=-666;
        44:zeta=-1618; 45:zeta=-1162; 46:zeta=126; 47:zeta=1469;
        48:zeta=-853; 49:zeta=-90; 50:zeta=-271; 51:zeta=830;
        52:zeta=107; 53:zeta=-1421; 54:zeta=-247; 55:zeta=-951;
        56:zeta=-398; 57:zeta=961; 58:zeta=-1508; 59:zeta=-725;
        60:zeta=448; 61:zeta=-1065; 62:zeta=677; 63:zeta=-1275;
        64:zeta=-1103; 65:zeta=430; 66:zeta=555; 67:zeta=843;
        68:zeta=-1251; 69:zeta=871; 70:zeta=1550; 71:zeta=105;
        72:zeta=422; 73:zeta=587; 74:zeta=177; 75:zeta=-235;
        76:zeta=-291; 77:zeta=-460; 78:zeta=1574; 79:zeta=1653;
        80:zeta=-246; 81:zeta=778; 82:zeta=1159; 83:zeta=-147;
        84:zeta=-777; 85:zeta=1483; 86:zeta=-602; 87:zeta=1119;
        88:zeta=-1590; 89:zeta=644; 90:zeta=-872; 91:zeta=349;
        92:zeta=418; 93:zeta=329; 94:zeta=-156; 95:zeta=-75;
        96:zeta=817; 97:zeta=1097; 98:zeta=603; 99:zeta=610;
        100:zeta=1322; 101:zeta=-1285; 102:zeta=-1465; 103:zeta=384;
        104:zeta=-1215; 105:zeta=-136; 106:zeta=1218; 107:zeta=-1335;
        108:zeta=-874; 109:zeta=220; 110:zeta=-1187; 111:zeta=-1659;
        112:zeta=-1185; 113:zeta=-1530; 114:zeta=-1278; 115:zeta=794;
        116:zeta=-1510; 117:zeta=-854; 118:zeta=-870; 119:zeta=478;
        120:zeta=-108; 121:zeta=-308; 122:zeta=996; 123:zeta=991;
        124:zeta=958; 125:zeta=-1460; 126:zeta=1522; default:zeta=1628;
      endcase
    end
  endfunction

  typedef enum logic [5:0] {
    P_IDLE,
    P_NTT_GROUP, P_NTT_READ, P_NTT_MUL, P_NTT_WRITE,
    P_INTT_GROUP, P_INTT_READ, P_INTT_MUL, P_INTT_WRITE,
    P_SCALE_READ, P_SCALE_MUL, P_SCALE_WRITE,
    P_BM0_READ, P_BM0_M0, P_BM0_M1, P_BM0_M2, P_BM0_M3, P_BM0_M4,
    P_BM0_M5, P_BM0_M6, P_BM0_WRITE,
    P_BM1_READ, P_BM1_M0, P_BM1_M1, P_BM1_M2, P_BM1_M3, P_BM1_M4,
    P_BM1_M5, P_BM1_M6, P_BM1_WRITE,
    P_ZEROIZE, P_DONE
  } pstate_e;
  pstate_e state;

  logic [7:0] len_reg, k_reg, scale_index, bm_index, zero_index;
  logic [8:0] start_reg, j_reg;
  logic signed [15:0] zeta_reg;
  logic signed [15:0] hold0, hold1, hold2, hold3, hold4, hold5, hold6;
  logic signed [16:0] intt_sum_full, intt_diff_full, bm_sum0_full, bm_sum1_full;

  logic read_prefetch_active;
  logic read_prefetch_slot;
  logic read_select_q1;
  logic read_start_hold;
  logic [7:0] read_expected_addr;
  logic [7:0] read_next_addr;
  logic read_restart;

  always_comb begin
    read_restart = !read_prefetch_active ||
                   (read_slot_i != read_prefetch_slot) ||
                   (read_addr_i != read_expected_addr);
  end

  always_comb begin
    intt_sum_full = $signed(a_q0) + $signed(a_q1);
    intt_diff_full = $signed(a_q1) - $signed(a_q0);
    bm_sum0_full = $signed(hold1) + $signed(hold2);
    bm_sum1_full = $signed(hold3) + $signed(hold4);

    mul_lhs = 16'sd0;
    mul_rhs = 16'sd0;
    case (state)
      P_NTT_MUL: begin mul_lhs = zeta_reg; mul_rhs = a_q1; end
      P_INTT_MUL: begin mul_lhs = zeta_reg; mul_rhs = intt_diff_full[15:0]; end
      P_SCALE_MUL: begin mul_lhs = a_q0; mul_rhs = 16'sd512; end
      P_BM0_M0, P_BM1_M0: begin mul_lhs = a_q1; mul_rhs = b_q1; end
      P_BM0_M1, P_BM1_M1: begin mul_lhs = hold0; mul_rhs = zeta_reg; end
      P_BM0_M2, P_BM1_M2: begin mul_lhs = a_q0; mul_rhs = b_q0; end
      P_BM0_M3, P_BM1_M3: begin mul_lhs = a_q0; mul_rhs = b_q1; end
      P_BM0_M4, P_BM1_M4: begin mul_lhs = a_q1; mul_rhs = b_q0; end
      P_BM0_M5, P_BM1_M5: begin mul_lhs = bm_sum0_full[15:0]; mul_rhs = 16'sd1353; end
      P_BM0_M6, P_BM1_M6: begin mul_lhs = bm_sum1_full[15:0]; mul_rhs = 16'sd1353; end
      default: begin end
    endcase
  end

  always_comb begin
    a_addr0 = read_addr_i;
    a_addr1 = 8'd0;
    b_addr0 = read_addr_i;
    b_addr1 = 8'd0;
    a_we0 = 1'b0; a_we1 = 1'b0; b_we0 = 1'b0; b_we1 = 1'b0;
    a_din0 = 16'sd0; a_din1 = 16'sd0; b_din0 = 16'sd0; b_din1 = 16'sd0;

    case (state)
      P_IDLE: begin
        if (load_we_i) begin
          if (load_slot_i) begin
            b_addr0 = load_addr_i; b_we0 = 1'b1; b_din0 = $signed(load_data_i);
          end else begin
            a_addr0 = load_addr_i; a_we0 = 1'b1; a_din0 = $signed(load_data_i);
          end
        end else if (read_restart) begin
          if (read_slot_i) begin
            b_addr0 = read_addr_i;
            b_addr1 = read_addr_i + 8'd1;
          end else begin
            a_addr0 = read_addr_i;
            a_addr1 = read_addr_i + 8'd1;
          end
        end else if (read_prefetch_slot) begin
          if (read_select_q1) begin
            b_addr0 = read_next_addr - 8'd1;
            b_addr1 = read_next_addr;
          end else begin
            b_addr0 = read_next_addr;
            b_addr1 = read_next_addr - 8'd1;
          end
        end else begin
          if (read_select_q1) begin
            a_addr0 = read_next_addr - 8'd1;
            a_addr1 = read_next_addr;
          end else begin
            a_addr0 = read_next_addr;
            a_addr1 = read_next_addr - 8'd1;
          end
        end
      end

      P_NTT_READ, P_NTT_MUL, P_NTT_WRITE,
      P_INTT_READ, P_INTT_MUL, P_INTT_WRITE: begin
        a_addr0 = j_reg[7:0];
        a_addr1 = j_reg[7:0] + len_reg;
        if (state == P_NTT_WRITE) begin
          a_we0 = 1'b1; a_we1 = 1'b1;
          a_din0 = $signed(a_q0) + $signed(hold0);
          a_din1 = $signed(a_q0) - $signed(hold0);
        end else if (state == P_INTT_WRITE) begin
          a_we0 = 1'b1; a_we1 = 1'b1;
          a_din0 = barrett_reduce(intt_sum_full);
          a_din1 = hold0;
        end
      end

      P_SCALE_READ, P_SCALE_MUL, P_SCALE_WRITE: begin
        a_addr0 = scale_index;
        if (state == P_SCALE_WRITE) begin
          a_we0 = 1'b1;
          a_din0 = hold0;
        end
      end

      P_BM0_READ, P_BM0_M0, P_BM0_M1, P_BM0_M2, P_BM0_M3, P_BM0_M4,
      P_BM0_M5, P_BM0_M6, P_BM0_WRITE: begin
        a_addr0 = {bm_index[5:0], 2'b00};
        a_addr1 = {bm_index[5:0], 2'b00} + 8'd1;
        b_addr0 = {bm_index[5:0], 2'b00};
        b_addr1 = {bm_index[5:0], 2'b00} + 8'd1;
        if (state == P_BM0_WRITE) begin
          a_we0 = 1'b1; a_we1 = 1'b1;
          a_din0 = hold5; a_din1 = hold6;
        end
      end

      P_BM1_READ, P_BM1_M0, P_BM1_M1, P_BM1_M2, P_BM1_M3, P_BM1_M4,
      P_BM1_M5, P_BM1_M6, P_BM1_WRITE: begin
        a_addr0 = {bm_index[5:0], 2'b00} + 8'd2;
        a_addr1 = {bm_index[5:0], 2'b00} + 8'd3;
        b_addr0 = {bm_index[5:0], 2'b00} + 8'd2;
        b_addr1 = {bm_index[5:0], 2'b00} + 8'd3;
        if (state == P_BM1_WRITE) begin
          a_we0 = 1'b1; a_we1 = 1'b1;
          a_din0 = hold5; a_din1 = hold6;
        end
      end

      P_ZEROIZE: begin
        a_addr0 = zero_index; b_addr0 = zero_index;
        a_we0 = 1'b1; b_we0 = 1'b1;
        a_din0 = 16'sd0; b_din0 = 16'sd0;
      end
      default: begin end
    endcase
  end

  always_comb begin
    if (read_prefetch_slot)
      read_data_o = canonical(read_select_q1 ? b_q1 : b_q0);
    else
      read_data_o = canonical(read_select_q1 ? a_q1 : a_q0);
  end

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      state <= P_IDLE;
      busy_o <= 1'b0;
      done_o <= 1'b0;
      error_o <= 1'b0;
      zeroize_busy_o <= 1'b0;
      zeroize_done_o <= 1'b0;
      len_reg <= 8'd0; start_reg <= 9'd0; j_reg <= 9'd0; k_reg <= 8'd0;
      scale_index <= 8'd0; bm_index <= 8'd0; zero_index <= 8'd0;
      zeta_reg <= 16'sd0;
      hold0 <= 16'sd0; hold1 <= 16'sd0; hold2 <= 16'sd0;
      hold3 <= 16'sd0; hold4 <= 16'sd0; hold5 <= 16'sd0; hold6 <= 16'sd0;
      read_prefetch_active <= 1'b0;
      read_prefetch_slot <= 1'b0;
      read_select_q1 <= 1'b0;
      read_start_hold <= 1'b0;
      read_expected_addr <= 8'd0;
      read_next_addr <= 8'd0;
    end else begin
      done_o <= 1'b0;
      zeroize_done_o <= 1'b0;

      if (state != P_IDLE || load_we_i || start_i || zeroize_i) begin
        read_prefetch_active <= 1'b0;
      end else if (read_restart) begin
        read_prefetch_active <= 1'b1;
        read_prefetch_slot <= read_slot_i;
        read_select_q1 <= 1'b0;
        read_start_hold <= 1'b1;
        read_expected_addr <= read_addr_i;
        read_next_addr <= read_addr_i + 8'd2;
      end else begin
        read_select_q1 <= ~read_select_q1;
        read_next_addr <= read_next_addr + 8'd1;
        read_expected_addr <= read_expected_addr + 8'd1;
        if (read_start_hold) read_start_hold <= 1'b0;
      end

      if (zeroize_i && state != P_ZEROIZE) begin
        state <= P_ZEROIZE;
        zero_index <= 8'd0;
        busy_o <= 1'b0;
        zeroize_busy_o <= 1'b1;
        error_o <= 1'b0;
      end else begin
        case (state)
          P_IDLE: begin
            busy_o <= 1'b0;
            zeroize_busy_o <= 1'b0;
            if (start_i) begin
              busy_o <= 1'b1;
              error_o <= 1'b0;
              case (operation_i)
                2'd1: begin len_reg <= 8'd128; start_reg <= 9'd0; k_reg <= 8'd1; state <= P_NTT_GROUP; end
                2'd2: begin len_reg <= 8'd2; start_reg <= 9'd0; k_reg <= 8'd127; state <= P_INTT_GROUP; end
                2'd3: begin bm_index <= 8'd0; state <= P_BM0_READ; end
                default: begin error_o <= 1'b1; state <= P_DONE; end
              endcase
            end
          end

          P_NTT_GROUP: begin
            if (start_reg >= 9'd256) begin
              if (len_reg == 8'd2) state <= P_DONE;
              else begin len_reg <= len_reg >> 1; start_reg <= 9'd0; end
            end else begin
              zeta_reg <= zeta(k_reg);
              k_reg <= k_reg + 8'd1;
              j_reg <= start_reg;
              state <= P_NTT_READ;
            end
          end
          P_NTT_READ: state <= P_NTT_MUL;
          P_NTT_MUL: begin hold0 <= mul_result; state <= P_NTT_WRITE; end
          P_NTT_WRITE: begin
            if (j_reg == start_reg + len_reg - 9'd1) begin
              start_reg <= start_reg + ({1'b0, len_reg} << 1);
              state <= P_NTT_GROUP;
            end else begin
              j_reg <= j_reg + 9'd1;
              state <= P_NTT_READ;
            end
          end

          P_INTT_GROUP: begin
            if (start_reg >= 9'd256) begin
              if (len_reg == 8'd128) begin scale_index <= 8'd0; state <= P_SCALE_READ; end
              else begin len_reg <= len_reg << 1; start_reg <= 9'd0; end
            end else begin
              zeta_reg <= zeta(k_reg);
              k_reg <= k_reg - 8'd1;
              j_reg <= start_reg;
              state <= P_INTT_READ;
            end
          end
          P_INTT_READ: state <= P_INTT_MUL;
          P_INTT_MUL: begin hold0 <= mul_result; state <= P_INTT_WRITE; end
          P_INTT_WRITE: begin
            if (j_reg == start_reg + len_reg - 9'd1) begin
              start_reg <= start_reg + ({1'b0, len_reg} << 1);
              state <= P_INTT_GROUP;
            end else begin
              j_reg <= j_reg + 9'd1;
              state <= P_INTT_READ;
            end
          end

          P_SCALE_READ: state <= P_SCALE_MUL;
          P_SCALE_MUL: begin hold0 <= mul_result; state <= P_SCALE_WRITE; end
          P_SCALE_WRITE: begin
            if (scale_index == 8'd255) state <= P_DONE;
            else begin scale_index <= scale_index + 8'd1; state <= P_SCALE_READ; end
          end

          P_BM0_READ: begin zeta_reg <= zeta(8'd64 + bm_index); state <= P_BM0_M0; end
          P_BM0_M0: begin hold0 <= mul_result; state <= P_BM0_M1; end
          P_BM0_M1: begin hold1 <= mul_result; state <= P_BM0_M2; end
          P_BM0_M2: begin hold2 <= mul_result; state <= P_BM0_M3; end
          P_BM0_M3: begin hold3 <= mul_result; state <= P_BM0_M4; end
          P_BM0_M4: begin hold4 <= mul_result; state <= P_BM0_M5; end
          P_BM0_M5: begin hold5 <= mul_result; state <= P_BM0_M6; end
          P_BM0_M6: begin hold6 <= mul_result; state <= P_BM0_WRITE; end
          P_BM0_WRITE: state <= P_BM1_READ;

          P_BM1_READ: begin zeta_reg <= -zeta(8'd64 + bm_index); state <= P_BM1_M0; end
          P_BM1_M0: begin hold0 <= mul_result; state <= P_BM1_M1; end
          P_BM1_M1: begin hold1 <= mul_result; state <= P_BM1_M2; end
          P_BM1_M2: begin hold2 <= mul_result; state <= P_BM1_M3; end
          P_BM1_M3: begin hold3 <= mul_result; state <= P_BM1_M4; end
          P_BM1_M4: begin hold4 <= mul_result; state <= P_BM1_M5; end
          P_BM1_M5: begin hold5 <= mul_result; state <= P_BM1_M6; end
          P_BM1_M6: begin hold6 <= mul_result; state <= P_BM1_WRITE; end
          P_BM1_WRITE: begin
            if (bm_index == 8'd63) state <= P_DONE;
            else begin bm_index <= bm_index + 8'd1; state <= P_BM0_READ; end
          end

          P_ZEROIZE: begin
            if (zero_index == 8'd255) begin
              zeroize_busy_o <= 1'b0;
              zeroize_done_o <= 1'b1;
              state <= P_IDLE;
            end else zero_index <= zero_index + 8'd1;
          end

          P_DONE: begin
            busy_o <= 1'b0;
            done_o <= 1'b1;
            state <= P_IDLE;
          end
          default: state <= P_IDLE;
        endcase
      end
    end
  end
endmodule
