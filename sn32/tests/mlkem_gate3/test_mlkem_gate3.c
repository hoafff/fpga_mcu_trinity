#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "trinity_mlkem.h"

/* Exact pinned mlkem-native reference entry points. */
int trinity_mlkem512_keypair_derand(
    uint8_t public_key[TRINITY_MLKEM512_PUBLIC_KEY_BYTES],
    uint8_t secret_key[TRINITY_MLKEM512_SECRET_KEY_BYTES],
    const uint8_t coins[TRINITY_MLKEM_KEYGEN_COINS_BYTES]);
int trinity_mlkem512_enc_derand(
    uint8_t ciphertext[TRINITY_MLKEM512_CIPHERTEXT_BYTES],
    uint8_t shared_secret[TRINITY_MLKEM_SHARED_SECRET_BYTES],
    const uint8_t public_key[TRINITY_MLKEM512_PUBLIC_KEY_BYTES],
    const uint8_t coins[TRINITY_MLKEM_ENCAPS_COINS_BYTES]);
int trinity_mlkem512_dec(
    uint8_t shared_secret[TRINITY_MLKEM_SHARED_SECRET_BYTES],
    const uint8_t ciphertext[TRINITY_MLKEM512_CIPHERTEXT_BYTES],
    const uint8_t secret_key[TRINITY_MLKEM512_SECRET_KEY_BYTES]);

static uint8_t public_key_a[TRINITY_MLKEM512_PUBLIC_KEY_BYTES];
static uint8_t public_key_b[TRINITY_MLKEM512_PUBLIC_KEY_BYTES];
static uint8_t secret_key_a[TRINITY_MLKEM512_SECRET_KEY_BYTES];
static uint8_t secret_key_b[TRINITY_MLKEM512_SECRET_KEY_BYTES];
static uint8_t ciphertext_a[TRINITY_MLKEM512_CIPHERTEXT_BYTES];
static uint8_t ciphertext_b[TRINITY_MLKEM512_CIPHERTEXT_BYTES];
static uint8_t shared_secret_a[TRINITY_MLKEM_SHARED_SECRET_BYTES];
static uint8_t shared_secret_b[TRINITY_MLKEM_SHARED_SECRET_BYTES];

static int deterministic_entropy(uint8_t *output, size_t length, void *context) {
    uint32_t *counter = (uint32_t *)context;
    size_t index;
    for (index = 0u; index < length; ++index) {
        output[index] = (uint8_t)(*counter + (uint32_t)index);
    }
    *counter += (uint32_t)length;
    return 0;
}

static int failing_entropy(uint8_t *output, size_t length, void *context) {
    (void)output;
    (void)length;
    (void)context;
    return -1;
}

static int all_zero(const uint8_t *buffer, size_t length) {
    size_t index;
    uint8_t value = 0u;
    for (index = 0u; index < length; ++index) {
        value |= buffer[index];
    }
    return value == 0u;
}

static void test_deterministic_mlkem(void) {
    uint8_t keygen_coins[TRINITY_MLKEM_KEYGEN_COINS_BYTES];
    uint8_t encaps_coins[TRINITY_MLKEM_ENCAPS_COINS_BYTES];
    uint8_t corrupted[TRINITY_MLKEM512_CIPHERTEXT_BYTES];
    uint8_t rejected_secret[TRINITY_MLKEM_SHARED_SECRET_BYTES];
    uint8_t reference_rejected_secret[TRINITY_MLKEM_SHARED_SECRET_BYTES];
    size_t index;

    for (index = 0u; index < sizeof(keygen_coins); ++index) {
        keygen_coins[index] = (uint8_t)index;
    }
    for (index = 0u; index < sizeof(encaps_coins); ++index) {
        encaps_coins[index] = (uint8_t)(0xA0u + index);
    }

    assert(trinity_mlkem512_keygen_deterministic(public_key_a, secret_key_a,
                                                  keygen_coins) == TRINITY_OK);
    assert(trinity_mlkem512_keypair_derand(public_key_b, secret_key_b,
                                           keygen_coins) == 0);
    assert(memcmp(public_key_a, public_key_b, sizeof(public_key_a)) == 0);
    assert(memcmp(secret_key_a, secret_key_b, sizeof(secret_key_a)) == 0);

    memset(public_key_b, 0, sizeof(public_key_b));
    memset(secret_key_b, 0, sizeof(secret_key_b));
    assert(trinity_mlkem512_keygen_deterministic(public_key_b, secret_key_b,
                                                  keygen_coins) == TRINITY_OK);
    assert(memcmp(public_key_a, public_key_b, sizeof(public_key_a)) == 0);
    assert(memcmp(secret_key_a, secret_key_b, sizeof(secret_key_a)) == 0);

    assert(trinity_mlkem512_encaps_deterministic(ciphertext_a, shared_secret_a,
                                                  public_key_a,
                                                  encaps_coins) == TRINITY_OK);
    assert(trinity_mlkem512_enc_derand(ciphertext_b, shared_secret_b,
                                       public_key_a, encaps_coins) == 0);
    assert(memcmp(ciphertext_a, ciphertext_b, sizeof(ciphertext_a)) == 0);
    assert(memcmp(shared_secret_a, shared_secret_b, sizeof(shared_secret_a)) == 0);

    memset(shared_secret_b, 0, sizeof(shared_secret_b));
    assert(trinity_mlkem512_decaps(shared_secret_b, ciphertext_a,
                                   secret_key_a) == TRINITY_OK);
    assert(trinity_constant_time_equal(shared_secret_a, shared_secret_b,
                                       sizeof(shared_secret_a)));

    memcpy(corrupted, ciphertext_a, sizeof(corrupted));
    corrupted[17] ^= 0x01u;
    assert(trinity_mlkem512_decaps(rejected_secret, corrupted,
                                   secret_key_a) == TRINITY_OK);
    assert(trinity_mlkem512_dec(reference_rejected_secret, corrupted,
                                secret_key_a) == 0);
    assert(!trinity_constant_time_equal(shared_secret_a, rejected_secret,
                                        sizeof(shared_secret_a)));
    assert(trinity_constant_time_equal(rejected_secret,
                                       reference_rejected_secret,
                                       sizeof(rejected_secret)));

    trinity_secure_zero(keygen_coins, sizeof(keygen_coins));
    trinity_secure_zero(encaps_coins, sizeof(encaps_coins));
    trinity_secure_zero(corrupted, sizeof(corrupted));
    trinity_secure_zero(rejected_secret, sizeof(rejected_secret));
    trinity_secure_zero(reference_rejected_secret,
                        sizeof(reference_rejected_secret));
}

