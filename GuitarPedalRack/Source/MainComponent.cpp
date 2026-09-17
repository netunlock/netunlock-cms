/*
    ============================================================================
    MainComponent.cpp
    ============================================================================
*/

#include "MainComponent.h"

//==============================================================================
// Ventana flotante que contiene la GUI de un plugin.
// Se declara aquí porque solo se usa en este archivo.
//==============================================================================
class PluginWindow : public juce::DocumentWindow
{
public:
    PluginWindow (juce::AudioPluginInstance& instance,
                  juce::OwnedArray<juce::DocumentWindow>& ownerList)
        : DocumentWindow (instance.getName(),
                          juce::Colours::black,
                          DocumentWindow::closeButton),
          owner (ownerList)
    {
        setUsingNativeTitleBar (true);

        /*  createEditorIfNeeded() devuelve la GUI propia del VST. Si el plugin
            no trae GUI, JUCE fabrica una genérica con sliders automáticos.  */
        if (auto* editor = instance.createEditorIfNeeded())
            setContentOwned (editor, true);
        else
            setContentOwned (new juce::GenericAudioProcessorEditor (instance), true);

        setResizable (true, false);
        centreWithSize (getWidth(), getHeight());
        setVisible (true);
    }

    void closeButtonPressed() override
    {
        /*  Nos auto-eliminamos de la lista del propietario, pero de forma
            diferida: borrar 'this' dentro de un callback de la propia ventana
            es pedir problemas. callAsync lo hace en la siguiente vuelta del
            bucle de mensajes, cuando ya nadie está usando el objeto.  */
        juce::Component::SafePointer<PluginWindow> safeThis (this);

        juce::MessageManager::callAsync ([safeThis]
        {
            if (safeThis != nullptr)
                safeThis->owner.removeObject (safeThis.getComponent(), true);
        });
    }

private:
    juce::OwnedArray<juce::DocumentWindow>& owner;
};

//==============================================================================
MainComponent::MainComponent()
{
    initialisePluginFormats();
    buildUI();

    setSize (820, 560);

    /*  setAudioChannels abre el dispositivo de audio (2 in / 2 out) y arranca
        el hilo de audio. A partir de aquí prepareToPlay() puede dispararse.  */
    setAudioChannels (2, 2);

    initialiseAudioDevice();

    knownPlugins.addChangeListener (this);
    updateUI();
}

MainComponent::~MainComponent()
{
    /*  ORDEN IMPORTANTE:
        1) parar el audio  2) cerrar ventanas de plugin  3) vaciar el grafo.
        Si destruyes plugins mientras el hilo de audio corre -> crash.  */
    knownPlugins.removeChangeListener (this);
    shutdownAudio();
    pluginWindows.clear();
    graphManager.clear();
}

//==============================================================================
// Rutas de trabajo (todo junto al .exe, para que sea portátil)
//==============================================================================

juce::File MainComponent::getSettingsFile() const
{
    return juce::File::getSpecialLocation (juce::File::currentExecutableFile)
             .getParentDirectory();
}

juce::File MainComponent::getPluginCacheFile() const
{
    return getSettingsFile().getChildFile ("PluginCache.xml");
}

juce::File MainComponent::getDeadMansPedalFile() const
{
    /*  El "dead man's pedal": JUCE apunta aquí qué plugin está analizando.
        Si ese plugin cuelga el escáner, al reintentar se lo salta.  */
    return getSettingsFile().getChildFile ("PluginScanCrashLog.txt");
}

//==============================================================================
// Inicialización
//==============================================================================

void MainComponent::initialisePluginFormats()
{
    /*  addDefaultFormats() registra los formatos activados en el CMakeLists:
        VST3 siempre; VST2 solo si tuvieras el SDK legacy de Steinberg.  */
    formatManager.addDefaultFormats();

    /*  Recuperamos la lista de plugins escaneada en sesiones anteriores, para
        no tener que re-escanear cada vez que abres la app.  */
    if (auto xml = juce::XmlDocument::parse (getPluginCacheFile()))
        knownPlugins.recreateFromXml (*xml);
}

