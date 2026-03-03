import QtQuick
import QtQuick.Controls.FluentWinUI3
import QtQuick.Layouts
import "../"
import "../Widgets"
import "../Components"

Item {
    id: root

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
                anchors.fill: parent
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
                        }

                        // ── 预览去黑边效果 ──
                        Button {
                            text: "预览去黑边的效果"
                            Layout.fillWidth: true
                            icon.source: ImagePath.crop
                        }

                        // ── 旋转按钮行 ──
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Button {
                                text: "顺时针旋转90°"
                                Layout.fillWidth: true
                                icon.source: ImagePath.clockwise
                            }

                            Button {
                                text: "逆时针旋转90°"
                                Layout.fillWidth: true
                                icon.source: ImagePath.counterClockwise
                            }
                        }

                        // ── 视频信息 ──
                        VideoInfo {
                            id: videoInfoItem
                            Layout.fillWidth: true
                            Layout.preferredHeight: implicitHeight
                            fileName: "示例视频_01.mp4"
                            filePath: "C:/Users/Videos/示例视频_01.mp4"
                            durationAndResolution: "00:15:30 / 1920x1080"
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
                                text: "横屏"
                                checked: true
                                ButtonGroup.group: orientationGroup
                            }

                            RadioButton {
                                text: "竖屏"
                                ButtonGroup.group: orientationGroup
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
                                            Layout.fillWidth: true
                                            model: ["速度", "普通", "质量"]
                                            currentIndex: 1
                                        }
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 4

                                        Text {
                                            text: "不合规默认旋转角度"
                                            font.pixelSize: 12
                                            font.family: "Microsoft YaHei UI"
                                            color: "#5c6670"
                                            renderType: Text.NativeRendering
                                        }

                                        ComboBox {
                                            Layout.fillWidth: true
                                            model: ["0°", "90°", "180°", "270°"]
                                            currentIndex: 1
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
                                        Layout.alignment: Qt.AlignVCenter
                                    }
                                }
                            }
                        }

                        // ── 开始处理按钮 ──
                        Button {
                            id: startButton
                            text: "开始处理"
                            highlighted: true
                            icon.source: ImagePath.play
                            Layout.fillWidth: true
                            implicitHeight: 44
                        }
                    }
                }
            }
        }
    }
}
