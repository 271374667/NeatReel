import QtQuick
import QtQuick.Controls.FluentWinUI3
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

    property bool orientationDebouncing: false
    property bool topActionButtonsDebouncing: false
    property string previewFrameSource: ""
    property bool showingOriginal: false

    // ── backend signal connections ──
    Connections {
        target: homeService

        function onDisplayStateChanged(state) {
            if (state === 0) displayScreen.setWaiting()
            else if (state === 1) displayScreen.setLoading()
            else if (state === 2) displayScreen.setNormal()
            else if (state === 3) displayScreen.setError("")
        }

        function onThumbnailReady(imageUrl) {
            root.previewFrameSource = imageUrl
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
        interval: 2000
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

    // ── 画面方向互斥组 ──
    ButtonGroup { id: orientationGroup }

    // ════════════════════════════════════════════════════════
    //  主布局：左右两列
    // ════════════════════════════════════════════════════════
    RowLayout {
        id: mainLayout
        anchors.fill: parent
        anchors.margins: 12
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
                anchors.fill: parent
                onLeftclicked: function(data) {
                    if (data && data.filePath) {
                        root.showingOriginal = false
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
                            landscapeRadio.checked
                        )
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

                        // ── 视频预览 ──
                        DisplayScreen {
                            id: displayScreen
                            Layout.fillWidth: true
                            Layout.preferredHeight: Math.max(180, width * 9 / 16)

                            frameSource: root.previewFrameSource
                        }

                        // ── 预览去黑边效果（切换按钮） ──
                        Button {
                            text: root.showingOriginal ? "预览去黑边后的视频" : "预览原视频(不去黑边)"
                            Layout.fillWidth: true
                            icon.source: ImagePath.crop
                            enabled: !root.topActionButtonsDebouncing
                            onClicked: {
                                root.beginTopActionButtonsDebounce()
                                if (videoInfoItem.filePath) {
                                    root.showingOriginal = !root.showingOriginal
                                    if (root.showingOriginal) {
                                        homeService.onPreviewOriginal(
                                            videoInfoItem.filePath,
                                            videoInfoItem.rotationAngle,
                                            landscapeRadio.checked
                                        )
                                    } else {
                                        homeService.onRotatePreview(
                                            videoInfoItem.filePath,
                                            videoInfoItem.rotationAngle,
                                            landscapeRadio.checked
                                        )
                                    }
                                }
                            }
                            HandCursor {}
                        }

                        // ── 旋转按钮行 ──
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Button {
                                text: "顺时针旋转90°"
                                Layout.fillWidth: true
                                icon.source: ImagePath.clockwise
                                enabled: !root.topActionButtonsDebouncing
                                onClicked: {
                                    root.beginTopActionButtonsDebounce()
                                    root.updateRotationAngle(90)
                                    if (videoInfoItem.filePath) {
                                        homeService.onRotatePreview(
                                            videoInfoItem.filePath,
                                            videoInfoItem.rotationAngle,
                                            landscapeRadio.checked
                                        )
                                    }
                                }
                                HandCursor {}
                            }

                            Button {
                                text: "逆时针旋转90°"
                                Layout.fillWidth: true
                                icon.source: ImagePath.counterClockwise
                                enabled: !root.topActionButtonsDebouncing
                                onClicked: {
                                    root.beginTopActionButtonsDebounce()
                                    root.updateRotationAngle(-90)
                                    if (videoInfoItem.filePath) {
                                        homeService.onRotatePreview(
                                            videoInfoItem.filePath,
                                            videoInfoItem.rotationAngle,
                                            landscapeRadio.checked
                                        )
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
                                onClicked: root.beginOrientationDebounce()
                                HandCursor {}
                            }

                            RadioButton {
                                id: portraitRadio
                                text: "竖屏"
                                ButtonGroup.group: orientationGroup
                                enabled: !root.orientationDebouncing
                                onClicked: root.beginOrientationDebounce()
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

                                // 第一行：处理模式 + 旋转角度
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 12

                                    ColumnLayout {
                                        Layout.fillWidth: true
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
                                            model: ["速度", "均衡", "质量"]
                                            currentIndex: 1
                                            HandCursor {}
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
        onClicked: {
            var items = dropList.getAllItems()
            if (items.length === 0) return
            var processMode = videoProcessMode.currentIndex
            var isLandscape = landscapeRadio.checked
            var coverPath = coverSelecter.hasCover ? coverSelecter.coverSource.toString() : ""
            homeService.onStartProcessing(processMode, isLandscape, coverPath, items)
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
