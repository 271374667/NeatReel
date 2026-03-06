import QtQuick
import QtQuick.Controls.FluentWinUI3
import QtQuick.Layouts
import QtQuick.Effects
import "../Components"
import "../Widgets"
import "../"

Item {
    id: root

    property real totalProgress: 0.0
    property int totalCurrent: 0
    property int totalCount: 0
    property real stageProgress: 0.0
    property string stageName: "准备中"
    property string elapsedTime: "00:00:00"
    property real processingSpeed: 0.0
    property string estimatedRemaining: "0 秒"
    property string projectId: ""
    property int processingStatus: 0 // 0: 进行中, 1: 完成, 2: 错误
    property int displayState: 0
    property url frameSource: ""

    signal cancelRequested()
    signal continueRequested()
    signal openOutputDir()

    // Smooth speed animation with Bezier curve
    Behavior on processingSpeed {
        NumberAnimation { duration: 800; easing.type: Easing.InOutCubic }
    }

    // ── backend signal connections ──
    Connections {
        target: processingService

        function onTotalProgressChanged(v) { root.totalProgress = v }
        function onTotalCurrentChanged(v) { root.totalCurrent = v }
        function onTotalCountChanged(v) { root.totalCount = v }
        function onStageProgressChanged(v) { root.stageProgress = v }
        function onStageNameChanged(v) { root.stageName = v }
        function onElapsedTimeChanged(v) { root.elapsedTime = v }
        function onProcessingSpeedChanged(v) { root.processingSpeed = v }
        function onEstimatedRemainingChanged(v) { root.estimatedRemaining = v }
        function onProcessingStatusChanged(v) { root.processingStatus = v }
        function onDisplayStateChanged(v) { root.displayState = v }
        function onFrameSourceChanged(v) { root.frameSource = v }
        function onProjectIdChanged(v) { root.projectId = v }
    }

    readonly property real tp: Math.max(0.0, Math.min(1.0, totalProgress))
    readonly property real sp: Math.max(0.0, Math.min(1.0, stageProgress))
    readonly property real displayTotalProgress: processingStatus === 1 ? 1.0 : tp
    readonly property real displayStageProgress: processingStatus === 1 ? 1.0 : sp
    readonly property int displayCurrentCount: processingStatus === 1 && totalCount > 0 ? totalCount : totalCurrent
    readonly property string displayStageName: processingStatus === 1 ? "完成" : (stageName.length > 0 ? stageName : "准备中")
    readonly property color barColor: processingStatus === 1 ? "#107C10" : processingStatus === 2 ? "#C42B1C" : "#0078D4"
    readonly property string pctText: Math.round(displayTotalProgress * 100) + "%"
    readonly property string statusText: processingStatus === 1 ? "完成" : processingStatus === 2 ? "错误" : "进行中"

    component StatCard: Rectangle {
        id: statCard
        property string title: ""
        property string value: ""              
        property string note: ""
        property color valueColor: "#111111"
        property bool mono: false
        property bool big: false
        implicitWidth: 170
        implicitHeight: 88
        radius: 10
        color: "#f8f9fa"
        border.width: 1
        border.color: "#e6eaef"
        clip: true

        Rectangle {
            anchors.fill: parent
            anchors.margins: -1
            radius: parent.radius + 1
            color: "transparent"
            border.width: 1
            border.color: Qt.rgba(0, 0, 0, 0.05)
            z: -1
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 3

            Text {
                text: statCard.title
                font.pixelSize: 12
                font.family: "Microsoft YaHei UI"
                color: "#5c6670"
                renderType: Text.NativeRendering
            }
            Text {
                text: statCard.value
                font.pixelSize: statCard.big ? 22 : 18
                font.family: statCard.mono ? "Consolas" : "Microsoft YaHei UI"
                font.weight: Font.DemiBold
                color: statCard.valueColor
                elide: Text.ElideRight
                renderType: Text.NativeRendering
            }
            Text {
                visible: statCard.note.length > 0
                text: statCard.note
                font.pixelSize: 11
                font.family: "Microsoft YaHei UI"
                color: "#8a939d"
                elide: Text.ElideRight
                renderType: Text.NativeRendering
            }
        }
    }

    component ActionButton: Rectangle {
        id: btn
        property string text: ""
        property bool primary: false
        property bool danger: false
        property bool hovered: false
        property bool pressed: false
        signal clicked()

        implicitHeight: 36
        implicitWidth: Math.max(96, label.implicitWidth + 28)
        radius: 8
        border.width: 1
        border.color: primary ? "#006FC6" : danger && hovered ? "#d49a95" : "#d2d7dd"
        color: primary
               ? (pressed ? "#0063B1" : hovered ? "#1384da" : "#0078D4")
               : danger
                 ? (pressed ? Qt.rgba(196 / 255, 43 / 255, 28 / 255, 0.14)
                            : hovered ? Qt.rgba(196 / 255, 43 / 255, 28 / 255, 0.08) : "transparent")
                 : (pressed ? Qt.rgba(0, 0, 0, 0.08)
                            : hovered ? Qt.rgba(0, 0, 0, 0.04) : "transparent")

        Behavior on color { ColorAnimation { duration: 140; easing.type: Easing.OutCubic } }

        Text {
            id: label
            anchors.centerIn: parent
            text: btn.text
            font.pixelSize: 13
            font.family: "Microsoft YaHei UI"
            font.weight: Font.DemiBold
            color: btn.primary ? "white" : btn.danger ? btn.hovered ? "#a4262c" : "#5e6670" : "#2f343a"
            renderType: Text.NativeRendering
        }

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onEntered: btn.hovered = true
            onExited: { btn.hovered = false; btn.pressed = false }
            onPressed: btn.pressed = true
            onReleased: btn.pressed = false
            onClicked: btn.clicked()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 12

        TextMetrics {
            id: pctMetrics
            font.family: "Segoe UI Variable Display"
            font.pixelSize: 32
            font.weight: Font.Bold
            text: "100%"
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredHeight: Math.max(260, root.height * 0.6)

            Rectangle {
                anchors.fill: parent
                radius: 10
                color: "#111315"
                border.width: 1
                border.color: "#d8dde3"
                clip: true

                DisplayScreen {
                    anchors.fill: parent
                    anchors.margins: -8
                    displayState: root.displayState
                    frameSource: root.frameSource
                }

                Rectangle {
                    anchors.fill: parent
                    radius: parent.radius
                    color: Qt.rgba(1, 1, 1, 0.05)
                }

                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    height: parent.height * 0.34
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: Qt.rgba(1, 1, 1, 0.12) }
                        GradientStop { position: 1.0; color: Qt.rgba(1, 1, 1, 0.0) }
                    }
                }
            }
        }

        FluentPane {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredHeight: Math.max(240, root.height * 0.4)
            title: "处理信息"
            icon: ImagePath.info
            contentTopMargin: 14
            contentLeftMargin: 16
            contentRightMargin: 16
            contentBottomMargin: 14

            ColumnLayout {
                anchors.fill: parent
                spacing: 10

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    Text {
                        text: root.pctText
                        width: pctMetrics.advanceWidth + 2
                        horizontalAlignment: Text.AlignRight
                        font.pixelSize: 32
                        font.family: "Segoe UI Variable Display"
                        font.weight: Font.Bold
                        color: root.barColor
                        renderType: Text.NativeRendering
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2

                        Text {
                            text: root.totalCount > 0 ? "总任务 " + root.displayCurrentCount + " / " + root.totalCount : "已处理任务 " + root.displayCurrentCount
                            font.pixelSize: 13
                            font.family: "Microsoft YaHei UI"
                            font.weight: Font.DemiBold
                            color: "#1f252b"
                            renderType: Text.NativeRendering
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 8
                    radius: 4
                    color: "#e5e8ec"
                    clip: true

                    Rectangle {
                        id: totalFill
                        width: parent.width * root.displayTotalProgress
                        height: parent.height
                        radius: parent.radius
                        color: root.barColor
                        Behavior on width { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
                        Behavior on color { ColorAnimation { duration: 220; easing.type: Easing.OutCubic } }

                        Item {
                            id: glowHead
                            width: 24
                            height: 24
                            anchors.right: parent.right
                            anchors.rightMargin: -8
                            anchors.verticalCenter: parent.verticalCenter
                            visible: root.processingStatus === 0 && root.displayTotalProgress > 0.0 && root.displayTotalProgress < 1.0

                            Rectangle {
                                id: glowBlob
                                anchors.centerIn: parent
                                width: 14
                                height: 14
                                radius: 7
                                color: root.barColor
                                opacity: 0.78
                            }

                            MultiEffect {
                                anchors.fill: glowBlob
                                anchors.margins: -8
                                source: glowBlob
                                blurEnabled: true
                                blur: 1.0
                                blurMax: 32
                                brightness: 0.35
                            }

                            Rectangle {
                                anchors.centerIn: parent
                                width: 6
                                height: 6
                                radius: 3
                                color: "white"
                                opacity: 0.88
                            }

                            SequentialAnimation on opacity {
                                running: glowHead.visible
                                loops: Animation.Infinite
                                NumberAnimation { to: 0.56; duration: 520; easing.type: Easing.InOutQuad }
                                NumberAnimation { to: 1.0; duration: 520; easing.type: Easing.InOutQuad }
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Text {
                        text: root.displayStageName
                        Layout.fillWidth: true
                        font.pixelSize: 12
                        font.family: "Microsoft YaHei UI"
                        color: "#4e5964"
                        elide: Text.ElideRight
                        renderType: Text.NativeRendering
                    }

                    Text {
                        text: Math.round(root.displayStageProgress * 100) + "%"
                        font.pixelSize: 12
                        font.family: "Microsoft YaHei UI"
                        color: "#6c7783"
                        renderType: Text.NativeRendering
                    }

                    Text {
                        visible: root.processingStatus === 0 && root.estimatedRemaining.length > 0
                        text: "预计剩余 " + root.estimatedRemaining
                        font.pixelSize: 12
                        font.family: "Microsoft YaHei UI"
                        color: "#7c8793"
                        renderType: Text.NativeRendering
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 4
                    radius: 2
                    color: "#edf0f3"
                    clip: true

                    Rectangle {
                        width: parent.width * root.displayStageProgress
                        height: parent.height
                        radius: parent.radius
                        color: Qt.rgba(0, 120 / 255, 212 / 255, 0.58)
                        Behavior on width { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 1
                    color: "#edf1f4"
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 10

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignVCenter
                        spacing: 10

                        StatCard {
                            Layout.fillWidth: true
                            title: "已用时间"
                            value: root.elapsedTime
                            note: "实时累计"
                            mono: true
                            big: true
                        }

                        StatCard {
                            Layout.fillWidth: true
                            title: "处理速度"
                            value: root.processingSpeed.toFixed(1) + "x"
                            note: "平均速度"
                            mono: true
                            big: true
                        }

                        StatCard {
                            Layout.fillWidth: true
                            title: "当前状态"
                            value: root.statusText
                            note: "项目 " + root.projectId
                            valueColor: root.processingStatus === 1 ? "#107C10" : root.processingStatus === 2 ? "#C42B1C" : "#0078D4"
                        }
                    }

                    Item {
                        Layout.preferredWidth: Math.max(cancelBtn.implicitWidth, doneActions.implicitWidth, errorBtn.implicitWidth)
                        Layout.minimumWidth: 132
                        Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                        implicitHeight: 40

                        Item {
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            width: cancelBtn.implicitWidth
                            height: cancelBtn.implicitHeight
                            visible: opacity > 0.01
                            opacity: root.processingStatus === 0 ? 1.0 : 0.0
                            scale: root.processingStatus === 0 ? 1.0 : 0.95
                            Behavior on opacity { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
                            Behavior on scale { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }

                            ActionButton {
                                id: cancelBtn
                                anchors.right: parent.right
                                text: "中止"
                                danger: true
                                onClicked: root.cancelRequested()
                            }
                        }

                        RowLayout {
                            id: doneActions
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 8
                            visible: opacity > 0.01
                            opacity: root.processingStatus === 1 ? 1.0 : 0.0
                            scale: root.processingStatus === 1 ? 1.0 : 0.95
                            Behavior on opacity { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
                            Behavior on scale { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }

                            ActionButton {
                                text: "继续"
                                onClicked: root.continueRequested()
                            }

                            ActionButton {
                                text: "打开输出目录"
                                primary: true
                                onClicked: root.openOutputDir()
                            }
                        }

                        Item {
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            width: errorBtn.implicitWidth
                            height: errorBtn.implicitHeight
                            visible: opacity > 0.01
                            opacity: root.processingStatus === 2 ? 1.0 : 0.0
                            scale: root.processingStatus === 2 ? 1.0 : 0.95
                            Behavior on opacity { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
                            Behavior on scale { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }

                            ActionButton {
                                id: errorBtn
                                anchors.right: parent.right
                                text: "继续"
                                primary: true
                                onClicked: root.continueRequested()
                            }
                        }
                    }
                }
            }
        }
    }
}
