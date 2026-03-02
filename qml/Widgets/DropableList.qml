import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    id: root
    width: 420
    height: 500

    // ── 公共属性 ──
    property int currentIndex: -1

    // ── 内联 ListModel，填充随机数据 ──
    ListModel {
        id: videoModel
        ListElement {
            fileName: "示例视频_01.mp4"
            filePath: "C:/Users/PythonImporter/Videos/Captures/示例视频_01.mp4"
            iconSource: "qrc:/icons/video"
        }
        ListElement {
            fileName: "旅拍合集_Summer_2025.mp4"
            filePath: "D:/MediaLibrary/Projects/Travel/Summer2025/旅拍合集_Summer_2025.mp4"
            iconSource: "qrc:/icons/video"
        }
        ListElement {
            fileName: "会议录屏_03_15.mkv"
            filePath: "E:/WorkRecordings/2026/March/会议录屏_03_15.mkv"
            iconSource: "qrc:/icons/video"
        }
        ListElement {
            fileName: "产品演示_Final_v2.mp4"
            filePath: "C:/Users/PythonImporter/Desktop/产品发布/产品演示视频/产品演示_Final_v2.mp4"
            iconSource: "qrc:/icons/video"
        }
        ListElement {
            fileName: "无人机航拍_城市夜景.mov"
            filePath: "F:/DroneFootage/CityNight/Export/无人机航拍_城市夜景.mov"
            iconSource: "qrc:/icons/video"
        }
        ListElement {
            fileName: "教程_QML入门.mp4"
            filePath: "D:/Tutorials/QML/Beginner/教程_QML入门.mp4"
            iconSource: "qrc:/icons/video"
        }
        ListElement {
            fileName: "家庭聚会_20260101.mp4"
            filePath: "C:/Users/PythonImporter/Videos/Family/NewYear/家庭聚会_20260101.mp4"
            iconSource: "qrc:/icons/video"
        }
    }

    // ── 路径省略工具函数 ──
    function elideMiddlePath(path, maxLen) {
        if (path.length <= maxLen) return path;
        var headLen = Math.ceil(maxLen * 0.4);
        var tailLen = maxLen - headLen - 3; // 3 for "..."
        if (tailLen < 4) tailLen = 4;
        return path.substring(0, headLen) + "..." + path.substring(path.length - tailLen);
    }

    // ── 拖拽状态管理 ──
    QtObject {
        id: dragState
        property int draggedIndex: -1       // 当前被拖拽的项原始索引
        property bool isDragging: false
        property real dragMouseY: 0         // 鼠标在列表坐标系中的 Y
        property int dropTargetIndex: -1    // 放下目标位置
        property real dragMouseRootX: 0     // 鼠标在根坐标系中的 X
        property real dragMouseRootY: 0     // 鼠标在根坐标系中的 Y
        property string draggedFileName: "" // 被拖拽项的文件名
    }

    Rectangle {
        anchors.fill: parent
        color: "#f3f3f3"
        radius: 8

        ListView {
            id: listView
            anchors.fill: parent
            anchors.margins: 4
            model: videoModel
            clip: true
            spacing: 2
            boundsBehavior: Flickable.StopAtBounds

            // ── 全局位移动画 ──
            displaced: Transition {
                NumberAnimation { properties: "x,y"; duration: 300; easing.type: Easing.OutCubic }
            }

            // ── 内联 delegate 组件 ──
            delegate: Item {
                id: delegateRoot
                width: listView.width
                height: 62

                // 当前项的模型索引
                required property int index
                required property string fileName
                required property string filePath
                required property string iconSource

                property bool isSelected: root.currentIndex === index
                property bool isBeingDragged: dragState.draggedIndex === index && dragState.isDragging

                // ── 拖拽时的占位偏移：如果有东西正在被拖到此位置附近，则上下挤开 ──
                property real displaceOffset: {
                    if (!dragState.isDragging) return 0;
                    if (isBeingDragged) return 0;
                    if (dragState.dropTargetIndex < 0) return 0;

                    // 在拖拽目标位置之后的项往下移动
                    if (dragState.draggedIndex < index) {
                        // 原始位置在上面，拖到下面
                        if (index > dragState.dropTargetIndex) return 0;
                        if (index <= dragState.dropTargetIndex && index > dragState.draggedIndex) return -62;
                    } else if (dragState.draggedIndex > index) {
                        // 原始位置在下面，拖到上面
                        if (index < dragState.dropTargetIndex) return 0;
                        if (index >= dragState.dropTargetIndex && index < dragState.draggedIndex) return 62;
                    }
                    return 0;
                }

                // 位移动画
                transform: Translate {
                    id: itemTranslate
                    y: delegateRoot.isBeingDragged ? 0 : delegateRoot.displaceOffset
                    Behavior on y {
                        NumberAnimation { duration: 280; easing.type: Easing.OutCubic }
                    }
                }

                // ── 可见的卡片内容 ──
                Rectangle {
                    id: cardBackground
                    anchors.fill: parent
                    anchors.leftMargin: 4
                    anchors.rightMargin: 4
                    anchors.topMargin: 1
                    anchors.bottomMargin: 1
                    radius: 6
                    color: delegateRoot.isBeingDragged ? "#f5f5f5" : (delegateRoot.isSelected ? "#f0f6ff" : (itemMouse.containsMouse ? "#f8f8f8" : "#ffffff"))
                    border.color: delegateRoot.isBeingDragged ? "#e0e0e0" : "transparent"
                    border.width: delegateRoot.isBeingDragged ? 1 : 0

                    // 拖起时原位置变为占位符
                    opacity: delegateRoot.isBeingDragged ? 0.35 : 1.0

                    Behavior on opacity {
                        NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
                    }
                    Behavior on color {
                        ColorAnimation { duration: 160 }
                    }

                    // 拖拽时的阴影层
                    layer.enabled: delegateRoot.isBeingDragged
                    layer.effect: Item {}  // 占位，实际阴影用 Rectangle 模拟

                    // ── 选中态：左侧蓝色指示线 ──
                    Rectangle {
                        id: selectionIndicator
                        width: 3
                        height: delegateRoot.isSelected ? 18 : 0
                        radius: 1.5
                        color: "#0078D4"
                        anchors.left: parent.left
                        anchors.leftMargin: 0
                        anchors.verticalCenter: parent.verticalCenter

                        Behavior on height {
                            NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
                        }
                    }

                    // ── 选中态：淡蓝色遮罩 ──
                    Rectangle {
                        anchors.fill: parent
                        radius: parent.radius
                        color: "#0078D4"
                        opacity: delegateRoot.isSelected ? 0.06 : 0
                        Behavior on opacity {
                            NumberAnimation { duration: 160 }
                        }
                    }

                    // ── 内容布局 ──
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 14
                        anchors.rightMargin: 14
                        spacing: 12

                        // ── 视频图标 ──
                        Rectangle {
                            Layout.preferredWidth: 36
                            Layout.preferredHeight: 36
                            radius: 6
                            color: delegateRoot.isSelected ? "#e3effc" : "#f0f0f0"
                            Behavior on color {
                                ColorAnimation { duration: 160 }
                            }

                            // 使用 Canvas 绘制一个视频播放器图标
                            Canvas {
                                anchors.centerIn: parent
                                width: 20
                                height: 20
                                onPaint: {
                                    var ctx = getContext("2d");
                                    ctx.clearRect(0, 0, width, height);

                                    // 显示器外框
                                    ctx.strokeStyle = delegateRoot.isSelected ? "#0078D4" : "#606060";
                                    ctx.lineWidth = 1.5;
                                    ctx.beginPath();
                                    ctx.roundedRect(1, 1, 18, 13, 2, 2);
                                    ctx.stroke();

                                    // 底座
                                    ctx.beginPath();
                                    ctx.moveTo(7, 14);
                                    ctx.lineTo(7, 17);
                                    ctx.lineTo(13, 17);
                                    ctx.lineTo(13, 14);
                                    ctx.stroke();

                                    // 底座横线
                                    ctx.beginPath();
                                    ctx.moveTo(5, 17);
                                    ctx.lineTo(15, 17);
                                    ctx.stroke();

                                    // 播放三角形
                                    ctx.fillStyle = delegateRoot.isSelected ? "#0078D4" : "#606060";
                                    ctx.beginPath();
                                    ctx.moveTo(7.5, 4.5);
                                    ctx.lineTo(7.5, 11);
                                    ctx.lineTo(13, 7.75);
                                    ctx.closePath();
                                    ctx.fill();
                                }

                                // 选中时重绘图标颜色
                                Connections {
                                    target: delegateRoot
                                    function onIsSelectedChanged() {
                                        parent.requestPaint && parent.requestPaint();
                                    }
                                }
                            }

                            // 选中状态变化时重绘 Canvas
                            onColorChanged: {
                                for (var i = 0; i < children.length; i++) {
                                    if (children[i] instanceof Canvas) {
                                        children[i].requestPaint();
                                    }
                                }
                            }
                        }

                        // ── 文字信息 ──
                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            spacing: 2

                            Item { Layout.fillHeight: true }  // 上方弹簧

                            // 视频名称
                            Text {
                                Layout.fillWidth: true
                                text: delegateRoot.fileName
                                font.pixelSize: 13
                                font.weight: Font.Medium
                                font.family: "Microsoft YaHei UI"
                                color: "#1a1a1a"
                                elide: Text.ElideRight
                                maximumLineCount: 1
                            }

                            // 视频路径（中间省略）
                            Text {
                                Layout.fillWidth: true
                                text: root.elideMiddlePath(delegateRoot.filePath, 45)
                                font.pixelSize: 11
                                font.family: "Microsoft YaHei UI"
                                color: "#888888"
                                elide: Text.ElideRight
                                maximumLineCount: 1
                            }

                            Item { Layout.fillHeight: true }  // 下方弹簧
                        }
                    }

                    // ── 鼠标交互区域 ──
                    MouseArea {
                        id: itemMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        pressAndHoldInterval: 150
                        cursorShape: dragState.isDragging ? Qt.ClosedHandCursor : (containsMouse ? Qt.OpenHandCursor : Qt.ArrowCursor)

                        property real pressStartY: 0
                        property bool dragActive: false

                        onClicked: {
                            root.currentIndex = delegateRoot.index;
                        }

                        onPressed: function(mouse) {
                            pressStartY = mouse.y;
                            dragActive = false;
                            root.currentIndex = delegateRoot.index;
                        }

                        onPressAndHold: function(mouse) {
                            // 开始拖拽
                            dragActive = true;
                            dragState.draggedIndex = delegateRoot.index;
                            dragState.isDragging = true;
                            dragState.dropTargetIndex = delegateRoot.index;
                            dragState.draggedFileName = delegateRoot.fileName;

                            // 记录鼠标在根坐标系中的位置
                            var posInRoot = mapToItem(root, mouse.x, mouse.y);
                            dragState.dragMouseRootX = posInRoot.x;
                            dragState.dragMouseRootY = posInRoot.y;
                        }

                        onPositionChanged: function(mouse) {
                            if (!dragActive || !dragState.isDragging) return;

                            // 计算鼠标在 ListView 中的 Y 坐标
                            var posInList = mapToItem(listView.contentItem, mouse.x, mouse.y);
                            dragState.dragMouseY = posInList.y;

                            // 记录鼠标在根坐标系中的位置
                            var posInRoot = mapToItem(root, mouse.x, mouse.y);
                            dragState.dragMouseRootX = posInRoot.x;
                            dragState.dragMouseRootY = posInRoot.y;

                            // 根据鼠标位置计算目标放置索引
                            var targetIdx = Math.floor(posInList.y / 64); // 62 height + 2 spacing
                            targetIdx = Math.max(0, Math.min(targetIdx, videoModel.count - 1));
                            dragState.dropTargetIndex = targetIdx;
                        }

                        onReleased: function(mouse) {
                            if (dragActive && dragState.isDragging) {
                                // 执行实际的 model 移动
                                var fromIdx = dragState.draggedIndex;
                                var toIdx = dragState.dropTargetIndex;

                                if (fromIdx !== toIdx && toIdx >= 0 && toIdx < videoModel.count) {
                                    videoModel.move(fromIdx, toIdx, 1);
                                    // 更新选中索引
                                    root.currentIndex = toIdx;
                                }
                            }

                            // 重置拖拽状态
                            dragActive = false;
                            dragState.isDragging = false;
                            dragState.draggedIndex = -1;
                            dragState.dropTargetIndex = -1;
                        }
                    }
                }

                // ── 拖拽时的浮动阴影效果（通过额外 Rectangle 模拟） ──
                Rectangle {
                    visible: delegateRoot.isBeingDragged
                    anchors.fill: cardBackground
                    anchors.margins: -2
                    radius: 8
                    color: "transparent"
                    border.color: "#20000000"
                    border.width: 2
                    z: -1
                }
            }
        }

        // ── 拖放位置指示线 ──
        Rectangle {
            id: dropIndicator
            visible: dragState.isDragging && dragState.dropTargetIndex >= 0
                     && dragState.dropTargetIndex !== dragState.draggedIndex
            width: listView.width - 16
            height: 2
            radius: 1
            color: "#0078D4"
            x: 12
            z: 100

            y: {
                if (!dragState.isDragging || dragState.dropTargetIndex < 0
                    || dragState.dropTargetIndex === dragState.draggedIndex)
                    return -100;
                var screenY = 4 + dragState.dropTargetIndex * 64 - listView.contentY;
                if (screenY < 2 || screenY > listView.height + 6)
                    return -100;
                return screenY;
            }

            Behavior on y {
                NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
            }

            // 左侧圆点
            Rectangle {
                width: 8; height: 8; radius: 4
                color: "#0078D4"
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.leftMargin: -3
            }

            // 右侧圆点
            Rectangle {
                width: 8; height: 8; radius: 4
                color: "#0078D4"
                anchors.verticalCenter: parent.verticalCenter
                anchors.right: parent.right
                anchors.rightMargin: -3
            }
        }
    }

    // ── 拖拽时的浮动副本（跟随鼠标） ──
    Rectangle {
        id: dragGhost
        visible: dragState.isDragging
        width: root.width * 0.65
        height: 48
        x: dragState.dragMouseRootX - width / 2
        y: dragState.dragMouseRootY - height - 12
        z: 1000
        radius: 8
        color: "#ffffff"
        opacity: 0.88
        border.color: "#0078D4"
        border.width: 1.5

        // 外层阴影
        Rectangle {
            anchors.fill: parent
            anchors.margins: -2
            radius: parent.radius + 2
            color: "transparent"
            border.color: "#180078D4"
            border.width: 3
            z: -1
        }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 10
            anchors.rightMargin: 10
            spacing: 8

            // 视频图标
            Rectangle {
                Layout.preferredWidth: 28
                Layout.preferredHeight: 28
                radius: 5
                color: "#e3effc"

                Canvas {
                    anchors.centerIn: parent
                    width: 16; height: 16
                    onPaint: {
                        var ctx = getContext("2d");
                        ctx.clearRect(0, 0, width, height);
                        ctx.strokeStyle = "#0078D4";
                        ctx.lineWidth = 1.2;
                        ctx.beginPath();
                        ctx.roundedRect(0.5, 0.5, 15, 10.5, 1.5, 1.5);
                        ctx.stroke();
                        ctx.beginPath();
                        ctx.moveTo(5.5, 11); ctx.lineTo(5.5, 14);
                        ctx.lineTo(10.5, 14); ctx.lineTo(10.5, 11);
                        ctx.stroke();
                        ctx.beginPath();
                        ctx.moveTo(4, 14); ctx.lineTo(12, 14);
                        ctx.stroke();
                        ctx.fillStyle = "#0078D4";
                        ctx.beginPath();
                        ctx.moveTo(6, 3.5); ctx.lineTo(6, 8.5);
                        ctx.lineTo(10.5, 6); ctx.closePath();
                        ctx.fill();
                    }
                }
            }

            // 文件名
            Text {
                Layout.fillWidth: true
                text: dragState.draggedFileName
                font.pixelSize: 12
                font.weight: Font.Medium
                font.family: "Microsoft YaHei UI"
                color: "#1a1a1a"
                elide: Text.ElideRight
                maximumLineCount: 1
            }
        }
    }
}
