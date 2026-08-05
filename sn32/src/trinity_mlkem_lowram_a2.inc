/*
 * ML-KEM-512 low-RAM A2 implementation.
 *
 * The deploy image owns only one 1792-byte phase-shared workspace. During
 * session creation its first 768 bytes are the ciphertext output, while two
 * polynomial work areas occupy the remaining 1024 bytes. A single serialized
 * NTT polynomial (384 bytes) is kept on the bounded call stack. This replaces
 * the upstream polymat/polyvec temporaries and its 800-byte decapsulation
 * re-encryption buffer without changing FIPS 203 wire outputs.
 */

#if MLKEM_K != 2
#error "Trinity low-RAM A2 is intentionally restricted to ML-KEM-512"
#endif

#define TRINITY_MLKEM512_POLY_BYTES MLKEM_POLYBYTES
#define TRINITY_MLKEM512_B_POLY_BYTES MLKEM_POLYCOMPRESSEDBYTES_D10
#define TRINITY_MLKEM512_V_POLY_BYTES MLKEM_POLYCOMPRESSEDBYTES_D4
#define TRINITY_MLKEM512_B_BYTES \
    (MLKEM_K * TRINITY_MLKEM512_B_POLY_BYTES)
#define TRINITY_MLKEM512_SK_HASH_OFFSET \
    (TRINITY_MLKEM512_SECRET_KEY_BYTES - 2u * MLKEM_SYMBYTES)
#define TRINITY_MLKEM512_REJECTION_KEY_OFFSET \
    (TRINITY_MLKEM512_SECRET_KEY_BYTES - MLKEM_SYMBYTES)

typedef struct {
    uint8_t ciphertext[TRINITY_MLKEM512_CIPHERTEXT_BYTES];
    mlk_poly accumulator;
    mlk_poly scratch;
} trinity_mlkem512_lowram_a2_workspace_t;

typedef char trinity_lowram_a2_workspace_size_check[
    sizeof(trinity_mlkem512_lowram_a2_workspace_t) ==
            TRINITY_MLKEM512_LOW_RAM_WORKSPACE_BYTES
        ? 1
        : -1];

/* zetas[64..127] from the exact pinned mlkem-native zetas.inc. Keeping only
 * the BaseCaseMultiply layer lets A2 compute the multiplication cache one
 * coefficient pair at a time instead of retaining a 256-byte cache. */
static const int16_t trinity_lowram_basemul_zetas[MLKEM_N / 4u] = {
    -1103, 430, 555, 843, -1251, 871, 1550, 105,
    422, 587, 177, -235, -291, -460, 1574, 1653,
    -246, 778, 1159, -147, -777, 1483, -602, 1119,
    -1590, 644, -872, 349, 418, 329, -156, -75,
    817, 1097, 603, 610, 1322, -1285, -1465, 384,
    -1215, -136, 1218, -1335, -874, 220, -1187, -1659,
    -1185, -1530, -1278, 794, -1510, -854, -870, 478,
    -108, -308, 996, 991, 958, -1460, 1522, 1628
};

static trinity_mlkem512_lowram_a2_workspace_t *trinity_lowram_a2_workspace(void) {
    return (trinity_mlkem512_lowram_a2_workspace_t *)(void *)g_lowram_keygen;
}

static void trinity_lowram_decode12_pair(const uint8_t *encoded,
                                         unsigned pair,
                                         int16_t *coefficient0,
                                         int16_t *coefficient1) {
    const unsigned offset = 3u * pair;
    *coefficient0 = (int16_t)((uint16_t)encoded[offset] |
                              ((uint16_t)(encoded[offset + 1u] & 0x0Fu) << 8));
    *coefficient1 = (int16_t)(((uint16_t)encoded[offset + 1u] >> 4) |
                              ((uint16_t)encoded[offset + 2u] << 4));
}

static int trinity_lowram_encoded_polyvec_is_canonical(const uint8_t *encoded) {
    unsigned polynomial;
    unsigned pair;

    for (polynomial = 0u; polynomial < MLKEM_K; ++polynomial) {
        const uint8_t *poly_bytes =
            encoded + polynomial * TRINITY_MLKEM512_POLY_BYTES;
        for (pair = 0u; pair < MLKEM_N / 2u; ++pair) {
            int16_t coefficient0;
            int16_t coefficient1;
            trinity_lowram_decode12_pair(poly_bytes, pair,
                                         &coefficient0, &coefficient1);
            if (coefficient0 >= MLKEM_Q || coefficient1 >= MLKEM_Q) {
                return 0;
            }
        }
    }
    return 1;
}

