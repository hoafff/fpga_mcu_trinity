    UART_TIMEOUT_MS = 100u,
    PC_FRAME_TIMEOUT_MS = 250u,
    SPI_RESPONSE_SETTLE_MS = 1u
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
    uint16_t host_txid;
    uint16_t target_txid;
    uint8_t original_host_command;
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
static volatile bool g_fault;
static volatile bool g_spi_selected;
static bool g_uart_ready;
static bool g_spi_ready;
static bool g_heartbeat_level;
static uint16_t g_spi_txid = 1u;
static uint16_t g_active_host_txid;
static error_record_t g_error;
static host_transaction_t g_host_txn;
static trinity_controller_t g_controller;
static trinity_deploy_crypto_t g_crypto;

static endpoint_t g_p1 = {
