#include "trinity_mlkem.h"

#include <stddef.h>
#include <string.h>

/* The exact pinned mlkem-native build also exposes its namespaced internal
 * single-polynomial primitives. The compiler supplies MLK_CONFIG_PARAMETER_SET
 * and MLK_CONFIG_NAMESPACE_PREFIX before these headers are included. */
#include "src/compress.h"
#include "src/poly.h"
#include "src/poly_k.h"
#include "src/sampling.h"

/* common.h, included above, derives the public API parameter-set and namespace
 * settings from the internal build configuration. */
#define MLK_CONFIG_API_NO_SUPERCOP
#include "mlkem_native.h"

/* These one-shot FIPS-202 functions are part of the exact pinned upstream
 * implementation and use MLK_CONFIG_NAMESPACE_PREFIX at link time. */
void trinity_mlkem512_sha3_256(uint8_t output[32],
                               const uint8_t *input,
                               size_t input_length);
void trinity_mlkem512_sha3_512(uint8_t output[64],
                               const uint8_t *input,
                               size_t input_length);
void trinity_mlkem512_shake256(uint8_t *output,
                               size_t output_length,
                               const uint8_t *input,
                               size_t input_length);

typedef struct {
    mlk_poly accumulator;
    mlk_poly matrix_entry;
    mlk_poly vector_entry;
    mlk_poly_mulcache vector_cache;
} trinity_mlkem512_lowram_keygen_workspace_t;

/* One shared, non-reentrant workspace replaces the upstream keygen stack
 * frame containing a full 2x2 matrix and three complete polyvec objects.
 * Firmware dispatch is single-threaded and allows only one managed crypto
 * transaction at a time. */
static trinity_mlkem512_lowram_keygen_workspace_t g_lowram_keygen;

static trinity_error_code_t trinity_upstream_result(int result,
                                                     void *primary_output,
                                                     size_t primary_length,
                                                     void *secondary_output,
                                                     size_t secondary_length) {
    trinity_error_code_t error = trinity_mlkem_backend_error();
    if (result != 0 && error == TRINITY_OK) {
        error = TRINITY_INTERNAL_FAULT;
        trinity_mlkem_backend_latch_error(error, (uint32_t)(unsigned int)(-result));
    }
    if (error != TRINITY_OK) {
        trinity_secure_zero(primary_output, primary_length);
        trinity_secure_zero(secondary_output, secondary_length);
    }
    return error;
}

static void trinity_lowram_sample_eta1(mlk_poly *output,
                                       const uint8_t seed[MLKEM_SYMBYTES],
                                       uint8_t nonce) {
    uint8_t input[MLKEM_SYMBYTES + 1u];
    uint8_t sample[MLKEM_ETA1 * MLKEM_N / 4u];

    memcpy(input, seed, MLKEM_SYMBYTES);
    input[MLKEM_SYMBYTES] = nonce;
    trinity_mlkem512_shake256(sample, sizeof(sample), input, sizeof(input));
#if MLKEM_ETA1 == 3
    mlk_poly_cbd3(output, sample);
#elif MLKEM_ETA1 == 2
    mlk_poly_cbd2(output, sample);
#else
#error "Unsupported ML-KEM eta1"
#endif
    trinity_secure_zero(sample, sizeof(sample));
    trinity_secure_zero(input, sizeof(input));
}

static void trinity_lowram_matrix_entry(
    mlk_poly *output,
    const uint8_t seed[MLKEM_SYMBYTES],
    uint8_t row,
    uint8_t column,
    int transposed) {
    uint8_t extended_seed[MLKEM_SYMBYTES + 2u];

    memcpy(extended_seed, seed, MLKEM_SYMBYTES);
    if (transposed != 0) {
        extended_seed[MLKEM_SYMBYTES] = row;
        extended_seed[MLKEM_SYMBYTES + 1u] = column;
    } else {
        extended_seed[MLKEM_SYMBYTES] = column;
        extended_seed[MLKEM_SYMBYTES + 1u] = row;
    }
    mlk_poly_rej_uniform(output, extended_seed);
    trinity_secure_zero(extended_seed, sizeof(extended_seed));
}

