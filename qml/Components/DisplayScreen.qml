import QtQuick
import QtQuick.Controls.FluentWinUI3
import "../"

Item {
    id: root
    width: 854
    height: 480
    implicitWidth: 854
    implicitHeight: 480

    // ══════════════════════════════════════
    //  状态枚举
    // ══════════════════════════════════════
    enum State {
        Waiting,    // 等待任务
        Loading,    // 加载中
        Normal,     // 正常显示画面
        Error       // 错误
    }

    // ══════════════════════════════════════
    //  公共属性
    // ══════════════════════════════════════
    property int displayState: DisplayScreen.State.Waiting   // 当前显示状态

    property url frameSource: ""            // 后端传来的画面 source（image:// 或 file:// 等）
    property real cornerRadius: 8           // 圆角半径
    property color backgroundColor: "#f3f3f3"  // 卡片背景
    property color borderColor: "#e8e8e8"      // 边框颜色
    property color placeholderBg: "#1a1a1a"    // Normal 状态无图时的黑屏背景
    property int iconSize: 96                  // 状态图标尺寸
    property int textSize: 18                  // 提示文字大小
    property color textColor: "#888888"        // 提示文字颜色
    property int loadingTimeoutMs: 10000        // Loading 超时毫秒（可修改）
    property string defaultErrorText: qsTr("无法打开该视频")
    property string loadingTimeoutErrorText: qsTr("视频加载超时\n请检查视频文件是否正常")
    property string errorText: defaultErrorText

    // ── 便捷函数 ──
    function setWaiting() {
        displayState = DisplayScreen.State.Waiting;
    }
    function setLoading() {
        displayState = DisplayScreen.State.Loading;
        loadingTimeoutTimer.restart();
    }
    function setNormal() {
        displayState = DisplayScreen.State.Normal;
    }
    function setError(message) {
        if (message !== undefined && message !== null && message !== "") {
            errorText = message;
        } else {
            errorText = defaultErrorText;
        }
        displayState = DisplayScreen.State.Error;
    }

    onDisplayStateChanged: {
        if (displayState === DisplayScreen.State.Loading) {
            loadingTimeoutTimer.restart();
        } else {
            loadingTimeoutTimer.stop();
        }
    }

    Timer {
        id: loadingTimeoutTimer
        interval: root.loadingTimeoutMs
        repeat: false
        onTriggered: {
            if (root.displayState === DisplayScreen.State.Loading) {
                root.setError(root.loadingTimeoutErrorText);
            }
        }
    }

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
        anchors.margins: 8          // 为阴影留出空间
        radius: root.cornerRadius
        color: root.displayState === DisplayScreen.State.Normal ? root.placeholderBg : root.backgroundColor
        border.color: root.borderColor
        border.width: 1
        clip: true

        Behavior on color {
            ColorAnimation {
                duration: 250
                easing.type: Easing.OutCubic
            }
        }

        // ── 顶部高光线（Fluent2 微妙亮边） ──
        Rectangle {
            width: parent.width - 2 * root.cornerRadius
            height: 1
            anchors.top: parent.top
            anchors.horizontalCenter: parent.horizontalCenter
            color: Qt.rgba(1, 1, 1, 0.45)
            visible: root.displayState !== DisplayScreen.State.Normal
        }

        // ─────────────────────────────────
        //  等待状态
        // ─────────────────────────────────
        Column {
            id: waitingContent
            anchors.centerIn: parent
            spacing: 20
            visible: opacity > 0
            opacity: root.displayState === DisplayScreen.State.Waiting ? 1 : 0

            Behavior on opacity {
                NumberAnimation {
                    duration: 300
                    easing.type: Easing.InOutCubic
                }
            }

            Image {
                id: waitingIcon
                source: ImagePath.waiting
                sourceSize.width: root.iconSize
                sourceSize.height: root.iconSize
                anchors.horizontalCenter: parent.horizontalCenter
                fillMode: Image.PreserveAspectFit
                opacity: 0.55
            }

            Text {
                text: qsTr("等待任务中")
                font.pixelSize: root.textSize
                font.family: appFontFamily
                font.weight: Font.Normal
                color: root.textColor
                anchors.horizontalCenter: parent.horizontalCenter
                renderType: Text.NativeRendering
            }
        }

        Loading {
            id: loadingContent
            anchors.fill: parent
            text: qsTr("视频加载中")
            running: root.displayState === DisplayScreen.State.Loading
            crop: true
        }

        // ─────────────────────────────────
        //  错误状态
        // ─────────────────────────────────
        Column {
            id: errorContent
            anchors.centerIn: parent
            spacing: 20
            visible: opacity > 0
            opacity: root.displayState === DisplayScreen.State.Error ? 1 : 0

            Behavior on opacity {
                NumberAnimation {
                    duration: 300
                    easing.type: Easing.InOutCubic
                }
            }

            Image {
                id: errorIcon
                source: ImagePath.fail
                sourceSize.width: root.iconSize
                sourceSize.height: root.iconSize
                anchors.horizontalCenter: parent.horizontalCenter
                fillMode: Image.PreserveAspectFit
                opacity: 0.55
            }

            Text {
                text: root.errorText
                font.pixelSize: root.textSize
                font.family: appFontFamily
                font.weight: Font.Normal
                color: "#d83b01"
                anchors.horizontalCenter: parent.horizontalCenter
                renderType: Text.NativeRendering
                horizontalAlignment: Text.AlignHCenter
            }
        }

        // ─────────────────────────────────
        //  正常状态 – 后端画面
        // ─────────────────────────────────
        Image {
            id: frameImage
            anchors.fill: parent
            fillMode: Image.PreserveAspectFit
            source: root.displayState === DisplayScreen.State.Normal ? root.frameSource : ""
            visible: opacity > 0
            opacity: (root.displayState === DisplayScreen.State.Normal && root.frameSource.toString().length > 0) ? 1 : 0
            cache: false       // 实时画面不缓存

            Behavior on opacity {
                NumberAnimation {
                    duration: 300
                    easing.type: Easing.InOutCubic
                }
            }
        }

        // ── Normal 但无画面时的黑屏（已由 cardBody 颜色处理） ──
    }
}

