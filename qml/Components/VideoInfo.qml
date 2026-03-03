import QtQuick
import QtQuick.Controls.FluentWinUI3
import QtQuick.Layouts
import "../"

Item {
    id: root
    width: 480
    height: headerRow.height + contentGrid.height + contentGrid.anchors.topMargin + 32

    // ══════════════════════════════════════
    //  公共接口属性（外部可读写）
    // ══════════════════════════════════════
    property string fileName: ""                     // 文件名
    property string filePath: ""                     // 文件路径
    property string durationAndResolution: ""        // 总时长 / 原始分辨率
    property string rotationAngle: "0°"              // 相对于原视频顺时针旋转角度

    // ── 样式属性 ──
    property real  cornerRadius: 8
    property color backgroundColor: "#ffffff"
    property color borderColor: "#e8e8e8"
    property color labelColor: "#5c6670"             // 标签文字颜色（灰色）
    property color valueColor: "#1a1a1a"             // 值文字颜色（深色）
    property color accentColor: "#0078D4"            // 强调色（旋转角度高亮）
    property color iconTintColor: "#0078D4"          // 图标着色

    // ══════════════════════════════════════
    //  阴影层（与 FluentPane 风格统一）
    // ══════════════════════════════════════
    Rectangle {
        anchors.fill: cardBody
        anchors.margins: -1
        radius: root.cornerRadius + 1
        color: "transparent"
        border.color: Qt.rgba(0, 0, 0, 0.09)
        border.width: 1

        Rectangle {
            anchors.fill: parent
            anchors.margins: -2
            radius: root.cornerRadius + 3
            color: "transparent"
            border.color: Qt.rgba(0, 0, 0, 0.04)
            border.width: 1
            z: -1
        }
        Rectangle {
            anchors.fill: parent
            anchors.margins: -4
            radius: root.cornerRadius + 5
            color: "transparent"
            border.color: Qt.rgba(0, 0, 0, 0.025)
            border.width: 1
            z: -2
        }
        Rectangle {
            anchors.fill: parent
            anchors.margins: -7
            radius: root.cornerRadius + 8
            color: "transparent"
            border.color: Qt.rgba(0, 0, 0, 0.015)
            border.width: 1
            z: -3
        }
    }

    // ══════════════════════════════════════
    //  主卡片本体
    // ══════════════════════════════════════
    Rectangle {
        id: cardBody
        anchors.fill: parent
        anchors.margins: 8              // 为阴影留出空间
        radius: root.cornerRadius
        color: root.backgroundColor
        border.color: root.borderColor
        border.width: 1
        clip: true

        // ── 顶部高光线（Fluent2 微妙亮边） ──
        Rectangle {
            width: parent.width - 2 * root.cornerRadius
            height: 1
            anchors.top: parent.top
            anchors.horizontalCenter: parent.horizontalCenter
            color: Qt.rgba(1, 1, 1, 0.65)
        }

        // ─────────────────────────────────
        //  标题栏：Info 图标 + "视频信息"
        // ─────────────────────────────────
        Row {
            id: headerRow
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.leftMargin: 16
            anchors.topMargin: 12
            spacing: 8
            height: 24

            Image {
                id: infoIcon
                source: ImagePath.info
                sourceSize.width: 18
                sourceSize.height: 18
                anchors.verticalCenter: parent.verticalCenter
                fillMode: Image.PreserveAspectFit
                opacity: 0.55
            }

            Text {
                text: "视频信息"
                font.pixelSize: 13
                font.family: "Microsoft YaHei UI"
                font.weight: Font.DemiBold
                color: root.labelColor
                anchors.verticalCenter: parent.verticalCenter
                renderType: Text.NativeRendering
            }
        }

        // ── 标题栏底部分割线 ──
        Rectangle {
            id: headerDivider
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: headerRow.bottom
            anchors.topMargin: 10
            height: 1
            color: Qt.rgba(0, 0, 0, 0.06)
        }

        // ─────────────────────────────────
        //  内容区域：2×2 网格布局
        // ─────────────────────────────────
        GridLayout {
            id: contentGrid
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: headerDivider.bottom
            anchors.leftMargin: 16
            anchors.rightMargin: 16
            anchors.topMargin: 14
            columns: 2
            columnSpacing: 32
            rowSpacing: 16

            // ── 文件名 ──
            Column {
                spacing: 4
                Layout.fillWidth: true

                Text {
                    text: "文件名"
                    font.pixelSize: 12
                    font.family: "Microsoft YaHei UI"
                    font.weight: Font.Normal
                    color: root.labelColor
                    renderType: Text.NativeRendering
                }

                Text {
                    text: root.fileName || "—"
                    font.pixelSize: 14
                    font.family: "Microsoft YaHei UI"
                    font.weight: Font.Normal
                    color: root.valueColor
                    elide: Text.ElideMiddle
                    width: parent.parent ? parent.parent.width : implicitWidth
                    maximumLineCount: 1
                    renderType: Text.NativeRendering
                }
            }

            // ── 文件路径 ──
            Column {
                spacing: 4
                Layout.fillWidth: true

                Text {
                    text: "文件路径"
                    font.pixelSize: 12
                    font.family: "Microsoft YaHei UI"
                    font.weight: Font.Normal
                    color: root.labelColor
                    renderType: Text.NativeRendering
                }

                Text {
                    text: root.filePath || "—"
                    font.pixelSize: 14
                    font.family: "Microsoft YaHei UI"
                    font.weight: Font.Normal
                    color: root.valueColor
                    elide: Text.ElideMiddle
                    width: parent.parent ? parent.parent.width : implicitWidth
                    maximumLineCount: 1
                    renderType: Text.NativeRendering
                }
            }

            // ── 总时长 / 原始分辨率 ──
            Column {
                spacing: 4
                Layout.fillWidth: true

                Text {
                    text: "总时长 / 原始分辨率"
                    font.pixelSize: 12
                    font.family: "Microsoft YaHei UI"
                    font.weight: Font.Normal
                    color: root.labelColor
                    renderType: Text.NativeRendering
                }

                Text {
                    text: root.durationAndResolution || "—"
                    font.pixelSize: 14
                    font.family: "Microsoft YaHei UI"
                    font.weight: Font.Normal
                    color: root.valueColor
                    elide: Text.ElideRight
                    width: parent.parent ? parent.parent.width : implicitWidth
                    maximumLineCount: 1
                    renderType: Text.NativeRendering
                }
            }

            // ── 相对于原视频顺时针旋转角度 ──
            Column {
                spacing: 4
                Layout.fillWidth: true

                Text {
                    text: "相对于原视频顺时针旋转角度"
                    font.pixelSize: 12
                    font.family: "Microsoft YaHei UI"
                    font.weight: Font.Normal
                    color: root.accentColor
                    renderType: Text.NativeRendering
                }

                Text {
                    text: root.rotationAngle || "0°"
                    font.pixelSize: 14
                    font.family: "Microsoft YaHei UI"
                    font.weight: Font.DemiBold
                    color: root.accentColor
                    elide: Text.ElideRight
                    width: parent.parent ? parent.parent.width : implicitWidth
                    maximumLineCount: 1
                    renderType: Text.NativeRendering
                }
            }
        }
    }
}
