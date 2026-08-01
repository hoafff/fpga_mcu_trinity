#include "trinity_mlkem_backend.h"

static trinity_entropy_provider_t g_entropy_provider;
static void *g_entropy_context;
static trinity_error_code_t g_backend_error = TRINITY_OK;
static uint32_t g_backend_error_detail;

void trinity_secure_zero(void *buffer, size_t length) {
    volatile uint8_t *cursor = (volatile uint8_t *)buffer;
    if (cursor == NULL) {
        return;
    }
    while (length != 0u) {
        *cursor++ = 0u;
        --length;
    }
}

int trinity_constant_time_equal(const uint8_t *a, const uint8_t *b, size_t length) {
    uint8_t difference = 0u;
    size_t index;
    if ((a == NULL || b == NULL) && length != 0u) {
        return 0;
    }
    for (index = 0u; index < length; ++index) {
        difference |= (uint8_t)(a[index] ^ b[index]);
    }
    return difference == 0u;
}

void trinity_mlkem_backend_set_entropy_provider(trinity_entropy_provider_t provider,
                                                 void *context) {
    g_entropy_provider = provider;
    g_entropy_context = context;
}

trinity_error_code_t trinity_mlkem_backend_entropy(uint8_t *output, size_t length) {
    if ((output == NULL && length != 0u) || g_entropy_provider == NULL) {
        trinity_mlkem_backend_latch_error(TRINITY_NOT_SUPPORTED, 0u);
        trinity_secure_zero(output, length);
        return TRINITY_NOT_SUPPORTED;
    }
    if (g_entropy_provider(output, length, g_entropy_context) != 0) {
        trinity_mlkem_backend_latch_error(TRINITY_INTERNAL_FAULT, 1u);
        trinity_secure_zero(output, length);
        return TRINITY_INTERNAL_FAULT;
    }
    return TRINITY_OK;
}

void trinity_mlkem_backend_clear_error(void) {
    g_backend_error = TRINITY_OK;
    g_backend_error_detail = 0u;
}

void trinity_mlkem_backend_latch_error(trinity_error_code_t error,
                                       uint32_t detail) {
    if (error != TRINITY_OK && g_backend_error == TRINITY_OK) {
        g_backend_error = error;
        g_backend_error_detail = detail;
    }
}

trinity_error_code_t trinity_mlkem_backend_error(void) {
    return g_backend_error;
}

uint32_t trinity_mlkem_backend_error_detail(void) {
    return g_backend_error_detail;
}

void randombytes(uint8_t *output, size_t output_length) {
    (void)trinity_mlkem_backend_entropy(output, output_length);
}
