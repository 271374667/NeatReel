pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Window
import "Components"
import "Windows"

Window {
    id: root
    width: 900
    height: 920
    minimumWidth: 600
    minimumHeight: 700
    visible: true
    title: "净影连 NeatReel"
    color: "#f5f7fa"
    readonly property url defaultPreviewFrameSource: ""
    readonly property int homePageIndex: 0
    readonly property int cropPageIndex: 1
    readonly property int processingPageIndex: 2
    property int currentPage: homePageIndex
    property url cropFrameSource: ""
    property int cropDisplayState: DisplayScreen.State.Waiting
    property string cropErrorText: ""
    property int cropRotationAngle: 0
    property int cropOriginalWidth: 0
    property int cropOriginalHeight: 0
    property int cropLogicalWidth: 0
    property int cropLogicalHeight: 0

    function resolvePreviewFrameSource(source) {
        if (source && source.toString().length > 0) {
            return source
        }
        return root.defaultPreviewFrameSource
    }

    function openManualCropPage() {
        cropFrameSource = ""
        cropDisplayState = DisplayScreen.State.Loading
        cropErrorText = ""
        cropRotationAngle = 0
        cropOriginalWidth = 0
        cropOriginalHeight = 0
        cropLogicalWidth = 0
        cropLogicalHeight = 0
        currentPage = cropPageIndex
        homeService.onOpenManualCrop(
            homePage.currentFilePath,
            homePage.currentRotationAngle,
            homePage.currentManualCropPayload()
        )
    }

    Connections {
        target: homeService

        function onManualCropSessionReady(imageUrl, rotationAngle, originalWidth, originalHeight, cropX, cropY, cropWidth, cropHeight) {
            root.cropFrameSource = imageUrl
            root.cropDisplayState = DisplayScreen.State.Normal
            root.cropErrorText = ""
            root.cropRotationAngle = rotationAngle
            root.cropOriginalWidth = originalWidth
            root.cropOriginalHeight = originalHeight
            root.cropLogicalWidth = (rotationAngle === 90 || rotationAngle === 270) ? originalHeight : originalWidth
            root.cropLogicalHeight = (rotationAngle === 90 || rotationAngle === 270) ? originalWidth : originalHeight
            cropPage.setCropRect(cropX, cropY, cropWidth, cropHeight)
        }

        function onManualCropErrorOccurred(message) {
            root.cropDisplayState = DisplayScreen.State.Error
            root.cropErrorText = message
        }
    }

    Item {
        anchors.fill: parent

        Home {
            id: homePage
            anchors.fill: parent
            visible: root.currentPage === root.homePageIndex

            onStartProcessing: {
                const initialFrame = root.resolvePreviewFrameSource(homePage.previewFrameSource)
                processingPage.frameSource = initialFrame
                processingPage.displayState = 2
                root.currentPage = root.processingPageIndex
            }

            onOpenManualCropRequested: {
                if (homePage.currentFilePath.length === 0)
                    return
                root.openManualCropPage()
            }
        }

        Crop {
            id: cropPage
            anchors.fill: parent
            visible: root.currentPage === root.cropPageIndex
            frameSource: root.cropFrameSource
            displayState: root.cropDisplayState
            errorText: root.cropErrorText
            rotationAngle: root.cropRotationAngle
            originalSourceWidth: root.cropOriginalWidth
            originalSourceHeight: root.cropOriginalHeight
            logicalSourceWidth: root.cropLogicalWidth
            logicalSourceHeight: root.cropLogicalHeight

            onCancelRequested: root.currentPage = root.homePageIndex
            onConfirmRequested: function(cropInfo) {
                homePage.applyManualCrop(cropInfo)
                root.currentPage = root.homePageIndex
            }
        }

        Processing {
            id: processingPage
            anchors.fill: parent
            visible: root.currentPage === root.processingPageIndex

            onCancelRequested: processingService.onCancel()
            onContinueRequested: {
                processingService.reset()
                root.currentPage = root.homePageIndex
            }
            onOpenOutputDir: processingService.onOpenOutputDir()
        }
    }
}
