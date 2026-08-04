    UART_TIMEOUT_MS = 100u,
    PC_FRAME_TIMEOUT_MS = 250u,
    /* Match the ESP32-C3 harness that hardware-qualified P1/P2 responses. */
    SPI_RESPONSE_SETTLE_MS = 15u,
    /* Allow Primer startup scrub and SN32 SPI/pinmux settling before probe 1. */
    SPI_STARTUP_WARMUP_MS = 2000u,
    SPI_RESPONSE_SAMPLE_MAX = 8u,
    SPI_TRANSFER_STAGE_NONE = 0u,
    SPI_TRANSFER_STAGE_TX_FULL = 1u,
    SPI_TRANSFER_STAGE_BUSY = 2u,
    SPI_TRANSFER_STAGE_RX_EMPTY = 3u,
    SPI_TRANSFER_DIRECTION_NONE = 0u,
    SPI_TRANSFER_DIRECTION_REQUEST = 1u,
    SPI_TRANSFER_DIRECTION_RESPONSE = 2u,
    SPI_TRACE_CONTEXT_NONE = 0u,
    SPI_TRACE_CONTEXT_STARTUP_DRAIN_P1 = 1u,
    SPI_TRACE_CONTEXT_STARTUP_DRAIN_P2 = 2u,
    SPI_TRACE_CONTEXT_STARTUP_PROBE = 3u,
    SPI_TRACE_CONTEXT_PERIODIC_PROBE = 4u,
    SPI_TRACE_CONTEXT_HOST_DIAGNOSTIC = 5u
};

typedef struct {
    uint8_t id;
    unsigned cs_port;
    unsigned cs_pin;
    unsigned irq_port;
    unsigned irq_pin;
    bool ready;
    uint32_t capabilities;
    uint32_t build_id;
    uint8_t session_state;
    uint8_t operation_state;
    uint8_t pending_flags;
    uint8_t secure_flags;
    uint32_t session_id;
    uint16_t last_error;
    uint16_t active_transaction_id;
    uint32_t diagnostic_summary;
} endpoint_t;

typedef struct {
    trinity_error_code_t code;
    trinity_source_t source;
    uint32_t detail;
} error_record_t;

typedef struct {
    bool valid;
    uint8_t context;
    uint8_t target_id;
    uint8_t command;
    trinity_source_t source;
    trinity_error_code_t result_code;
    uint16_t target_txid;
    uint32_t request_fingerprint;
    uint16_t request_length;
    uint16_t response_capture_length;
    uint16_t response_frame_length;
    uint16_t request_crc;
    uint16_t response_crc_received;
    uint16_t response_crc_calculated;
    bool irq_before_request;
    bool irq_after_request;
    bool irq_before_response;
    bool irq_after_response;
    uint8_t transfer_stage;
    uint8_t transfer_direction;
    uint16_t transfer_byte_index;
    uint16_t transfer_length;
    uint16_t transfer_completed;
    uint32_t spi_status;
    uint32_t spi_ctrl0;
    uint32_t spi_ctrl1;
    uint32_t spi_clkdiv;
    uint32_t spi_fifo_th;
    uint8_t response_sample_count;
    uint32_t response_status_before_read[SPI_RESPONSE_SAMPLE_MAX];
    uint32_t response_data_words[SPI_RESPONSE_SAMPLE_MAX];
    uint32_t response_status_after_read[SPI_RESPONSE_SAMPLE_MAX];
} spi_exchange_trace_t;

typedef struct {
    spi_exchange_trace_t metadata;
    uint8_t request_bytes[TRINITY_SPI_MAX_PACKET];
    uint8_t response_bytes[TRINITY_SPI_MAX_PACKET];
} spi_retained_trace_t;

typedef struct {
    bool valid;
    uint16_t host_txid;
    uint16_t target_txid;
    uint8_t original_host_command;
    uint8_t result_system_state;
    uint8_t result_source;
    uint16_t result_related_target_txid;
    uint32_t request_fingerprint;
    trinity_transaction_state_t state;
    trinity_error_code_t result_code;
    uint16_t result_length;
    uint8_t result_data[P1_SELF_TEST_RESULT_MAX];
} host_transaction_t;

volatile uint32_t g_trinity_deploy_marker;
volatile uint32_t g_trinity_deploy_last_error;

static volatile uint32_t g_ms;
static volatile uint32_t g_progress_ms;
static volatile uint32_t g_heartbeat_ms;
static volatile uint32_t g_guard_faults;
static volatile uint32_t g_crypto_lease_deadline_ms;
static volatile bool g_crypto_lease_active;
static volatile bool g_fault;
static volatile bool g_spi_selected;
static bool g_uart_ready;
static bool g_spi_ready;
static bool g_heartbeat_level;
static bool g_pc_service_enabled;
static bool g_pc_poll_active;
static bool g_pc_frame_pending;
static bool g_automatic_probe_active;
static uint16_t g_spi_txid = 1u;
static uint16_t g_active_host_txid;
static uint8_t g_spi_trace_context;
static error_record_t g_error;

/*
 * Work and retained traces have separate, fixed storage. Hardware v0.7.19
 * showed retained byte data changing even while the sampled SPI DATA words
 * remained correct. A failure is now copied once into this dedicated snapshot
 * and no transport path writes it.
 */
static spi_exchange_trace_t g_spi_trace;
static spi_retained_trace_t g_spi_retained_trace;
static bool g_spi_retained_failure;
static bool g_spi_retained_startup_residue;

static host_transaction_t g_host_txn;
static trinity_controller_t g_controller;
static trinity_deploy_crypto_t g_crypto;

static endpoint_t g_p1 = {
