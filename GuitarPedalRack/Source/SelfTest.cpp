/*
    ============================================================================
    SelfTest.cpp

    Programa de consola aparte (RackSelfTest.exe) que usa EXACTAMENTE las mismas
    clases que la app y comprueba que el audio realmente atraviesa los plugins.

    No forma parte de la aplicación: existe para poder verificar el motor sin
    tener que enchufar una guitarra y escuchar.

    Se compila solo, con:   cmake --build build --target RackSelfTest
    ============================================================================
*/

#include <JuceHeader.h>
#include "AudioGraphManager.h"
#include "PresetManager.h"

namespace
{
    constexpr double kSampleRate = 48000.0;
    constexpr int    kBlockSize  = 512;

    int failures = 0;

    void check (bool condition, const juce::String& what)
    {
        std::cout << (condition ? "  [OK]   " : "  [FALLA] ") << what << std::endl;

        if (! condition)
            ++failures;
    }

    /*  Llena el buffer con una senoide de 440 Hz, como una cuerda al aire.  */
    void fillWithSine (juce::AudioBuffer<float>& buffer, double& phase)
    {
        const double increment = 2.0 * juce::MathConstants<double>::pi * 440.0 / kSampleRate;

        for (int i = 0; i < buffer.getNumSamples(); ++i)
        {
            auto value = (float) std::sin (phase) * 0.25f;
            phase += increment;

            for (int ch = 0; ch < buffer.getNumChannels(); ++ch)
                buffer.setSample (ch, i, value);
        }
    }

    float rms (const juce::AudioBuffer<float>& buffer)
    {
        return buffer.getRMSLevel (0, 0, buffer.getNumSamples());
    }
}

/*  Escanea la carpeta VST3 de 64 bits y deja el resultado en PluginCache.xml,
    junto al ejecutable indicado. Sirve para que la app arranque ya con la
    lista de plugins hecha, sin que el usuario tenga que escanear a mano.  */
static int writePluginCache (const juce::File& targetFolder)
{
    juce::ScopedJuceInitialiser_GUI juceInit;

    juce::AudioPluginFormatManager formatManager;
    formatManager.addDefaultFormats();

    juce::KnownPluginList knownPlugins;
    juce::FileSearchPath searchPath ("C:\\Program Files\\Common Files\\VST3");
    auto deadMansPedal = targetFolder.getChildFile ("PluginScanCrashLog.txt");
    deadMansPedal.deleteFile();

    for (auto* format : formatManager.getFormats())
    {
        if (format->getName() != "VST3")
            continue;

        juce::PluginDirectoryScanner scanner (knownPlugins, *format, searchPath,
                                              true, deadMansPedal);
        juce::String nameBeingScanned;

        while (scanner.scanNextFile (true, nameBeingScanned))
            std::cout << "  " << nameBeingScanned << std::endl;
    }

    auto cacheFile = targetFolder.getChildFile ("PluginCache.xml");

    if (auto xml = knownPlugins.createXml())
        xml->writeTo (cacheFile);

    std::cout << "\n" << knownPlugins.getNumTypes() << " plugins escritos en "
              << cacheFile.getFullPathName() << std::endl;

    return knownPlugins.getNumTypes() > 0 ? 0 : 1;
}

