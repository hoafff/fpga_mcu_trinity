CC ?= gcc
CFLAGS ?= -std=c99 -O2 -Wall -Wextra -Werror -Wshadow -Wpointer-arith -pedantic
ROOT := ../..
VENDOR := $(ROOT)/third_party/mlkem-native/upstream
MLKEM_ROOT := $(VENDOR)/mlkem

MLKEM_SOURCES := $(MLKEM_ROOT)/mlkem_native.c
TRINITY_SOURCES := $(ROOT)/src/trinity_mlkem_backend.c \
                   $(ROOT)/src/trinity_mlkem.c
TEST_SOURCES := test_mlkem_gate3.c

CPPFLAGS += -I$(ROOT)/include -I$(MLKEM_ROOT) \
            -DMLK_CONFIG_PARAMETER_SET=512 \
            -DMLK_CONFIG_NAMESPACE_PREFIX=trinity_mlkem512

SOURCES := $(MLKEM_SOURCES) $(TRINITY_SOURCES) $(TEST_SOURCES)

.PHONY: test clean no-dynamic-allocation

test_mlkem_gate3: $(SOURCES)
	@test -f "$(MLKEM_ROOT)/mlkem_native.c" || \
		(echo "ERROR: initialize the pinned mlkem-native submodule"; exit 1)
	$(CC) $(CPPFLAGS) $(CFLAGS) $(SOURCES) -o $@

no-dynamic-allocation:
	@! grep -R -n -E '\b(malloc|calloc|realloc|free)[[:space:]]*\(' \
		$(ROOT)/src/trinity_mlkem.c $(ROOT)/src/trinity_mlkem_backend.c \
		$(ROOT)/include/trinity_mlkem.h $(ROOT)/include/trinity_mlkem_backend.h

test: no-dynamic-allocation test_mlkem_gate3
	./test_mlkem_gate3

clean:
	rm -f test_mlkem_gate3