static void trinity_lowram_sample_eta2(mlk_poly *output,
                                       const uint8_t seed[MLKEM_SYMBYTES],
                                       uint8_t nonce) {
    uint8_t input[MLKEM_SYMBYTES + 1u];
    uint8_t sample[MLKEM_ETA2 * MLKEM_N / 4u];

    memcpy(input, seed, MLKEM_SYMBYTES);
    input[MLKEM_SYMBYTES] = nonce;
    trinity_mlkem512_shake256(sample, sizeof(sample), input, sizeof(input));
#if MLKEM_ETA2 == 2
    mlk_poly_cbd2(output, sample);
#else
#error "Unsupported ML-KEM eta2"
#endif
    trinity_secure_zero(sample, sizeof(sample));
    trinity_secure_zero(input, sizeof(input));
}

static int16_t trinity_lowram_pair_cache(int16_t odd_coefficient,
                                         unsigned pair) {
    int16_t zeta = trinity_lowram_basemul_zetas[pair >> 1];
    if ((pair & 1u) != 0u) {
        zeta = (int16_t)-zeta;
    }
    return mlk_montgomery_reduce((int32_t)odd_coefficient * zeta);
}

static void trinity_lowram_basemul_poly_serialized_right(
    mlk_poly *accumulator,
    const mlk_poly *left,
    const uint8_t right[TRINITY_MLKEM512_POLY_BYTES],
    int initialize) {
    unsigned pair;

    for (pair = 0u; pair < MLKEM_N / 2u; ++pair) {
        int16_t right0;
        int16_t right1;
        int16_t cache;
        int16_t reduced0;
        int16_t reduced1;
        const int16_t left0 = left->coeffs[2u * pair];
        const int16_t left1 = left->coeffs[2u * pair + 1u];

        trinity_lowram_decode12_pair(right, pair, &right0, &right1);
        cache = trinity_lowram_pair_cache(right1, pair);
        reduced0 = mlk_montgomery_reduce((int32_t)left1 * cache +
                                         (int32_t)left0 * right0);
        reduced1 = mlk_montgomery_reduce((int32_t)left0 * right1 +
                                         (int32_t)left1 * right0);

        if (initialize != 0) {
            accumulator->coeffs[2u * pair] = reduced0;
            accumulator->coeffs[2u * pair + 1u] = reduced1;
        } else {
            accumulator->coeffs[2u * pair] =
                (int16_t)(accumulator->coeffs[2u * pair] + reduced0);
            accumulator->coeffs[2u * pair + 1u] =
                (int16_t)(accumulator->coeffs[2u * pair + 1u] + reduced1);
        }
    }
}

static void trinity_lowram_basemul_serialized_left_poly_right(
    mlk_poly *accumulator,
    const uint8_t left[TRINITY_MLKEM512_POLY_BYTES],
    const mlk_poly *right,
    int initialize) {
    unsigned pair;

    for (pair = 0u; pair < MLKEM_N / 2u; ++pair) {
        int16_t left0;
        int16_t left1;
        int16_t cache;
        int16_t reduced0;
        int16_t reduced1;
        const int16_t right0 = right->coeffs[2u * pair];
        const int16_t right1 = right->coeffs[2u * pair + 1u];

        trinity_lowram_decode12_pair(left, pair, &left0, &left1);
        cache = trinity_lowram_pair_cache(right1, pair);
        reduced0 = mlk_montgomery_reduce((int32_t)left1 * cache +
                                         (int32_t)left0 * right0);
        reduced1 = mlk_montgomery_reduce((int32_t)left0 * right1 +
                                         (int32_t)left1 * right0);

        if (initialize != 0) {
            accumulator->coeffs[2u * pair] = reduced0;
            accumulator->coeffs[2u * pair + 1u] = reduced1;
        } else {
            accumulator->coeffs[2u * pair] =
                (int16_t)(accumulator->coeffs[2u * pair] + reduced0);
            accumulator->coeffs[2u * pair + 1u] =
                (int16_t)(accumulator->coeffs[2u * pair + 1u] + reduced1);
        }
    }
}

typedef struct {
    uint8_t *output;
    const uint8_t *expected;
    uint8_t difference;
} trinity_lowram_ciphertext_sink_t;

static void trinity_lowram_ciphertext_emit(
    trinity_lowram_ciphertext_sink_t *sink,
    size_t offset,
    const uint8_t *data,
    size_t length) {
    size_t index;

    if (sink->output != NULL) {
        memcpy(sink->output + offset, data, length);
        return;
    }

    for (index = 0u; index < length; ++index) {
        sink->difference |= (uint8_t)(data[index] ^ sink->expected[offset + index]);
    }
}

