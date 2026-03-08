pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.FluentWinUI3
import QtQuick.Dialogs
import QtQuick.Layouts
import "../"
import "../Widgets"
import "../Components"

Item {
    id: root

    signal requestVideoInfo(string filePath)
    signal requestCropPreview(string filePath)
    signal requestRotatePreview(string filePath, int angle)
    signal startProcessing()
    signal openManualCropRequested()

    property bool orientationDebouncing: false
    property bool topActionButtonsDebouncing: false
    property string previewFrameSource: ""
    property bool showingOriginal: false
    property bool globalAutoCropEnabled: true
    property int previewDisplayState: DisplayScreen.State.Waiting
    property var currentCropRect: ({})
    property string defaultOutputDirectory: homeService.defaultOutputDirectory
    property string outputDirectory: defaultOutputDirectory
    readonly property string currentFilePath: videoInfoItem.filePath
    readonly property int currentRotationAngle: videoInfoItem.rotationAngle
    readonly property bool hasSelectedVideo: (
        typeof dropList !== "undefined"
        && dropList.currentIndex >= 0
        && videoInfoItem.filePath !== ""
    )
    readonly property bool hasPreviewThumbnail: (
        previewDisplayState === DisplayScreen.State.Normal
        && previewFrameSource !== ""
    )
    readonly property bool topActionButtonsEnabled: (
        !topActionButtonsDebouncing
        && hasSelectedVideo
        && hasPreviewThumbnail
    )

    // ── backend signal connections ──
    Connections {
        target: homeService

        function onDisplayStateChanged(state) {
            root.previewDisplayState = state
            if (state === 0) displayScreen.setWaiting()
            else if (state === 1) displayScreen.setLoading()
            else if (state === 2) displayScreen.setNormal()
            else if (state === 3) displayScreen.setError("")
        }

        function onThumbnailReady(imageUrl) {
            root.previewFrameSource = imageUrl
        }

        function onCropRectReady(x, y, width, height, sourceWidth, sourceHeight) {
            root.currentCropRect = {
                x: x,
                y: y,
                width: width,
                height: height,
                sourceWidth: sourceWidth,
                sourceHeight: sourceHeight
            }
        }

        function onVideoInfoReady(durationAndResolution) {
            videoInfoItem.durationAndResolution = durationAndResolution
        }

        function onRecommendedRotationReady(angle) {
            videoInfoItem.rotationAngle = angle
            if (typeof dropList !== "undefined" && dropList.currentIndex >= 0) {
                dropList.setItemRotation(dropList.currentIndex, angle)
            }
        }

        function onErrorOccurred(message) {
            root.previewFrameSource = ""
            displayScreen.setError(message)
        }
    }

    function beginOrientationDebounce() {
        orientationDebouncing = true
        orientationDebounceTimer.restart()
    }

    function beginTopActionButtonsDebounce() {
        topActionButtonsDebouncing = true
        topActionButtonsDebounceTimer.restart()
    }

    function currentManualCropPayload() {
        if (typeof dropList === "undefined" || dropList.currentIndex < 0)
            return {}
        return dropList.getItemManualCrop(dropList.currentIndex)
    }

    function currentAutoCropEnabled() {
        if (typeof dropList === "undefined" || dropList.currentIndex < 0)
            return globalAutoCropEnabled
        return dropList.getItemAutoCropEnabled(dropList.currentIndex)
    }

    function syncSelectedAutoCropState() {
        showingOriginal = !currentAutoCropEnabled()
    }

    function refreshSelectedPreview(autoDetectRotation) {
        if (!videoInfoItem.filePath)
            return

        var useAutoCrop = currentAutoCropEnabled()
        if (autoDetectRotation) {
            homeService.onVideoItemClicked(
                videoInfoItem.filePath,
                videoInfoItem.rotationAngle,
                landscapeRadio.checked,
                useAutoCrop,
                currentManualCropPayload()
            )
            return
        }

        homeService.onRotatePreview(
            videoInfoItem.filePath,
            videoInfoItem.rotationAngle,
            landscapeRadio.checked,
            useAutoCrop,
            currentManualCropPayload()
        )
    }

    function applyManualCrop(cropInfo) {
        if (typeof dropList === "undefined" || dropList.currentIndex < 0 || !cropInfo)
            return

        dropList.setItemManualCrop(dropList.currentIndex, cropInfo)
        dropList.setItemAutoCropEnabled(dropList.currentIndex, true)
        currentCropRect = {
            x: Number(cropInfo.x || 0),
            y: Number(cropInfo.y || 0),
            width: Number(cropInfo.width || 0),
            height: Number(cropInfo.height || 0),
            sourceWidth: Number(cropInfo.sourceWidth || 0),
            sourceHeight: Number(cropInfo.sourceHeight || 0)
        }
        showingOriginal = false

        if (videoInfoItem.filePath) {
            refreshSelectedPreview(false)
        }
    }

    function updateRotationAngle(delta) {
        const current = ((videoInfoItem.rotationAngle % 360) + 360) % 360
        var newAngle = (current + delta + 360) % 360
        videoInfoItem.rotationAngle = newAngle
        if (typeof dropList !== "undefined" && dropList.currentIndex >= 0) {
            dropList.setItemRotation(dropList.currentIndex, newAngle)
        }
    }

    Timer {
        id: orientationDebounceTimer
        interval: 1000
        repeat: false
        onTriggered: root.orientationDebouncing = false
    }

    Timer {
        id: topActionButtonsDebounceTimer
        interval: 500
        repeat: false
        onTriggered: root.topActionButtonsDebouncing = false
    }

    component HandCursor: HoverHandler {
        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
        cursorShape: parent.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
    }

    FolderDialog {
        id: outputFolderDialog
        title: "选择输出文件夹"
        currentFolder: homeService.localPathToUrl(root.outputDirectory)
        onAccepted: {
            root.outputDirectory = homeService.normalizeLocalPath(selectedFolder.toString())
        }
    }

    // ── 互斥组 ──
    ButtonGroup { id: orientationGroup }
    ButtonGroup { id: outputModeGroup }

    // ════════════════════════════════════════════════════════
    //  主布局：左右两列
    // ════════════════════════════════════════════════════════
    RowLayout {
        id: mainLayout
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        anchors.bottomMargin: 12
        anchors.topMargin: 8
        spacing: 12

        // ════════════════════════════════════════════════════
        //  左侧 — 视频列表（占 1/4 宽度）
        // ════════════════════════════════════════════════════
        FluentPane {
            id: leftPane
            title: "视频列表"
            icon: ImagePath.videoList
            contentTopMargin: 0
            contentLeftMargin: 0
            contentRightMargin: 0
            contentBottomMargin: 0

            Layout.preferredWidth: Math.floor(root.width * 0.25)
            Layout.minimumWidth: 220
            Layout.fillHeight: true

            DropableList {
                id: dropList
                defaultAutoCropEnabled: root.globalAutoCropEnabled
                anchors.fill: parent
                onLeftclicked: function(data) {
                    if (data && data.filePath) {
                        root.showingOriginal = data.autoCropEnabled === false
                        root.currentCropRect = {}
                        videoInfoItem.filePath = data.filePath
                        var pathStr = data.filePath.toString().replace(/\\/g, "/")
                        var parts = pathStr.split("/")
                        videoInfoItem.fileName = parts[parts.length - 1]
                        if (data.rotation !== undefined) {
                            videoInfoItem.rotationAngle = data.rotation
                        }
                        homeService.onVideoItemClicked(
                            data.filePath,
                            videoInfoItem.rotationAngle,
                            landscapeRadio.checked,
                            data.autoCropEnabled !== false,
                            dropList.getItemManualCrop(dropList.currentIndex)
                        )
                    }
                }
                onItemRemoved: function(filePath) {
                    if (videoInfoItem.filePath === filePath) {
                        root.previewFrameSource = ""
                        root.showingOriginal = false
                        root.currentCropRect = {}
                        videoInfoItem.fileName = ""
                        videoInfoItem.filePath = ""
                        videoInfoItem.durationAndResolution = ""
                        videoInfoItem.rotationAngle = 0
                        displayScreen.setWaiting()
                    }
                }
            }
        }

        // ════════════════════════════════════════════════════
        //  右侧 — 视频详情 + 输出配置（占 3/4 宽度，可滚动）
        // ════════════════════════════════════════════════════
        Flickable {
            id: rightFlickable
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: width
            contentHeight: rightColumn.implicitHeight + 8
            clip: true

            ScrollBar.vertical: ScrollBar {}

            ColumnLayout {
                id: rightColumn
                width: parent.width
                spacing: 12

                // ════════════════════════════════════════════
                //  视频详情面板
                // ════════════════════════════════════════════
                FluentPane {
                    id: detailPane
                    title: "视频详情"
                    icon: ImagePath.movie

                    Layout.fillWidth: true
                    Layout.preferredHeight: detailContent.implicitHeight + 88

                    ColumnLayout {
                        id: detailContent
                        width: parent.width
                        spacing: 10
                        readonly property real actionButtonWidth: Math.max(0, (width - 8) / 2)

                        // ── 视频预览 ──
                        DisplayScreen {
                            id: displayScreen
                            Layout.fillWidth: true
                            Layout.preferredHeight: Math.max(180, width * 9 / 16)

                            frameSource: root.previewFrameSource
                        }

                        // ── 预览去黑边效果（切换按钮） ──
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Button {
                                id: autoCropToggleButton
                                text: root.showingOriginal ? "使用自动去黑边算法" : "使用原始视频"
                                Layout.preferredWidth: detailContent.actionButtonWidth
                                icon.source: ImagePath.crop
                                enabled: root.topActionButtonsEnabled
                                onClicked: {
                                    root.beginTopActionButtonsDebounce()
                                    if (videoInfoItem.filePath) {
                                        var nextUseAutoCrop = !root.currentAutoCropEnabled()
                                        dropList.setItemAutoCropEnabled(dropList.currentIndex, nextUseAutoCrop)
                                        root.showingOriginal = !nextUseAutoCrop
                                        root.refreshSelectedPreview(false)
                                    }
                                }
                                HandCursor {}
                            }

                            Button {
                                text: "手动剪裁"
                                icon.source: ImagePath.crop
                                Layout.preferredWidth: detailContent.actionButtonWidth
                                enabled: root.topActionButtonsEnabled
                                onClicked: root.openManualCropRequested()
                                HandCursor {}
                            }
                        }

                        // ── 旋转按钮行 ──
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Button {
                                text: "顺时针旋转90°"
                                Layout.preferredWidth: detailContent.actionButtonWidth
                                icon.source: ImagePath.clockwise
                                enabled: root.topActionButtonsEnabled
                                onClicked: {
                                    root.beginTopActionButtonsDebounce()
                                    root.updateRotationAngle(90)
                                    if (videoInfoItem.filePath) {
                                        root.refreshSelectedPreview(false)
                                    }
                                }
                                HandCursor {}
                            }

                            Button {
                                text: "逆时针旋转90°"
                                Layout.preferredWidth: detailContent.actionButtonWidth
                                icon.source: ImagePath.counterClockwise
                                enabled: root.topActionButtonsEnabled
                                onClicked: {
                                    root.beginTopActionButtonsDebounce()
                                    root.updateRotationAngle(-90)
                                    if (videoInfoItem.filePath) {
                                        root.refreshSelectedPreview(false)
                                    }
                                }
                                HandCursor {}
                            }
                        }

                        // ── 视频信息 ──
                        VideoInfo {
                            id: videoInfoItem
                            Layout.fillWidth: true
                            Layout.preferredHeight: implicitHeight
                            fileName: ""
                            filePath: ""
                            durationAndResolution: ""
                        }
                    }
                }

                // ════════════════════════════════════════════
                //  输出配置面板
                // ════════════════════════════════════════════
                FluentPane {
                    id: outputPane
                    title: "输出配置"
                    icon: ImagePath.setting

                    Layout.fillWidth: true
                    Layout.preferredHeight: outputContent.implicitHeight + 88

                    ColumnLayout {
                        id: outputContent
                        width: parent.width
                        spacing: 12

                        // ── 画面方向 ──
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 16

                            Text {
                                text: "画面方向"
                                font.pixelSize: 13
                                font.family: "Microsoft YaHei UI"
                                font.weight: Font.Medium
                                color: "#1a1a1a"
                                verticalAlignment: Text.AlignVCenter
                                renderType: Text.NativeRendering
                            }

                            RadioButton {
                                id: landscapeRadio
                                text: "横屏"
                                checked: true
                                ButtonGroup.group: orientationGroup
                                enabled: !root.orientationDebouncing
                                onClicked: {
                                    root.beginOrientationDebounce()
                                    if (videoInfoItem.filePath) {
                                        root.syncSelectedAutoCropState()
                                        root.refreshSelectedPreview(true)
                                    }
                                }
                                HandCursor {}
                            }

                            RadioButton {
                                id: portraitRadio
                                text: "竖屏"
                                ButtonGroup.group: orientationGroup
                                enabled: !root.orientationDebouncing
                                onClicked: {
                                    root.beginOrientationDebounce()
                                    if (videoInfoItem.filePath) {
                                        root.syncSelectedAutoCropState()
                                        root.refreshSelectedPreview(true)
                                    }
                                }
                                HandCursor {}
                            }

                            Item { Layout.fillWidth: true }
                        }

                        // ── 输出视频 ──
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 16

                            Text {
                                text: "输出视频"
                                font.pixelSize: 13
                                font.family: "Microsoft YaHei UI"
                                font.weight: Font.Medium
                                color: "#1a1a1a"
                                verticalAlignment: Text.AlignVCenter
                                renderType: Text.NativeRendering
                            }

                            RadioButton {
                                id: mergeOutputRadio
                                text: "合并成一个视频"
                                checked: true
                                ButtonGroup.group: outputModeGroup
                                HandCursor {}
                            }

                            RadioButton {
                                id: separateOutputRadio
                                text: "分别输出"
                                ButtonGroup.group: outputModeGroup
                                HandCursor {}
                            }

                            Item { Layout.fillWidth: true }
                        }

                        // ── 高级设置手风琴 ──
                        Accordion {
                            id: advancedAccordion
                            title: "高级设置"
                            Layout.fillWidth: true

                            ColumnLayout {
                                width: parent.width
                                spacing: 12

                                // 第一行：处理模式 + 启动自动剪裁
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 12

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Layout.preferredWidth: 1
                                        spacing: 4

                                        Text {
                                            text: "处理模式"
                                            font.pixelSize: 12
                                            font.family: "Microsoft YaHei UI"
                                            color: "#5c6670"
                                            renderType: Text.NativeRendering
                                        }

                                        ComboBox {
                                            id: videoProcessMode
                                            Layout.fillWidth: true
                                            textRole: "text"
                                            model: [
                                                {
                                                    text: "速度",
                                                    tooltip: "比均衡快2~3倍,但体积增大20%~40%，画质略微损失"
                                                },
                                                {
                                                    text: "均衡",
                                                    tooltip: "速度，体积，大小的均衡选择"
                                                },
                                                {
                                                    text: "质量",
                                                    tooltip: "比均衡慢 1~2 倍，体积减少 20%~40%"
                                                },
                                                {
                                                    text: "GPU",
                                                    tooltip: "需要有N卡硬件支持，否则会报错"
                                                }
                                            ]
                                            currentIndex: 1
                                            delegate: ItemDelegate {
                                                required property int index
                                                required property var modelData

                                                width: videoProcessMode.width
                                                text: modelData.text
                                                highlighted: videoProcessMode.highlightedIndex === index
                                                hoverEnabled: true

                                                ToolTip.visible: hovered
                                                ToolTip.delay: 0
                                                ToolTip.text: modelData.tooltip
                                            }
                                            HandCursor {}
                                        }
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Layout.preferredWidth: 1
                                        spacing: 4

                                        Text {
                                            text: "启动自动剪裁"
                                            font.pixelSize: 12
                                            font.family: "Microsoft YaHei UI"
                                            color: "#5c6670"
                                            renderType: Text.NativeRendering
                                        }

                                        Switch {
                                            id: globalAutoCropSwitch
                                            Layout.alignment: Qt.AlignLeft
                                            checked: root.globalAutoCropEnabled
                                            onToggled: {
                                                root.globalAutoCropEnabled = checked
                                                dropList.setAllItemsAutoCropEnabled(checked)
                                                if (videoInfoItem.filePath) {
                                                    root.showingOriginal = !checked
                                                    root.refreshSelectedPreview(false)
                                                }
                                            }
                                        }
                                    }
                                }

                                // 第二行：视频封面
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 10

                                    Text {
                                        text: "视频封面"
                                        font.pixelSize: 13
                                        font.family: "Microsoft YaHei UI"
                                        color: "#1a1a1a"
                                        verticalAlignment: Text.AlignVCenter
                                        renderType: Text.NativeRendering
                                    }

                                    Item { Layout.fillWidth: true }

                                    CoverSelecter {
                                        id: coverSelecter
                                        Layout.alignment: Qt.AlignVCenter
                                    }
                                }

                                // 第三行：输出文件夹
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 10

                                    Text {
                                        text: "输出文件夹"
                                        font.pixelSize: 13
                                        font.family: "Microsoft YaHei UI"
                                        color: "#1a1a1a"
                                        verticalAlignment: Text.AlignVCenter
                                        renderType: Text.NativeRendering
                                    }

                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 36
                                        radius: 6
                                        color: "#ffffff"
                                        border.color: "#d0d7de"
                                        border.width: 1
                                        clip: true

                                        Text {
                                            anchors.fill: parent
                                            anchors.leftMargin: 12
                                            anchors.rightMargin: 12
                                            text: root.outputDirectory
                                            font.pixelSize: 12
                                            font.family: "Microsoft YaHei UI"
                                            color: "#5c6670"
                                            verticalAlignment: Text.AlignVCenter
                                            elide: Text.ElideMiddle
                                            renderType: Text.NativeRendering
                                        }
                                    }

                                    Button {
                                        text: "浏览"
                                        onClicked: outputFolderDialog.open()
                                        HandCursor {}
                                    }

                                    Button {
                                        text: "默认"
                                        enabled: root.outputDirectory !== root.defaultOutputDirectory
                                        onClicked: root.outputDirectory = root.defaultOutputDirectory
                                        HandCursor {}
                                    }
                                }
                            }
                        }

                    }
                }

                // ── 为浮动按钮留出底部空间，防止遮挡最底部控件 ──
                Item {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 68
                }
            }
        }
    }

    // ════════════════════════════════════════════════════════
    //  浮动"开始处理"按钮 — 固定右下角，始终可见
    //  Fluent 风格多层阴影（与 FluentPane 保持一致）
    // ════════════════════════════════════════════════════════

    // ── 阴影层（多层叠加，柔和投影） ──
    Rectangle {
        anchors.top: startFloatButton.top
        anchors.bottom: startFloatButton.bottom
        anchors.left: startFloatButton.left
        anchors.right: startFloatButton.right
        anchors.margins: -1
        radius: 6
        color: "transparent"
        border.color: Qt.rgba(0, 0, 0, 0.12)
        border.width: 1
        z: 99

        Rectangle {
            anchors.fill: parent
            anchors.margins: -2
            radius: parent.radius + 2
            color: "transparent"
            border.color: Qt.rgba(0, 0, 0, 0.07)
            border.width: 1
            z: -1
        }
        Rectangle {
            anchors.fill: parent
            anchors.margins: -5
            radius: parent.radius + 5
            color: "transparent"
            border.color: Qt.rgba(0, 0, 0, 0.04)
            border.width: 1
            z: -2
        }
        Rectangle {
            anchors.fill: parent
            anchors.margins: -9
            radius: parent.radius + 9
            color: "transparent"
            border.color: Qt.rgba(0, 0, 0, 0.02)
            border.width: 1
            z: -3
        }
        Rectangle {
            anchors.fill: parent
            anchors.margins: -14
            radius: parent.radius + 14
            color: "transparent"
            border.color: Qt.rgba(0, 0, 0, 0.008)
            border.width: 1
            z: -4
        }
    }

    Button {
        id: startFloatButton
        text: "开始处理"
        highlighted: true
        icon.source: ImagePath.play
        enabled: dropList.itemCount > 0
        onClicked: {
            var items = dropList.getAllItems()
            if (items.length === 0) return
            var processMode = videoProcessMode.currentIndex
            var isLandscape = landscapeRadio.checked
            var outputMode = mergeOutputRadio.checked ? 0 : 1
            var coverPath = coverSelecter.hasCover ? coverSelecter.coverSource.toString() : ""
            processingService.startMerge(processMode, isLandscape, outputMode, coverPath, root.outputDirectory, items)
            root.startProcessing()
        }
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.rightMargin: 24
        anchors.bottomMargin: 24
        height: 44
        z: 100
        HandCursor {}
    }
}
