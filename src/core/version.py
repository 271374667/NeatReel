import json
import urllib.request
import urllib.error

__version__ = "1.0.0"

class VersionHandler:
    GITHUB_API_URL = "https://api.github.com/repos/271374667/NeatReel/releases"
    
    @staticmethod
    def _parse_version(v_str: str) -> tuple:
        """
        将版本号字符串（如 'v1.3.2'）解析为元组 (1, 3, 2) 以便进行比较。
        忽略非纯数字后缀。
        """
        clean_v = v_str.lstrip('vV')
        parts = []
        for part in clean_v.split('.'):
            # 提取数字部分
            num_part = ''.join(filter(str.isdigit, part))
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
    def check_for_updates(cls) -> list[dict[str, str]]:
        """
        检测当前 Github 仓库是否有新版本。
        返回需要升级的版本号和更新内容的列表。
        例如: [{"1.3.2": "更新了:\n 1. xxx"}]
        """
        current_v = cls._parse_version(__version__)
        updates = []
        
        try:
            # 发起请求，添加 User-Agent 防止被 Github API 拒绝
            req = urllib.request.Request(
                cls.GITHUB_API_URL, 
                headers={
                    'User-Agent': 'NeatReel-Updater',
                    'Accept': 'application/vnd.github.v3+json'
                }
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    
                    for release in data:
                        # 忽略草稿版本
                        if release.get("draft", False):
                            continue
                            
                        tag_name = release.get("tag_name", "")
                        release_v = cls._parse_version(tag_name)
                        
                        # 判断是否比当前版本新
                        if release_v > current_v:
                            version_str = tag_name.lstrip('vV')
                            body = release.get("body", "无详细更新内容")
                            updates.append({version_str: body})
                            
                    # GitHub API 返回的数据通常是按时间倒序排列的（最新的在前）
                    return updates
        except Exception as e:
            # 在控制台打印错误，实际应用中可以替换为标准的 logging
            print(f"检测更新时发生错误: {e}")
            
        return updates
