CC ?= cc
CFLAGS ?= -std=c11 -Wall -Wextra -Werror
INCLUDES = -I../../include
SOURCES = ../../src/trinity_protocol_common.c ../../src/app/trinity_full_controller.c test_full_controller.c

.PHONY: test clean

test: test_full_controller
	./test_full_controller

test_full_controller: $(SOURCES)
	$(CC) $(CFLAGS) $(INCLUDES) $(SOURCES) -o $@

clean:
	rm -f test_full_controller
