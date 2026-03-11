import QtQuick
import QtQuick.Controls.FluentWinUI3
import QtQuick.Layouts
import QtQuick.Dialogs
import Qt5Compat.GraphicalEffects
import "../"

Item {
    id: root

    // ══════════════════════════════════════
    //  公共属性 & 接口
    // ══════════════════════════════════════
    property bool hasCover: false                       // 是否已选择封面
    property url coverSource: ""                        // 当前封面图片路径 (file:///...)
    property url defaultCover: ""                       // 默认封面图 (可选，外部指定)
    property real cornerRadius: 6                       // 按钮圆角
    property real imageSize: 40                         // 左侧缩略图尺寸
    property color accentColor: "#0078D4"               // 强调色（Fluent 蓝）
    property color hoverColor: Qt.rgba(0, 120/255, 212/255, 0.08)  // 悬停背景
    property color pressedColor: Qt.rgba(0, 120/255, 0.83, 0.12)   // 按下背景
    property color clearColor: "#666666"                // 清除按钮颜色
    property color clearHoverColor: "#c42b1c"           // 清除按钮悬停颜色
    property int fontSize: 13                           // 文字大小
    property int iconSvgSize: 20                        // SVG 图标大小

    // ── 信号 ──
    signal coverSelected(url path)                      // 选择封面后触发
    signal coverCleared()                               // 清除封面后触发

    // ── 便捷函数 ──
    function selectCover() {
        fileDialog.open()
    }

    function clearCover() {
        root.hasCover = false
        root.coverSource = ""
        coverCleared()
    }

    function setCover(path) {
        root.coverSource = path
        root.hasCover = true
        coverSelected(path)
    }

    // ── 尺寸 ──
    implicitWidth: contentRow.implicitWidth + 16
    implicitHeight: Math.max(imageSize + 8, 40)

    // ══════════════════════════════════════
    //  文件选择对话框
    // ══════════════════════════════════════
    FileDialog {
        id: fileDialog
        title: "选择封面图片"
        nameFilters: [
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.svg)"
        ]
        onAccepted: {
            root.setCover(fileDialog.selectedFile)
        }
    }

    // ══════════════════════════════════════
    //  状态 1 — 设置封面按钮
    // ══════════════════════════════════════
    Rectangle {
        id: setupButton
        anchors.fill: parent
        radius: root.cornerRadius
        color: setupMa.pressed
               ? root.pressedColor
               : (setupMa.containsMouse ? root.hoverColor : "transparent")
        visible: !root.hasCover
        opacity: !root.hasCover ? 1 : 0

        Behavior on color {
            ColorAnimation { duration: 150; easing.type: Easing.OutCubic }
        }
        Behavior on opacity {
            NumberAnimation { duration: 200; easing.type: Easing.InOutCubic }
        }

        MouseArea {
            id: setupMa
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: root.selectCover()
        }

        RowLayout {
            anchors.centerIn: parent
            spacing: 6

            // ── Image.svg 图标 ──
            Item {
                width: root.iconSvgSize
                height: root.iconSvgSize
                Layout.alignment: Qt.AlignVCenter

                Image {
                    id: setupIcon
                    anchors.fill: parent
                    source: ImagePath.image
                    sourceSize.width: root.iconSvgSize
                    sourceSize.height: root.iconSvgSize
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                    visible: false
                }

                ColorOverlay {
                    anchors.fill: setupIcon
                    source: setupIcon
                    color: root.accentColor
                    cached: true
                }
            }

            // ── "设置封面" 文字 ──
            Text {
                text: "设置封面"
                font.pixelSize: root.fontSize
                font.family: appFontFamily
                font.weight: Font.DemiBold
                color: root.accentColor
                Layout.alignment: Qt.AlignVCenter
                renderType: Text.NativeRendering
            }
        }
    }

    // ══════════════════════════════════════
    //  状态 2 — 已选封面（缩略图 + 更改/清除）
    // ══════════════════════════════════════
    Item {
        id: coverView
        anchors.fill: parent
        visible: root.hasCover
        opacity: root.hasCover ? 1 : 0

        Behavior on opacity {
            NumberAnimation { duration: 200; easing.type: Easing.InOutCubic }
        }

        RowLayout {
            id: contentRow
            anchors.verticalCenter: parent.verticalCenter
            anchors.left: parent.left
            spacing: 10

            // ── 封面缩略图 ──
            Rectangle {
                id: thumbnailFrame
                width: root.imageSize
                height: root.imageSize
                radius: 4
                color: "#f0f0f0"
                clip: true
                Layout.alignment: Qt.AlignVCenter

                Image {
                    id: coverImage
                    anchors.fill: parent
                    source: root.coverSource
                    fillMode: Image.PreserveAspectCrop
                    smooth: true
                    asynchronous: true

                    // 加载过渡动画
                    opacity: status === Image.Ready ? 1 : 0
                    Behavior on opacity {
                        NumberAnimation { duration: 250; easing.type: Easing.OutCubic }
                    }
                }

                // 加载中占位
                Image {
                    anchors.centerIn: parent
                    source: ImagePath.image
                    sourceSize.width: 16
                    sourceSize.height: 16
                    opacity: coverImage.status !== Image.Ready ? 0.3 : 0
                    visible: opacity > 0
                    Behavior on opacity {
                        NumberAnimation { duration: 200 }
                    }
                }
            }

            // ── "更改" 按钮 ──
            Rectangle {
                id: changeBtn
                width: changeRow.implicitWidth + 12
                height: 28
                radius: 4
                color: changeMa.pressed
                       ? root.pressedColor
                       : (changeMa.containsMouse ? root.hoverColor : "transparent")
                Layout.alignment: Qt.AlignVCenter

                Behavior on color {
                    ColorAnimation { duration: 120; easing.type: Easing.OutCubic }
                }

                MouseArea {
                    id: changeMa
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.selectCover()
                }

                RowLayout {
                    id: changeRow
                    anchors.centerIn: parent
                    spacing: 0

                    Text {
                        text: "更改"
                        font.pixelSize: root.fontSize
                        font.family: appFontFamily
                        font.weight: Font.DemiBold
                        color: root.accentColor
                        Layout.alignment: Qt.AlignVCenter
                        renderType: Text.NativeRendering
                    }
                }
            }

            // ── "清除" 按钮 ──
            Rectangle {
                id: clearBtn
                width: clearRow.implicitWidth + 12
                height: 28
                radius: 4
                color: clearMa.pressed
                       ? Qt.rgba(196/255, 43/255, 28/255, 0.1)
                       : (clearMa.containsMouse ? Qt.rgba(196/255, 43/255, 28/255, 0.06) : "transparent")
                Layout.alignment: Qt.AlignVCenter

                Behavior on color {
                    ColorAnimation { duration: 120; easing.type: Easing.OutCubic }
                }

                MouseArea {
                    id: clearMa
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.clearCover()
                }

                RowLayout {
                    id: clearRow
                    anchors.centerIn: parent
                    spacing: 0

                    Text {
                        text: "清除"
                        font.pixelSize: root.fontSize
                        font.family: appFontFamily
                        font.weight: Font.Normal
                        color: clearMa.containsMouse ? root.clearHoverColor : root.clearColor
                        Layout.alignment: Qt.AlignVCenter
                        renderType: Text.NativeRendering

                        Behavior on color {
                            ColorAnimation { duration: 150; easing.type: Easing.OutCubic }
                        }
                    }
                }
            }
        }
    }
}

