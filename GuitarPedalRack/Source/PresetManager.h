/*
    ============================================================================
    PresetManager.h

    Serializa la pedalera completa a un juce::ValueTree y de ahi a XML.

    Un ValueTree es basicamente un dict anidado con tipos ("un XML en memoria"),
    con la ventaja de que JUCE sabe convertirlo a/desde XML y a/desde binario.

    Estructura generada:

        <RACK version="1">
          <PLUGIN bypassed="0" state="BASE64...">
            <!-- hijo con la PluginDescription serializada por JUCE -->
            <PLUGIN name="TSE808" format="VST3" fileOrIdentifier="C:\..." .../>
          </PLUGIN>
          ...
        </RACK>

    Guardamos la PluginDescription porque al abrir el preset hay que volver a
    localizar e instanciar exactamente ese .dll/.vst3.
    ============================================================================
*/

#pragma once

#include <JuceHeader.h>

class AudioGraphManager;

class PresetManager
{
public:
    /*  Por defecto los presets van junto al .exe, en .\Presets\, para que la
        aplicacion sea realmente portatil (llevas la carpeta en un pendrive y
        los presets viajan con ella).  */
    PresetManager();

    void setPresetsFolder (const juce::File& folder);
    juce::File getPresetsFolder() const { return presetsFolder; }

    // ------------------------------------------------------------------
    // Serializacion
    // ------------------------------------------------------------------

    /*  Recorre la cadena y devuelve un ValueTree con todo el estado.  */
    juce::ValueTree captureState (const AudioGraphManager& graphManager) const;

    /*  Escribe el ValueTree como XML en <presetsFolder>/<name>.xml  */
    bool saveToFile (const juce::ValueTree& state, const juce::String& presetName) const;

    /*  Lee un XML y lo devuelve como ValueTree. Devuelve un arbol invalido
        (isValid() == false) si el archivo no existe o esta corrupto.  */
    juce::ValueTree loadFromFile (const juce::String& presetName) const;

    bool deletePreset (const juce::String& presetName) const;
    juce::StringArray getAllPresetNames() const;

    // ------------------------------------------------------------------
    // Identificadores del ValueTree (evita errores de tipeo por el codigo)
    // ------------------------------------------------------------------
    struct IDs
    {
        static const juce::Identifier rack;        // nodo raiz
        static const juce::Identifier plugin;      // un pedal
        static const juce::Identifier state;       // estado interno en base64
        static const juce::Identifier bypassed;
        static const juce::Identifier version;
    };

private:
    juce::File presetsFolder;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (PresetManager)
};
