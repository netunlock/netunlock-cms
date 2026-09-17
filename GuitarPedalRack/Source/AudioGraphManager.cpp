/*
    ============================================================================
    AudioGraphManager.cpp
    ============================================================================
*/

#include "AudioGraphManager.h"

using IOProcessor = juce::AudioProcessorGraph::AudioGraphIOProcessor;

//==============================================================================
AudioGraphManager::AudioGraphManager()
{
    /*  El grafo es un AudioProcessor mas: hay que decirle cuantos canales de
        entrada y salida tiene antes de usarlo.  */
    graph.setPlayConfigDetails (2, 2, currentSampleRate, currentBlockSize);

    /*  Nodos de entrada/salida: son procesadores "virtuales" que representan
        la tarjeta de sonido dentro del grafo.  */
    inputNode  = graph.addNode (std::make_unique<IOProcessor> (IOProcessor::audioInputNode));
    outputNode = graph.addNode (std::make_unique<IOProcessor> (IOProcessor::audioOutputNode));

    // Sin pedales todavia: conectamos entrada directa a salida (passthrough).
    rebuildConnections();
}

AudioGraphManager::~AudioGraphManager()
{
    // El grafo libera sus nodos (y por tanto los plugins) automaticamente.
    graph.clear();
}

//==============================================================================
// Ciclo de vida del audio
//==============================================================================

void AudioGraphManager::prepareToPlay (double sampleRate, int blockSize)
{
    currentSampleRate = sampleRate;
    currentBlockSize  = blockSize;

    graph.setPlayConfigDetails (2, 2, sampleRate, blockSize);
    graph.prepareToPlay (sampleRate, blockSize);
}

void AudioGraphManager::releaseResources()
{
    graph.releaseResources();
}

void AudioGraphManager::processBlock (juce::AudioBuffer<float>& buffer,
                                      juce::MidiBuffer& midi)
{
    /*  Una sola llamada: el grafo se encarga de recorrer los nodos en el orden
        topologico correcto y de pasar los buffers de uno a otro.  */
    graph.processBlock (buffer, midi);
}

//==============================================================================
// Gestion de la cadena
//==============================================================================

int AudioGraphManager::addPlugin (std::unique_ptr<juce::AudioPluginInstance> instance,
                                  const juce::PluginDescription& description)
{
    if (instance == nullptr)
        return -1;

    /*  Forzamos el plugin a estereo y al sample rate actual ANTES de meterlo en
        el grafo. Muchos VST se quejan si no se hace.  */
    instance->setPlayConfigDetails (2, 2, currentSampleRate, currentBlockSize);
    instance->enableAllBuses();

    /*  suspendProcessing pausa el hilo de audio mientras modificamos el grafo.
        Sin esto podrias estar reordenando nodos mientras se procesa un bloque. */
    graph.suspendProcessing (true);

    auto node = graph.addNode (std::move (instance));

    if (node == nullptr)
    {
        graph.suspendProcessing (false);
        return -1;
    }

    slots.push_back ({ node, description, false });
    rebuildConnections();

    graph.suspendProcessing (false);

    return (int) slots.size() - 1;
}

void AudioGraphManager::removePlugin (int index)
{
    if (! juce::isPositiveAndBelow (index, (int) slots.size()))
        return;

    graph.suspendProcessing (true);

    auto nodeID = slots[(size_t) index].node->nodeID;
    slots.erase (slots.begin() + index);
    graph.removeNode (nodeID);

    rebuildConnections();
    graph.suspendProcessing (false);
}

void AudioGraphManager::movePlugin (int fromIndex, int toIndex)
{
    if (! juce::isPositiveAndBelow (fromIndex, (int) slots.size())
        || ! juce::isPositiveAndBelow (toIndex, (int) slots.size())
        || fromIndex == toIndex)
        return;

    graph.suspendProcessing (true);

    auto moved = slots[(size_t) fromIndex];
    slots.erase (slots.begin() + fromIndex);
    slots.insert (slots.begin() + toIndex, moved);

    rebuildConnections();
    graph.suspendProcessing (false);
}

void AudioGraphManager::clear()
{
    graph.suspendProcessing (true);

    for (auto& slot : slots)
        graph.removeNode (slot.node->nodeID);

    slots.clear();
    rebuildConnections();

    graph.suspendProcessing (false);
}

void AudioGraphManager::setBypassed (int index, bool shouldBeBypassed)
{
    if (! juce::isPositiveAndBelow (index, (int) slots.size()))
        return;

    graph.suspendProcessing (true);
    slots[(size_t) index].bypassed = shouldBeBypassed;
    rebuildConnections();   // el pedal en bypass simplemente no se conecta
    graph.suspendProcessing (false);
}

bool AudioGraphManager::isBypassed (int index) const
{
    if (! juce::isPositiveAndBelow (index, (int) slots.size()))
        return false;

    return slots[(size_t) index].bypassed;
}

//==============================================================================
// Consultas
//==============================================================================

const AudioGraphManager::Slot* AudioGraphManager::getSlot (int index) const
{
    if (! juce::isPositiveAndBelow (index, (int) slots.size()))
        return nullptr;

    return &slots[(size_t) index];
}

juce::AudioPluginInstance* AudioGraphManager::getPluginInstance (int index) const
{
    if (auto* slot = getSlot (index))
        return dynamic_cast<juce::AudioPluginInstance*> (slot->node->getProcessor());

    return nullptr;
}

juce::String AudioGraphManager::getPluginName (int index) const
{
    if (auto* slot = getSlot (index))
        return slot->description.name;

    return {};
}

//==============================================================================
// Conexiones
//==============================================================================

void AudioGraphManager::rebuildConnections()
{
    // 1. Borrar todas las conexiones existentes.
    for (auto& connection : graph.getConnections())
        graph.removeConnection (connection);

    // 2. Construir la lista de nodos activos en orden (saltando los bypasseados).
    std::vector<Graph::Node::Ptr> chain;
    chain.push_back (inputNode);

    for (auto& slot : slots)
        if (! slot.bypassed)
            chain.push_back (slot.node);

    chain.push_back (outputNode);

    // 3. Encadenar: 0->1, 1->2, 2->3 ...
    for (size_t i = 0; i + 1 < chain.size(); ++i)
        connect (chain[i], chain[i + 1]);
}

void AudioGraphManager::connect (Graph::Node::Ptr source, Graph::Node::Ptr destination)
{
    if (source == nullptr || destination == nullptr)
        return;

    auto numSourceOuts = source->getProcessor()->getTotalNumOutputChannels();
    auto numDestIns    = destination->getProcessor()->getTotalNumInputChannels();

    // Si el plugin es mono y la cadena estereo, conectamos lo que se pueda.
    auto numChannels = juce::jmin (numSourceOuts, numDestIns);

    for (int channel = 0; channel < numChannels; ++channel)
        graph.addConnection ({ { source->nodeID,      channel },
                               { destination->nodeID, channel } });
}
