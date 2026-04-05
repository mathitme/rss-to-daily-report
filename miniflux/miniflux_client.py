"""
Miniflux 客户端
用于从 Miniflux API 获取文章内容
"""

import requests
from typing import List, Dict, Optional
from datetime import datetime


class MinifluxClient:
    """Miniflux API 客户端"""
    
    def __init__(self, base_url: str, api_key: str):
        """
        初始化 Miniflux 客户端

        Args:
            base_url: Miniflux 服务器地址，如 https://miniflux.example.com
            api_key: Miniflux API Key
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'X-Auth-Token': api_key,
            'Content-Type': 'application/json'
        })
    
    def get_entries(
        self,
        status: str = 'unread',
        limit: int = 100,
        offset: int = 0,
        direction: str = 'desc',
        order: str = 'published_at',
        fetch_all: bool = False,
        feed_id: Optional[int] = None
    ) -> List[Dict]:
        """
        获取文章列表

        Args:
            status: 文章状态 (unread, read, all)
            limit: 返回数量限制
            offset: 偏移量
            direction: 排序方向 (asc, desc)
            order: 排序字段 (published_at, created_at, title)
            fetch_all: 是否获取所有文章（忽略 limit，自动分页）
            feed_id: 订阅源 ID（可选，用于筛选特定订阅源）

        Returns:
            文章列表
        """
        if fetch_all:
            # 获取所有文章，自动分页
            all_entries = []
            current_offset = 0
            page_size = 500  # 每页获取数量
            
            while True:
                params = {
                    'status': status,
                    'limit': page_size,
                    'offset': current_offset,
                    'direction': direction,
                    'order': order
                }
                
                # 如果指定了订阅源，添加 feed_id 参数
                if feed_id is not None:
                    params['feed_id'] = feed_id
                
                try:
                    response = self.session.get(f"{self.base_url}/v1/entries", params=params)
                    response.raise_for_status()
                    data = response.json()
                    
                    # Miniflux API 可能返回字典或列表
                    entries = data.get('entries', data) if isinstance(data, dict) else data
                    
                    if not entries:
                        break
                    
                    all_entries.extend(entries)
                    
                    # 如果返回的数量少于请求的数量，说明已经获取完了
                    if len(entries) < page_size:
                        break
                    
                    current_offset += page_size
                    
                except Exception as e:
                    print(f"获取文章列表失败 (offset={current_offset}): {e}")
                    break
            
            return all_entries
        else:
            # 获取指定数量的文章
            url = f"{self.base_url}/v1/entries"
            params = {
                'status': status,
                'limit': limit,
                'offset': offset,
                'direction': direction,
                'order': order
            }
            
            # 如果指定了订阅源，添加 feed_id 参数
            if feed_id is not None:
                params['feed_id'] = feed_id
            
            try:
                response = self.session.get(url, params=params)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                print(f"获取文章列表失败: {e}")
                return []
    
    def get_entry(self, entry_id: int) -> Optional[Dict]:
        """
        获取单篇文章详情

        Args:
            entry_id: 文章 ID

        Returns:
            文章详情
        """
        url = f"{self.base_url}/v1/entries/{entry_id}"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"获取文章详情失败: {e}")
            return None
    
    def get_feeds(self) -> List[Dict]:
        """
        获取所有订阅源

        Returns:
            订阅源列表
        """
        url = f"{self.base_url}/v1/feeds"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"获取订阅源失败: {e}")
            return []
    
    def mark_entry_as_read(self, entry_id: int) -> bool:
        """
        标记文章为已读

        Args:
            entry_id: 文章 ID

        Returns:
            是否成功
        """
        url = f"{self.base_url}/v1/entries"
        data = {
            "entry_ids": [entry_id],
            "status": "read"
        }
        
        try:
            response = self.session.put(url, json=data)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"标记文章已读失败: {e}")
            return False
    
    def get_starred_entries(self, limit: int = 100, fetch_all: bool = False) -> List[Dict]:
        """
        获取加星标的文章

        Args:
            limit: 返回数量限制
            fetch_all: 是否获取所有文章（忽略 limit，自动分页）

        Returns:
            文章列表
        """
        if fetch_all:
            # 获取所有星标文章，自动分页
            all_entries = []
            current_offset = 0
            page_size = 500
            
            while True:
                params = {
                    'starred': True,
                    'limit': page_size,
                    'offset': current_offset,
                    'direction': 'desc',
                    'order': 'published_at'
                }
                
                try:
                    response = self.session.get(f"{self.base_url}/v1/entries", params=params)
                    response.raise_for_status()
                    data = response.json()
                    
                    entries = data.get('entries', data) if isinstance(data, dict) else data
                    
                    if not entries:
                        break
                    
                    all_entries.extend(entries)
                    
                    if len(entries) < page_size:
                        break
                    
                    current_offset += page_size
                    
                except Exception as e:
                    print(f"获取星标文章失败 (offset={current_offset}): {e}")
                    break
            
            return all_entries
        else:
            url = f"{self.base_url}/v1/entries"
            params = {
                'starred': True,
                'limit': limit,
                'direction': 'desc',
                'order': 'published_at'
            }
            
            try:
                response = self.session.get(url, params=params)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                print(f"获取星标文章失败: {e}")
                return []
    
    def get_entries_by_feed(
        self,
        feed_id: int,
        status: str = 'unread',
        limit: int = 100
    ) -> List[Dict]:
        """
        获取特定订阅源的文章

        Args:
            feed_id: 订阅源 ID
            status: 文章状态
            limit: 返回数量限制

        Returns:
            文章列表
        """
        url = f"{self.base_url}/v1/feeds/{feed_id}/entries"
        params = {
            'status': status,
            'limit': limit,
            'direction': 'desc',
            'order': 'published_at'
        }
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"获取订阅源文章失败: {e}")
            return []
    
    def refresh_feed(self, feed_id: int) -> bool:
        """
        刷新特定订阅源

        Args:
            feed_id: 订阅源 ID

        Returns:
            是否成功
        """
        url = f"{self.base_url}/v1/feeds/{feed_id}/refresh"
        
        try:
            response = self.session.put(url)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"刷新订阅源失败: {e}")
            return False