/* Returns the accumulated ciphertext difference. Zero means byte-exact. */
static uint8_t trinity_lowram_indcpa_encrypt(
    uint8_t *ciphertext,
    const uint8_t *expected_ciphertext,
    const uint8_t message[MLKEM_INDCPA_MSGBYTES],
    const uint8_t public_key[TRINITY_MLKEM512_PUBLIC_KEY_BYTES],
    const uint8_t coins[MLKEM_SYMBYTES]) {
    trinity_mlkem512_lowram_a2_workspace_t *workspace =
        trinity_lowram_a2_workspace();
    trinity_lowram_ciphertext_sink_t sink;
    uint8_t serialized_sp[TRINITY_MLKEM512_POLY_BYTES];
    const uint8_t *matrix_seed = public_key + MLKEM_POLYVECBYTES;
    unsigned row;
    unsigned column;

    sink.output = ciphertext;
    sink.expected = expected_ciphertext;
    sink.difference = 0u;

    for (row = 0u; row < MLKEM_K; ++row) {
        for (column = 0u; column < MLKEM_K; ++column) {
            trinity_lowram_sample_eta1(&workspace->scratch, coins,
                                       (uint8_t)column);
            mlk_poly_ntt(&workspace->scratch);
            mlk_poly_reduce(&workspace->scratch);
            mlk_poly_tobytes(serialized_sp, &workspace->scratch);

            trinity_lowram_matrix_entry(&workspace->scratch,
                                        matrix_seed,
                                        (uint8_t)row,
                                        (uint8_t)column,
                                        1);
            trinity_lowram_basemul_poly_serialized_right(
                &workspace->accumulator,
                &workspace->scratch,
                serialized_sp,
                column == 0u);
        }

        mlk_poly_invntt_tomont(&workspace->accumulator);
        trinity_lowram_sample_eta2(&workspace->scratch, coins,
                                   (uint8_t)(MLKEM_K + row));
        mlk_poly_add(&workspace->accumulator, &workspace->scratch);
        mlk_poly_reduce(&workspace->accumulator);
        mlk_poly_compress_d10(serialized_sp, &workspace->accumulator);
        trinity_lowram_ciphertext_emit(
            &sink, row * TRINITY_MLKEM512_B_POLY_BYTES,
            serialized_sp, TRINITY_MLKEM512_B_POLY_BYTES);
    }

    for (column = 0u; column < MLKEM_K; ++column) {
        trinity_lowram_sample_eta1(&workspace->scratch, coins,
                                   (uint8_t)column);
        mlk_poly_ntt(&workspace->scratch);
        mlk_poly_reduce(&workspace->scratch);
        trinity_lowram_basemul_serialized_left_poly_right(
            &workspace->accumulator,
            public_key + column * TRINITY_MLKEM512_POLY_BYTES,
            &workspace->scratch,
            column == 0u);
    }

    mlk_poly_invntt_tomont(&workspace->accumulator);
    trinity_lowram_sample_eta2(&workspace->scratch, coins,
                               (uint8_t)(2u * MLKEM_K));
    mlk_poly_add(&workspace->accumulator, &workspace->scratch);
    mlk_poly_frommsg(&workspace->scratch, message);
    mlk_poly_add(&workspace->accumulator, &workspace->scratch);
    mlk_poly_reduce(&workspace->accumulator);
    mlk_poly_compress_d4(serialized_sp, &workspace->accumulator);
    trinity_lowram_ciphertext_emit(&sink, TRINITY_MLKEM512_B_BYTES,
                                   serialized_sp,
                                   TRINITY_MLKEM512_V_POLY_BYTES);

    trinity_secure_zero(serialized_sp, sizeof(serialized_sp));
    trinity_secure_zero(&workspace->accumulator,
                        sizeof(workspace->accumulator));
    trinity_secure_zero(&workspace->scratch, sizeof(workspace->scratch));
    return sink.difference;
}

