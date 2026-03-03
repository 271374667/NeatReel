import QtQuick
import QtQuick.Controls.FluentWinUI3
import QtQuick.Layouts

Item {
    id: root

    // ── 公共属性 ──
    property string title: ""                     // 面板标题
    property string icon: ""                      // 面板图标（仅支持图片路径）
    property bool showHeader: true                // 是否显示顶部标题栏
    property real cornerRadius: 8                 // 圆角半径
    property real shadowRadius: 16                // 阴影模糊半径
    property color backgroundColor: "#ffffff"     // 面板背景色
    property color borderColor: "#e8e8e8"         // 边框颜色
    property color titleColor: "#1a1a1a"          // 标题文字颜色
    property color iconColor: "#0078D4"           // 图标颜色
    property color shadowColor: "#18000000"       // 阴影颜色
    property int headerHeight: 44                 // 标题栏高度
    property int titleSize: 13                    // 标题文字大小
    property int iconSize: 16                     // 图标文字大小
    property int contentTopMargin: 12             // 内容区域上方留白
    property int contentLeftMargin: 16            // 内容区域左侧留白
    property int contentRightMargin: 16           // 内容区域右侧留白
    property int contentBottomMargin: 16          // 内容区域底部留白

    // ── 内容区 (default property) ──
    default property alias contentData: contentContainer.data

    // ── 计算: header实际高度 ──
    readonly property int _effectiveHeaderHeight: showHeader && (title.length > 0 || icon.length > 0) ? headerHeight : 0
    readonly property bool _hasValidIconPath: {
        if (!icon || icon.length === 0) return false
        return icon.indexOf("/") !== -1
            || icon.indexOf("\\") !== -1
            || icon.indexOf("qrc:") === 0
            || icon.indexOf("file:") === 0
            || icon.indexOf("http:") === 0
            || icon.indexOf("https:") === 0
            || icon.indexOf("data:") === 0
            || icon.indexOf(":/") === 0
    }

    // ── 外层阴影（通过偏移模糊的 Rectangle 模拟） ──
    Rectangle {
        id: shadowLayer
        anchors.fill: cardBody
        anchors.margins: -1
        radius: root.cornerRadius + 1
        color: "transparent"
        border.color: root.shadowColor
        border.width: 1
        visible: true

        // 外层投影（利用多层叠加实现柔和阴影）
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

    // ── 主卡片本体 ──
    Rectangle {
        id: cardBody
        anchors.fill: parent
        anchors.margins: 8           // 为阴影留出空间
        radius: root.cornerRadius
        color: root.backgroundColor
        border.color: root.borderColor
        border.width: 1
        clip: true

        // ── 顶部高光线（Fluent2 微妙的顶部 1px 亮边） ──
        Rectangle {
            width: parent.width - 2 * root.cornerRadius
            height: 1
            anchors.top: parent.top
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.topMargin: 0
            color: Qt.rgba(1, 1, 1, 0.65)
            visible: root.showHeader
        }

        // ── 标题栏区域 ──
        Item {
            id: headerArea
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: root._effectiveHeaderHeight
            visible: root._effectiveHeaderHeight > 0

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 16
                spacing: 8

                // ── 图标 ──
                Image {
                    id: iconImage
                    visible: root._hasValidIconPath
                    source: root.icon
                    sourceSize.width: root.iconSize
                    sourceSize.height: root.iconSize
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                    asynchronous: true
                    Layout.preferredWidth: root.iconSize
                    Layout.preferredHeight: root.iconSize
                    Layout.alignment: Qt.AlignVCenter
                }

                // ── 标题文字 ──
                Text {
                    id: titleLabel
                    visible: root.title.length > 0
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

                // 右侧弹簧
                Item { Layout.fillWidth: !titleLabel.visible }
            }

            // ── 标题栏底部分割线 ──
            Rectangle {
                id: headerDivider
                width: parent.width
                height: 1
                anchors.bottom: parent.bottom
                color: Qt.rgba(0, 0, 0, 0.06)
            }
        }

        // ── 内容容器 ──
        Item {
            id: contentContainer
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.top: headerArea.visible ? headerArea.bottom : parent.top
            anchors.leftMargin: root.contentLeftMargin
            anchors.rightMargin: root.contentRightMargin
            anchors.topMargin: root.contentTopMargin
            anchors.bottomMargin: root.contentBottomMargin
        }
    }
}
