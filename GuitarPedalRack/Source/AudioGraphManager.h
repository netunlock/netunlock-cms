/*
    ============================================================================
    AudioGraphManager.h

    Envuelve el juce::AudioProcessorGraph y mantiene la cadena de pedales.

    Analogía para venir de Python:
        El "graph" es como un DAG de nodos. Cada nodo es un objeto que procesa
        audio. Nosotros construimos siempre una cadena lineal:

            [Audio In] -> [Pedal 0] -> [Pedal 1] -> ... -> [Audio Out]

    IMPORTANTE (ownership / memoria):
        Cuando haces graph.addNode(std::move(instance)) el GRAFO se queda con la
        propiedad del plugin. No guardes ademas un unique_ptr al mismo objeto en
        otra clase: se liberaria dos veces y el programa crashea. Por eso aqui
        solo guardamos Node::Ptr, que es un puntero con conteo de referencias
        (parecido a como funcionan las referencias en Python).
    ============================================================================
*/

#pragma once

#include <JuceHeader.h>

class AudioGraphManager
{
public:
    using Graph = juce::AudioProcessorGraph;

    /*  Un "slot" es una posicion de la pedalera: el nodo dentro del grafo mas
        la descripcion del plugin (fabricante, formato, ruta al .dll/.vst3).
        Guardamos la descripcion porque la necesitamos para los presets: al
        cargar un preset hay que volver a instanciar exactamente ese plugin.  */
    struct Slot
    {
        Graph::Node::Ptr node;
        juce::PluginDescription description;
        bool bypassed = false;
    };

    AudioGraphManager();
    ~AudioGraphManager();

    // ------------------------------------------------------------------
    // Ciclo de vida del audio
    // ------------------------------------------------------------------

    /*  Se llama una vez antes de empezar a procesar. Fija sample rate y tamano
        de bloque tanto en el grafo como (en cascada) en todos los plugins.  */
    void prepareToPlay (double sampleRate, int blockSize);

    void releaseResources();

    /*  Llamado desde el hilo de audio en cada bloque. No hace asignaciones de
        memoria ni bloquea: es codigo de tiempo real.  */
    void processBlock (juce::AudioBuffer<float>& buffer, juce::MidiBuffer& midi);

    // ------------------------------------------------------------------
    // Gestion de la cadena
    // ------------------------------------------------------------------

    /*  Anade un plugin al final de la cadena y reconstruye las conexiones.
        Devuelve el indice del slot creado, o -1 si fallo.  */
    int addPlugin (std::unique_ptr<juce::AudioPluginInstance> instance,
                   const juce::PluginDescription& description);

    void removePlugin (int index);

    /*  Mueve un pedal dentro de la cadena (para el drag & drop de la GUI).  */
    void movePlugin (int fromIndex, int toIndex);

    /*  Vacia la pedalera entera. Se usa antes de cargar un preset.  */
    void clear();

    /*  Bypass: el pedal sigue cargado pero el audio lo esquiva.  */
    void setBypassed (int index, bool shouldBeBypassed);
    bool isBypassed (int index) const;

    // ------------------------------------------------------------------
    // Consultas
    // ------------------------------------------------------------------

    int getNumPlugins() const                 { return (int) slots.size(); }
    const Slot* getSlot (int index) const;
    juce::AudioPluginInstance* getPluginInstance (int index) const;
    juce::String getPluginName (int index) const;

    Graph& getGraph()                         { return graph; }

private:
    /*  Borra TODAS las conexiones y las vuelve a crear en orden. Es mas simple
        y menos propenso a errores que intentar parchear conexiones sueltas, y
        se ejecuta solo cuando el usuario toca la cadena (no en tiempo real).  */
    void rebuildConnections();

    /*  Conecta canal a canal dos nodos (estereo = 2 conexiones).  */
    void connect (Graph::Node::Ptr source, Graph::Node::Ptr destination);

    juce::AudioProcessorGraph graph;

    // Nodos especiales que representan la tarjeta de sonido.
    Graph::Node::Ptr inputNode;
    Graph::Node::Ptr outputNode;

    std::vector<Slot> slots;

    double currentSampleRate = 44100.0;
    int    currentBlockSize  = 512;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (AudioGraphManager)
};
