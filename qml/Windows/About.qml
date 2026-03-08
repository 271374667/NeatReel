import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "../"

Window {
    id: root
    width: 760
    height: 740
    minimumWidth: 620
    minimumHeight: 680
    visible: false
    title: "关于 - 净影连"
    color: "#f5f7fa"
    modality: Qt.WindowModal

    function openWindow() {
        if (transientParent) {
            x = transientParent.x + Math.round((transientParent.width - width) / 2)
            y = transientParent.y + Math.max(24, Math.round((transientParent.height - height) / 2))
        }
        show()
        raise()
        requestActivate()
    }

    component LinkIconButton: Rectangle {
        id: iconButton
        property string iconSource: ""
        property string targetUrl: ""
        property bool hovered: false

        width: 44
        height: 44
        radius: 12
        color: hovered ? "#eef4fb" : "#ffffff"
        border.width: 1
        border.color: hovered ? "#bfd6f6" : "#dbe3ec"

        Image {
            anchors.centerIn: parent
            source: iconButton.iconSource
            sourceSize.width: 22
            sourceSize.height: 22
            fillMode: Image.PreserveAspectFit
        }

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onEntered: iconButton.hovered = true
            onExited: iconButton.hovered = false
            onClicked: {
                if (iconButton.targetUrl.length > 0)
                    Qt.openUrlExternally(iconButton.targetUrl)
            }
        }
    }

    component ActionCard: Rectangle {
        id: card
        property string iconSource: ""
        property string titleText: ""
        property string descriptionText: ""
        property bool busy: false
        property bool hovered: false
        signal clicked()

        width: parent ? parent.width : 0
        implicitHeight: descriptionText.length > 0 ? 78 : 62
        radius: 16
        color: hovered ? "#f8fbff" : "#ffffff"
        border.width: 1
        border.color: hovered ? "#c8d8ea" : "#dde5ee"

        Behavior on color {
            ColorAnimation { duration: 140 }
        }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 18
            anchors.rightMargin: 18
            spacing: 14

            Rectangle {
                Layout.preferredWidth: 38
                Layout.preferredHeight: 38
                radius: 12
                color: "#f3f6fa"
                border.width: 1
                border.color: "#e4ebf2"

                Image {
                    id: actionIcon
                    anchors.centerIn: parent
                    source: card.iconSource
                    sourceSize.width: 20
                    sourceSize.height: 20
                    fillMode: Image.PreserveAspectFit

                    RotationAnimation on rotation {
                        running: card.busy
                        loops: Animation.Infinite
                        from: 0
                        to: 360
                        duration: 900
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

                Text {
                    text: card.titleText
                    font.pixelSize: 18
                    font.family: "Microsoft YaHei UI"
                    font.weight: Font.DemiBold
                    color: "#111827"
                    renderType: Text.NativeRendering
                }

                Text {
                    visible: card.descriptionText.length > 0
                    text: card.descriptionText
                    font.pixelSize: 12
                    font.family: "Microsoft YaHei UI"
                    color: "#667085"
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                    renderType: Text.NativeRendering
                }
            }

            Text {
                text: "›"
                font.pixelSize: 24
                font.family: "Segoe UI Symbol"
                color: "#7c8795"
                Layout.alignment: Qt.AlignVCenter
                renderType: Text.NativeRendering
            }
        }

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onEntered: card.hovered = true
            onExited: card.hovered = false
            onClicked: card.clicked()
        }
    }

    Flickable {
        id: flickable
        anchors.fill: parent
        anchors.margins: 14
        clip: true
        contentWidth: width
        contentHeight: contentColumn.height + 24

        ScrollBar.vertical: ScrollBar {
            policy: ScrollBar.AsNeeded
        }

        Column {
            id: contentColumn
            width: flickable.width - 12
            x: 6
            y: 6
            spacing: 16

            Rectangle {
                id: heroCard
                width: parent.width
                implicitHeight: heroContent.implicitHeight + 62
                radius: 24
                color: "#ffffff"
                border.width: 1
                border.color: "#dde5ee"
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#fbfdff" }
                    GradientStop { position: 1.0; color: "#f7f9fc" }
                }

                Column {
                    id: heroContent
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.leftMargin: 28
                    anchors.rightMargin: 28
                    anchors.topMargin: 34
                    width: heroCard.width - 56
                    spacing: 12

                    Rectangle {
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: 112
                        height: 112
                        radius: 28
                        color: "#eef5ff"
                        border.width: 1
                        border.color: "#d9e7fb"

                        Image {
                            anchors.centerIn: parent
                            source: ImagePath.logo
                            sourceSize.width: 72
                            sourceSize.height: 72
                            fillMode: Image.PreserveAspectFit
                        }
                    }

                    Text {
                        width: parent.width
                        text: "净影连 NeatReel"
                        font.pixelSize: 36
                        font.family: "Microsoft YaHei UI"
                        font.weight: Font.Bold
                        color: "#101828"
                        horizontalAlignment: Text.AlignHCenter
                        renderType: Text.NativeRendering
                    }

                    Text {
                        text: "版本 " + aboutService.version
                        width: parent.width
                        font.pixelSize: 18
                        font.family: "Microsoft YaHei UI"
                        color: "#344054"
                        horizontalAlignment: Text.AlignHCenter
                        renderType: Text.NativeRendering
                    }

                    Text {
                        width: parent.width
                        text: "去黑边，正朝向，一键拼出好影像"
                        font.pixelSize: 17
                        font.family: "Microsoft YaHei UI"
                        color: "#475467"
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        renderType: Text.NativeRendering
                    }
                }
            }

            Rectangle {
                id: contactCard
                width: parent.width
                implicitHeight: contactContent.implicitHeight + 36
                radius: 18
                color: "#ffffff"
                border.width: 1
                border.color: "#dde5ee"

                Column {
                    id: contactContent
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.leftMargin: 20
                    anchors.rightMargin: 20
                    anchors.topMargin: 18
                    width: contactCard.width - 40
                    spacing: 12

                    Text {
                        text: "开发者：PythonImporter"
                        font.pixelSize: 18
                        font.family: "Microsoft YaHei UI"
                        font.weight: Font.DemiBold
                        color: "#111827"
                        renderType: Text.NativeRendering
                    }

                    RowLayout {
                        width: parent.width
                        spacing: 12

                        Text {
                            text: "联系作者"
                            font.pixelSize: 15
                            font.family: "Microsoft YaHei UI"
                            color: "#475467"
                            renderType: Text.NativeRendering
                        }

                        LinkIconButton {
                            iconSource: ImagePath.bilibili
                            targetUrl: "https://space.bilibili.com/282527875"
                        }

                        LinkIconButton {
                            iconSource: ImagePath.github
                            targetUrl: "https://github.com/271374667"
                        }

                        Item { Layout.fillWidth: true }

                    }
                }
            }

            ActionCard {
                width: parent.width
                iconSource: ImagePath.question
                titleText: "帮助"
                descriptionText: "提交问题或查看已知问题"
                onClicked: Qt.openUrlExternally("https://github.com/271374667/NeatReel/issues")
            }

            ActionCard {
                width: parent.width
                iconSource: ImagePath.refresh
                titleText: "检查更新"
                descriptionText: aboutService.isCheckingForUpdates
                                 ? "正在从 GitHub 获取最新发布信息..."
                                 : (aboutService.updateStatusText.length > 0
                                    ? aboutService.updateStatusText
                                    : "检查 GitHub 发布，获取最新版本信息")
                busy: aboutService.isCheckingForUpdates
                onClicked: aboutService.checkForUpdates()
            }

            Text {
                width: parent.width
                text: "\u00A9 " + new Date().getFullYear() + " PythonImporter · 当前许可：" + aboutService.licenseText
                font.pixelSize: 13
                font.family: "Microsoft YaHei UI"
                color: "#667085"
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                renderType: Text.NativeRendering
            }
        }
    }
}
