import QtQuick
import QtQuick.Controls.FluentWinUI3
import QtQuick.Layouts
import "../Components"
import "../Widgets"
import "../"

Item {
    id: root

    // ══════════════════════════════════════
    //  公共属性
    // ══════════════════════════════════════
    property real   totalProgress: 0.0              // 总进度 0.0–1.0
    property int    totalCurrent: 0                 // 当前已处理数
    property int    totalCount: 0                   // 总数量
    property real   stageProgress: 0.0             // 当前阶段进度 0.0–1.0
    property string stageName: "准备中"            // 阶段名称
    property string elapsedTime: "00:00:00"        // 已用时间
    property real   processingSpeed: 0.0           // 处理速度（倍速）
    property string estimatedRemaining: "0 秒"     // 预计剩余时间
    property string projectId: ""                  // 项目编号（随机8位hex）
    // 状态：0=进行中  1=完成  2=错误
    property int    processingStatus: 0

    // DisplayScreen 转发属性
    property int    displayState: 0                // DisplayScreen.State.Waiting
    property url    frameSource: ""

    // ══════════════════════════════════════
    //  信号
    // ══════════════════════════════════════
    signal cancelRequested()
    signal continueRequested()
    signal openOutputDir()

    // ══════════════════════════════════════
    //  初始化
    // ══════════════════════════════════════
    Component.onCompleted: {
        var chars = "0123456789abcdef"
        var result = ""
        for (var i = 0; i < 8; i++)
            result += chars[Math.floor(Math.random() * chars.length)]
        projectId = result
    }

    // ══════════════════════════════════════
    //  布局
    // ══════════════════════════════════════
    ColumnLayout {
        anchors.fill: parent
        spacing: 8

        // ── 视频预览 ──────────────────────────────
        DisplayScreen {
            Layout.fillWidth: true
            Layout.fillHeight: true
            displayState: root.displayState
            frameSource: root.frameSource
        }

        // ── 处理信息面板 ──────────────────────────
        FluentPane {
            Layout.fillWidth: true
            Layout.preferredHeight: 308
            title: "处理信息"
            icon: ImagePath.info

            ColumnLayout {
                anchors.fill: parent
                spacing: 14

                // ── 总进度 ──
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    RowLayout {
                        Layout.fillWidth: true

                        Text {
                            text: "总进度"
                            font.pixelSize: 13
                            font.family: "Microsoft YaHei UI"
                            font.weight: Font.DemiBold
                            color: "#1a1a1a"
                            renderType: Text.NativeRendering
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: root.totalCurrent + " / " + root.totalCount
                                  + "   " + Math.round(root.totalProgress * 100) + "%"
                            font.pixelSize: 13
                            font.family: "Microsoft YaHei UI"
                            font.weight: Font.DemiBold
                            color: "#0078D4"
                            renderType: Text.NativeRendering
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        height: 6
                        radius: 3
                        color: "#e8e8e8"

                        Rectangle {
                            width: parent.width * Math.max(0.0, Math.min(1.0, root.totalProgress))
                            height: parent.height
                            radius: parent.radius
                            color: "#0078D4"
                            Behavior on width {
                                NumberAnimation { duration: 300; easing.type: Easing.OutCubic }
                            }
                        }
                    }
                }

                // ── 当前阶段进度 ──
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 5

                    RowLayout {
                        Layout.fillWidth: true

                        Text {
                            text: "当前阶段: " + root.stageName
                            font.pixelSize: 12
                            font.family: "Microsoft YaHei UI"
                            color: "#555555"
                            renderType: Text.NativeRendering
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: Math.round(root.stageProgress * 100) + "%"
                            font.pixelSize: 12
                            font.family: "Microsoft YaHei UI"
                            color: "#888888"
                            renderType: Text.NativeRendering
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        height: 4
                        radius: 2
                        color: "#f0f0f0"

                        Rectangle {
                            width: parent.width * Math.max(0.0, Math.min(1.0, root.stageProgress))
                            height: parent.height
                            radius: parent.radius
                            color: "#60bdff"
                            Behavior on width {
                                NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
                            }
                        }
                    }
                }

                // ── 预计剩余时间 ──
                Row {
                    spacing: 5

                    Image {
                        source: ImagePath.clock
                        sourceSize.width: 13
                        sourceSize.height: 13
                        anchors.verticalCenter: parent.verticalCenter
                        opacity: 0.5
                    }

                    Text {
                        text: "预计剩余: " + root.estimatedRemaining
                        font.pixelSize: 12
                        font.family: "Microsoft YaHei UI"
                        color: "#888888"
                        renderType: Text.NativeRendering
                    }
                }

                // ── 分割线 ──
                Rectangle {
                    Layout.fillWidth: true
                    height: 1
                    color: "#f0f0f0"
                }

                // ── 底部统计（四列等宽） ──
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 0

                    // 项目编号
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 3

                        Text {
                            text: "项目编号"
                            font.pixelSize: 11
                            font.family: "Microsoft YaHei UI"
                            color: "#888888"
                            renderType: Text.NativeRendering
                        }
                        Text {
                            text: root.projectId
                            font.pixelSize: 14
                            font.family: "Consolas"
                            font.weight: Font.DemiBold
                            color: "#1a1a1a"
                            renderType: Text.NativeRendering
                        }
                    }

                    // 已用时间
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 3

                        Text {
                            text: "已用时间"
                            font.pixelSize: 11
                            font.family: "Microsoft YaHei UI"
                            color: "#888888"
                            renderType: Text.NativeRendering
                        }
                        Text {
                            text: root.elapsedTime
                            font.pixelSize: 16
                            font.family: "Microsoft YaHei UI"
                            font.weight: Font.DemiBold
                            color: "#1a1a1a"
                            renderType: Text.NativeRendering
                        }
                    }

                    // 处理速度
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 3

                        Text {
                            text: "处理速度"
                            font.pixelSize: 11
                            font.family: "Microsoft YaHei UI"
                            color: "#888888"
                            renderType: Text.NativeRendering
                        }
                        Text {
                            text: root.processingSpeed.toFixed(1) + " x"
                            font.pixelSize: 16
                            font.family: "Microsoft YaHei UI"
                            font.weight: Font.DemiBold
                            color: "#1a1a1a"
                            renderType: Text.NativeRendering
                        }
                    }

                    // 状态
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 3

                        Text {
                            text: "状态"
                            font.pixelSize: 11
                            font.family: "Microsoft YaHei UI"
                            color: "#888888"
                            renderType: Text.NativeRendering
                        }
                        Text {
                            text: root.processingStatus === 1 ? "完成"
                                : root.processingStatus === 2 ? "错误"
                                : "进行中"
                            font.pixelSize: 14
                            font.family: "Microsoft YaHei UI"
                            font.weight: Font.DemiBold
                            color: root.processingStatus === 1 ? "#107C10"
                                 : root.processingStatus === 2 ? "#C42B1C"
                                 : "#0078D4"
                            renderType: Text.NativeRendering
                        }
                    }
                }

                // ── 按钮行 ──
                Item {
                    Layout.fillWidth: true
                    implicitHeight: 32

                    // 主操作按钮（3/4 宽度）
                    Rectangle {
                        id: actionBtn
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        width: parent.width * 3 / 4 - 4
                        radius: 4
                        border.color: Qt.rgba(0, 0, 0, 0.12)
                        border.width: 1

                        property bool btnHovered: false
                        property bool btnPressed: false

                        readonly property color baseColor: root.processingStatus === 0 ? "#C42B1C" : "#107C10"
                        color: btnPressed ? Qt.darker(baseColor, 1.12)
                             : btnHovered ? Qt.lighter(baseColor, 1.10)
                             : baseColor

                        Behavior on color {
                            ColorAnimation { duration: 100 }
                        }

                        Row {
                            anchors.centerIn: parent
                            spacing: 6

                            Image {
                                source: root.processingStatus === 0 ? ImagePath.cancel : ImagePath.ok
                                sourceSize.width: 15
                                sourceSize.height: 15
                                anchors.verticalCenter: parent.verticalCenter
                            }
                            Text {
                                text: root.processingStatus === 0 ? "中止" : "继续"
                                font.pixelSize: 13
                                font.family: "Microsoft YaHei UI"
                                color: "white"
                                renderType: Text.NativeRendering
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onEntered:  { actionBtn.btnHovered = true }
                            onExited:   { actionBtn.btnHovered = false; actionBtn.btnPressed = false }
                            onPressed:  { actionBtn.btnPressed = true }
                            onReleased: { actionBtn.btnPressed = false }
                            onClicked:  {
                                if (root.processingStatus === 0)
                                    root.cancelRequested()
                                else
                                    root.continueRequested()
                            }
                        }
                    }

                    // 打开输出目录按钮（1/4 宽度）
                    Rectangle {
                        id: dirBtn
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        width: parent.width / 4 - 4
                        radius: 4
                        color: dirBtnPressed ? "#ebebeb" : dirBtnHovered ? "#f5f5f5" : "#ffffff"
                        border.color: "#e0e0e0"
                        border.width: 1

                        property bool dirBtnHovered: false
                        property bool dirBtnPressed: false

                        Behavior on color {
                            ColorAnimation { duration: 100 }
                        }

                        Row {
                            anchors.centerIn: parent
                            spacing: 5

                            Image {
                                source: ImagePath.folder
                                sourceSize.width: 15
                                sourceSize.height: 15
                                anchors.verticalCenter: parent.verticalCenter
                            }
                            Text {
                                text: "打开输出目录"
                                font.pixelSize: 12
                                font.family: "Microsoft YaHei UI"
                                color: "#1a1a1a"
                                renderType: Text.NativeRendering
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onEntered:  { dirBtn.dirBtnHovered = true }
                            onExited:   { dirBtn.dirBtnHovered = false; dirBtn.dirBtnPressed = false }
                            onPressed:  { dirBtn.dirBtnPressed = true }
                            onReleased: { dirBtn.dirBtnPressed = false }
                            onClicked:  root.openOutputDir()
                        }
                    }
                }
            }
        }
    }
}
