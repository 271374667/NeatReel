import QtQuick
import QtQuick.Controls.FluentWinUI3
import QtQuick.Layouts

Item {
    id: root

    // ── 公共属性 ──
    property string title: ""                       // 手风琴标题
    property bool expanded: false                   // 是否展开
    property real cornerRadius: 8                   // 圆角半径
    property color backgroundColor: "#ffffff"       // 头部背景色
    property color hoverColor: "#f5f5f5"            // 悬停背景色
    property color pressedColor: "#ebebeb"          // 按下背景色
    property color borderColor: "#e8e8e8"           // 边框颜色
    property color titleColor: "#1a1a1a"            // 标题文字颜色
    property color arrowColor: "#606060"            // 箭头颜色
    property color contentBackgroundColor: "#e8e8e8" // 展开内容区背景（明显深于父级）
    property color contentBorderColor: "#d0d0d0"    // 内容区内边框颜色
    property int headerHeight: 44                   // 头部高度
    property int titleSize: 13                      // 标题大小
    property int animationDuration: 250             // 动画时长 (ms)
    property int contentLeftMargin: 16              // 内容区域左侧留白
    property int contentRightMargin: 16             // 内容区域右侧留白
    property int contentTopMargin: 12               // 内容区域顶部留白
    property int contentBottomMargin: 16            // 内容区域底部留白

    // ── 内容区 (default property) ──
    default property alias contentData: contentContainer.data

    // ── 计算展开后的总高度 ──
    implicitHeight: headerHeight + (expanded ? contentPane.height : 0)
    clip: true

    // ── 高度动画 ──
    Behavior on implicitHeight {
        NumberAnimation {
            duration: root.animationDuration
            easing.type: Easing.OutCubic
        }
    }

    // ── 外层容器 ──
    Rectangle {
        id: outerFrame
        anchors.fill: parent
        radius: root.cornerRadius
        color: "transparent"
        border.color: root.borderColor
        border.width: 1
        clip: true

        // ── 头部按钮区域 ──
        Rectangle {
            id: headerArea
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: root.headerHeight
            radius: root.expanded ? 0 : root.cornerRadius
            color: headerMouse.pressed
                   ? root.pressedColor
                   : headerMouse.containsMouse
                     ? root.hoverColor
                     : root.backgroundColor

            Behavior on color {
                ColorAnimation { duration: 120 }
            }

            // ── 顶部圆角遮罩（始终保持顶部圆角） ──
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: root.cornerRadius
                radius: root.cornerRadius
                color: parent.color
            }

            // ── 底部方角遮罩（展开时覆盖底部圆角） ──
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: root.cornerRadius
                color: parent.color
                visible: !root.expanded
                radius: root.cornerRadius
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 16
                spacing: 10

                // ── Canvas 绘制箭头 (不依赖字体) ──
                Item {
                    id: arrowWrapper
                    Layout.preferredWidth: 16
                    Layout.preferredHeight: 16
                    Layout.alignment: Qt.AlignVCenter

                    // 旋转动画: 收起 0° → 展开 90°
                    rotation: root.expanded ? 90 : 0
                    Behavior on rotation {
                        NumberAnimation {
                            duration: root.animationDuration
                            easing.type: Easing.OutCubic
                        }
                    }
                    transformOrigin: Item.Center

                    Canvas {
                        id: arrowCanvas
                        anchors.fill: parent
                        onPaint: {
                            var ctx = getContext("2d");
                            ctx.clearRect(0, 0, width, height);
                            ctx.strokeStyle = root.arrowColor;
                            ctx.lineWidth = 1.6;
                            ctx.lineCap = "round";
                            ctx.lineJoin = "round";
                            ctx.beginPath();
                            // 绘制 > 形右箭头
                            ctx.moveTo(5, 3);
                            ctx.lineTo(11, 8);
                            ctx.lineTo(5, 13);
                            ctx.stroke();
                        }
                    }

                    // 颜色变化时重绘
                    Connections {
                        target: root
                        function onArrowColorChanged() { arrowCanvas.requestPaint(); }
                    }
                }

                // ── 标题文字 ──
                Text {
                    id: titleLabel
                    text: root.title
                    font.pixelSize: root.titleSize
                    font.family: "Microsoft YaHei UI"
                    font.weight: Font.DemiBold
                    color: root.titleColor
                    elide: Text.ElideRight
                    maximumLineCount: 1
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignVCenter
                    renderType: Text.NativeRendering
                }
            }

            // ── 点击事件 ──
            MouseArea {
                id: headerMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.expanded = !root.expanded
            }

            // ── 底部分割线 ──
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 1
                color: Qt.rgba(0, 0, 0, 0.08)
                visible: root.expanded
                opacity: root.expanded ? 1 : 0
                Behavior on opacity {
                    NumberAnimation {
                        duration: root.animationDuration
                        easing.type: Easing.OutCubic
                    }
                }
            }
        }

        // ── 展开内容面板 ──
        Rectangle {
            id: contentPane
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: headerArea.bottom
            height: contentContainer.implicitHeight
                    + root.contentTopMargin
                    + root.contentBottomMargin
            color: root.contentBackgroundColor
            visible: root.expanded || contentOpacityAnim.running

            opacity: root.expanded ? 1 : 0
            Behavior on opacity {
                NumberAnimation {
                    id: contentOpacityAnim
                    duration: root.animationDuration
                    easing.type: Easing.OutCubic
                }
            }

            // 拦截展开区域的空白点击，防止事件穿透到下层控件
            MouseArea {
                anchors.fill: parent
                enabled: root.expanded
                acceptedButtons: Qt.AllButtons
                hoverEnabled: true
                preventStealing: true
                onPressed: function(mouse) { mouse.accepted = true; }
                onReleased: function(mouse) { mouse.accepted = true; }
                onClicked: function(mouse) { mouse.accepted = true; }
                onWheel: function(wheel) { wheel.accepted = true; }
            }

            // ── 顶部内凹阴影 (inset shadow) ──
            Rectangle {
                id: insetShadow1
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: 6
                gradient: Gradient {
                    GradientStop { position: 0.0; color: Qt.rgba(0, 0, 0, 0.08) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }

            // ── 左侧强调线 (Fluent 2 accent bar) ──
            Rectangle {
                id: accentBar
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                anchors.leftMargin: 0
                anchors.topMargin: 4
                anchors.bottomMargin: 4
                width: 3
                radius: 1.5
                color: "#0078D4"   // Fluent 2 主题蓝
                opacity: root.expanded ? 1 : 0
                Behavior on opacity {
                    NumberAnimation {
                        duration: root.animationDuration
                        easing.type: Easing.OutCubic
                    }
                }
            }

            // ── 内容区内边框 ──
            Rectangle {
                anchors.fill: parent
                radius: 0
                color: "transparent"
                border.color: root.contentBorderColor
                border.width: 1
            }

            // ── 内容容器 ──
            Item {
                id: contentContainer
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.leftMargin: root.contentLeftMargin
                anchors.rightMargin: root.contentRightMargin
                anchors.topMargin: root.contentTopMargin
                implicitHeight: childrenRect.height
            }
        }
    }
}
