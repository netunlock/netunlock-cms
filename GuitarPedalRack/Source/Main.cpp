/*
    ============================================================================
    Main.cpp

    Punto de entrada de la aplicacion. Es codigo de plantilla: crea la ventana
    y mete dentro un MainComponent. Rara vez hay que tocarlo.

    Equivalente mental en Python:
        if __name__ == "__main__":
            app = App()
            app.run()
    ============================================================================
*/

#include <JuceHeader.h>
#include "MainComponent.h"

class GuitarPedalRackApplication  : public juce::JUCEApplication
{
public:
    GuitarPedalRackApplication() = default;

    const juce::String getApplicationName() override    { return ProjectInfo::projectName; }
    const juce::String getApplicationVersion() override  { return ProjectInfo::versionString; }
    bool moreThanOneInstanceAllowed() override           { return false; }

    void initialise (const juce::String&) override
    {
        mainWindow = std::make_unique<MainWindow> ("Guitar Pedal Rack");
    }

    void shutdown() override
    {
        mainWindow = nullptr;   // destruye la ventana y con ella el audio
    }

    void systemRequestedQuit() override
    {
        quit();
    }

    //==========================================================================
    class MainWindow : public juce::DocumentWindow
    {
    public:
        explicit MainWindow (const juce::String& name)
            : DocumentWindow (name,
                              juce::Colour (0xff141414),
                              DocumentWindow::allButtons)
        {
            setUsingNativeTitleBar (true);

            // 'true' = la ventana se hace duena del componente y lo destruye.
            setContentOwned (new MainComponent(), true);

            setResizable (true, true);
            setResizeLimits (640, 420, 4000, 3000);
            centreWithSize (getWidth(), getHeight());
            setVisible (true);
        }

        void closeButtonPressed() override
        {
            juce::JUCEApplication::getInstance()->systemRequestedQuit();
        }

    private:
        JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (MainWindow)
    };

private:
    std::unique_ptr<MainWindow> mainWindow;
};

// Genera la funcion main() / WinMain() por nosotros.
START_JUCE_APPLICATION (GuitarPedalRackApplication)
