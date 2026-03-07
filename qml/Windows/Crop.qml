pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.FluentWinUI3
import QtQuick.Layouts
import "../"
import "../Components"
import "../Widgets"

Item {
    id: root

    property url frameSource: ""
    property int displayState: DisplayScreen.State.Normal // 只要进入肯定是正常显示状态，所以一直保持固定
    property string errorText: ""
    property int rotationAngle: 0
    property int originalSourceWidth: 0
    property int originalSourceHeight: 0
    property int logicalSourceWidth: 0
    property int logicalSourceHeight: 0
    property real minimumCropSize: 48
    property real cropLeftRatio: 0.18
    property real cropTopRatio: 0.16
    property real cropRightRatio: 0.82
    property real cropBottomRatio: 0.84

    readonly property bool hasLoadedImage: (displayState === DisplayScreen.State.Normal && metricImage.status === Image.Ready && cropStage.imageRect.width > 0 && cropStage.imageRect.height > 0)
    readonly property int normalizedRotationAngle: ((rotationAngle % 360) + 360) % 360
    readonly property int fallbackPreviewWidth: Math.round(Math.max(metricImage.sourceSize.width, metricImage.implicitWidth))
    readonly property int fallbackPreviewHeight: Math.round(Math.max(metricImage.sourceSize.height, metricImage.implicitHeight))
    readonly property int sourceImageWidth: hasLoadedImage ? (logicalSourceWidth > 0 ? logicalSourceWidth : fallbackPreviewWidth) : 0
    readonly property int sourceImageHeight: hasLoadedImage ? (logicalSourceHeight > 0 ? logicalSourceHeight : fallbackPreviewHeight) : 0
    readonly property real cropLeftPx: cropStage.imageRect.x + cropLeftRatio * cropStage.imageRect.width
    readonly property real cropTopPx: cropStage.imageRect.y + cropTopRatio * cropStage.imageRect.height
    readonly property real cropRightPx: cropStage.imageRect.x + cropRightRatio * cropStage.imageRect.width
    readonly property real cropBottomPx: cropStage.imageRect.y + cropBottomRatio * cropStage.imageRect.height
    readonly property int cropLeftValue: hasLoadedImage ? Math.round(cropLeftRatio * sourceImageWidth) : 0
    readonly property int cropTopValue: hasLoadedImage ? Math.round(cropTopRatio * sourceImageHeight) : 0
    readonly property int cropRightValue: hasLoadedImage ? Math.round(cropRightRatio * sourceImageWidth) : 0
    readonly property int cropBottomValue: hasLoadedImage ? Math.round(cropBottomRatio * sourceImageHeight) : 0
    readonly property int cropWidthValue: hasLoadedImage ? Math.max(0, cropRightValue - cropLeftValue) : 0
    readonly property int cropHeightValue: hasLoadedImage ? Math.max(0, cropBottomValue - cropTopValue) : 0
    readonly property var rawOriginalCropRect: root.previewRectToOriginalRect(
        cropLeftValue,
        cropTopValue,
        cropWidthValue,
        cropHeightValue
    )
    readonly property var originalCropRect: root.normalizeOriginalRect(
        rawOriginalCropRect.x,
        rawOriginalCropRect.y,
        rawOriginalCropRect.width,
        rawOriginalCropRect.height
    )
    readonly property var cropInfo: ({
            sourceWidth: root.originalSourceWidth > 0 ? root.originalSourceWidth : sourceImageWidth,
            sourceHeight: root.originalSourceHeight > 0 ? root.originalSourceHeight : sourceImageHeight,
            cropWidth: originalCropRect.width,
            cropHeight: originalCropRect.height,
            left: originalCropRect.x,
            top: originalCropRect.y,
            right: originalCropRect.x + originalCropRect.width,
            bottom: originalCropRect.y + originalCropRect.height,
            x: originalCropRect.x,
            y: originalCropRect.y,
            width: originalCropRect.width,
            height: originalCropRect.height,
            leftRatio: (root.originalSourceWidth > 0 && root.originalSourceHeight > 0) ? originalCropRect.x / root.originalSourceWidth : cropLeftRatio,
            topRatio: (root.originalSourceWidth > 0 && root.originalSourceHeight > 0) ? originalCropRect.y / root.originalSourceHeight : cropTopRatio,
            rightRatio: (root.originalSourceWidth > 0 && root.originalSourceHeight > 0) ? (originalCropRect.x + originalCropRect.width) / root.originalSourceWidth : cropRightRatio,
            bottomRatio: (root.originalSourceWidth > 0 && root.originalSourceHeight > 0) ? (originalCropRect.y + originalCropRect.height) / root.originalSourceHeight : cropBottomRatio
        })

    property bool resetCropPending: true
    property var pendingSourceCropRect: null
    property string activeDragMode: ""
    property real dragStartX: 0
    property real dragStartY: 0
    property var dragStartRect: ({
            left: 0,
            top: 0,
            right: 0,
            bottom: 0
        })

    signal confirmRequested(var cropInfo)
    signal cancelRequested()

    function clamp(value, minValue, maxValue) {
        return Math.max(minValue, Math.min(maxValue, value));
    }

    function formatResolution(widthValue, heightValue) {
        return widthValue > 0 && heightValue > 0 ? widthValue + " × " + heightValue : "--";
    }

    function formatPoint(xValue, yValue) {
        return hasLoadedImage ? "(" + xValue + ", " + yValue + ")" : "--";
    }

    function minimumCropWidth() {
        return Math.min(minimumCropSize, cropStage.imageRect.width);
    }

    function minimumCropHeight() {
        return Math.min(minimumCropSize, cropStage.imageRect.height);
    }

    function originalBoundsWidth() {
        return originalSourceWidth > 0 ? originalSourceWidth : sourceImageWidth;
    }

    function originalBoundsHeight() {
        return originalSourceHeight > 0 ? originalSourceHeight : sourceImageHeight;
    }

    function resetCrop() {
        cropLeftRatio = 0.18;
        cropTopRatio = 0.16;
        cropRightRatio = 0.82;
        cropBottomRatio = 0.84;
    }

    function applySourceCropRect(x, y, width, height) {
        if (!hasLoadedImage)
            return false;

        const boundsWidth = originalBoundsWidth();
        const boundsHeight = originalBoundsHeight();
        const safeX = clamp(Number(x), 0, Math.max(0, boundsWidth - 1));
        const safeY = clamp(Number(y), 0, Math.max(0, boundsHeight - 1));
        const safeWidth = clamp(Number(width), 1, Math.max(1, boundsWidth - safeX));
        const safeHeight = clamp(Number(height), 1, Math.max(1, boundsHeight - safeY));
        const previewRect = originalRectToPreviewRect(safeX, safeY, safeWidth, safeHeight);
        const safeRight = Math.min(sourceImageWidth, previewRect.x + previewRect.width);
        const safeBottom = Math.min(sourceImageHeight, previewRect.y + previewRect.height);

        cropLeftRatio = clamp(previewRect.x / sourceImageWidth, 0, 1);
        cropTopRatio = clamp(previewRect.y / sourceImageHeight, 0, 1);
        cropRightRatio = clamp(safeRight / sourceImageWidth, 0, 1);
        cropBottomRatio = clamp(safeBottom / sourceImageHeight, 0, 1);
        return true;
    }

    function setCropRect(x, y, width, height) {
        pendingSourceCropRect = {
            x: Math.round(Number(x)),
            y: Math.round(Number(y)),
            width: Math.round(Number(width)),
            height: Math.round(Number(height))
        };
        resetCropPending = false;

        if (hasLoadedImage) {
            applySourceCropRect(
                pendingSourceCropRect.x,
                pendingSourceCropRect.y,
                pendingSourceCropRect.width,
                pendingSourceCropRect.height
            );
            pendingSourceCropRect = null;
        }
    }

    function setCropPixels(left, top, right, bottom) {
        if (!hasLoadedImage)
            return;
        cropLeftRatio = clamp((left - cropStage.imageRect.x) / cropStage.imageRect.width, 0, 1);
        cropTopRatio = clamp((top - cropStage.imageRect.y) / cropStage.imageRect.height, 0, 1);
        cropRightRatio = clamp((right - cropStage.imageRect.x) / cropStage.imageRect.width, 0, 1);
        cropBottomRatio = clamp((bottom - cropStage.imageRect.y) / cropStage.imageRect.height, 0, 1);
    }

    function beginDrag(mode, xPos, yPos) {
        if (!hasLoadedImage)
            return;
        activeDragMode = mode;
        dragStartX = xPos;
        dragStartY = yPos;
        dragStartRect = {
            left: cropLeftPx,
            top: cropTopPx,
            right: cropRightPx,
            bottom: cropBottomPx
        };
    }

    function updateDrag(xPos, yPos) {
        if (!hasLoadedImage || activeDragMode.length === 0)
            return;
        const dx = xPos - dragStartX;
        const dy = yPos - dragStartY;
        const minWidth = minimumCropWidth();
        const minHeight = minimumCropHeight();
        const imageLeft = cropStage.imageRect.x;
        const imageTop = cropStage.imageRect.y;
        const imageRight = cropStage.imageRect.x + cropStage.imageRect.width;
        const imageBottom = cropStage.imageRect.y + cropStage.imageRect.height;

        if (activeDragMode === "move") {
            const widthValue = dragStartRect.right - dragStartRect.left;
            const heightValue = dragStartRect.bottom - dragStartRect.top;
            const nextLeft = clamp(dragStartRect.left + dx, imageLeft, imageRight - widthValue);
            const nextTop = clamp(dragStartRect.top + dy, imageTop, imageBottom - heightValue);
            setCropPixels(nextLeft, nextTop, nextLeft + widthValue, nextTop + heightValue);
            return;
        }

        let nextLeft = dragStartRect.left;
        let nextTop = dragStartRect.top;
        let nextRight = dragStartRect.right;
        let nextBottom = dragStartRect.bottom;

        if (activeDragMode.indexOf("w") !== -1)
            nextLeft = clamp(dragStartRect.left + dx, imageLeft, dragStartRect.right - minWidth);
        if (activeDragMode.indexOf("e") !== -1)
            nextRight = clamp(dragStartRect.right + dx, dragStartRect.left + minWidth, imageRight);
        if (activeDragMode.indexOf("n") !== -1)
            nextTop = clamp(dragStartRect.top + dy, imageTop, dragStartRect.bottom - minHeight);
        if (activeDragMode.indexOf("s") !== -1)
            nextBottom = clamp(dragStartRect.bottom + dy, dragStartRect.top + minHeight, imageBottom);

        setCropPixels(nextLeft, nextTop, nextRight, nextBottom);
    }

    function endDrag() {
        activeDragMode = "";
    }

    function originalRectToPreviewRect(x, y, width, height) {
        const ow = originalBoundsWidth();
        const oh = originalBoundsHeight();
        if (ow <= 0 || oh <= 0) {
            return { x: 0, y: 0, width: 0, height: 0 };
        }
        const safeX = clamp(Number(x), 0, Math.max(0, ow - 1));
        const safeY = clamp(Number(y), 0, Math.max(0, oh - 1));
        const safeWidth = clamp(Number(width), 1, Math.max(1, ow - safeX));
        const safeHeight = clamp(Number(height), 1, Math.max(1, oh - safeY));

        if (normalizedRotationAngle === 90) {
            return {
                x: oh - (safeY + safeHeight),
                y: safeX,
                width: safeHeight,
                height: safeWidth
            };
        }
        if (normalizedRotationAngle === 180) {
            return {
                x: ow - (safeX + safeWidth),
                y: oh - (safeY + safeHeight),
                width: safeWidth,
                height: safeHeight
            };
        }
        if (normalizedRotationAngle === 270) {
            return {
                x: safeY,
                y: ow - (safeX + safeWidth),
                width: safeHeight,
                height: safeWidth
            };
        }

        return {
            x: safeX,
            y: safeY,
            width: safeWidth,
            height: safeHeight
        };
    }

    function previewRectToOriginalRect(x, y, width, height) {
        const pw = sourceImageWidth;
        const ph = sourceImageHeight;
        if (pw <= 0 || ph <= 0) {
            return { x: 0, y: 0, width: 0, height: 0 };
        }
        const safeX = clamp(Number(x), 0, Math.max(0, pw - 1));
        const safeY = clamp(Number(y), 0, Math.max(0, ph - 1));
        const safeWidth = clamp(Number(width), 1, Math.max(1, pw - safeX));
        const safeHeight = clamp(Number(height), 1, Math.max(1, ph - safeY));
        const ow = originalBoundsWidth();
        const oh = originalBoundsHeight();

        if (normalizedRotationAngle === 90) {
            return {
                x: safeY,
                y: oh - (safeX + safeWidth),
                width: safeHeight,
                height: safeWidth
            };
        }
        if (normalizedRotationAngle === 180) {
            return {
                x: ow - (safeX + safeWidth),
                y: oh - (safeY + safeHeight),
                width: safeWidth,
                height: safeHeight
            };
        }
        if (normalizedRotationAngle === 270) {
            return {
                x: ow - (safeY + safeHeight),
                y: safeX,
                width: safeHeight,
                height: safeWidth
            };
        }

        return {
            x: safeX,
            y: safeY,
            width: safeWidth,
            height: safeHeight
        };
    }

    function normalizeOriginalRect(x, y, width, height) {
        const boundsWidth = originalBoundsWidth();
        const boundsHeight = originalBoundsHeight();
        if (boundsWidth < 2 || boundsHeight < 2) {
            return { x: 0, y: 0, width: 0, height: 0 };
        }

        let left = clamp(Math.round(Number(x)), 0, Math.max(0, boundsWidth - 2));
        let top = clamp(Math.round(Number(y)), 0, Math.max(0, boundsHeight - 2));
        left -= left % 2;
        top -= top % 2;

        let maxWidth = boundsWidth - left;
        let maxHeight = boundsHeight - top;
        maxWidth -= maxWidth % 2;
        maxHeight -= maxHeight % 2;

        let cropWidth = clamp(Math.round(Number(width)), 2, Math.max(2, boundsWidth - left));
        let cropHeight = clamp(Math.round(Number(height)), 2, Math.max(2, boundsHeight - top));
        cropWidth -= cropWidth % 2;
        cropHeight -= cropHeight % 2;

        cropWidth = Math.max(2, Math.min(cropWidth, maxWidth));
        cropHeight = Math.max(2, Math.min(cropHeight, maxHeight));

        return {
            x: left,
            y: top,
            width: cropWidth,
            height: cropHeight
        };
    }

    onFrameSourceChanged: resetCropPending = true
    onDisplayStateChanged: {
        if (displayState !== DisplayScreen.State.Normal)
            resetCropPending = true;
    }

    component HandCursor: HoverHandler {
        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
        cursorShape: parent.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
    }

    component InfoCard: Rectangle {
        id: infoCard
        property string title: ""
        property string value: "--"
        property string note: ""
        property color valueColor: "#111111"
        property bool mono: false

        radius: 10
        color: "#f8f9fb"
        border.width: 1
        border.color: "#e6eaef"
        implicitHeight: 92
        Layout.fillWidth: true

        Rectangle {
            anchors.fill: parent
            anchors.margins: -1
            radius: parent.radius + 1
            color: "transparent"
            border.color: Qt.rgba(0, 0, 0, 0.05)
            border.width: 1
            z: -1
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 4

            Text {
                text: infoCard.title
                font.pixelSize: 12
                font.family: "Microsoft YaHei UI"
                color: "#5c6670"
                renderType: Text.NativeRendering
            }

            Text {
                text: infoCard.value
                font.pixelSize: 18
                font.family: infoCard.mono ? "Consolas" : "Segoe UI Variable Display"
                font.weight: Font.DemiBold
                color: infoCard.valueColor
                elide: Text.ElideRight
                renderType: Text.NativeRendering
            }

            Text {
                visible: infoCard.note.length > 0
                text: infoCard.note
                font.pixelSize: 11
                font.family: "Microsoft YaHei UI"
                color: "#8a939d"
                elide: Text.ElideRight
                renderType: Text.NativeRendering
            }
        }
    }

    component CropHandle: Rectangle {
        id: handleRoot
        required property string dragMode
        required property real centerX
        required property real centerY
        required property int handleCursor

        width: 12
        height: 12
        radius: 6
        x: centerX - width / 2
        y: centerY - height / 2
        color: "white"
        border.color: "#0078D4"
        border.width: 2
        visible: root.hasLoadedImage
        z: 8

        MouseArea {
            id: handleMouseArea
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: handleRoot.handleCursor

            onPressed: function (mouse) {
                const point = cropStage.mapFromItem(handleMouseArea, mouse.x, mouse.y);
                root.beginDrag(handleRoot.dragMode, point.x, point.y);
            }

            onPositionChanged: function (mouse) {
                const point = cropStage.mapFromItem(handleMouseArea, mouse.x, mouse.y);
                root.updateDrag(point.x, point.y);
            }

            onReleased: root.endDrag()
            onCanceled: root.endDrag()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 12

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredHeight: Math.max(300, root.height * 0.58)

            DisplayScreen {
                id: displayScreen
                anchors.fill: parent
                displayState: root.displayState
                frameSource: root.frameSource
                errorText: root.errorText
            }

            Item {
                id: cropStage
                anchors.fill: displayScreen
                anchors.margins: 8
                clip: true
                visible: root.displayState === DisplayScreen.State.Normal && root.frameSource.toString().length > 0

                readonly property rect imageRect: Qt.rect((width - metricImage.paintedWidth) / 2, (height - metricImage.paintedHeight) / 2, metricImage.paintedWidth, metricImage.paintedHeight)

                Image {
                    id: metricImage
                    anchors.fill: parent
                    fillMode: Image.PreserveAspectFit
                    source: root.displayState === DisplayScreen.State.Normal ? root.frameSource : ""
                    asynchronous: true
                    smooth: true
                    opacity: 0

                    onStatusChanged: {
                        if (status === Image.Ready) {
                            if (root.pendingSourceCropRect !== null) {
                                root.applySourceCropRect(
                                    root.pendingSourceCropRect.x,
                                    root.pendingSourceCropRect.y,
                                    root.pendingSourceCropRect.width,
                                    root.pendingSourceCropRect.height
                                );
                                root.pendingSourceCropRect = null;
                                root.resetCropPending = false;
                            } else if (root.resetCropPending) {
                                root.resetCrop();
                                root.resetCropPending = false;
                            }
                        }
                    }
                }

                Rectangle {
                    x: cropStage.imageRect.x
                    y: cropStage.imageRect.y
                    width: cropStage.imageRect.width
                    height: cropStage.imageRect.height
                    color: "transparent"
                    border.width: 1
                    border.color: Qt.rgba(1, 1, 1, 0.24)
                }

                Rectangle {
                    x: cropStage.imageRect.x
                    y: cropStage.imageRect.y
                    width: cropStage.imageRect.width
                    height: Math.max(0, root.cropTopPx - cropStage.imageRect.y)
                    color: Qt.rgba(0, 0, 0, 0.48)
                }

                Rectangle {
                    x: cropStage.imageRect.x
                    y: root.cropTopPx
                    width: Math.max(0, root.cropLeftPx - cropStage.imageRect.x)
                    height: Math.max(0, root.cropBottomPx - root.cropTopPx)
                    color: Qt.rgba(0, 0, 0, 0.48)
                }

                Rectangle {
                    x: root.cropRightPx
                    y: root.cropTopPx
                    width: Math.max(0, cropStage.imageRect.x + cropStage.imageRect.width - root.cropRightPx)
                    height: Math.max(0, root.cropBottomPx - root.cropTopPx)
                    color: Qt.rgba(0, 0, 0, 0.48)
                }

                Rectangle {
                    x: cropStage.imageRect.x
                    y: root.cropBottomPx
                    width: cropStage.imageRect.width
                    height: Math.max(0, cropStage.imageRect.y + cropStage.imageRect.height - root.cropBottomPx)
                    color: Qt.rgba(0, 0, 0, 0.48)
                }

                Rectangle {
                    id: cropFrame
                    x: root.cropLeftPx
                    y: root.cropTopPx
                    width: Math.max(0, root.cropRightPx - root.cropLeftPx)
                    height: Math.max(0, root.cropBottomPx - root.cropTopPx)
                    color: "transparent"
                    border.width: 2
                    border.color: "#ffffff"
                    z: 5

                    Repeater {
                        model: 2

                        Rectangle {
                            required property int index
                            width: 1
                            height: cropFrame.height
                            x: Math.round(cropFrame.width * (index + 1) / 3)
                            color: Qt.rgba(1, 1, 1, 0.34)
                        }
                    }

                    Repeater {
                        model: 2

                        Rectangle {
                            required property int index
                            width: cropFrame.width
                            height: 1
                            y: Math.round(cropFrame.height * (index + 1) / 3)
                            color: Qt.rgba(1, 1, 1, 0.34)
                        }
                    }

                    Rectangle {
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.margins: 10
                        radius: 6
                        color: Qt.rgba(0, 0, 0, 0.56)
                        border.width: 1
                        border.color: Qt.rgba(1, 1, 1, 0.12)
                        implicitWidth: cropSizeText.implicitWidth + 18
                        implicitHeight: cropSizeText.implicitHeight + 10

                        Text {
                            id: cropSizeText
                            anchors.centerIn: parent
                            text: root.formatResolution(root.cropWidthValue, root.cropHeightValue)
                            font.pixelSize: 12
                            font.family: "Consolas"
                            font.weight: Font.DemiBold
                            color: "white"
                            renderType: Text.NativeRendering
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.SizeAllCursor

                        onPressed: function (mouse) {
                            root.beginDrag("move", mouse.x + cropFrame.x, mouse.y + cropFrame.y);
                        }

                        onPositionChanged: function (mouse) {
                            root.updateDrag(mouse.x + cropFrame.x, mouse.y + cropFrame.y);
                        }

                        onReleased: root.endDrag()
                        onCanceled: root.endDrag()
                    }
                }

                CropHandle {
                    dragMode: "nw"
                    centerX: cropFrame.x
                    centerY: cropFrame.y
                    handleCursor: Qt.SizeFDiagCursor
                }

                CropHandle {
                    dragMode: "n"
                    centerX: cropFrame.x + cropFrame.width / 2
                    centerY: cropFrame.y
                    handleCursor: Qt.SizeVerCursor
                }

                CropHandle {
                    dragMode: "ne"
                    centerX: cropFrame.x + cropFrame.width
                    centerY: cropFrame.y
                    handleCursor: Qt.SizeBDiagCursor
                }

                CropHandle {
                    dragMode: "e"
                    centerX: cropFrame.x + cropFrame.width
                    centerY: cropFrame.y + cropFrame.height / 2
                    handleCursor: Qt.SizeHorCursor
                }

                CropHandle {
                    dragMode: "se"
                    centerX: cropFrame.x + cropFrame.width
                    centerY: cropFrame.y + cropFrame.height
                    handleCursor: Qt.SizeFDiagCursor
                }

                CropHandle {
                    dragMode: "s"
                    centerX: cropFrame.x + cropFrame.width / 2
                    centerY: cropFrame.y + cropFrame.height
                    handleCursor: Qt.SizeVerCursor
                }

                CropHandle {
                    dragMode: "sw"
                    centerX: cropFrame.x
                    centerY: cropFrame.y + cropFrame.height
                    handleCursor: Qt.SizeBDiagCursor
                }

                CropHandle {
                    dragMode: "w"
                    centerX: cropFrame.x
                    centerY: cropFrame.y + cropFrame.height / 2
                    handleCursor: Qt.SizeHorCursor
                }
            }
        }

        FluentPane {
            Layout.fillWidth: true
            Layout.preferredHeight: cropInfoContent.implicitHeight + 88
            title: "裁剪信息"
            icon: ImagePath.crop
            contentTopMargin: 14
            contentLeftMargin: 16
            contentRightMargin: 16
            contentBottomMargin: 14

            ColumnLayout {
                id: cropInfoContent
                width: parent.width
                spacing: 12

                Text {
                    text: "拖拽裁剪框或边缘控制点，实时查看输出尺寸与坐标。确认时会自动换算回原视频坐标。"
                    font.pixelSize: 12
                    font.family: "Microsoft YaHei UI"
                    color: "#5f6973"
                    renderType: Text.NativeRendering
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    InfoCard {
                        title: "裁剪后分辨率"
                        value: root.formatResolution(root.cropWidthValue, root.cropHeightValue)
                        note: "输出图像尺寸"
                        valueColor: "#0078D4"
                        mono: true
                    }

                    InfoCard {
                        title: "原始分辨率"
                        value: root.formatResolution(root.sourceImageWidth, root.sourceImageHeight)
                        note: "原图尺寸"
                        mono: true
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    InfoCard {
                        title: "左上角坐标"
                        value: root.formatPoint(root.cropLeftValue, root.cropTopValue)
                        note: "裁剪起点"
                        mono: true
                    }

                    InfoCard {
                        title: "右下角坐标"
                        value: root.formatPoint(root.cropRightValue, root.cropBottomValue)
                        note: "裁剪终点"
                        mono: true
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true

            Button {
                text: "返回"
                implicitWidth: 124
                implicitHeight: 40
                onClicked: root.cancelRequested()
                HandCursor {}
            }

            Item { Layout.fillWidth: true }

            Button {
                text: "确定"
                highlighted: true
                enabled: root.hasLoadedImage
                icon.source: ImagePath.crop
                implicitWidth: 124
                implicitHeight: 40
                onClicked: root.confirmRequested(root.cropInfo)
                HandCursor {}
            }
        }
    }
}
