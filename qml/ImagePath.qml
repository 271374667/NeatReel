pragma Singleton
import QtQuick

QtObject {
    readonly property string imageDirectory: Qt.resolvedUrl("./Images")

    readonly property string config: imageDirectory + "/Config.svg"
    readonly property string crop: imageDirectory + "/Crop.svg"
    readonly property string info: imageDirectory + "/Info.svg"
    readonly property string setting: imageDirectory + "/Setting.svg"
    readonly property string image: imageDirectory + "/Image.svg"
    readonly property string counterClockwise: imageDirectory + "/Counterclockwise.svg"
    readonly property string clockwise: imageDirectory + "/Clockwise.svg"
    readonly property string play: imageDirectory + "/Play.svg"
    readonly property string stop: imageDirectory + "/Stop.svg"
    readonly property string fail: imageDirectory + "/Fail.svg"
    readonly property string waiting: imageDirectory + "/Waiting.svg"
    readonly property string videoList: imageDirectory + "/VideoList.svg"
    readonly property string movie: imageDirectory + "/Movie.svg"
    readonly property string add: imageDirectory + "/Add.svg"
}