static void trinity_lowram_basemul_accumulate(
    mlk_poly *accumulator,
    const mlk_poly *left,
    const mlk_poly *right,
    const mlk_poly_mulcache *right_cache,
    int initialize) {
    unsigned index;

    for (index = 0u; index < MLKEM_N / 2u; ++index) {
        int32_t value0;
        int32_t value1;
        int16_t reduced0;
        int16_t reduced1;

        value0 = (int32_t)left->coeffs[2u * index + 1u] *
                 right_cache->coeffs[index];
        value0 += (int32_t)left->coeffs[2u * index] *
                  right->coeffs[2u * index];
        value1 = (int32_t)left->coeffs[2u * index] *
                 right->coeffs[2u * index + 1u];
        value1 += (int32_t)left->coeffs[2u * index + 1u] *
                  right->coeffs[2u * index];
        reduced0 = mlk_montgomery_reduce(value0);
        reduced1 = mlk_montgomery_reduce(value1);

        if (initialize != 0) {
            accumulator->coeffs[2u * index] = reduced0;
            accumulator->coeffs[2u * index + 1u] = reduced1;
        } else {
            accumulator->coeffs[2u * index] =
                (int16_t)(accumulator->coeffs[2u * index] + reduced0);
            accumulator->coeffs[2u * index + 1u] =
                (int16_t)(accumulator->coeffs[2u * index + 1u] + reduced1);
        }
    }
}

static trinity_error_code_t trinity_mlkem512_keygen_deterministic_lowram(
    uint8_t public_key[TRINITY_MLKEM512_PUBLIC_KEY_BYTES],
    uint8_t secret_key[TRINITY_MLKEM512_SECRET_KEY_BYTES],
    const uint8_t coins[TRINITY_MLKEM_KEYGEN_COINS_BYTES]) {
    uint8_t seeds[2u * MLKEM_SYMBYTES];
    uint8_t coins_with_domain_separator[MLKEM_SYMBYTES + 1u];
    unsigned row;
    unsigned column;

    memcpy(coins_with_domain_separator, coins, MLKEM_SYMBYTES);
    coins_with_domain_separator[MLKEM_SYMBYTES] = MLKEM_K;
    trinity_mlkem512_sha3_512(seeds, coins_with_domain_separator,
                              sizeof(coins_with_domain_separator));

    /* Serialize each secret polynomial immediately. This avoids retaining
     * the complete secret polyvec while preserving the exact FIPS 203 byte
     * representation used by the pinned backend. */
    for (column = 0u; column < MLKEM_K; ++column) {
        trinity_lowram_sample_eta1(&g_lowram_keygen.vector_entry,
                                   &seeds[MLKEM_SYMBYTES],
                                   (uint8_t)column);
        mlk_poly_ntt(&g_lowram_keygen.vector_entry);
        mlk_poly_reduce(&g_lowram_keygen.vector_entry);
        mlk_poly_tobytes(secret_key + column * MLKEM_POLYBYTES,
                         &g_lowram_keygen.vector_entry);
    }

    /* Recreate one matrix entry and one serialized secret polynomial at a
     * time. Recomputing/unpacking trades execution time for a bounded RAM
     * footprint and keeps the public-key result byte-compatible. */
    for (row = 0u; row < MLKEM_K; ++row) {
        for (column = 0u; column < MLKEM_K; ++column) {
            trinity_lowram_matrix_entry(&g_lowram_keygen.matrix_entry,
                                        seeds,
                                        (uint8_t)row,
                                        (uint8_t)column,
                                        0);
            mlk_poly_frombytes(&g_lowram_keygen.vector_entry,
                               secret_key + column * MLKEM_POLYBYTES);
            mlk_poly_mulcache_compute(&g_lowram_keygen.vector_cache,
                                      &g_lowram_keygen.vector_entry);
            trinity_lowram_basemul_accumulate(
                &g_lowram_keygen.accumulator,
                &g_lowram_keygen.matrix_entry,
                &g_lowram_keygen.vector_entry,
                &g_lowram_keygen.vector_cache,
                column == 0u);
        }

        mlk_poly_tomont(&g_lowram_keygen.accumulator);
        trinity_lowram_sample_eta1(&g_lowram_keygen.vector_entry,
                                   &seeds[MLKEM_SYMBYTES],
                                   (uint8_t)(MLKEM_K + row));
        mlk_poly_ntt(&g_lowram_keygen.vector_entry);
        mlk_poly_add(&g_lowram_keygen.accumulator,
                     &g_lowram_keygen.vector_entry);
        mlk_poly_reduce(&g_lowram_keygen.accumulator);
        mlk_poly_tobytes(public_key + row * MLKEM_POLYBYTES,
                         &g_lowram_keygen.accumulator);
    }

    memcpy(public_key + MLKEM_POLYVECBYTES, seeds, MLKEM_SYMBYTES);
    if (public_key != secret_key + TRINITY_MLKEM512_PUBLIC_KEY_IN_SECRET_KEY_OFFSET) {
        memcpy(secret_key + TRINITY_MLKEM512_PUBLIC_KEY_IN_SECRET_KEY_OFFSET,
               public_key, TRINITY_MLKEM512_PUBLIC_KEY_BYTES);
    }
    trinity_mlkem512_sha3_256(
        secret_key + TRINITY_MLKEM512_SECRET_KEY_BYTES - 2u * MLKEM_SYMBYTES,
        public_key, TRINITY_MLKEM512_PUBLIC_KEY_BYTES);
    memcpy(secret_key + TRINITY_MLKEM512_SECRET_KEY_BYTES - MLKEM_SYMBYTES,
           coins + MLKEM_SYMBYTES, MLKEM_SYMBYTES);

    trinity_secure_zero(&g_lowram_keygen, sizeof(g_lowram_keygen));
    trinity_secure_zero(seeds, sizeof(seeds));
    trinity_secure_zero(coins_with_domain_separator,
                        sizeof(coins_with_domain_separator));
    return TRINITY_OK;
}