void MainComponent::initialiseAudioDevice()
{
    /*  Prioridad de drivers en Windows.

        ASIO es lo mejor para tocar en directo, pero requiere compilar con el
        SDK de Steinberg (ver CMakeLists.txt). Si no está, usamos WASAPI en
        modo exclusivo, que en Windows 10 da una latencia bastante decente.  */
    juce::StringArray preferred { "ASIO", "Windows Audio (Exclusive Mode)", "Windows Audio" };

    for (auto& wanted : preferred)
    {
        for (auto* type : deviceManager.getAvailableDeviceTypes())
        {
            if (type->getTypeName() == wanted)
            {
                deviceManager.setCurrentAudioDeviceType (wanted, true);
                break;
            }
        }

        if (deviceManager.getCurrentAudioDeviceType() == wanted)
            break;
    }

    /*  Pedimos el buffer más pequeño razonable. Si la tarjeta no lo soporta,
        JUCE elige el más cercano disponible en vez de fallar.  */
    auto setup = deviceManager.getAudioDeviceSetup();
    setup.bufferSize = 128;
    setup.sampleRate = 48000.0;

    auto error = deviceManager.setAudioDeviceSetup (setup, true);

    if (error.isNotEmpty())
        DBG ("Aviso al configurar el audio: " << error);
}

void MainComponent::buildUI()
{
    /*  OJO con los acentos:
        juce::String interpreta un const char* como ASCII, NO como UTF-8. Si
        escribes setButtonText("Añadir") la eñe (bytes C3 B1) se lee como dos
        caracteres sueltos y en pantalla sale "AÃ±adir".

        La solucion es envolver el literal en CharPointer_UTF8. El archivo esta
        guardado en UTF-8 y compilamos con /utf-8 (ver CMakeLists.txt), asi que
        los bytes del literal ya son correctos: solo hay que decirle a JUCE
        como interpretarlos.  */
    addButton.setButtonText (juce::CharPointer_UTF8 ("+ Añadir pedal"));

    // --- Lista de la cadena ---
    chainList.setRowHeight (34);
    chainList.setColour (juce::ListBox::backgroundColourId, juce::Colour (0xff1e1e1e));
    chainList.setOutlineThickness (1);
    chainList.setColour (juce::ListBox::outlineColourId, juce::Colour (0xff333333));
    addAndMakeVisible (chainList);

    // --- Botones ---
    // onClick es una std::function: el equivalente C++ de pasar una lambda
    // como callback en Python.
    for (auto* b : { &scanButton, &addButton, &removeButton, &upButton,
                     &downButton, &bypassButton, &saveButton, &loadButton,
                     &settingsButton })
        addAndMakeVisible (b);

    scanButton.onClick   = [this] { showPluginManager(); };
    addButton.onClick    = [this] { showAddPluginMenu(); };

    removeButton.onClick = [this]
    {
        auto row = chainList.getSelectedRow();

        if (row >= 0)
        {
            pluginWindows.clear();          // evitamos editores huérfanos
            graphManager.removePlugin (row);
            updateUI();
        }
    };

    upButton.onClick = [this]
    {
        auto row = chainList.getSelectedRow();

        if (row > 0)
        {
            graphManager.movePlugin (row, row - 1);
            chainList.selectRow (row - 1);
            updateUI();
        }
    };

    downButton.onClick = [this]
    {
        auto row = chainList.getSelectedRow();

        if (row >= 0 && row < graphManager.getNumPlugins() - 1)
        {
            graphManager.movePlugin (row, row + 1);
            chainList.selectRow (row + 1);
            updateUI();
        }
    };

    bypassButton.onClick = [this]
    {
        auto row = chainList.getSelectedRow();

        if (row >= 0)
        {
            graphManager.setBypassed (row, ! graphManager.isBypassed (row));
            updateUI();
        }
    };

    saveButton.onClick = [this] { savePresetPressed(); };
    loadButton.onClick = [this] { loadPresetPressed(); };

    settingsButton.onClick = [this]
    {
        /*  Panel estándar de JUCE para elegir driver, sample rate y buffer.
            Es el mismo que ves en cualquier DAW.  */
        auto selector = std::make_unique<juce::AudioDeviceSelectorComponent> (
                            deviceManager, 0, 2, 0, 2, false, false, true, false);
        selector->setSize (520, 420);

        juce::DialogWindow::LaunchOptions options;
        options.content.setOwned (selector.release());
        options.dialogTitle = juce::CharPointer_UTF8 ("Configuración de audio");
        options.dialogBackgroundColour = juce::Colour (0xff1e1e1e);
        options.useNativeTitleBar = true;
        options.resizable = false;
        options.launchAsync();
    };

    // --- Etiquetas ---
    statusLabel.setColour (juce::Label::textColourId, juce::Colours::grey);
    statusLabel.setFont (juce::Font (12.0f));
    addAndMakeVisible (statusLabel);

    hintLabel.setColour (juce::Label::textColourId, juce::Colour (0xff707070));
    hintLabel.setFont (juce::Font (14.0f));
    hintLabel.setJustificationType (juce::Justification::centred);
    addAndMakeVisible (hintLabel);
}

