#!/usr/bin/env python3
"""
StyleLogic - UI Style Management Logic
スタイル管理ロジック（フォント、色、テーマ、レイアウト）の分離クラス

Phase 4 of Logic Separation: UI Style Management
- フォント管理とロード
- 色テーマとパレット管理  
- CSS-likeスタイル定義
- 動的スタイル適用
- Material Iconsフォント統合

Author: Logic Separation Project
Date: 2025-09-02
"""

import os
import logging
from PyQt5.QtGui import QFont, QFontDatabase
from PyQt5.QtWidgets import QApplication


class StyleLogic:
    """UI スタイル管理ロジッククラス"""
    
    def __init__(self):
        """StyleLogic 初期化"""
        self.logger = logging.getLogger(__name__)
        
        # フォント設定
        self.material_font = QFont("Arial", 48)  # デフォルトフォント
        
        # 色定義
        self.colors = {
            'primary': '#4299e1',
            'success': '#38a169', 
            'error': '#e53e3e',
            'warning': '#ff7675',
            'info': '#74b9ff',
            'white': 'white',
            'transparent': 'transparent',
            
            # センサー色
            'temperature': '#ff7777',
            'humidity': '#4299ff', 
            'discomfort': '#88cc88',
            
            # 状態色
            'status_good': '#38a169',
            'status_error': '#e53e3e',
            
            # カレンダー色
            'today': '#4299e1',
            'holiday': '#ff7675',
            'weekend': '#74b9ff',
            'event_personal': 'white'
        }
        
        # フォントファミリー優先順位
        self.font_families = [
            "Noto Sans JP",
            "Hiragino Sans",
            "ヒラギノ角ゴシック",
            "Meiryo",
            "メイリオ",
            "MS Gothic",
            "sans-serif"
        ]
        
        # Material Icons用CSS文字列キャッシュ
        self._main_stylesheet = None
        
    def setup_fonts(self):
        """日本語フォント設定とMaterial Iconsフォントロード"""
        try:
            # 日本語フォント設定
            font_db = QFontDatabase()
            available_fonts = font_db.families()
            
            # 優先順位順でフォント検索・適用
            for family in self.font_families:
                if family in available_fonts:
                    font = QFont(family)
                    font.setPointSize(14)  # Web版に近いサイズ
                    font.setWeight(QFont.Normal)
                    QApplication.instance().setFont(font)
                    self.logger.info(f"日本語フォント設定完了: {family}")
                    break
            else:
                self.logger.warning("適切な日本語フォントが見つかりません")
            
            # Material Icons フォントロード
            self._load_material_icons_font()
            
        except Exception as e:
            self.logger.error(f"フォント設定エラー: {e}")
            # フォールバック
            self.material_font = QFont("Arial", 48)
    
    def _load_material_icons_font(self):
        """Material Iconsフォントの読み込み"""
        try:
            # アイコンディレクトリパスの動的検出
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)  # raspberry-pi-dashboard
            icons_dir = os.path.join(project_root, "static", "icons")
            font_path = os.path.join(icons_dir, "MaterialIcons-Regular.ttf")
            
            if os.path.exists(font_path):
                font_id = QFontDatabase.addApplicationFont(font_path)
                if font_id != -1:
                    font_families = QFontDatabase.applicationFontFamilies(font_id)
                    if font_families:
                        self.material_font = QFont(font_families[0], 48)  # 36→48に拡大
                        self.logger.info(f"Material Iconsフォントをロード: {font_families[0]}")
                        return
                    else:
                        self.logger.warning("Material Iconsフォントファミリーが取得できません")
                        self.material_font = QFont("Arial", 48)  # 36→48に拡大
                else:
                    self.logger.warning("Material Iconsフォントの追加に失敗")
                    self.material_font = QFont("Arial", 48)  # 36→48に拡大
            else:
                self.logger.warning("Material Iconsフォントが見つかりません:", extra={"font_path": font_path})
                self.material_font = QFont("Arial", 48)  # 36→48に拡大
                
        except Exception as e:
            self.logger.error(f"Material Iconsフォント読み込みエラー: {e}")
            self.material_font = QFont("Arial", 48)
    
    def get_material_font(self):
        """Material Iconsフォント取得"""
        return self.material_font
    
    def get_color(self, color_name):
        """色定義取得"""
        return self.colors.get(color_name, 'white')
    
    def get_calendar_day_style(self, day_type, is_today=False):
        """カレンダー日付スタイル取得
        
        Args:
            day_type: 'holiday', 'weekend', 'normal'
            is_today: 今日かどうか
        """
        base_style = "font-family: 'Comfortaa', 'Quicksand', sans-serif; font-weight: bold; font-size: 24px;"
        
        if is_today:
            return f"{base_style} color: white; background: {self.colors['today']}; border-radius: 12px; padding: 3px 8px;"
        elif day_type == 'holiday':
            return f"{base_style} color: {self.colors['holiday']};"
        elif day_type == 'weekend':  
            return f"{base_style} color: {self.colors['weekend']};"
        else:
            return f"{base_style} color: rgba(255, 255, 255, 0.6);"
    
    def get_event_style(self, event_type='personal'):
        """イベント表示スタイル取得"""
        color = self.colors.get(f'event_{event_type}', self.colors['event_personal'])
        return f"font-family: 'Quicksand', 'Noto Sans JP', sans-serif; color: {color}; font-size: 12px; font-weight: bold; margin-top: 5px;"
    
    def get_holiday_style(self):
        """祝日表示スタイル取得"""
        return f"font-family: 'Quicksand', 'Noto Sans JP', sans-serif; color: {self.colors['holiday']}; font-size: 12px; font-weight: bold; margin-top: 5px;"
    
    def get_status_dot_style(self, status='good'):
        """ステータスドットスタイル取得"""
        color = self.colors['status_good'] if status == 'good' else self.colors['status_error']
        return f"color: {color}; font-size: 8px;"
    
    def get_main_stylesheet(self):
        """メインスタイルシート取得（1000行以上のCSS定義）"""
        if self._main_stylesheet is None:
            self._main_stylesheet = self._generate_main_stylesheet()
        return self._main_stylesheet
    
    def _generate_main_stylesheet(self):
        """Web版完全再現CSS - dashboard.pyの完全なスタイル定義"""
        return """
        QMainWindow {
            background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, 
                                       stop: 0 #667eea, stop: 1 #764ba2);
        }
        
        #calendar_section {
            background: transparent;
        }
        
        #calendar_header {
            background: transparent;
            border: none;
            min-height: 120px;
            padding: 0px;
        }
        
        #calendar_title {
            font-family: 'Comfortaa', 'Quicksand', sans-serif;
            font-size: 42px;
            color: white;
            font-weight: 700;
        }
        
        #status_dot {
            color: #38a169;
            font-size: 8px;
        }
        
        #status_text {
            font-family: 'Quicksand', 'Noto Sans JP', sans-serif;
            font-size: 18px;
            color: rgba(255, 255, 255, 0.9);
            font-weight: 500;
        }
        
        #current_time_display {
            background: transparent;
        }
        
        #time_main {
            font-family: 'Comfortaa', 'Quicksand', sans-serif;
            font-size: 42px;
            font-weight: 700;
            color: white;
            min-height: 60px;
            padding: 0px 0px;
        }
        
        #date_main {
            font-family: 'Quicksand', 'Noto Sans JP', sans-serif;
            font-size: 18px;
            font-weight: 600;
            color: rgba(255, 255, 255, 0.95);
            min-height: 20px;
            padding: 0px 0px;
        }
        
        #nav_button {
            background: #4299e1;
            color: white;
            border: none;
            border-radius: 20px;
            font-size: 16px;
            font-weight: bold;
        }
        
        #nav_button:hover {
            background: #3182ce;
        }
        
        #calendar_grid_container {
            background: transparent;
            border: none;
        }
        
        #weekday_sunday {
            color: #ff6b7a;
            font-weight: bold;
            font-size: 16px;
            background: rgba(255, 107, 122, 0.2);
            border-radius: 8px;
            padding: 5px;
        }
        
        #weekday_saturday {
            color: #4fb3f9;
            font-weight: bold;
            font-size: 16px;
            background: rgba(79, 179, 249, 0.2);
            border-radius: 8px;
            padding: 5px;
        }
        
        #weekday_normal {
            color: white;
            font-weight: bold;
            font-size: 16px;
            background: rgba(255, 255, 255, 0.15);
            border-radius: 8px;
            padding: 5px;
        }
        
        #calendar_day_empty {
            background: transparent;
        }
        
        #calendar_day_normal {
            background: transparent;
            border: none;
        }
        
        #calendar_day_today {
            background: transparent;
            border: none;
        }
        
        #calendar_day_holiday {
            background: transparent;
            border: none;
        }
        
        #calendar_day_sunday {
            background: transparent;
            border: none;
        }
        
        #calendar_day_saturday {
            background: transparent;
            border: none;
        }
        
        #system_status {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            padding: 10px;
        }
        
        #system_info {
            font-size: 12px;
            color: rgba(255, 255, 255, 0.7);
            text-align: center;
        }
        
        #sensor_icon_temperature {
            color: #ff7777;  /* 温度アイコンは薄めの赤色 */
            font-size: 48px;  /* 36px→48pxに拡大 */
            text-align: center;
            margin-bottom: 5px;
        }
        
        #sensor_icon_humidity {
            color: #4299ff;  /* 湿度アイコンは青色（従来通り） */
            font-size: 48px;  /* 36px→48pxに拡大 */
            text-align: center;
            margin-bottom: 5px;
        }
        
        #sensor_icon_discomfort {
            color: #88cc88;  /* 不快度指数アイコンは薄い緑色 */
            font-size: 48px;  /* 36px→48pxに拡大 */
            text-align: center;
            margin-bottom: 5px;
        }
        
        #sensor_simple_label {
            font-family: 'Comfortaa', 'Quicksand', sans-serif;
            font-size: 20px;  /* 36px→20pxに縮小 */
            font-weight: bold;
            color: white;
        }
        
        #sensor_simple_value {
            font-family: 'Comfortaa', 'Quicksand', sans-serif;
            font-size: 36px;  /* 24px→36pxに拡大（数字を大きく） */
            font-weight: bold;
            color: white;
        }
        
        #sensor_simple_level {
            font-family: 'Quicksand', 'Noto Sans JP', sans-serif;
            font-size: 20px;
            font-weight: bold;
            color: rgba(255, 255, 255, 0.95);
        }
        
        #sensor_simple_timestamp {
            font-family: 'Quicksand', 'Noto Sans JP', sans-serif;
            font-size: 11px;
            color: rgba(255, 255, 255, 0.8);
        }
        
        #sensor_simple_info {
            font-family: 'Quicksand', 'Noto Sans JP', sans-serif;
            font-size: 11px;
            color: rgba(255, 255, 255, 0.7);
        }
        
        #sensor_co2_icon {
            font-family: 'Material Icons';
            font-size: 48px;
            text-align: center;
            margin-bottom: 5px;
        }
        
        #sensor_co2_level {
            font-family: 'Quicksand', 'Noto Sans JP', sans-serif;
            font-size: 20px;
            font-weight: 600;
            margin-top: 3px;
        }
        
        #sensor_co2_value {
            font-family: 'Comfortaa', 'Quicksand', sans-serif;
            font-size: 32px;
            font-weight: bold;
            color: white;
        }
        
        #sensor_co2_unit {
            font-family: 'Quicksand', 'Noto Sans JP', sans-serif;
            font-size: 14px;
            font-weight: 500;
            color: rgba(255, 255, 255, 0.8);
            margin-left: 3px;
        }
        
        #sensor_co2_message {
            font-family: 'Quicksand', 'Noto Sans JP', sans-serif;
            font-size: 18px;
            font-weight: 600;
            padding: 10px;
            border-radius: 8px;
            margin: 10px;
        }
        
        """
    
    
    def apply_main_styles(self, widget):
        """メインウィジェットにスタイル適用"""
        widget.setStyleSheet(self.get_main_stylesheet())
    
    def get_font_families(self):
        """フォントファミリー一覧取得"""
        return self.font_families.copy()
    
    def get_colors_dict(self):
        """色定義辞書取得"""
        return self.colors.copy()