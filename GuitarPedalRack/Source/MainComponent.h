/*
    ============================================================================
    MainComponent.h

    Componente principal: GUI + callbacks de audio.

    Hereda de:
      - juce::AudioAppComponent : le da un juce::AudioDeviceManager llamado
        'deviceManager' y los tres callbacks de audio (prepareToPlay,
        getNextAudioBlock, releaseResources).
      - juce::ListBoxModel : para pintar la lista de pedales de la cadena.
        En Python sería el equivalente a implementar el "model" de una tabla.
      - juce::ChangeListener : para enterarnos de cuándo cambia la lista de
        plugins conocidos y guardarla en disco.
    ============================================================================
*/

#pragma once

#include <JuceHeader.h>
#include "AudioGraphManager.h"
#include "PresetManager.h"

class MainComponent  : public juce::AudioAppComponent,
                       public juce::ListBoxModel,
                       public juce::ChangeListener
{
public:
    MainComponent();
    ~MainComponent() override;

    //==========================================================================
    // Callbacks de audio
    //==========================================================================
    void prepareToPlay (int samplesPerBlockExpected, double sampleRate) override;
    void getNextAudioBlock (const juce::AudioSourceChannelInfo& bufferToFill) override;
    void releaseResources() override;

    //==========================================================================
    // GUI
    //==========================================================================
    void paint (juce::Graphics& g) override;
    void resized() override;

    //==========================================================================
    // ListBoxModel: la ListBox nos pregunta qué pintar en cada fila
    //==========================================================================
    int getNumRows() override;
    void paintListBoxItem (int rowNumber, juce::Graphics& g,
                           int width, int height, bool rowIsSelected) override;
    void listBoxItemDoubleClicked (int row, const juce::MouseEvent&) override;
    void selectedRowsChanged (int lastRowSelected) override;

    //==========================================================================
    // ChangeListener: se dispara cuando cambia 'knownPlugins'
    //==========================================================================
    void changeListenerCallback (juce::ChangeBroadcaster* source) override;

private:
    //==========================================================================
    // Inicialización
    //==========================================================================
    void initialisePluginFormats();
    void initialiseAudioDevice();
    void buildUI();

    /*  Rutas donde viven los plugins en este PC. Se guardan/leen del archivo
        de ajustes para que el usuario no tenga que reconfigurarlas.  */
    juce::File getSettingsFile() const;
    juce::File getPluginCacheFile() const;
    juce::File getDeadMansPedalFile() const;

    //==========================================================================
    // Plugins
    //==========================================================================

    /*  Abre la ventana de gestión de plugins de JUCE (PluginListComponent).
        Se encarga sola del escaneo, la barra de progreso, y de meter en una
        lista negra los plugins que crashean al analizarlos.  */
    void showPluginManager();

    void showAddPluginMenu();
    int  addPluginFromDescription (const juce::PluginDescription& description);
    void openEditorForRow (int row);
    void updateUI();

    //==========================================================================
    // Presets
    //==========================================================================
    void savePresetPressed();
    void loadPresetPressed();
    void applyState (const juce::ValueTree& state);

    //==========================================================================
    // Miembros
    //==========================================================================

    juce::AudioPluginFormatManager formatManager;
    juce::KnownPluginList          knownPlugins;

    AudioGraphManager graphManager;
    PresetManager     presetManager;

    // --- Widgets ---
    juce::ListBox    chainList  { "Cadena", this };
    juce::TextButton scanButton     { "Buscar plugins..." };
    juce::TextButton addButton      { "+ Anadir pedal" };   // se re-etiqueta en buildUI()
    juce::TextButton removeButton   { "- Quitar" };
    juce::TextButton upButton       { "Subir" };
    juce::TextButton downButton     { "Bajar" };
    juce::TextButton bypassButton   { "Bypass" };
    juce::TextButton saveButton     { "Guardar preset" };
    juce::TextButton loadButton     { "Cargar preset" };
    juce::TextButton settingsButton { "Audio..." };
    juce::Label      statusLabel;
    juce::Label      hintLabel;

    /*  Ventanas flotantes con la GUI de cada plugin.  */
    juce::OwnedArray<juce::DocumentWindow> pluginWindows;

    double currentSampleRate = 44100.0;
    int    currentBlockSize  = 512;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (MainComponent)
};