//==============================================================================
// Callbacks de audio
//==============================================================================

void MainComponent::prepareToPlay (int samplesPerBlockExpected, double sampleRate)
{
    currentSampleRate = sampleRate;
    currentBlockSize  = samplesPerBlockExpected;

    graphManager.prepareToPlay (sampleRate, samplesPerBlockExpected);
}

void MainComponent::getNextAudioBlock (const juce::AudioSourceChannelInfo& bufferToFill)
{
    /*  ESTO CORRE EN EL HILO DE AUDIO, EN TIEMPO REAL.
        Prohibido: reservar memoria, abrir archivos, tomar locks, tocar la GUI.

        bufferToFill puede referirse a un TROZO (startSample..numSamples) de un
        buffer mayor, así que creamos una "vista" sobre esos punteros en vez de
        copiar. Es como un slice de numpy que comparte memoria.  */
    juce::AudioBuffer<float> block (bufferToFill.buffer->getArrayOfWritePointers(),
                                    bufferToFill.buffer->getNumChannels(),
                                    bufferToFill.startSample,
                                    bufferToFill.numSamples);

    juce::MidiBuffer midi;   // vacío: por ahora solo audio
    graphManager.processBlock (block, midi);
}

void MainComponent::releaseResources()
{
    graphManager.releaseResources();
}

//==============================================================================
// Plugins
//==============================================================================

void MainComponent::showPluginManager()
{
    /*  PluginListComponent es la ventana de gestión de plugins que trae JUCE
        (la misma que usa su AudioPluginHost de ejemplo). Nos regala:
          - escaneo en segundo plano con barra de progreso
          - lista negra automática de plugins que crashean al analizarlos
          - botón para añadir/quitar carpetas de búsqueda
        Escribirlo a mano sería cientos de líneas peor probadas.  */
    auto* list = new juce::PluginListComponent (formatManager,
                                                knownPlugins,
                                                getDeadMansPedalFile(),
                                                nullptr,   // sin PropertiesFile
                                                true);     // permitir escaneo asíncrono
    list->setSize (640, 480);

    juce::DialogWindow::LaunchOptions options;
    options.content.setOwned (list);
    options.dialogTitle = "Plugins disponibles";
    options.dialogBackgroundColour = juce::Colour (0xff1e1e1e);
    options.useNativeTitleBar = true;
    options.resizable = true;
    options.launchAsync();
}

void MainComponent::changeListenerCallback (juce::ChangeBroadcaster* source)
{
    if (source == &knownPlugins)
    {
        // Persistimos la lista escaneada para el próximo arranque.
        if (auto xml = knownPlugins.createXml())
            xml->writeTo (getPluginCacheFile());

        updateUI();
    }
}

void MainComponent::showAddPluginMenu()
{
    juce::PopupMenu menu;
    auto types = knownPlugins.getTypes();

    if (types.isEmpty())
    {
        menu.addItem (1, "(Sin plugins: pulsa 'Buscar plugins...')", false);
    }
    else
    {
        /*  addToMenu agrupa los plugins en submenus por fabricante. Con 400+
            plugins instalados un menu plano es inusable: ocupa varias columnas
            y hay que buscar a ojo.

            Los ids que genera son opacos; para saber cual se eligio hay que
            traducirlos con getIndexChosenByMenu, no compararlos a mano.  */
        juce::KnownPluginList::addToMenu (menu, types,
                                          juce::KnownPluginList::sortByManufacturer);
    }

    menu.showMenuAsync (juce::PopupMenu::Options().withTargetComponent (addButton),
        [this, types] (int result)
        {
            auto index = juce::KnownPluginList::getIndexChosenByMenu (types, result);

            if (juce::isPositiveAndBelow (index, types.size()))
            {
                addPluginFromDescription (types[index]);
                updateUI();
            }
        });
}

