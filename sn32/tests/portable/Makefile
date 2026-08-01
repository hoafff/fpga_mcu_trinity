CC ?= gcc
CFLAGS ?= -std=c11 -Wall -Wextra -Werror -pedantic -O2
ROOT := ../..

SOURCES := \
	$(ROOT)/src/trinity_protocol_common.c \
	$(ROOT)/src/trinity_pc_protocol.c \
	$(ROOT)/src/trinity_spi_protocol.c \
	test_protocol.c

test_protocol: $(SOURCES)
	$(CC) $(CFLAGS) -I$(ROOT)/include $(SOURCES) -o $@

test: test_protocol
	./test_protocol

clean:
	rm -f test_protocol
