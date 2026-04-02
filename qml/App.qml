pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.FluentWinUI3
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
    flags: Qt.Window | Qt.FramelessWindowHint
    title: qsTr("净影连 NeatReel")
    color: "#f5f7fa"
    readonly property url defaultPreviewFrameSource: ""
    readonly property int titleBarHeight: 40
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
    property url processingFrameSource: ""
    property int processingDisplayState: DisplayScreen.State.Waiting
    property bool cropPageCreated: false
    property bool processingPageCreated: false
    property var pendingCropRect: null

    function resolvePreviewFrameSource(source) {
        if (source && source.toString().length > 0) {
            return source
        }
        return root.defaultPreviewFrameSource
    }

    function openManualCropPage() {
        cropPageCreated = true
        pendingCropRect = null
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

    function openAboutDialog() {
        aboutDialogLoader.active = true
        if (aboutDialogLoader.status === Loader.Ready && aboutDialogLoader.item) {
            aboutDialogLoader.item.openWindow()
        } else {
            aboutDialogLoader.pendingOpen = true
        }
    }

    function applyPendingCropRect() {
        if (!pendingCropRect || !cropPageLoader.item)
            return

        cropPageLoader.item.setCropRect(
            pendingCropRect.x,
            pendingCropRect.y,
            pendingCropRect.width,
            pendingCropRect.height
        )
        pendingCropRect = null
    }

    component TitleBarMenuButton: Button {
        id: menuButton
        flat: true
        implicitWidth: Math.max(56, contentItem.implicitWidth + leftPadding + rightPadding)
        implicitHeight: 24
        leftPadding: 8
        rightPadding: 8
        topPadding: 2
        bottomPadding: 2
        hoverEnabled: true

        background: Rectangle {
            radius: 5
            color: menuButton.down ? "#dbeafe" : (menuButton.hovered ? "#eef3f9" : "transparent")
        }

        contentItem: Text {
            text: menuButton.text
            font.pixelSize: 12
            font.family: appFontFamily
            font.weight: Font.Normal
            color: "#4b5563"
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            renderType: Text.QtRendering
        }
    }

    FluentTitleBar {
        id: titleBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: root.titleBarHeight
        appName: root.title
        logoSource: ImagePath.logo
        leadingContent: Component {
            TitleBarMenuButton {
                id: settingsMenuButton
                text: qsTr("设置")
                onClicked: {
                    const popupPoint = settingsMenuButton.mapToItem(
                        null,
                        0,
                        settingsMenuButton.height + 8
                    )
                    settingsMenu.x = popupPoint.x
                    settingsMenu.y = popupPoint.y
                    settingsMenu.open()
                }
            }
        }
        z: 30
    }

    Menu {
        id: settingsMenu
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside | Popup.CloseOnReleaseOutside

        MenuItem {
            text: qsTr("关于")
            onTriggered: root.openAboutDialog()
        }

        Menu {
            title: qsTr("语言")

            MenuItem {
                text: qsTr("中文")
                checkable: true
                checked: languageManager
                         && languageManager.currentLanguage === languageManager.chineseLanguage
                onTriggered: languageManager.setLanguage(languageManager.chineseLanguage)
            }

            MenuItem {
                text: qsTr("英文")
                checkable: true
                checked: languageManager
                         && languageManager.currentLanguage === languageManager.englishLanguage
                onTriggered: languageManager.setLanguage(languageManager.englishLanguage)
            }
        }
    }

    Loader {
        id: aboutDialogLoader
        active: false
        asynchronous: true
        property bool pendingOpen: false

        sourceComponent: Component {
            About {
                transientParent: root
            }
        }

        onLoaded: {
            if (pendingOpen && item) {
                pendingOpen = false
                item.openWindow()
            }
        }
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
            root.pendingCropRect = {
                x: cropX,
                y: cropY,
                width: cropWidth,
                height: cropHeight
            }
            root.applyPendingCropRect()
        }

        function onManualCropErrorOccurred(message) {
            root.cropDisplayState = DisplayScreen.State.Error
            root.cropErrorText = message
        }
    }

    Item {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: titleBar.bottom
        anchors.bottom: parent.bottom

        Home {
            id: homePage
            anchors.fill: parent
            visible: root.currentPage === root.homePageIndex

            onStartProcessing: {
                const initialFrame = root.resolvePreviewFrameSource(homePage.previewFrameSource)
                root.processingPageCreated = true
                root.processingFrameSource = initialFrame
                root.processingDisplayState = DisplayScreen.State.Normal
                root.currentPage = root.processingPageIndex
            }

            onOpenManualCropRequested: {
                if (homePage.currentFilePath.length === 0)
                    return
                root.openManualCropPage()
            }
        }

        Loader {
            id: cropPageLoader
            anchors.fill: parent
            active: root.cropPageCreated
            asynchronous: true
            visible: status === Loader.Ready && root.currentPage === root.cropPageIndex

            sourceComponent: Component {
                Crop {
                    anchors.fill: parent
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
            }

            onLoaded: {
                root.applyPendingCropRect()
            }
        }

        Loader {
            id: processingPageLoader
            anchors.fill: parent
            active: root.processingPageCreated
            asynchronous: true
            visible: status === Loader.Ready && root.currentPage === root.processingPageIndex

            sourceComponent: Component {
                Processing {
                    anchors.fill: parent
                    frameSource: root.processingFrameSource
                    displayState: root.processingDisplayState

                    onCancelRequested: processingService.onCancel()
                    onContinueRequested: {
                        processingService.reset()
                        root.currentPage = root.homePageIndex
                    }
                    onOpenOutputDir: processingService.onOpenOutputDir()
                }
            }
        }
    }
}