int MainComponent::addPluginFromDescription (const juce::PluginDescription& description)
{
    juce::String error;

    /*  createPluginInstance carga el .vst3 y devuelve un unique_ptr.
        Es síncrono y puede tardar un segundo; para una app de directo está
        bien, porque solo ocurre montando la pedalera, no tocando.  */
    auto instance = formatManager.createPluginInstance (description,
                                                        currentSampleRate,
                                                        currentBlockSize,
                                                        error);

    if (instance == nullptr)
    {
        juce::AlertWindow::showMessageBoxAsync (juce::MessageBoxIconType::WarningIcon,
                                                "No se pudo cargar el plugin",
                                                error);
        return -1;
    }

    return graphManager.addPlugin (std::move (instance), description);
}

void MainComponent::openEditorForRow (int row)
{
    if (auto* instance = graphManager.getPluginInstance (row))
        pluginWindows.add (new PluginWindow (*instance, pluginWindows));
}

//==============================================================================
// Presets
//==============================================================================

void MainComponent::savePresetPressed()
{
    auto* window = new juce::AlertWindow ("Guardar preset",
                                          "Nombre del preset:",
                                          juce::MessageBoxIconType::NoIcon);
    window->addTextEditor ("name", "Mi sonido");
    window->addButton ("Guardar",  1, juce::KeyPress (juce::KeyPress::returnKey));
    window->addButton ("Cancelar", 0, juce::KeyPress (juce::KeyPress::escapeKey));

    window->enterModalState (true, juce::ModalCallbackFunction::create (
        [this, window] (int result)
        {
            if (result == 1)
            {
                auto name  = window->getTextEditorContents ("name");
                auto state = presetManager.captureState (graphManager);

                if (! presetManager.saveToFile (state, name))
                    DBG ("Fallo al guardar el preset");
            }

            delete window;
        }), false);
}

void MainComponent::loadPresetPressed()
{
    auto names = presetManager.getAllPresetNames();
    juce::PopupMenu menu;

    if (names.isEmpty())
        menu.addItem (1, "(No hay presets guardados)", false);
    else
        for (int i = 0; i < names.size(); ++i)
            menu.addItem (i + 1, names[i]);

    menu.showMenuAsync (juce::PopupMenu::Options().withTargetComponent (loadButton),
        [this, names] (int result)
        {
            if (result > 0 && result <= names.size())
                applyState (presetManager.loadFromFile (names[result - 1]));
        });
}

void MainComponent::applyState (const juce::ValueTree& state)
{
    if (! state.hasType (PresetManager::IDs::rack))
        return;

    // Cerramos editores y vaciamos la pedalera actual.
    pluginWindows.clear();
    graphManager.clear();

    for (const auto& slotTree : state)
    {
        // El primer hijo es la PluginDescription serializada.
        auto descTree = slotTree.getChild (0);

        if (! descTree.isValid())
            continue;

        juce::PluginDescription description;

        if (auto descXml = descTree.createXml())
            if (! description.loadFromXml (*descXml))
                continue;

        auto index = addPluginFromDescription (description);

        if (index < 0)
            continue;

        // Restauramos los knobs del plugin desde el base64.
        juce::MemoryBlock binaryState;

        if (binaryState.fromBase64Encoding (slotTree[PresetManager::IDs::state].toString()))
            if (auto* instance = graphManager.getPluginInstance (index))
                instance->setStateInformation (binaryState.getData(),
                                               (int) binaryState.getSize());

        graphManager.setBypassed (index, (bool) slotTree[PresetManager::IDs::bypassed]);
    }

    updateUI();
}

//==============================================================================
// GUI
//==============================================================================

void MainComponent::paint (juce::Graphics& g)
{
    g.fillAll (juce::Colour (0xff141414));

    g.setColour (juce::Colours::white);
    g.setFont (juce::Font (22.0f, juce::Font::bold));
    g.drawText ("Guitar Pedal Rack", 16, 12, 400, 28, juce::Justification::centredLeft);

    g.setColour (juce::Colour (0xff333333));
    g.drawLine (16.0f, 46.0f, (float) getWidth() - 16.0f, 46.0f);
}

