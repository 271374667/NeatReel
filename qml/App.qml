pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Window
import QtQuick.Controls.FluentWinUI3
import "Windows"

Window {
    id: root
    width: 900
    height: 920
    minimumWidth: 600
    minimumHeight: 700
    visible: true
    title: "VideoMerger"
    color: "#f5f7fa"
    readonly property url defaultPreviewFrameSource: ""
    property bool onProcessingPage: false

    function resolvePreviewFrameSource(source) {
        if (source && source.toString().length > 0) {
            return source
        }
        return root.defaultPreviewFrameSource
    }

    Item {
        anchors.fill: parent

        Home {
            id: homePage
            anchors.fill: parent
            visible: !root.onProcessingPage

            onStartProcessing: {
                const initialFrame = root.resolvePreviewFrameSource(homePage.previewFrameSource)
                processingPage.frameSource = initialFrame
                processingPage.displayState = 2
                root.onProcessingPage = true
            }
        }

        Processing {
            id: processingPage
            anchors.fill: parent
            visible: root.onProcessingPage

            onCancelRequested: root.onProcessingPage = false
            onContinueRequested: root.onProcessingPage = false
        }
    }
}
