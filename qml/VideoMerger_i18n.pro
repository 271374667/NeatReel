TEMPLATE = aux
CONFIG += lrelease
CODECFORTR = UTF-8

lupdate_only {
    SOURCES += $$files($$PWD/*.qml, true)
}

TRANSLATIONS += \
    $$PWD/i18n/VideoMerger_zh_CN.ts \
    $$PWD/i18n/VideoMerger_en_US.ts
