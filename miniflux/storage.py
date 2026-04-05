"""
存储管理器
负责文件的保存和管理
"""

import os
import json
import hashlib
import zoneinfo
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Set

# 本地时区
LOCAL_TZ = zoneinfo.ZoneInfo("Asia/Shanghai")


class StorageManager:
    """存储管理器"""
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # 哈希索引文件
        self.hash_index_file = self.base_dir / '.hash_index.json'
        # 已保存的内容哈希集合（内容 SHA256）
        self.content_hashes: Set[str] = set()
        # 已保存的链接哈希集合（链接 SHA256）
        self.link_hashes: Set[str] = set()
        
        # 加载现有的哈希索引
        self._load_hash_index()
    
    def _load_hash_index(self):
        """加载哈希索引"""
        if self.hash_index_file.exists():
            try:
                with open(self.hash_index_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.content_hashes = set(data.get('content_hashes', []))
                    self.link_hashes = set(data.get('link_hashes', []))
            except Exception as e:
                print(f"加载哈希索引失败: {e}")
    
    def _save_hash_index(self):
        """保存哈希索引"""
        try:
            data = {
                'content_hashes': list(self.content_hashes),
                'link_hashes': list(self.link_hashes)
            }
            with open(self.hash_index_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存哈希索引失败: {e}")
    
    def _compute_sha256(self, content: str) -> str:
        """计算内容的 SHA256 哈希"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def _is_duplicate_by_content(self, content: str) -> bool:
        """根据内容哈希检查是否重复"""
        content_hash = self._compute_sha256(content)
        return content_hash in self.content_hashes
    
    def _is_duplicate_by_link(self, link: str) -> bool:
        """根据链接哈希检查是否重复"""
        link_hash = self._compute_sha256(link)
        return link_hash in self.link_hashes
    
    def is_duplicate(self, content: str, link: str) -> bool:
        """
        检查文章是否重复

        Args:
            content: 文章内容
            link: 文章链接

        Returns:
            是否重复
        """
        return self._is_duplicate_by_content(content) or self._is_duplicate_by_link(link)
    
    def save_article(
        self,
        title: str,
        content: str,
        date: datetime,
        link: str,
        source: str,
        author: Optional[str] = None,
        check_duplicate: bool = True,
        force_overwrite: bool = False
    ) -> Optional[Path]:
        """
        保存文章

        Args:
            title: 文章标题
            content: 文章内容
            date: 发布日期（可以是 aware 或 naive datetime）
            link: 文章链接
            source: 内容来源
            author: 作者（可选）
            check_duplicate: 是否检查重复（默认 True）
            force_overwrite: 是否强制覆盖已存在的文件（默认 False）

        Returns:
            文件路径（如果重复或已存在且不强制覆盖返回 None）
        """
        # 检查重复
        if check_duplicate and self.is_duplicate(content, link):
            print(f"文章已存在（重复）: {title}")
            return None

        # 将时间转换为本地时区（Asia/Shanghai）
        if date.tzinfo is not None:
            # aware datetime -> 转换到本地时区
            local_date = date.astimezone(LOCAL_TZ)
        else:
            # naive datetime -> 假设已经是本地时间，添加时区信息
            local_date = date.replace(tzinfo=LOCAL_TZ)

        # 创建日期目录 - 使用本地时间的日期
        date_dir = self.base_dir / str(local_date.year) / f"{local_date.month:02d}" / f"{local_date.day:02d}"
        date_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成文件名
        safe_title = self._sanitize_filename(title)
        filename = f"{safe_title}.md"
        filepath = date_dir / filename
        
        # 如果文件已存在且不强制覆盖，跳过
        if filepath.exists() and not force_overwrite:
            return None

        # 创建 Markdown 内容 - 传入本地时间
        markdown = self._create_markdown(
            title=title,
            content=content,
            date=local_date,
            link=link,
            source=source,
            author=author
        )
        
        # 写入文件
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(markdown)
            
            # 更新哈希索引
            content_hash = self._compute_sha256(content)
            link_hash = self._compute_sha256(link)
            self.content_hashes.add(content_hash)
            self.link_hashes.add(link_hash)
            self._save_hash_index()
            
            return filepath
        except Exception as e:
            print(f"保存文件失败: {e}")
            return None
    
    def _sanitize_filename(self, name: str) -> str:
        """清理文件名，移除所有可能导致问题的特殊字符"""
        import re
        
        # 中文标点符号
        chinese_punctuations = r'，。、；：？！""''（）【】「」《》·…—'
        
        # 英文标点符号和特殊字符
        special_chars = r'<>:"/\\|?*\n\r\t'
        
        # 替换所有特殊字符为下划线
        name = re.sub(r'[' + chinese_punctuations + special_chars + r']+', '_', name)
        
        # 移除连续的多个下划线
        name = re.sub(r'_+', '_', name)
        
        # 移除开头和结尾的下划线、空格、点
        name = name.strip('_ .')
        
        # 限制长度
        if len(name) > 200:
            name = name[:200]
        
        # 如果清理后为空，使用默认名称
        return name or 'untitled'
    
    def _create_markdown(
        self,
        title: str,
        content: str,
        date: datetime,
        link: str,
        source: str,
        author: Optional[str] = None
    ) -> str:
        """创建 Markdown 内容

        Args:
            date: 本地时间（带时区信息）
        """
        # ISO 8601 格式保留时区信息
        iso_time = date.isoformat()
        # 人类可读格式
        readable_time = date.strftime('%Y-%m-%d %H:%M:%S %Z')

        md = "---\n"
        md += f"title: \"{title}\"\n"
        md += f"date: \"{iso_time}\"\n"
        md += f"source: \"{source}\"\n"
        md += f"link: \"{link}\"\n"
        if author:
            md += f"author: \"{author}\"\n"
        md += "---\n\n"
        md += f"# {title}\n\n"
        md += f"**链接**: [{link}]({link})\n\n"
        md += f"**发布时间**: {readable_time}\n\n"
        md += f"**内容来源**: {source}\n\n"
        md += "---\n\n"
        md += content

        return md
    
    def get_article_path(self, date: datetime, title: str) -> Optional[Path]:
        """获取文章路径"""
        safe_title = self._sanitize_filename(title)
        filename = f"{safe_title}.md"
        filepath = self.base_dir / str(date.year) / f"{date.month:02d}" / f"{date.day:02d}" / filename
        return filepath if filepath.exists() else None