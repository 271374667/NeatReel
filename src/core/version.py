import json
import urllib.request
import urllib.error

__version__ = "v1.29.3"


class VersionHandler:
    GITHUB_API_URL = "https://api.github.com/repos/271374667/NeatReel/releases"

    @staticmethod
    def _parse_version(v_str: str) -> tuple:
        """
        将版本号字符串（如 'v1.3.2'）解析为元组 (1, 3, 2) 以便进行比较。
        忽略非纯数字后缀。
        """
        clean_v = v_str.lstrip("vV")
        parts = []
        for part in clean_v.split("."):
            # 提取数字部分
            num_part = "".join(filter(str.isdigit, part))
            if num_part:
                parts.append(int(num_part))
            else:
                break
        return tuple(parts)

    @classmethod
    def get_current_version(cls) -> str:
        """获取当前本地版本号"""
        return __version__

    @classmethod
    def _fetch_releases(cls) -> list[dict]:
        req = urllib.request.Request(
            cls.GITHUB_API_URL,
            headers={
                "User-Agent": "NeatReel-Updater",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status != 200:
                raise RuntimeError(f"GitHub API 返回异常状态码: {response.status}")
            return json.loads(response.read().decode("utf-8"))

    @classmethod
    def check_for_updates_detailed(cls) -> tuple[list[dict[str, str]], str | None]:
        """
        检测 Github 是否存在新版本。
        返回值: (updates, error_message)
        """
        current_v = cls._parse_version(__version__)
        updates: list[dict[str, str]] = []

        try:
            data = cls._fetch_releases()
            for release in data:
                if release.get("draft", False):
                    continue

                tag_name = release.get("tag_name", "")
                release_v = cls._parse_version(tag_name)
                if release_v > current_v:
                    version_str = tag_name.lstrip("vV")
                    body = release.get("body", "无详细更新内容")
                    updates.append({version_str: body})
            return updates, None
        except Exception as e:
            print(f"检测更新时发生错误: {e}")
            return [], str(e)

    @classmethod
    def check_for_updates(cls) -> list[dict[str, str]]:
        """
        检测当前 Github 仓库是否有新版本。
        返回需要升级的版本号和更新内容的列表。
        例如: [{"1.3.2": "更新了:\n 1. xxx"}]
        """
        updates, _ = cls.check_for_updates_detailed()
        return updates


if __name__ == "__main__":
    v = VersionHandler()
    print("当前版本:", v.get_current_version())
    updates, error = v.check_for_updates_detailed()
    if error:
        print("检查更新时发生错误:", error)
    else:
        if updates:
            print("发现新版本:")
            for update in updates:
                for version, details in update.items():
                    print(f"版本 {version}:\n{details}\n")
        else:
            print("当前已是最新版本。")
