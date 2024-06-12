cmake_minimum_required(VERSION 3.12)

# Pull in SDK (must be before project)
include(pico_sdk_import.cmake)
#include(pico_extras_import_optional.cmake)

include($ENV{PICO_SDK_PATH}/pico_sdk_init.cmake)

project(serial_passthrough LANGUAGES C CXX ASM)

#set(CMAKE_C_STANDARD 8)
#set(CMAKE_CXX_STANDARD 12)

if (PICO_SDK_VERSION_STRING VERSION_LESS "1.3.0")
    message(FATAL_ERROR "Raspberry Pi Pico SDK version 1.3.0 (or later) required. Your version is ${PICO_SDK_VERSION_STRING}")
endif()

pico_sdk_init()

add_compile_options(-Wall
        -Wno-format          # int != int32_t as far as the compiler is concerned because gcc has int32_t as long int
        -Wno-unused-function # we have some for the docs that aren't called
        )
if (CMAKE_C_COMPILER_ID STREQUAL "GNU")
    add_compile_options(-Wno-maybe-uninitialized)
endif()

add_executable(serial_passthrough
  serial_passthrough.c
        )

# Pull in our pico_stdlib which pulls in commonly used features
target_link_libraries(serial_passthrough pico_stdlib)

# create map/bin/hex file etc.
pico_add_extra_outputs(serial_passthrough)

# add url via pico_set_program_url
#example_auto_set_url(serial_passthrough)

# enable usb output, disable uart output
pico_enable_stdio_usb(serial_passthrough 1)
pico_enable_stdio_uart(serial_passthrough 0)
