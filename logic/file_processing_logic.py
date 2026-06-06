"""
FileProcessingLogic - ファイル処理Logic分離

PersonalEventsCacheの成功パターンを参考にした動的パス認識機能付き
ファイル処理Logic。実行環境に応じて安全にパスを解決します。

分離対象:
- metrics.json読み込み処理  
- Material Iconsフォント処理
- アイコンマッピング処理
- 各種ファイル存在確認処理

パス依存関係を安全に管理し、既存機能の完全動作を維持します。
"""

import os
import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from PyQt5.QtGui import QFontDatabase

from logging_system import get_logger


class FileProcessingLogic:
    """
    ファイル処理Logic - 動的パス認識機能付き
    
    PersonalEventsCacheパターンを参考にした安全な
    パス解決とファイル処理を提供します。
    """
    
    def __init__(self, base_path: Optional[str] = None):
        """
        FileProcessingLogic初期化
        
        Args:
            base_path: ベースパス（Noneの場合は動的検知）
        """
        self.logger = get_logger("file_processing_logic")
        self.base_path = self._detect_base_path(base_path)
        self.logger.info(f"🗂️ FileProcessingLogic初期化完了", base_path=self.base_path)
        
        # キャッシュ用辞書
        self._path_cache = {}
        self._file_exists_cache = {}
        
    def _detect_base_path(self, provided_path: Optional[str] = None) -> str:
        """
        実行環境に応じた動的パス検知
        
        PersonalEventsCacheのパターンを参考にした
        安全な基底パス検知処理
        
        Args:
            provided_path: 提供されたパス
            
        Returns:
            str: 検知された基底パス
        """
        if provided_path and os.path.exists(provided_path):
            return provided_path
            
        # 現在のファイルの位置を基準にする
        current_file = os.path.abspath(__file__)
        current_dir = os.path.dirname(current_file)
        
        # raspberry-pi-dashboardディレクトリを探す
        search_paths = [
            # logic/からの相対パス（通常の場合）
            os.path.dirname(current_dir),
            # ファイルからの相対パス
            os.path.join(os.path.dirname(os.path.dirname(current_dir)), "raspberry-pi-dashboard"),
        ]
        
        for path in search_paths:
            if os.path.exists(path) and os.path.isdir(path):
                # dashboard.pyの存在確認
                if os.path.exists(os.path.join(path, "dashboard.py")):
                    self.logger.info(f"🔍 動的パス検知成功", detected_path=path)
                    return path
                    
        # フォールバック: 現在のディレクトリの親
        fallback_path = os.path.dirname(current_dir)
        self.logger.warning(f"⚠️ パス自動検知失敗、フォールバックを使用", fallback_path=fallback_path)
        return fallback_path
        
    def get_metrics_file_path(self) -> str:
        """
        metrics.jsonファイルの安全なパス取得
        
        Returns:
            str: metrics.jsonファイルの完全パス
        """
        cache_key = "metrics_json_path"
        
        if cache_key in self._path_cache:
            return self._path_cache[cache_key]
            
        # 複数の候補パスを試行
        candidate_paths = [
            # __file__からの相対パス
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "data", "metrics.json"),
            # 動的パス（基底パスベース）
            os.path.join(self.base_path, "static", "data", "metrics.json"),
            # 相対パス（現在の実装パターン）
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static", "data", "metrics.json"),
        ]
        
        for path in candidate_paths:
            normalized_path = os.path.normpath(path)
            if os.path.exists(normalized_path):
                self._path_cache[cache_key] = normalized_path
                self.logger.info(f"📊 metrics.jsonパス解決成功", path=normalized_path)
                return normalized_path
                
        # フォールバック: 最初の候補パスを返す
        fallback_path = candidate_paths[0]
        self._path_cache[cache_key] = fallback_path
        self.logger.warning(f"⚠️ metrics.jsonパス解決失敗、フォールバック使用", path=fallback_path)
        return fallback_path
        
    def get_icons_directory_path(self) -> str:
        """
        iconsディレクトリの安全なパス取得
        
        Returns:
            str: iconsディレクトリの完全パス
        """
        cache_key = "icons_directory_path"
        
        if cache_key in self._path_cache:
            return self._path_cache[cache_key]
            
        # 基底パスからの相対パス
        icons_path = os.path.join(self.base_path, "icons")
        
        if os.path.exists(icons_path) and os.path.isdir(icons_path):
            self._path_cache[cache_key] = icons_path
            self.logger.info(f"🎨 iconsディレクトリパス解決成功", path=icons_path)
            return icons_path
            
        # フォールバック: 現在ファイルからの相対パス
        fallback_path = os.path.join(os.path.dirname(self.base_path), "icons")
        self._path_cache[cache_key] = fallback_path
        self.logger.warning(f"⚠️ iconsディレクトリパス解決失敗、フォールバック使用", path=fallback_path)
        return fallback_path
        
    def get_material_icons_font_path(self) -> str:
        """
        Material Iconsフォントファイルの安全なパス取得
        
        Returns:
            str: フォントファイルの完全パス
        """
        icons_dir = self.get_icons_directory_path()
        font_path = os.path.join(icons_dir, "MaterialIcons-Regular.ttf")
        return font_path
        
    def get_icon_mappings_path(self) -> str:
        """
        アイコンマッピングファイルの安全なパス取得
        
        Returns:
            str: マッピングファイルの完全パス
        """
        icons_dir = self.get_icons_directory_path()
        mapping_path = os.path.join(icons_dir, "icon_mappings.py")
        return mapping_path
        
    def check_file_exists(self, file_path: str) -> bool:
        """
        ファイル存在確認（キャッシュ付き）
        
        Args:
            file_path: 確認するファイルパス
            
        Returns:
            bool: ファイルが存在する場合True
        """
        # キャッシュ確認
        if file_path in self._file_exists_cache:
            return self._file_exists_cache[file_path]
            
        exists = os.path.exists(file_path)
        self._file_exists_cache[file_path] = exists
        
        if exists:
            self.logger.debug(f"✅ ファイル存在確認", path=file_path)
        else:
            self.logger.debug(f"❌ ファイル未存在", path=file_path)
            
        return exists
        
    def load_metrics_json(self) -> Optional[Dict[str, Any]]:
        """
        metrics.json安全読み込み
        
        Returns:
            Optional[Dict]: JSONデータ、読み込み失敗時はNone
        """
        metrics_file = self.get_metrics_file_path()
        
        try:
            if not self.check_file_exists(metrics_file):
                self.logger.warning(f"📊 metrics.jsonファイルが見つかりません", path=metrics_file)
                return None
                
            with open(metrics_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.logger.info(f"📊 metrics.json読み込み成功", 
                               path=metrics_file,
                               data_keys=list(data.keys()) if data else [])
                return data
                
        except json.JSONDecodeError as e:
            self.logger.error(f"📊 metrics.json JSON解析エラー", 
                            path=metrics_file, error=str(e))
            return None
        except Exception as e:
            self.logger.error(f"📊 metrics.json読み込みエラー", 
                            path=metrics_file, error=str(e))
            return None
            
    def load_material_icons_font(self) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Material Iconsフォント安全読み込み
        
        Returns:
            Tuple[bool, Optional[int], Optional[str]]: 
                (成功フラグ, フォントID, フォントファミリー名)
        """
        font_path = self.get_material_icons_font_path()
        
        try:
            if not self.check_file_exists(font_path):
                self.logger.warning(f"🎨 Material Iconsフォントが見つかりません", path=font_path)
                return False, None, None
                
            # フォント追加
            font_id = QFontDatabase.addApplicationFont(font_path)
            
            if font_id != -1:
                font_families = QFontDatabase.applicationFontFamilies(font_id)
                if font_families:
                    font_family = font_families[0]
                    self.logger.success(f"🎨 Material Iconsフォント読み込み成功", 
                                      path=font_path, family=font_family)
                    return True, font_id, font_family
                else:
                    self.logger.warning(f"🎨 Material Iconsフォントファミリー取得失敗", path=font_path)
                    return False, None, None
            else:
                self.logger.warning(f"🎨 Material Iconsフォント追加失敗", path=font_path)
                return False, None, None
                
        except Exception as e:
            self.logger.error(f"🎨 Material Iconsフォント読み込みエラー", 
                            path=font_path, error=str(e))
            return False, None, None
            
    def load_icon_mappings(self) -> Optional[Dict[str, str]]:
        """
        アイコンマッピング安全読み込み
        
        Returns:
            Optional[Dict]: マッピング辞書、読み込み失敗時はNone
        """
        mapping_file = self.get_icon_mappings_path()
        
        try:
            if not self.check_file_exists(mapping_file):
                self.logger.warning(f"🗺️ アイコンマッピングファイルが見つかりません", path=mapping_file)
                return None
                
            # iconsディレクトリをsys.pathに一時追加
            icons_dir = self.get_icons_directory_path()
            path_added = False
            
            if icons_dir not in sys.path:
                sys.path.insert(0, icons_dir)
                path_added = True
                
            try:
                # dynamic import
                from icon_mappings import MATERIAL_ICONS
                
                self.logger.success(f"🗺️ アイコンマッピング読み込み成功", 
                                  path=mapping_file, 
                                  mappings_count=len(MATERIAL_ICONS))
                return MATERIAL_ICONS
                
            except ImportError as e:
                self.logger.error(f"🗺️ アイコンマッピングimportエラー", 
                                path=mapping_file, error=str(e))
                return None
                
            finally:
                # sys.pathクリーンアップ
                if path_added and icons_dir in sys.path:
                    sys.path.remove(icons_dir)
                    
        except Exception as e:
            self.logger.error(f"🗺️ アイコンマッピング読み込みエラー", 
                            path=mapping_file, error=str(e))
            return None
            
    def validate_required_files(self) -> Dict[str, bool]:
        """
        必須ファイル一括確認
        
        Returns:
            Dict[str, bool]: ファイル名: 存在フラグの辞書
        """
        required_files = {
            "metrics.json": self.get_metrics_file_path(),
            "MaterialIcons-Regular.ttf": self.get_material_icons_font_path(),
            "icon_mappings.py": self.get_icon_mappings_path(),
        }
        
        validation_result = {}
        
        for name, path in required_files.items():
            exists = self.check_file_exists(path)
            validation_result[name] = exists
            
            if exists:
                self.logger.info(f"✅ 必須ファイル確認OK", file=name, path=path)
            else:
                self.logger.warning(f"❌ 必須ファイル確認NG", file=name, path=path)
                
        return validation_result
        
    def get_file_size(self, file_path: str) -> Optional[int]:
        """
        ファイルサイズ取得
        
        Args:
            file_path: ファイルパス
            
        Returns:
            Optional[int]: ファイルサイズ（バイト）、取得失敗時はNone
        """
        try:
            if self.check_file_exists(file_path):
                size = os.path.getsize(file_path)
                self.logger.debug(f"📏 ファイルサイズ取得", path=file_path, size=size)
                return size
            else:
                self.logger.warning(f"📏 ファイルサイズ取得失敗（ファイル未存在）", path=file_path)
                return None
                
        except Exception as e:
            self.logger.error(f"📏 ファイルサイズ取得エラー", path=file_path, error=str(e))
            return None
            
    def clear_cache(self):
        """パスキャッシュとファイル存在キャッシュクリア"""
        self._path_cache.clear()
        self._file_exists_cache.clear()
        self.logger.info("🧹 FileProcessingLogicキャッシュクリア完了")
        
    def get_cache_status(self) -> Dict[str, int]:
        """
        キャッシュ状態取得
        
        Returns:
            Dict[str, int]: キャッシュ統計
        """
        return {
            "path_cache_count": len(self._path_cache),
            "file_exists_cache_count": len(self._file_exists_cache),
        }