void MainComponent::resized()
{
    auto area = getLocalBounds().reduced (16);
    area.removeFromTop (40);                        // hueco del título

    statusLabel.setBounds (area.removeFromBottom (20));
    area.removeFromBottom (8);

    // Columna derecha con los botones.
    auto sidebar = area.removeFromRight (180);
    area.removeFromRight (12);

    auto placeButton = [&sidebar] (juce::Component& b)
    {
        b.setBounds (sidebar.removeFromTop (30));
        sidebar.removeFromTop (6);
    };

    placeButton (scanButton);
    placeButton (addButton);
    placeButton (removeButton);
    sidebar.removeFromTop (12);
    placeButton (upButton);
    placeButton (downButton);
    placeButton (bypassButton);
    sidebar.removeFromTop (12);
    placeButton (saveButton);
    placeButton (loadButton);
    sidebar.removeFromTop (12);
    placeButton (settingsButton);

    chainList.setBounds (area);
    hintLabel.setBounds (area.reduced (20));
}

void MainComponent::updateUI()
{
    chainList.updateContent();
    chainList.repaint();

    // Mensaje de ayuda cuando la pedalera está vacía.
    if (graphManager.getNumPlugins() == 0)
    {
        hintLabel.setVisible (true);

        if (knownPlugins.getNumTypes() == 0)
            hintLabel.setText (juce::CharPointer_UTF8 (
                                   "Pedalera vacía.\n\n"
                                   "1. Pulsa 'Buscar plugins...' y dentro\n"
                                   "   'Scan for new or updated VST3 plugins'\n"
                                   "2. Pulsa '+ Añadir pedal'"),
                               juce::dontSendNotification);
        else
            hintLabel.setText (juce::CharPointer_UTF8 (
                                   "Pedalera vacía.\n\n"
                                   "Pulsa '+ Añadir pedal' para montar la cadena.\n"
                                   "Doble clic sobre un pedal abre su interfaz."),
                               juce::dontSendNotification);
    }
    else
    {
        hintLabel.setVisible (false);
    }

    juce::String status;
    status << graphManager.getNumPlugins() << " pedal(es)  |  "
           << knownPlugins.getNumTypes() << " plugins encontrados  |  ";

    if (auto* device = deviceManager.getCurrentAudioDevice())
    {
        auto latencyMs = 1000.0 * device->getCurrentBufferSizeSamples()
                                / device->getCurrentSampleRate();

        status << device->getTypeName() << " - " << device->getName()
               << "  |  " << device->getCurrentSampleRate() << " Hz"
               << "  |  buffer " << device->getCurrentBufferSizeSamples()
               << " (" << juce::String (latencyMs, 1) << " ms)";
    }
    else
    {
        status << "sin dispositivo de audio";
    }

    statusLabel.setText (status, juce::dontSendNotification);
}

//==============================================================================
// ListBoxModel
//==============================================================================

int MainComponent::getNumRows()
{
    return graphManager.getNumPlugins();
}

void MainComponent::paintListBoxItem (int rowNumber, juce::Graphics& g,
                                      int width, int height, bool rowIsSelected)
{
    if (! juce::isPositiveAndBelow (rowNumber, graphManager.getNumPlugins()))
        return;

    auto bypassed = graphManager.isBypassed (rowNumber);

    if (rowIsSelected)
        g.fillAll (juce::Colour (0xff2d4f6b));

    // Número de posición en la cadena.
    g.setColour (juce::Colour (0xff666666));
    g.setFont (juce::Font (13.0f));
    g.drawText (juce::String (rowNumber + 1), 10, 0, 26, height,
                juce::Justification::centredLeft);

    // Nombre del pedal.
    g.setColour (bypassed ? juce::Colours::grey : juce::Colours::white);
    g.setFont (juce::Font (15.0f));
    g.drawText (graphManager.getPluginName (rowNumber),
                40, 0, width - 120, height, juce::Justification::centredLeft);

    // Indicador de estado, como el LED de un pedal real.
    g.setColour (bypassed ? juce::Colour (0xff4a4a4a) : juce::Colour (0xff5ad46a));
    g.fillEllipse ((float) width - 28.0f, (float) height * 0.5f - 5.0f, 10.0f, 10.0f);

    g.setColour (juce::Colour (0xff2a2a2a));
    g.drawLine (0.0f, (float) height, (float) width, (float) height);
}

void MainComponent::listBoxItemDoubleClicked (int row, const juce::MouseEvent&)
{
    // Doble clic = abrir la interfaz del pedal.
    openEditorForRow (row);
}

void MainComponent::selectedRowsChanged (int)
{
    auto hasSelection = chainList.getSelectedRow() >= 0;

    removeButton.setEnabled (hasSelection);
    upButton    .setEnabled (hasSelection);
    downButton  .setEnabled (hasSelection);
    bypassButton.setEnabled (hasSelection);
}
