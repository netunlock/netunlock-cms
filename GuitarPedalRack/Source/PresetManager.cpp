/*
    ============================================================================
    PresetManager.cpp
    ============================================================================
*/

#include "PresetManager.h"
#include "AudioGraphManager.h"

const juce::Identifier PresetManager::IDs::rack     { "RACK" };
const juce::Identifier PresetManager::IDs::plugin   { "PLUGIN_SLOT" };
const juce::Identifier PresetManager::IDs::state    { "state" };
const juce::Identifier PresetManager::IDs::bypassed { "bypassed" };
const juce::Identifier PresetManager::IDs::version  { "version" };

//==============================================================================
PresetManager::PresetManager()
{
    /*  getSpecialLocation(currentExecutableFile) apunta al .exe. Ponemos los
        presets a su lado para que la app sea portatil.  */
    presetsFolder = juce::File::getSpecialLocation (juce::File::currentExecutableFile)
                        .getParentDirectory()
                        .getChildFile ("Presets");

    presetsFolder.createDirectory();   // no hace nada si ya existe
}

void PresetManager::setPresetsFolder (const juce::File& folder)
{
    presetsFolder = folder;
    presetsFolder.createDirectory();
}

//==============================================================================
// Guardar
//==============================================================================

juce::ValueTree PresetManager::captureState (const AudioGraphManager& graphManager) const
{
    juce::ValueTree rack (IDs::rack);
    rack.setProperty (IDs::version, 1, nullptr);

    for (int i = 0; i < graphManager.getNumPlugins(); ++i)
    {
        auto* slot = graphManager.getSlot (i);
        auto* instance = graphManager.getPluginInstance (i);

        if (slot == nullptr || instance == nullptr)
            continue;

        juce::ValueTree slotTree (IDs::plugin);
        slotTree.setProperty (IDs::bypassed, slot->bypassed, nullptr);

        /*  getStateInformation devuelve un blob binario opaco con TODOS los
            parametros del plugin (knobs, presets internos...). Lo pasamos a
            base64 para poder meterlo en un XML.  */
        juce::MemoryBlock binaryState;
        instance->getStateInformation (binaryState);
        slotTree.setProperty (IDs::state, binaryState.toBase64Encoding(), nullptr);

        /*  JUCE ya sabe serializar una PluginDescription. La metemos como hijo. */
        if (auto descXml = slot->description.createXml())
            slotTree.appendChild (juce::ValueTree::fromXml (*descXml), nullptr);

        rack.appendChild (slotTree, nullptr);
    }

    return rack;
}

bool PresetManager::saveToFile (const juce::ValueTree& state,
                                const juce::String& presetName) const
{
    if (! state.isValid() || presetName.isEmpty())
        return false;

    // Limpia caracteres ilegales para nombres de archivo en Windows.
    auto file = presetsFolder.getChildFile (juce::File::createLegalFileName (presetName) + ".xml");

    if (auto xml = state.createXml())
        return xml->writeTo (file);

    return false;
}

//==============================================================================
// Cargar
//==============================================================================

juce::ValueTree PresetManager::loadFromFile (const juce::String& presetName) const
{
    auto file = presetsFolder.getChildFile (juce::File::createLegalFileName (presetName) + ".xml");

    if (! file.existsAsFile())
        return {};

    auto xml = juce::XmlDocument::parse (file);

    if (xml == nullptr)
        return {};

    return juce::ValueTree::fromXml (*xml);
}

bool PresetManager::deletePreset (const juce::String& presetName) const
{
    auto file = presetsFolder.getChildFile (juce::File::createLegalFileName (presetName) + ".xml");
    return file.existsAsFile() && file.deleteFile();
}

juce::StringArray PresetManager::getAllPresetNames() const
{
    juce::StringArray names;

    for (auto& file : presetsFolder.findChildFiles (juce::File::findFiles, false, "*.xml"))
        names.add (file.getFileNameWithoutExtension());

    names.sort (true);
    return names;
}