static void trinity_lowram_indcpa_decrypt(
    uint8_t message[MLKEM_INDCPA_MSGBYTES],
    const uint8_t ciphertext[TRINITY_MLKEM512_CIPHERTEXT_BYTES],
    const uint8_t indcpa_secret_key[TRINITY_MLKEM512_INDCPA_SECRET_KEY_BYTES]) {
    trinity_mlkem512_lowram_a2_workspace_t *workspace =
        trinity_lowram_a2_workspace();
    unsigned column;

    for (column = 0u; column < MLKEM_K; ++column) {
        mlk_poly_decompress_d10(
            &workspace->scratch,
            ciphertext + column * TRINITY_MLKEM512_B_POLY_BYTES);
        mlk_poly_ntt(&workspace->scratch);
        mlk_poly_reduce(&workspace->scratch);
        trinity_lowram_basemul_serialized_left_poly_right(
            &workspace->accumulator,
            indcpa_secret_key + column * TRINITY_MLKEM512_POLY_BYTES,
            &workspace->scratch,
            column == 0u);
    }

    mlk_poly_invntt_tomont(&workspace->accumulator);
    mlk_poly_decompress_d4(&workspace->scratch,
                           ciphertext + TRINITY_MLKEM512_B_BYTES);
    mlk_poly_sub(&workspace->scratch, &workspace->accumulator);
    mlk_poly_reduce(&workspace->scratch);
    mlk_poly_tomsg(message, &workspace->scratch);

    trinity_secure_zero(&workspace->accumulator,
                        sizeof(workspace->accumulator));
    trinity_secure_zero(&workspace->scratch, sizeof(workspace->scratch));
}

static uint8_t trinity_lowram_difference(const uint8_t *left,
                                         const uint8_t *right,
                                         size_t length) {
    uint8_t difference = 0u;
    size_t index;
    for (index = 0u; index < length; ++index) {
        difference |= (uint8_t)(left[index] ^ right[index]);
    }
    return difference;
}

static trinity_error_code_t trinity_mlkem512_encaps_deterministic_lowram(
    uint8_t ciphertext[TRINITY_MLKEM512_CIPHERTEXT_BYTES],
    uint8_t shared_secret[TRINITY_MLKEM_SHARED_SECRET_BYTES],
    const uint8_t public_key[TRINITY_MLKEM512_PUBLIC_KEY_BYTES],
    const uint8_t coins[TRINITY_MLKEM_ENCAPS_COINS_BYTES]) {
    uint8_t coins_copy[TRINITY_MLKEM_ENCAPS_COINS_BYTES];
    uint8_t message_and_hash[2u * MLKEM_SYMBYTES];
    uint8_t key_and_coins[2u * MLKEM_SYMBYTES];

    if (g_lowram_keygen == NULL ||
        !trinity_lowram_encoded_polyvec_is_canonical(public_key)) {
        trinity_mlkem_backend_latch_error(TRINITY_INTERNAL_FAULT,
                                           UINT32_C(0x4C524550));
        trinity_secure_zero(ciphertext, TRINITY_MLKEM512_CIPHERTEXT_BYTES);
        trinity_secure_zero(shared_secret, TRINITY_MLKEM_SHARED_SECRET_BYTES);
        return TRINITY_INTERNAL_FAULT;
    }

    /* coins may live inside the phase-shared union that becomes polynomial
     * scratch as soon as IND-CPA encryption starts. */
    memcpy(coins_copy, coins, sizeof(coins_copy));
    memcpy(message_and_hash, coins_copy, MLKEM_SYMBYTES);
    trinity_mlkem512_sha3_256(message_and_hash + MLKEM_SYMBYTES,
                              public_key,
                              TRINITY_MLKEM512_PUBLIC_KEY_BYTES);
    trinity_mlkem512_sha3_512(key_and_coins,
                              message_and_hash,
                              sizeof(message_and_hash));

    (void)trinity_lowram_indcpa_encrypt(ciphertext, NULL,
                                        message_and_hash,
                                        public_key,
                                        key_and_coins + MLKEM_SYMBYTES);
    memcpy(shared_secret, key_and_coins, TRINITY_MLKEM_SHARED_SECRET_BYTES);

    trinity_secure_zero(coins_copy, sizeof(coins_copy));
    trinity_secure_zero(message_and_hash, sizeof(message_and_hash));
    trinity_secure_zero(key_and_coins, sizeof(key_and_coins));
    return TRINITY_OK;
}