trinity_error_code_t trinity_mlkem512_keygen_deterministic(
    uint8_t public_key[TRINITY_MLKEM512_PUBLIC_KEY_BYTES],
    uint8_t secret_key[TRINITY_MLKEM512_SECRET_KEY_BYTES],
    const uint8_t coins[TRINITY_MLKEM_KEYGEN_COINS_BYTES]) {
    if (public_key == NULL || secret_key == NULL || coins == NULL) {
        return TRINITY_INTERNAL_FAULT;
    }
    trinity_mlkem_backend_clear_error();
    return trinity_mlkem512_keygen_deterministic_lowram(
        public_key, secret_key, coins);
}

trinity_error_code_t trinity_mlkem512_encaps_deterministic(
    uint8_t ciphertext[TRINITY_MLKEM512_CIPHERTEXT_BYTES],
    uint8_t shared_secret[TRINITY_MLKEM_SHARED_SECRET_BYTES],
    const uint8_t public_key[TRINITY_MLKEM512_PUBLIC_KEY_BYTES],
    const uint8_t coins[TRINITY_MLKEM_ENCAPS_COINS_BYTES]) {
    int result;
    if (ciphertext == NULL || shared_secret == NULL || public_key == NULL || coins == NULL) {
        return TRINITY_INTERNAL_FAULT;
    }
    trinity_mlkem_backend_clear_error();
    result = trinity_mlkem512_enc_derand(ciphertext, shared_secret, public_key, coins);
    return trinity_upstream_result(result,
                                   ciphertext, TRINITY_MLKEM512_CIPHERTEXT_BYTES,
                                   shared_secret, TRINITY_MLKEM_SHARED_SECRET_BYTES);
}

trinity_error_code_t trinity_mlkem512_decaps(
    uint8_t shared_secret[TRINITY_MLKEM_SHARED_SECRET_BYTES],
    const uint8_t ciphertext[TRINITY_MLKEM512_CIPHERTEXT_BYTES],
    const uint8_t secret_key[TRINITY_MLKEM512_SECRET_KEY_BYTES]) {
    int result;
    if (shared_secret == NULL || ciphertext == NULL || secret_key == NULL) {
        return TRINITY_INTERNAL_FAULT;
    }
    trinity_mlkem_backend_clear_error();
    result = trinity_mlkem512_dec(shared_secret, ciphertext, secret_key);
    return trinity_upstream_result(result,
                                   shared_secret, TRINITY_MLKEM_SHARED_SECRET_BYTES,
                                   NULL, 0u);
}

