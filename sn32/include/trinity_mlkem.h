#ifndef TRINITY_MLKEM_H
#define TRINITY_MLKEM_H

#include <stddef.h>
#include <stdint.h>

#include "trinity_mlkem_backend.h"

#ifdef __cplusplus
extern "C" {
#endif

#define TRINITY_MLKEM512_PUBLIC_KEY_BYTES 800u
#define TRINITY_MLKEM512_SECRET_KEY_BYTES 1632u
#define TRINITY_MLKEM512_CIPHERTEXT_BYTES 768u
#define TRINITY_MLKEM512_INDCPA_SECRET_KEY_BYTES 768u
#define TRINITY_MLKEM512_PUBLIC_KEY_IN_SECRET_KEY_OFFSET \
    TRINITY_MLKEM512_INDCPA_SECRET_KEY_BYTES
#define TRINITY_MLKEM_SHARED_SECRET_BYTES 32u
#define TRINITY_MLKEM_KEYGEN_COINS_BYTES 64u
#define TRINITY_MLKEM_ENCAPS_COINS_BYTES 32u
#define TRINITY_ASCON_KEY_BYTES 16u
#define TRINITY_NONCE_PREFIX_BYTES 8u
#define TRINITY_SESSION_ID_BYTES 4u
#define TRINITY_KDF_OUTPUT_BYTES 28u

#define TRINITY_MLKEM512_LOW_RAM_WORKSPACE_BYTES 1792u
#define TRINITY_MLKEM512_LOW_RAM_WORKSPACE_ALIGNMENT 32u

#if defined(__GNUC__) || defined(__clang__)
#define TRINITY_MLKEM_WORKSPACE_ALIGN \
    __attribute__((aligned(TRINITY_MLKEM512_LOW_RAM_WORKSPACE_ALIGNMENT)))
#else
#define TRINITY_MLKEM_WORKSPACE_ALIGN
#endif

typedef struct TRINITY_MLKEM_WORKSPACE_ALIGN {
    uint8_t bytes[TRINITY_MLKEM512_LOW_RAM_WORKSPACE_BYTES];
} trinity_mlkem512_low_ram_workspace_t;

typedef struct {
    uint8_t ascon_key[TRINITY_ASCON_KEY_BYTES];
    uint8_t nonce_prefix[TRINITY_NONCE_PREFIX_BYTES];
    uint32_t session_id;
} trinity_session_material_t;

void trinity_mlkem512_bind_low_ram_workspace(
    trinity_mlkem512_low_ram_workspace_t *workspace);

void trinity_sha3_256(uint8_t output[32],
                      const uint8_t *input,
                      size_t input_length);
void trinity_shake256(uint8_t *output,
                      size_t output_length,
                      const uint8_t *input,
                      size_t input_length);

trinity_error_code_t trinity_mlkem512_keygen_deterministic(
    uint8_t public_key[TRINITY_MLKEM512_PUBLIC_KEY_BYTES],
    uint8_t secret_key[TRINITY_MLKEM512_SECRET_KEY_BYTES],
    const uint8_t coins[TRINITY_MLKEM_KEYGEN_COINS_BYTES]);

trinity_error_code_t trinity_mlkem512_encaps_deterministic(
    uint8_t ciphertext[TRINITY_MLKEM512_CIPHERTEXT_BYTES],
    uint8_t shared_secret[TRINITY_MLKEM_SHARED_SECRET_BYTES],
    const uint8_t public_key[TRINITY_MLKEM512_PUBLIC_KEY_BYTES],
    const uint8_t coins[TRINITY_MLKEM_ENCAPS_COINS_BYTES]);

trinity_error_code_t trinity_mlkem512_decaps(
    uint8_t shared_secret[TRINITY_MLKEM_SHARED_SECRET_BYTES],
    const uint8_t ciphertext[TRINITY_MLKEM512_CIPHERTEXT_BYTES],
    const uint8_t secret_key[TRINITY_MLKEM512_SECRET_KEY_BYTES]);

trinity_error_code_t trinity_mlkem512_keygen(
    uint8_t public_key[TRINITY_MLKEM512_PUBLIC_KEY_BYTES],
    uint8_t secret_key[TRINITY_MLKEM512_SECRET_KEY_BYTES]);

trinity_error_code_t trinity_mlkem512_encaps(
    uint8_t ciphertext[TRINITY_MLKEM512_CIPHERTEXT_BYTES],
    uint8_t shared_secret[TRINITY_MLKEM_SHARED_SECRET_BYTES],
    const uint8_t public_key[TRINITY_MLKEM512_PUBLIC_KEY_BYTES]);

trinity_error_code_t trinity_kdf_derive_session(
    trinity_session_material_t *material,
    const uint8_t shared_secret[TRINITY_MLKEM_SHARED_SECRET_BYTES],
    const uint8_t ciphertext[TRINITY_MLKEM512_CIPHERTEXT_BYTES]);

void trinity_session_material_zeroize(trinity_session_material_t *material);

#ifdef __cplusplus
}
#endif

#endif
