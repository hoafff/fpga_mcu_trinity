#ifndef TRINITY_MLKEM_H
#define TRINITY_MLKEM_H

#include <stdint.h>

#include "trinity_mlkem_backend.h"

#ifdef __cplusplus
extern "C" {
#endif

#define TRINITY_MLKEM512_PUBLIC_KEY_BYTES 800u
#define TRINITY_MLKEM512_SECRET_KEY_BYTES 1632u
#define TRINITY_MLKEM512_CIPHERTEXT_BYTES 768u
#define TRINITY_MLKEM_SHARED_SECRET_BYTES 32u
#define TRINITY_MLKEM_KEYGEN_COINS_BYTES 64u
#define TRINITY_MLKEM_ENCAPS_COINS_BYTES 32u
#define TRINITY_ASCON_KEY_BYTES 16u
#define TRINITY_NONCE_PREFIX_BYTES 8u
#define TRINITY_SESSION_ID_BYTES 4u
#define TRINITY_KDF_OUTPUT_BYTES 28u

typedef struct {
    uint8_t ascon_key[TRINITY_ASCON_KEY_BYTES];
    uint8_t nonce_prefix[TRINITY_NONCE_PREFIX_BYTES];
    uint32_t session_id;
} trinity_session_material_t;

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
