"""
Rust HTML to Markdown 转换器
使用 html-to-markdown Rust 工具进行高性能转换
"""

import subprocess
import tempfile
import os
from typing import Optional


class RustHtml2Markdown:
    """Rust HTML to Markdown 转换器"""
    
    def __init__(self, command: str = 'html-to-markdown'):
        """
        初始化转换器

        Args:
            command: html-to-markdown 命令路径，默认使用系统 PATH 中的命令
        """
        self.command = command
        # 验证命令是否可用
        try:
            subprocess.run(
                [self.command, '--version'],
                capture_output=True,
                check=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError(f"html-to-markdown 工具不可用，请检查是否正确安装: {self.command}")
    
    def convert(
        self,
        html_content: str,
        url: Optional[str] = None,
        preprocess: bool = True,
        preset: str = 'standard',
        heading_style: str = 'atx',
        code_block_style: str = 'backticks',
        strip_tags: Optional[str] = 'script,style,nav,footer,aside,iframe'
    ) -> Optional[str]:
        """
        将 HTML 转换为 Markdown

        Args:
            html_content: HTML 内容
            url: 可选，从 URL 获取 HTML（优先使用）
            preprocess: 是否启用预处理（清理导航、广告等）
            preset: 预处理级别 (minimal, standard, aggressive)
            heading_style: 标题样式 (atx, underlined, atx-closed)
            code_block_style: 代码块样式 (indented, backticks, tildes)
            strip_tags: 要移除的 HTML 标签列表，逗号分隔

        Returns:
            Markdown 内容，失败返回 None
        """
        try:
            # 如果提供了 URL，直接从 URL 获取
            if url:
                args = [
                    self.command,
                    '--url', url,
                    '--heading-style', heading_style,
                    '--code-block-style', code_block_style
                ]
                if preprocess:
                    args.extend(['--preprocess', '--preset', preset])
                if strip_tags:
                    args.extend(['--strip-tags', strip_tags])
                
                result = subprocess.run(
                    args,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
            else:
                # 从标准输入转换
                args = [
                    self.command,
                    '--heading-style', heading_style,
                    '--code-block-style', code_block_style
                ]
                if preprocess:
                    args.extend(['--preprocess', '--preset', preset])
                if strip_tags:
                    args.extend(['--strip-tags', strip_tags])
                
                result = subprocess.run(
                    args,
                    input=html_content,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
            
            if result.returncode != 0:
                print(f"html-to-markdown 转换失败: {result.stderr}")
                return None
            
            return result.stdout
        
        except subprocess.TimeoutExpired:
            print("html-to-markdown 转换超时")
            return None
        except Exception as e:
            print(f"html-to-markdown 转换异常: {e}")
            return None
    
    def convert_from_file(
        self,
        html_file: str,
        output_file: Optional[str] = None,
        **kwargs
    ) -> Optional[str]:
        """
        从文件转换 HTML 到 Markdown

        Args:
            html_file: HTML 文件路径
            output_file: 可选，输出文件路径
            **kwargs: 其他参数传递给 convert 方法

        Returns:
            Markdown 内容，失败返回 None
        """
        try:
            args = [
                self.command,
                html_file,
                '--heading-style', kwargs.get('heading_style', 'atx'),
                '--code-block-style', kwargs.get('code_block_style', 'backticks')
            ]
            
            if kwargs.get('preprocess', True):
                args.extend(['--preprocess', '--preset', kwargs.get('preset', 'standard')])
            
            if kwargs.get('strip_tags'):
                args.extend(['--strip-tags', kwargs['strip_tags']])
            
            if output_file:
                args.extend(['-o', output_file])
            
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                print(f"文件转换失败: {result.stderr}")
                return None
            
            # 如果指定了输出文件，从文件读取结果
            if output_file:
                try:
                    with open(output_file, 'r', encoding='utf-8') as f:
                        return f.read()
                except Exception as e:
                    print(f"读取输出文件失败: {e}")
                    return None
            
            return result.stdout
        
        except subprocess.TimeoutExpired:
            print("文件转换超时")
            return None
        except Exception as e:
            print(f"文件转换异常: {e}")
            return None
    
    def convert_with_metadata(
        self,
        html_content: str,
        **kwargs
    ) -> Optional[dict]:
        """
        转换 HTML 并提取元数据

        Args:
            html_content: HTML 内容
            **kwargs: 其他参数

        Returns:
            包含 markdown 和 metadata 的字典，失败返回 None
        """
        try:
            args = [
                self.command,
                '--with-metadata',
                '--heading-style', kwargs.get('heading_style', 'atx'),
                '--code-block-style', kwargs.get('code_block_style', 'backticks')
            ]
            
            if kwargs.get('preprocess', True):
                args.extend(['--preprocess', '--preset', kwargs.get('preset', 'standard')])
            
            result = subprocess.run(
                args,
                input=html_content,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                print(f"转换失败: {result.stderr}")
                return None
            
            import json
            return json.loads(result.stdout)
        
        except json.JSONDecodeError as e:
            print(f"解析 JSON 失败: {e}")
            return None
        except Exception as e:
            print(f"转换异常: {e}")
            return None