static void test_kdf_vector(void) {
    static const uint8_t expected_key[16] = {
        0xB8, 0xB5, 0x5F, 0x17, 0xB3, 0x3F, 0xDF, 0x3D,
        0x3D, 0x45, 0x89, 0xFE, 0xE9, 0xEE, 0x8A, 0x37
    };
    static const uint8_t expected_nonce_prefix[8] = {
        0xD7, 0xDA, 0x5D, 0x32, 0x0B, 0xDA, 0xE1, 0xC9
    };
    uint8_t shared_secret[32];
    uint8_t ciphertext[768];
    trinity_session_material_t material;
    size_t index;

    for (index = 0u; index < sizeof(shared_secret); ++index) {
        shared_secret[index] = (uint8_t)index;
    }
    for (index = 0u; index < sizeof(ciphertext); ++index) {
        ciphertext[index] = (uint8_t)index;
    }

    assert(trinity_kdf_derive_session(&material, shared_secret,
                                      ciphertext) == TRINITY_OK);
    assert(memcmp(material.ascon_key, expected_key, sizeof(expected_key)) == 0);
    assert(memcmp(material.nonce_prefix, expected_nonce_prefix,
                  sizeof(expected_nonce_prefix)) == 0);
    assert(material.session_id == UINT32_C(0x656BFD7A));

    trinity_session_material_zeroize(&material);
    assert(all_zero((const uint8_t *)&material, sizeof(material)));
    trinity_secure_zero(shared_secret, sizeof(shared_secret));
    trinity_secure_zero(ciphertext, sizeof(ciphertext));
}

static void test_entropy_and_error_latch(void) {
    uint32_t counter = 1u;
    trinity_mlkem_backend_set_entropy_provider(deterministic_entropy, &counter);
    assert(trinity_mlkem512_keygen(public_key_a, secret_key_a) == TRINITY_OK);
    assert(!all_zero(public_key_a, sizeof(public_key_a)));
    assert(!all_zero(secret_key_a, sizeof(secret_key_a)));

    memset(public_key_b, 0xA5, sizeof(public_key_b));
    memset(secret_key_b, 0xA5, sizeof(secret_key_b));
    trinity_mlkem_backend_set_entropy_provider(failing_entropy, NULL);
    assert(trinity_mlkem512_keygen(public_key_b, secret_key_b) == TRINITY_INTERNAL_FAULT);
    assert(all_zero(public_key_b, sizeof(public_key_b)));
    assert(all_zero(secret_key_b, sizeof(secret_key_b)));
    assert(trinity_mlkem_backend_error() == TRINITY_INTERNAL_FAULT);

    trinity_mlkem_backend_clear_error();
    trinity_mlkem_backend_latch_error(TRINITY_BAD_STATE, 7u);
    trinity_mlkem_backend_latch_error(TRINITY_INTERNAL_FAULT, 9u);
    assert(trinity_mlkem_backend_error() == TRINITY_BAD_STATE);
    assert(trinity_mlkem_backend_error_detail() == 7u);
}

int main(void) {
    test_deterministic_mlkem();
    test_kdf_vector();
    test_entropy_and_error_latch();

    trinity_secure_zero(public_key_a, sizeof(public_key_a));
    trinity_secure_zero(public_key_b, sizeof(public_key_b));
    trinity_secure_zero(secret_key_a, sizeof(secret_key_a));
    trinity_secure_zero(secret_key_b, sizeof(secret_key_b));
    trinity_secure_zero(ciphertext_a, sizeof(ciphertext_a));
    trinity_secure_zero(ciphertext_b, sizeof(ciphertext_b));
    trinity_secure_zero(shared_secret_a, sizeof(shared_secret_a));
    trinity_secure_zero(shared_secret_b, sizeof(shared_secret_b));

    puts("PASS: ML-KEM-512 low-RAM KeyGen, Encaps, Decaps, implicit rejection and KDF");
    return 0;
}
