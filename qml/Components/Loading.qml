import QtQuick
import QtQuick.Controls.FluentWinUI3

Item {
    id: root

    // ── 公共属性 ──
    property string text: "请稍候…"          // 自定义文字
    property bool running: false              // 控制显示/隐藏
    property color textColor: "#ffffff"       // 文字颜色
    property color indicatorColor: "#ffffff"  // BusyIndicator 颜色（可用透明度）
    property int textSize: 14                 // 文字大小
    property color maskColor: "#99000000"     // 遮罩颜色
    property bool crop: false                 // 是否裁剪到父元素边界
    property int minIndicatorSize: 36         // 指示器最小尺寸
    property int maxIndicatorSize: 132        // 指示器最大尺寸
    property int minTextSize: 12              // 文字最小尺寸
    property int maxTextSize: 32              // 文字最大尺寸
    property int minSpacing: 12               // 内容最小间距
    property int maxSpacing: 40               // 内容最大间距

    // ── 自适应尺寸 ──
    readonly property real shortSide: Math.min(width, height)
    readonly property real adaptiveScale: Math.max(0.9, Math.min(2.2, shortSide / 300.0))
    readonly property int adaptiveIndicatorSize: Math.round(Math.max(minIndicatorSize, Math.min(maxIndicatorSize, 64 * adaptiveScale)))
    readonly property int adaptiveTextSize: Math.round(Math.max(minTextSize, Math.min(maxTextSize, (textSize + 2) * adaptiveScale)))
    readonly property int adaptiveSpacing: Math.round(Math.max(minSpacing, Math.min(maxSpacing, 24 * adaptiveScale)))
    readonly property real minTenCjkWidth: textMetrics.advanceWidth("汉汉汉汉汉汉汉汉汉汉") + 6

    // 填满父元素
    anchors.fill: parent
    clip: crop
    z: 9999

    // ── 可见性控制 ──
    visible: fadeAnim.running || running

    // ── 遮罩层 ──
    Rectangle {
        id: mask
        anchors.fill: parent
        color: root.maskColor
        opacity: 0

        Behavior on opacity {
            NumberAnimation {
                id: fadeAnim
                duration: 350
                easing.type: Easing.InOutCubic
            }
        }

        // 阻止穿透点击
        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            preventStealing: true
            onClicked: function(mouse) { mouse.accepted = true; }
            onPressed: function(mouse) { mouse.accepted = true; }
            onReleased: function(mouse) { mouse.accepted = true; }
            onWheel: function(wheel) { wheel.accepted = true; }
        }
    }

    // ── 中央内容区域 ──
    Column {
        id: centerContent
        anchors.centerIn: parent
        spacing: root.adaptiveSpacing
        opacity: 0

        Behavior on opacity {
            NumberAnimation {
                duration: 350
                easing.type: Easing.InOutCubic
            }
        }

        // ── 官方 BusyIndicator ──
        BusyIndicator {
            id: busyIndicator
            running: root.running
            anchors.horizontalCenter: parent.horizontalCenter
            width: root.adaptiveIndicatorSize
            height: root.adaptiveIndicatorSize

            // Fluent 样式下不同角色可能参与着色，统一覆盖为自定义颜色
            palette.accent: root.indicatorColor
            palette.highlight: root.indicatorColor
            palette.dark: root.indicatorColor
        }

        // ── 提示文字 ──
        FontMetrics {
            id: textMetrics
            font.family: loadingText.font.family
            font.pixelSize: loadingText.font.pixelSize
            font.weight: loadingText.font.weight
        }

        Text {
            id: loadingText
            text: root.text
            color: root.textColor
            width: Math.max(root.minTenCjkWidth, implicitWidth)
            font.pixelSize: root.adaptiveTextSize
            font.family: "Microsoft YaHei UI"
            font.weight: Font.Normal
            wrapMode: Text.NoWrap
            maximumLineCount: 1
            horizontalAlignment: Text.AlignHCenter
            anchors.horizontalCenter: parent.horizontalCenter
            visible: root.text.length > 0
        }
    }

    // ── running 状态切换 ──
    onRunningChanged: {
        if (running) {
            mask.opacity = 1;
            centerContent.opacity = 1;
        } else {
            mask.opacity = 0;
            centerContent.opacity = 0;
        }
    }
}
