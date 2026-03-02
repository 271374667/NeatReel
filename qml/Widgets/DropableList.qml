import QtQuick
import QtQuick.Controls.FluentWinUI3
import QtQuick.Layouts
import QtQuick.Dialogs

Item {
    id: root
    width: 420
    height: 500

    // ── 公共属性 ──
    property int currentIndex: -1
    property var selectedIndices: ({})
    property int selectionVersion: 0
    property int anchorIndex: -1

    // ── 多选辅助函数 ──
    function isIndexSelected(idx) {
        void selectionVersion;
        return selectedIndices.hasOwnProperty(idx.toString());
    }
    function getSelectedCount() {
        void selectionVersion;
        return Object.keys(selectedIndices).length;
    }
    function selectOnly(idx) {
        selectedIndices = {};
        if (idx >= 0) selectedIndices[idx.toString()] = true;
        currentIndex = idx;
        anchorIndex = idx;
        selectionVersion++;
    }
    function toggleSelect(idx) {
        var s = selectedIndices;
        var key = idx.toString();
        if (s.hasOwnProperty(key)) delete s[key]; else s[key] = true;
        selectedIndices = s;
        currentIndex = idx;
        anchorIndex = idx;
        selectionVersion++;
    }
    function rangeSelect(idx) {
        var a = anchorIndex >= 0 ? anchorIndex : 0;
        var start = Math.min(a, idx);
        var end = Math.max(a, idx);
        var s = {};
        for (var i = start; i <= end; i++) s[i.toString()] = true;
        selectedIndices = s;
        currentIndex = idx;
        selectionVersion++;
    }
    function selectAll() {
        var s = {};
        for (var i = 0; i < videoModel.count; i++) s[i.toString()] = true;
        selectedIndices = s;
        selectionVersion++;
    }
    function clearSelection() {
        selectedIndices = {};
        currentIndex = -1;
        anchorIndex = -1;
        selectionVersion++;
    }
    function removeSelectedItems() {
        var indices = Object.keys(selectedIndices).map(function(k) { return parseInt(k); });
        indices.sort(function(a, b) { return b - a; });
        for (var i = 0; i < indices.length; i++) videoModel.remove(indices[i], 1);
        clearSelection();
    }
    property bool externalDragHover: false
    property var supportedVideoExts: [
        ".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv", ".m4v",
        ".mpg", ".mpeg", ".3gp", ".3g2", ".f4v", ".rm", ".rmvb", ".asf"
    ]

    // ── 内联 ListModel，填充随机数据 ──
    ListModel {
        id: videoModel
        ListElement {
            fileName: "示例视频_01.mp4"
            filePath: "C:/Users/PythonImporter/Videos/Captures/示例视频 _01.mp4"
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

    // ── 智能排序 ──
    function smartSort(ascending) {
        var count = videoModel.count;
        if (count <= 1) return;

        // 提取所有项目
        var items = [];
        for (var i = 0; i < count; i++) {
            var it = videoModel.get(i);
            items.push({ fileName: it.fileName, filePath: it.filePath, iconSource: it.iconSource });
        }

        var names = items.map(function(x) { return x.fileName; });

        // Windows 重命名模式: e.g. "文件 (1).mp4", "文件 (20).mp4"
        var winRenameRe = /\((\d+)\)/;
        // 日期模式: e.g. "20260101", "2026-01-01", "2026_01_01"
        var dateRe = /(\d{4})[-_.]?(\d{1,2})[-_.]?(\d{1,2})/;

        var compareFn;

        if (names.every(function(n) { return /^\d+$/.test(n); })) {
            // 全部为纯数字
            compareFn = function(a, b) { return parseInt(a.fileName) - parseInt(b.fileName); };
        } else if (names.every(function(n) { return winRenameRe.test(n); })) {
            // 全部符合 Windows 重命名规则
            compareFn = function(a, b) {
                return parseInt(a.fileName.match(winRenameRe)[1]) - parseInt(b.fileName.match(winRenameRe)[1]);
            };
        } else if (names.every(function(n) { return dateRe.test(n); })) {
            // 全部包含日期
            compareFn = function(a, b) {
                var mA = a.fileName.match(dateRe);
                var mB = b.fileName.match(dateRe);
                var valA = parseInt(mA[1]) * 10000 + parseInt(mA[2]) * 100 + parseInt(mA[3]);
                var valB = parseInt(mB[1]) * 10000 + parseInt(mB[2]) * 100 + parseInt(mB[3]);
                return valA - valB;
            };
        } else {
            // 默认按字符串排序
            compareFn = function(a, b) { return a.fileName.localeCompare(b.fileName); };
        }

        items.sort(compareFn);
        if (!ascending) items.reverse();

        // 重建 model
        videoModel.clear();
        for (var j = 0; j < items.length; j++) {
            videoModel.append(items[j]);
        }
        root.clearSelection();
    }

    // ── 置顶 ──
    function moveItemToTop(idx) {
        if (idx > 0 && idx < videoModel.count) {
            videoModel.move(idx, 0, 1);
            root.selectOnly(0);
        }
    }

    // ── 置底 ──
    function moveItemToBottom(idx) {
        if (idx >= 0 && idx < videoModel.count - 1) {
            videoModel.move(idx, videoModel.count - 1, 1);
            root.selectOnly(videoModel.count - 1);
        }
    }

    // ── 删除 ──
    function removeItem(idx) {
        if (idx >= 0 && idx < videoModel.count) {
            videoModel.remove(idx, 1);
            clearSelection();
        }
    }

    // ── 视频文件过滤 ──
    function isVideoFile(filePath) {
        var lowerPath = filePath.toString().toLowerCase();
        for (var i = 0; i < supportedVideoExts.length; i++) {
            if (lowerPath.endsWith(supportedVideoExts[i])) return true;
        }
        return false;
    }

    // ── 添加视频文件到列表末尾 ──
    function addVideoFiles(urls) {
        for (var i = 0; i < urls.length; i++) {
            var urlStr = urls[i].toString();
            if (!isVideoFile(urlStr)) continue;
            var path = urlStr;
            if (path.startsWith("file:///")) path = path.substring(8);
            path = decodeURIComponent(path);
            var parts = path.replace(/\\/g, "/").split("/");
            var fName = parts[parts.length - 1];
            videoModel.append({
                fileName: fName,
                filePath: path,
                iconSource: "qrc:/icons/video"
            });
        }
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
        id: mainContainer
        anchors.fill: parent
        color: "#f3f3f3"
        radius: 8
        focus: true

        Keys.onPressed: function(event) {
            if (event.key === Qt.Key_A && (event.modifiers & Qt.ControlModifier)) {
                root.selectAll();
                event.accepted = true;
            } else if (event.key === Qt.Key_Delete || event.key === Qt.Key_Backspace) {
                if (root.getSelectedCount() > 0) {
                    root.removeSelectedItems();
                    event.accepted = true;
                }
            } else if (event.key === Qt.Key_Escape) {
                root.clearSelection();
                event.accepted = true;
            }
        }

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

                property bool isSelected: root.isIndexSelected(index)
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

                    // ── 右上角序号标签 ──
                    Text {
                        anchors.top: parent.top
                        anchors.right: parent.right
                        anchors.topMargin: 4
                        anchors.rightMargin: 8
                        text: "#" + (delegateRoot.index + 1)
                        font.pixelSize: 11
                        font.family: "Microsoft YaHei UI"
                        font.weight: Font.Normal
                        color: delegateRoot.isSelected ? "#0078D4" : "#aaaaaa"
                        opacity: delegateRoot.isBeingDragged ? 0.5 : 1.0
                        Behavior on color {
                            ColorAnimation { duration: 160 }
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

                        onClicked: function(mouse) {
                            if (mouse.modifiers & Qt.ControlModifier) {
                                root.toggleSelect(delegateRoot.index);
                            } else if (mouse.modifiers & Qt.ShiftModifier) {
                                root.rangeSelect(delegateRoot.index);
                            } else {
                                root.selectOnly(delegateRoot.index);
                            }
                            mainContainer.forceActiveFocus();
                        }

                        onPressed: function(mouse) {
                            pressStartY = mouse.y;
                            dragActive = false;
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
                                    root.selectOnly(toIdx);
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

        // ── 右键菜单（空白区域） ──
        Menu {
            id: emptySpaceMenu
            MenuItem { text: "智能升序"; onTriggered: root.smartSort(true) }
            MenuItem { text: "智能降序"; onTriggered: root.smartSort(false) }
        }

        // ── 右键菜单（单选项目） ──
        Menu {
            id: itemContextMenu
            property int targetIndex: -1
            MenuItem { text: "智能升序"; onTriggered: root.smartSort(true) }
            MenuItem { text: "智能降序"; onTriggered: root.smartSort(false) }
            MenuSeparator {}
            MenuItem { text: "置顶"; onTriggered: root.moveItemToTop(itemContextMenu.targetIndex) }
            MenuItem { text: "置底"; onTriggered: root.moveItemToBottom(itemContextMenu.targetIndex) }
            MenuSeparator {}
            MenuItem {
                text: "删除"
                onTriggered: root.removeItem(itemContextMenu.targetIndex)
            }
        }

        // ── 右键菜单（多选） ──
        Menu {
            id: multiSelectMenu
            MenuItem {
                text: "删除选中项 (" + root.getSelectedCount() + ")"
                onTriggered: root.removeSelectedItems()
            }
        }

        // ── 鼠标交互区域（右键菜单 + 左键空白取消选择） ──
        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.RightButton | Qt.LeftButton

            onPressed: function(mouse) {
                if (mouse.button === Qt.LeftButton) {
                    var posInContent = mapToItem(listView.contentItem, mouse.x, mouse.y);
                    var clickedIndex = listView.indexAt(posInContent.x, posInContent.y);
                    if (clickedIndex >= 0) {
                        mouse.accepted = false;
                        return;
                    }
                }
            }

            onClicked: function(mouse) {
                mainContainer.forceActiveFocus();
                if (mouse.button === Qt.LeftButton) {
                    root.clearSelection();
                } else if (mouse.button === Qt.RightButton) {
                    var posInContent = mapToItem(listView.contentItem, mouse.x, mouse.y);
                    var clickedIndex = listView.indexAt(posInContent.x, posInContent.y);

                    if (clickedIndex >= 0) {
                        if (root.getSelectedCount() > 1 && root.isIndexSelected(clickedIndex)) {
                            multiSelectMenu.popup();
                        } else {
                            root.selectOnly(clickedIndex);
                            itemContextMenu.targetIndex = clickedIndex;
                            itemContextMenu.popup();
                        }
                    } else {
                        root.clearSelection();
                        emptySpaceMenu.popup();
                    }
                }
            }
        }

        // ── 空列表占位提示 ──
        Item {
            id: emptyPlaceholder
            anchors.fill: parent
            anchors.margins: 16
            visible: videoModel.count === 0 && !root.externalDragHover
            z: 10

            // 虚线边框
            Canvas {
                id: emptyBorderCanvas
                anchors.fill: parent
                onPaint: {
                    var ctx = getContext("2d");
                    ctx.clearRect(0, 0, width, height);
                    ctx.strokeStyle = "#c8c8c8";
                    ctx.lineWidth = 1.5;
                    ctx.setLineDash([6, 4]);
                    var r = 8;
                    ctx.beginPath();
                    ctx.moveTo(r, 0.75);
                    ctx.lineTo(width - r, 0.75);
                    ctx.arcTo(width - 0.75, 0.75, width - 0.75, r, r);
                    ctx.lineTo(width - 0.75, height - r);
                    ctx.arcTo(width - 0.75, height - 0.75, width - r, height - 0.75, r);
                    ctx.lineTo(r, height - 0.75);
                    ctx.arcTo(0.75, height - 0.75, 0.75, height - r, r);
                    ctx.lineTo(0.75, r);
                    ctx.arcTo(0.75, 0.75, r, 0.75, r);
                    ctx.closePath();
                    ctx.stroke();
                }
            }

            Column {
                anchors.centerIn: parent
                spacing: 12

                // 上传图标
                Canvas {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 40; height: 40
                    onPaint: {
                        var ctx = getContext("2d");
                        ctx.clearRect(0, 0, width, height);
                        ctx.strokeStyle = "#b0b0b0";
                        ctx.lineWidth = 1.8;
                        ctx.lineCap = "round";
                        ctx.lineJoin = "round";
                        // 上箭头
                        ctx.beginPath();
                        ctx.moveTo(20, 28); ctx.lineTo(20, 12);
                        ctx.stroke();
                        ctx.beginPath();
                        ctx.moveTo(13, 18); ctx.lineTo(20, 11); ctx.lineTo(27, 18);
                        ctx.stroke();
                        // 托盘
                        ctx.beginPath();
                        ctx.moveTo(8, 22); ctx.lineTo(8, 32);
                        ctx.lineTo(32, 32); ctx.lineTo(32, 22);
                        ctx.stroke();
                    }
                }

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "拖拽视频文件至此"
                    color: "#999999"
                    font.pixelSize: 14
                    font.family: "Microsoft YaHei UI"
                }

                // 浏览文件按钮
                Rectangle {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: browseLabel.width + 32
                    height: 32
                    radius: 4
                    color: browseArea.containsMouse ? "#f0f0f0" : "transparent"
                    border.color: "#d0d0d0"
                    border.width: 1

                    Text {
                        id: browseLabel
                        anchors.centerIn: parent
                        text: "浏览文件"
                        color: "#666666"
                        font.pixelSize: 13
                        font.family: "Microsoft YaHei UI"
                    }

                    MouseArea {
                        id: browseArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: fileDialog.open()
                    }
                }
            }
        }

        // ── 外部文件拖放区域 ──
        DropArea {
            id: externalDropArea
            anchors.fill: parent
            z: 300

            onEntered: {
                root.externalDragHover = true;
            }
            onExited: {
                root.externalDragHover = false;
            }
            onDropped: function(drop) {
                root.externalDragHover = false;
                if (drop.hasUrls) {
                    root.addVideoFiles(drop.urls);
                }
                drop.accept();
            }
        }

        // ── 拖放遮罩层（带动画） ──
        Rectangle {
            id: dropOverlay
            anchors.fill: parent
            radius: 8
            color: "#dce8f8"
            opacity: root.externalDragHover ? 0.94 : 0
            visible: opacity > 0
            z: 200

            Behavior on opacity {
                NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
            }

            // 蓝色虚线边框
            Canvas {
                id: overlayBorderCanvas
                anchors.fill: parent
                anchors.margins: 14
                onPaint: {
                    var ctx = getContext("2d");
                    ctx.clearRect(0, 0, width, height);
                    ctx.strokeStyle = "#0078D4";
                    ctx.lineWidth = 2;
                    ctx.setLineDash([8, 5]);
                    var r = 8;
                    ctx.beginPath();
                    ctx.moveTo(r, 1);
                    ctx.lineTo(width - r, 1);
                    ctx.arcTo(width - 1, 1, width - 1, r, r);
                    ctx.lineTo(width - 1, height - r);
                    ctx.arcTo(width - 1, height - 1, width - r, height - 1, r);
                    ctx.lineTo(r, height - 1);
                    ctx.arcTo(1, height - 1, 1, height - r, r);
                    ctx.lineTo(1, r);
                    ctx.arcTo(1, 1, r, 1, r);
                    ctx.closePath();
                    ctx.stroke();
                }
            }

            Column {
                anchors.centerIn: parent
                spacing: 12

                // 蓝色上传图标
                Canvas {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 44; height: 44
                    onPaint: {
                        var ctx = getContext("2d");
                        ctx.clearRect(0, 0, width, height);
                        ctx.strokeStyle = "#0078D4";
                        ctx.lineWidth = 2;
                        ctx.lineCap = "round";
                        ctx.lineJoin = "round";
                        ctx.beginPath();
                        ctx.moveTo(22, 30); ctx.lineTo(22, 12);
                        ctx.stroke();
                        ctx.beginPath();
                        ctx.moveTo(15, 19); ctx.lineTo(22, 12); ctx.lineTo(29, 19);
                        ctx.stroke();
                        ctx.beginPath();
                        ctx.moveTo(9, 24); ctx.lineTo(9, 35);
                        ctx.lineTo(35, 35); ctx.lineTo(35, 24);
                        ctx.stroke();
                    }
                }

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "松开以添加视频文件"
                    color: "#0078D4"
                    font.pixelSize: 15
                    font.weight: Font.Medium
                    font.family: "Microsoft YaHei UI"
                }
            }
        }
    }

    // ── 文件选择对话框 ──
    FileDialog {
        id: fileDialog
        title: "选择视频文件"
        fileMode: FileDialog.OpenFiles
        nameFilters: ["视频文件 (*.mp4 *.mkv *.mov *.avi *.webm *.flv *.wmv *.m4v *.mpg *.mpeg *.3gp *.3g2 *.f4v *.rm *.rmvb *.asf)", "所有文件 (*)"]
        onAccepted: {
            root.addVideoFiles(fileDialog.selectedFiles)
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