int main (int argc, char* argv[])
{
    /*  Modo alternativo: en vez de testear, solo generar la cache de plugins.
            RackSelfTest.exe --scan-cache "C:\ruta\donde\esta\el\exe"          */
    if (argc >= 3 && juce::String (argv[1]) == "--scan-cache")
        return writePluginCache (juce::File (juce::String::fromUTF8 (argv[2])));

    /*  Necesario para hostear plugins: crea el message thread que muchos VST
        dan por hecho que existe.  */
    juce::ScopedJuceInitialiser_GUI juceInit;

    std::cout << "\n=== Self-test del motor de audio ===\n" << std::endl;

    juce::AudioPluginFormatManager formatManager;
    formatManager.addDefaultFormats();

    std::cout << "Formatos registrados:" << std::endl;
    for (auto* f : formatManager.getFormats())
        std::cout << "  - " << f->getName() << std::endl;

    //--------------------------------------------------------------------------
    std::cout << "\n[1] Grafo vacio deja pasar el audio (passthrough)" << std::endl;
    //--------------------------------------------------------------------------
    {
        AudioGraphManager graph;
        graph.prepareToPlay (kSampleRate, kBlockSize);

        juce::AudioBuffer<float> buffer (2, kBlockSize);
        juce::MidiBuffer midi;
        double phase = 0.0;

        fillWithSine (buffer, phase);
        auto before = rms (buffer);

        graph.processBlock (buffer, midi);
        auto after = rms (buffer);

        check (before > 0.01f, "la senal de entrada no es silencio");
        check (std::abs (after - before) < 0.001f,
               "la salida es igual a la entrada (RMS " + juce::String (before, 4)
                 + " -> " + juce::String (after, 4) + ")");

        graph.releaseResources();
    }

    //--------------------------------------------------------------------------
    std::cout << "\n[2] Escaneo de la carpeta VST3 de 64 bits" << std::endl;
    //--------------------------------------------------------------------------
    juce::KnownPluginList knownPlugins;
    {
        juce::File vst3Folder ("C:\\Program Files\\Common Files\\VST3");
        check (vst3Folder.isDirectory(), "existe " + vst3Folder.getFullPathName());

        juce::FileSearchPath searchPath (vst3Folder.getFullPathName());
        auto deadMansPedal = juce::File::getSpecialLocation (juce::File::tempDirectory)
                                .getChildFile ("rack_selftest_scan.tmp");
        deadMansPedal.deleteFile();

        for (auto* format : formatManager.getFormats())
        {
            if (format->getName() != "VST3")
                continue;

            juce::PluginDirectoryScanner scanner (knownPlugins, *format, searchPath,
                                                  false, deadMansPedal);
            juce::String nameBeingScanned;

            while (scanner.scanNextFile (true, nameBeingScanned))
            {
                // Nada que hacer: el escaner rellena knownPlugins.
            }
        }

        std::cout << "  Encontrados " << knownPlugins.getNumTypes() << " plugins:" << std::endl;

        for (auto& type : knownPlugins.getTypes())
            std::cout << "    - " << type.name << "  (" << type.pluginFormatName
                      << (type.isInstrument ? ", instrumento" : ", efecto") << ")" << std::endl;

        check (knownPlugins.getNumTypes() > 0, "se encontro al menos un plugin");
    }

    //--------------------------------------------------------------------------
    std::cout << "\n[3] Cargar un efecto y pasar audio por el" << std::endl;
    //--------------------------------------------------------------------------
    juce::PluginDescription chosen;
    bool foundEffect = false;

    for (auto& type : knownPlugins.getTypes())
    {
        // Queremos un efecto estereo, no un instrumento.
        if (! type.isInstrument && type.numInputChannels >= 2)
        {
            chosen = type;
            foundEffect = true;
            break;
        }
    }

    check (foundEffect, "hay un efecto disponible para probar");

    if (foundEffect)
    {
        std::cout << "  Usando: " << chosen.name << std::endl;

        AudioGraphManager graph;
        graph.prepareToPlay (kSampleRate, kBlockSize);

        juce::String error;
        auto instance = formatManager.createPluginInstance (chosen, kSampleRate,
                                                            kBlockSize, error);

        check (instance != nullptr, "se instancio el plugin" +
               (instance == nullptr ? juce::String (" -> ") + error : juce::String()));

        if (instance != nullptr)
        {
            auto index = graph.addPlugin (std::move (instance), chosen);
            check (index == 0, "el plugin ocupa la posicion 0 de la cadena");
            check (graph.getNumPlugins() == 1, "la cadena tiene 1 pedal");

            // Re-preparamos: el nodo nuevo tiene que recibir prepareToPlay.
            graph.prepareToPlay (kSampleRate, kBlockSize);

            juce::AudioBuffer<float> buffer (2, kBlockSize);
            juce::MidiBuffer midi;
            double phase = 0.0;

            /*  Procesamos varios bloques: muchos efectos (reverbs, delays)
                necesitan unos cuantos antes de dar salida audible.  */
            float lastOut = 0.0f;

            for (int block = 0; block < 20; ++block)
            {
                fillWithSine (buffer, phase);
                graph.processBlock (buffer, midi);
                lastOut = rms (buffer);
            }

            std::cout << "  RMS de salida tras 20 bloques: "
                      << juce::String (lastOut, 4) << std::endl;

            check (lastOut > 0.0001f, "sale senal por el otro lado (no es silencio)");
            check (std::isfinite (lastOut), "la salida no tiene NaN ni infinitos");

            //------------------------------------------------------------------
            std::cout << "\n[4] Guardar y recargar un preset" << std::endl;
            //------------------------------------------------------------------
            PresetManager presets;
            auto state = presets.captureState (graph);

            check (state.isValid(), "se capturo el estado");
            check (state.getNumChildren() == 1, "el preset contiene 1 pedal");

            check (presets.saveToFile (state, "selftest"), "se escribio el XML");

            auto reloaded = presets.loadFromFile ("selftest");
            check (reloaded.isValid(), "se releyo el XML");
            check (reloaded.getNumChildren() == 1, "el XML releido contiene 1 pedal");

            // Comprobamos que la PluginDescription sobrevivio al viaje.
            auto descTree = reloaded.getChild (0).getChild (0);
            juce::PluginDescription roundTripped;

            if (auto xml = descTree.createXml())
                roundTripped.loadFromXml (*xml);

            check (roundTripped.name == chosen.name,
                   "el nombre del plugin sobrevive: '" + roundTripped.name + "'");
            check (roundTripped.fileOrIdentifier == chosen.fileOrIdentifier,
                   "la ruta al plugin sobrevive");

            presets.deletePreset ("selftest");

            //------------------------------------------------------------------
            std::cout << "\n[5] Bypass y borrado" << std::endl;
            //------------------------------------------------------------------
            graph.setBypassed (0, true);
            check (graph.isBypassed (0), "el pedal queda en bypass");

            fillWithSine (buffer, phase);
            auto inRms = rms (buffer);
            graph.processBlock (buffer, midi);
            auto outRms = rms (buffer);

            check (std::abs (outRms - inRms) < 0.001f,
                   "en bypass la senal pasa intacta (" + juce::String (inRms, 4)
                     + " -> " + juce::String (outRms, 4) + ")");

            graph.removePlugin (0);
            check (graph.getNumPlugins() == 0, "la cadena queda vacia tras borrar");

            graph.releaseResources();
        }
    }

    //--------------------------------------------------------------------------
    std::cout << "\n[6] El menu de plugins mapea al plugin correcto" << std::endl;
    //--------------------------------------------------------------------------
    /*  Esta es la parte fragil de showAddPluginMenu(): addToMenu genera ids
        OPACOS (no son 0,1,2...), y hay que traducirlos con getIndexChosenByMenu.
        Si ese mapeo se rompe, el usuario pulsa un pedal y le aparece otro.
        Se puede comprobar sin abrir ninguna ventana.  */
    {
        auto types = knownPlugins.getTypes();

        juce::PopupMenu menu;
        juce::KnownPluginList::addToMenu (menu, types,
                                          juce::KnownPluginList::sortByManufacturer);

        // Recorremos el menu entero, submenus incluidos.
        int itemsFound = 0;
        int mismatches = 0;
        int checkedIds = 0;

        juce::PopupMenu::MenuItemIterator iterator (menu, true);

        while (iterator.next())
        {
            const auto& item = iterator.getItem();

            if (item.itemID == 0)     // separadores y cabeceras de submenu
                continue;

            ++itemsFound;

            auto index = juce::KnownPluginList::getIndexChosenByMenu (types, item.itemID);

            if (! juce::isPositiveAndBelow (index, types.size()))
            {
                ++mismatches;
                continue;
            }

            /*  El texto del item tiene que corresponder al plugin al que
                apunta el indice. Comprobamos todos.  */
            if (! item.text.contains (types[index].name))
                ++mismatches;

            ++checkedIds;
        }

        std::cout << "  Items en el menu: " << itemsFound
                  << "  |  ids traducidos: " << checkedIds
                  << "  |  discrepancias: " << mismatches << std::endl;

        check (itemsFound == types.size(),
               "el menu contiene los " + juce::String (types.size()) + " plugins");
        check (mismatches == 0, "cada id del menu apunta al plugin correcto");
    }

    //--------------------------------------------------------------------------
    std::cout << "\n=== " << (failures == 0 ? "TODO OK" : juce::String (failures) + " FALLOS")
              << " ===\n" << std::endl;

    return failures == 0 ? 0 : 1;
}