static trinity_error_code_t trinity_mlkem512_decaps_lowram(
    uint8_t shared_secret[TRINITY_MLKEM_SHARED_SECRET_BYTES],
    const uint8_t ciphertext[TRINITY_MLKEM512_CIPHERTEXT_BYTES],
    const uint8_t secret_key[TRINITY_MLKEM512_SECRET_KEY_BYTES]) {
    trinity_mlkem512_lowram_a2_workspace_t *workspace =
        trinity_lowram_a2_workspace();
    const uint8_t *public_key =
        secret_key + TRINITY_MLKEM512_PUBLIC_KEY_IN_SECRET_KEY_OFFSET;
    const uint8_t *stored_public_key_hash =
        secret_key + TRINITY_MLKEM512_SK_HASH_OFFSET;
    const uint8_t *rejection_key =
        secret_key + TRINITY_MLKEM512_REJECTION_KEY_OFFSET;
    uint8_t message_and_hash[2u * MLKEM_SYMBYTES];
    uint8_t key_and_coins[2u * MLKEM_SYMBYTES];
    uint8_t calculated_public_key_hash[MLKEM_SYMBYTES];
    uint8_t rejection_secret[MLKEM_SYMBYTES];
    uint8_t *rejection_input;
    uint8_t ciphertext_difference;
    uint8_t secret_key_difference;
    uint8_t valid_mask;
    size_t index;

    if (workspace == NULL ||
        !trinity_lowram_encoded_polyvec_is_canonical(
            secret_key) ||
        !trinity_lowram_encoded_polyvec_is_canonical(public_key)) {
        trinity_mlkem_backend_latch_error(TRINITY_INTERNAL_FAULT,
                                           UINT32_C(0x4C524453));
        trinity_secure_zero(shared_secret, TRINITY_MLKEM_SHARED_SECRET_BYTES);
        return TRINITY_INTERNAL_FAULT;
    }

    trinity_mlkem512_sha3_256(calculated_public_key_hash,
                              public_key,
                              TRINITY_MLKEM512_PUBLIC_KEY_BYTES);
    secret_key_difference = trinity_lowram_difference(
        calculated_public_key_hash, stored_public_key_hash,
        MLKEM_SYMBYTES);
    if (secret_key_difference != 0u) {
        trinity_mlkem_backend_latch_error(TRINITY_INTERNAL_FAULT,
                                           UINT32_C(0x4C524448));
        trinity_secure_zero(shared_secret, TRINITY_MLKEM_SHARED_SECRET_BYTES);
        trinity_secure_zero(calculated_public_key_hash,
                            sizeof(calculated_public_key_hash));
        return TRINITY_INTERNAL_FAULT;
    }

    trinity_lowram_indcpa_decrypt(message_and_hash,
                                  ciphertext,
                                  secret_key);
    memcpy(message_and_hash + MLKEM_SYMBYTES,
           stored_public_key_hash, MLKEM_SYMBYTES);
    trinity_mlkem512_sha3_512(key_and_coins,
                              message_and_hash,
                              sizeof(message_and_hash));

    ciphertext_difference = trinity_lowram_indcpa_encrypt(
        NULL, ciphertext, message_and_hash, public_key,
        key_and_coins + MLKEM_SYMBYTES);

    /* The two polynomial areas are no longer live. Reuse their contiguous
     * 1024 bytes for J(z || c), avoiding the upstream 800-byte stack object. */
    rejection_input = (uint8_t *)(void *)&workspace->accumulator;
    memcpy(rejection_input, rejection_key, MLKEM_SYMBYTES);
    memcpy(rejection_input + MLKEM_SYMBYTES,
           ciphertext, TRINITY_MLKEM512_CIPHERTEXT_BYTES);
    trinity_mlkem512_shake256(rejection_secret,
                              sizeof(rejection_secret),
                              rejection_input,
                              MLKEM_SYMBYTES +
                                  TRINITY_MLKEM512_CIPHERTEXT_BYTES);
    trinity_secure_zero(rejection_input,
                        MLKEM_SYMBYTES +
                            TRINITY_MLKEM512_CIPHERTEXT_BYTES);

    /* 0xFF iff the byte-exact re-encryption comparison succeeded. */
    valid_mask = (uint8_t)(((uint16_t)ciphertext_difference - 1u) >> 8);
    for (index = 0u; index < TRINITY_MLKEM_SHARED_SECRET_BYTES; ++index) {
        shared_secret[index] =
            (uint8_t)((rejection_secret[index] & (uint8_t)~valid_mask) |
                      (key_and_coins[index] & valid_mask));
    }

    trinity_secure_zero(message_and_hash, sizeof(message_and_hash));
    trinity_secure_zero(key_and_coins, sizeof(key_and_coins));
    trinity_secure_zero(calculated_public_key_hash,
                        sizeof(calculated_public_key_hash));
    trinity_secure_zero(rejection_secret, sizeof(rejection_secret));
    trinity_secure_zero(&workspace->accumulator,
                        sizeof(workspace->accumulator));
    trinity_secure_zero(&workspace->scratch, sizeof(workspace->scratch));
    return TRINITY_OK;
}
