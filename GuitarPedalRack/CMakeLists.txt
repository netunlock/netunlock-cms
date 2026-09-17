cmake_minimum_required(VERSION 3.22)

# CMP0091 = poder elegir el runtime de MSVC (lo usamos para el .exe portatil)
cmake_policy(SET CMP0091 NEW)

# JUCE compila algunos .c internos (flac, ogg, VST3 SDK), asi que hacen falta
# los dos lenguajes, no solo CXX.
project(GuitarPedalRack VERSION 1.0.0 LANGUAGES C CXX)

# ---------------------------------------------------------------------------
# Runtime estatico de MSVC (/MT).
# Esto mete las librerias de C++ DENTRO del .exe, para que funcione en un PC
# que no tenga instalado el "Visual C++ Redistributable". Es lo que hace que
# la aplicacion sea de verdad portatil (llevarla en un pendrive y ya).
# ---------------------------------------------------------------------------
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")

# ---------------------------------------------------------------------------
# JUCE. Vive en ../_toolchain/JUCE (clonado desde GitHub).
# ---------------------------------------------------------------------------
add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/../_toolchain/JUCE" JUCE)

# ---------------------------------------------------------------------------
# ASIO (opcional).
# El SDK de ASIO es de Steinberg y no se puede redistribuir, hay que bajarlo
# a mano aceptando su licencia. Si algun dia lo haces:
#
#   1. Baja el ASIO SDK de https://www.steinberg.net/developers/
#   2. Descomprimelo, por ejemplo en C:\SDKs\asiosdk
#   3. Reconfigura con:
#        cmake -B build -DASIO_SDK_PATH="C:/SDKs/asiosdk"
#
# Mientras tanto la app usa WASAPI en modo exclusivo, que en Windows 10 da
# una latencia razonable (del orden de 5-10 ms) sin necesidad de ningun SDK.
# ---------------------------------------------------------------------------
set(ASIO_SDK_PATH "" CACHE PATH "Ruta al ASIO SDK de Steinberg (opcional)")

if(ASIO_SDK_PATH AND EXISTS "${ASIO_SDK_PATH}/common/iasiodrv.h")
    set(USE_ASIO 1)
    message(STATUS "ASIO ACTIVADO: ${ASIO_SDK_PATH}")
else()
    set(USE_ASIO 0)
    message(STATUS "ASIO desactivado (se usara WASAPI exclusivo)")
endif()

# ---------------------------------------------------------------------------
# El ejecutable
# ---------------------------------------------------------------------------
juce_add_gui_app(GuitarPedalRack
    PRODUCT_NAME  "Guitar Pedal Rack"
    COMPANY_NAME  "Fede"
    VERSION       "1.0.0")

# Genera el JuceHeader.h que incluyen nuestros .cpp
juce_generate_juce_header(GuitarPedalRack)

target_sources(GuitarPedalRack PRIVATE
    Source/Main.cpp
    Source/MainComponent.cpp
    Source/AudioGraphManager.cpp
    Source/PresetManager.cpp)

# Los fuentes están en UTF-8 (llevan acentos y eñes en los comentarios).
# Sin /utf-8 MSVC los interpretaría con la codificación local y saldrían mal.
if(MSVC)
    target_compile_options(GuitarPedalRack PRIVATE /utf-8)
endif()

target_compile_definitions(GuitarPedalRack PUBLIC
    # --- Hosting de plugins ---
    JUCE_PLUGINHOST_VST3=1      # VST3: siempre disponible
    JUCE_PLUGINHOST_VST=0       # VST2: necesita el SDK legacy de Steinberg
    JUCE_PLUGINHOST_AU=0        # solo macOS

    # --- Drivers de audio en Windows ---
    JUCE_ASIO=${USE_ASIO}
    JUCE_WASAPI=1
    JUCE_WASAPI_EXCLUSIVE=1     # modo exclusivo = baja latencia sin ASIO
    JUCE_DIRECTSOUND=1          # ultimo recurso

    # --- Cosas que no necesitamos (reducen tamano y dependencias) ---
    JUCE_WEB_BROWSER=0
    JUCE_USE_CURL=0

    JUCE_APPLICATION_NAME_STRING="$<TARGET_PROPERTY:GuitarPedalRack,JUCE_PRODUCT_NAME>"
    JUCE_APPLICATION_VERSION_STRING="$<TARGET_PROPERTY:GuitarPedalRack,JUCE_VERSION>")

if(USE_ASIO)
    target_include_directories(GuitarPedalRack PRIVATE "${ASIO_SDK_PATH}/common")
endif()

target_link_libraries(GuitarPedalRack
    PRIVATE
        juce::juce_audio_utils
        juce::juce_audio_processors
        juce::juce_gui_extra
    PUBLIC
        juce::juce_recommended_config_flags
        juce::juce_recommended_lto_flags)

# ---------------------------------------------------------------------------
# RackSelfTest: programa de consola que comprueba el motor de audio sin GUI.
# No es parte de la app. Se compila y ejecuta con:
#     cmake --build build --target RackSelfTest
#     build\RackSelfTest_artefacts\RackSelfTest.exe
# ---------------------------------------------------------------------------
juce_add_console_app(RackSelfTest PRODUCT_NAME "RackSelfTest")

juce_generate_juce_header(RackSelfTest)

target_sources(RackSelfTest PRIVATE
    Source/SelfTest.cpp
    Source/AudioGraphManager.cpp
    Source/PresetManager.cpp)

target_include_directories(RackSelfTest PRIVATE Source)

if(MSVC)
    target_compile_options(RackSelfTest PRIVATE /utf-8)
endif()

target_compile_definitions(RackSelfTest PUBLIC
    JUCE_PLUGINHOST_VST3=1
    JUCE_PLUGINHOST_VST=0
    JUCE_PLUGINHOST_AU=0
    JUCE_WEB_BROWSER=0
    JUCE_USE_CURL=0)

target_link_libraries(RackSelfTest
    PRIVATE
        juce::juce_audio_utils
        juce::juce_audio_processors
        juce::juce_gui_extra
    PUBLIC
        juce::juce_recommended_config_flags)