trinity_error_code_t trinity_mlkem512_keygen(
    uint8_t public_key[TRINITY_MLKEM512_PUBLIC_KEY_BYTES],
    uint8_t secret_key[TRINITY_MLKEM512_SECRET_KEY_BYTES]) {
    uint8_t coins[TRINITY_MLKEM_KEYGEN_COINS_BYTES];
    trinity_error_code_t error;
    if (public_key == NULL || secret_key == NULL) {
        return TRINITY_INTERNAL_FAULT;
    }
    trinity_mlkem_backend_clear_error();
    error = trinity_mlkem_backend_entropy(coins, sizeof(coins));
    if (error == TRINITY_OK) {
        error = trinity_mlkem512_keygen_deterministic(public_key, secret_key, coins);
    } else {
        trinity_secure_zero(public_key, TRINITY_MLKEM512_PUBLIC_KEY_BYTES);
        trinity_secure_zero(secret_key, TRINITY_MLKEM512_SECRET_KEY_BYTES);
    }
    trinity_secure_zero(coins, sizeof(coins));
    return error;
}

trinity_error_code_t trinity_mlkem512_encaps(
    uint8_t ciphertext[TRINITY_MLKEM512_CIPHERTEXT_BYTES],
    uint8_t shared_secret[TRINITY_MLKEM_SHARED_SECRET_BYTES],
    const uint8_t public_key[TRINITY_MLKEM512_PUBLIC_KEY_BYTES]) {
    uint8_t coins[TRINITY_MLKEM_ENCAPS_COINS_BYTES];
    trinity_error_code_t error;
    if (ciphertext == NULL || shared_secret == NULL || public_key == NULL) {
        return TRINITY_INTERNAL_FAULT;
    }
    trinity_mlkem_backend_clear_error();
    error = trinity_mlkem_backend_entropy(coins, sizeof(coins));
    if (error == TRINITY_OK) {
        error = trinity_mlkem512_encaps_deterministic(ciphertext, shared_secret,
                                                      public_key, coins);
    } else {
        trinity_secure_zero(ciphertext, TRINITY_MLKEM512_CIPHERTEXT_BYTES);
        trinity_secure_zero(shared_secret, TRINITY_MLKEM_SHARED_SECRET_BYTES);
    }
    trinity_secure_zero(coins, sizeof(coins));
    return error;
}

trinity_error_code_t trinity_kdf_derive_session(
    trinity_session_material_t *material,
    const uint8_t shared_secret[TRINITY_MLKEM_SHARED_SECRET_BYTES],
    const uint8_t ciphertext[TRINITY_MLKEM512_CIPHERTEXT_BYTES]) {
    static const uint8_t domain[] = {
        'T', 'R', 'I', 'N', 'I', 'T', 'Y', '-', 'K', 'D', 'F', '-', 'v', '1'
    };
    uint8_t ciphertext_hash[32];
    uint8_t input[sizeof(domain) + 1u + TRINITY_MLKEM_SHARED_SECRET_BYTES + 32u];
    uint8_t output[TRINITY_KDF_OUTPUT_BYTES];
    size_t offset = 0u;

    if (material == NULL || shared_secret == NULL || ciphertext == NULL) {
        return TRINITY_INTERNAL_FAULT;
    }

    trinity_mlkem512_sha3_256(ciphertext_hash, ciphertext,
                              TRINITY_MLKEM512_CIPHERTEXT_BYTES);
    memcpy(input + offset, domain, sizeof(domain));
    offset += sizeof(domain);
    input[offset++] = 0u;
    memcpy(input + offset, shared_secret, TRINITY_MLKEM_SHARED_SECRET_BYTES);
    offset += TRINITY_MLKEM_SHARED_SECRET_BYTES;
    memcpy(input + offset, ciphertext_hash, sizeof(ciphertext_hash));
    offset += sizeof(ciphertext_hash);

    trinity_mlkem512_shake256(output, sizeof(output), input, offset);
    memcpy(material->ascon_key, output, TRINITY_ASCON_KEY_BYTES);
    memcpy(material->nonce_prefix, output + TRINITY_ASCON_KEY_BYTES,
           TRINITY_NONCE_PREFIX_BYTES);
    material->session_id = ((uint32_t)output[24] << 24) |
                           ((uint32_t)output[25] << 16) |
                           ((uint32_t)output[26] << 8) |
                           (uint32_t)output[27];

    trinity_secure_zero(output, sizeof(output));
    trinity_secure_zero(input, sizeof(input));
    trinity_secure_zero(ciphertext_hash, sizeof(ciphertext_hash));
    return TRINITY_OK;
}

void trinity_session_material_zeroize(trinity_session_material_t *material) {
    if (material != NULL) {
        trinity_secure_zero(material, sizeof(*material));
    }
}
