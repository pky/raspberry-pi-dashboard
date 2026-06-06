#!/usr/bin/env python3
"""
Backup Monitoring Integration
バックアップシステム監視統合

Phase 3 Task 3: 監視システム統合
- バックアップ状態監視
- 統合ダッシュボード連携
- アラートシステム統合
- パフォーマンス監視
"""

import json
import os
import sys
import time
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

# Project imports
try:
    from logging_system import get_logger
    from advanced_backup_manager import AdvancedBackupManager, BackupAction, AlertSeverity
except ImportError:
    import logging
    def get_logger(name):
        return logging.getLogger(name)
    
    # Fallback implementations
    class BackupAction(Enum):
        RUN = "run"
        SKIP = "skip" 
        POSTPONE = "postpone"
    
    class AlertSeverity(Enum):
        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"
        CRITICAL = "critical"
    
    class AdvancedBackupManager:
        def __init__(self):
            pass
        def evaluate_backup_conditions(self, backup_type):
            return BackupAction.RUN, []


class BackupMonitoringStatus(Enum):
    """バックアップ監視ステータス"""
    HEALTHY = "healthy"
    WARNING = "warning" 
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class BackupHealthMetrics:
    """バックアップヘルスメトリクス"""
    overall_status: BackupMonitoringStatus
    health_score: float  # 0.0-1.0
    last_successful_backup: Optional[datetime.datetime]
    consecutive_failures: int
    backup_frequency_compliance: float  # 0.0-1.0
    storage_usage_percent: float
    performance_score: float  # 0.0-1.0
    alert_count_last_24h: int
    estimated_next_backup: Optional[datetime.datetime]
    backup_conditions_status: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Dict形式で返却 (JSONシリアライゼ用)"""
        result = asdict(self)
        # datetimeオブジェクトをISO形式文字列に変換
        if self.last_successful_backup:
            result['last_successful_backup'] = self.last_successful_backup.isoformat()
        if self.estimated_next_backup:
            result['estimated_next_backup'] = self.estimated_next_backup.isoformat()
        
        result['overall_status'] = self.overall_status.value
        return result


class BackupMonitoringIntegration:
    """バックアップ監視統合クラス"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.project_root = self._detect_project_root()
        self.backup_manager = self._initialize_backup_manager()
        self.monitoring_data_file = self.project_root / "static" / "data" / "backup_monitoring.json"
        
    def _detect_project_root(self) -> Path:
        """プロジェクトルート自動検出"""
        current_path = Path(__file__).parent.parent
        
        # Mac環境の場合
        if (current_path / 'raspberry-pi-dashboard').exists():
            return current_path / 'raspberry-pi-dashboard'
        
        # Raspberry Pi環境の場合
        return current_path
    
    def _initialize_backup_manager(self) -> Optional[AdvancedBackupManager]:
        """高度バックアップマネージャー初期化"""
        try:
            config_path = self.project_root / "config" / "backup_advanced_config.json"
            if config_path.exists():
                return AdvancedBackupManager(str(config_path))
            else:
                self.logger.warning("高度バックアップ設定ファイルが見つかりません")
                return None
        except Exception as e:
            self.logger.error(f"バックアップマネージャー初期化エラー: {e}")
            return None
    
    def collect_comprehensive_backup_status(self) -> BackupHealthMetrics:
        """包括的バックアップ状態収集"""
        try:
            self.logger.info("包括的バックアップ状態収集開始")
            
            # 基本メトリクス収集
            basic_metrics = self._collect_basic_backup_metrics()
            performance_metrics = self._collect_performance_metrics()
            alert_metrics = self._collect_alert_metrics()
            
            # バックアップ条件状態
            conditions_status = self._evaluate_backup_conditions()
            
            # 総合ヘルススコア計算
            health_score = self._calculate_comprehensive_health_score(
                basic_metrics, performance_metrics, alert_metrics, conditions_status
            )
            
            # 総合ステータス決定
            overall_status = self._determine_overall_status(health_score, basic_metrics, alert_metrics)
            
            # 次回バックアップ予測
            next_backup_estimate = self._estimate_next_backup_time()
            
            metrics = BackupHealthMetrics(
                overall_status=overall_status,
                health_score=health_score,
                last_successful_backup=basic_metrics.get('last_successful_backup'),
                consecutive_failures=basic_metrics.get('consecutive_failures', 0),
                backup_frequency_compliance=basic_metrics.get('frequency_compliance', 1.0),
                storage_usage_percent=basic_metrics.get('storage_usage_percent', 0.0),
                performance_score=performance_metrics.get('performance_score', 1.0),
                alert_count_last_24h=alert_metrics.get('alert_count_24h', 0),
                estimated_next_backup=next_backup_estimate,
                backup_conditions_status=conditions_status.get('status', 'unknown')
            )
            
            self.logger.info(f"バックアップ状態収集完了: {overall_status.value} (スコア: {health_score:.3f})")
            return metrics
            
        except Exception as e:
            self.logger.error(f"バックアップ状態収集エラー: {e}")
            return BackupHealthMetrics(
                overall_status=BackupMonitoringStatus.UNKNOWN,
                health_score=0.0,
                last_successful_backup=None,
                consecutive_failures=0,
                backup_frequency_compliance=0.0,
                storage_usage_percent=0.0,
                performance_score=0.0,
                alert_count_last_24h=0,
                estimated_next_backup=None,
                backup_conditions_status="unknown"
            )
    
    def _collect_basic_backup_metrics(self) -> Dict[str, Any]:
        """基本バックアップメトリクス収集"""
        metrics = {
            'total_backups': 0,
            'successful_backups': 0,
            'failed_backups': 0,
            'consecutive_failures': 0,
            'last_successful_backup': None,
            'frequency_compliance': 1.0,
            'storage_usage_percent': 0.0
        }
        
        try:
            # バックアップメタデータファイル検索
            metadata_paths = [
                "/tmp/test_backups/backup_metadata.json",
                str(Path.home() / "backups" / "backup_metadata.json")
            ]
            
            for metadata_path in metadata_paths:
                if os.path.exists(metadata_path):
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                    
                    stats = metadata.get('statistics', {})
                    metrics.update({
                        'total_backups': stats.get('total_backups', 0),
                        'successful_backups': stats.get('successful_backups', 0),
                        'failed_backups': stats.get('failed_backups', 0)
                    })
                    
                    # 連続失敗回数計算
                    backups = metadata.get('backups', [])
                    consecutive_failures = 0
                    for backup in reversed(backups):
                        if backup.get('status') == 'completed':
                            break
                        elif backup.get('status') == 'failed':
                            consecutive_failures += 1
                    metrics['consecutive_failures'] = consecutive_failures
                    
                    # 最終成功バックアップ時刻
                    last_success_str = stats.get('last_successful_backup')
                    if last_success_str:
                        try:
                            metrics['last_successful_backup'] = datetime.datetime.fromisoformat(
                                last_success_str.replace('Z', '+00:00')
                            ).replace(tzinfo=None)
                        except Exception as e:
                            self.logger.debug(f"最終成功バックアップ時刻パースエラー: {e}")
                    
                    break
            
            # 频度コンプライアンス計算 (日次バックアップを前提)
            if metrics['last_successful_backup']:
                hours_since_last = (datetime.datetime.now() - metrics['last_successful_backup']).total_seconds() / 3600
                if hours_since_last <= 24:
                    metrics['frequency_compliance'] = 1.0
                elif hours_since_last <= 48:
                    metrics['frequency_compliance'] = 0.7
                elif hours_since_last <= 72:
                    metrics['frequency_compliance'] = 0.4
                else:
                    metrics['frequency_compliance'] = 0.1
            
            # ストレージ使用率
            for backup_dir in ["/tmp/test_backups", str(Path.home() / "backups")]:
                if os.path.exists(backup_dir):
                    import shutil
                    total, used, free = shutil.disk_usage(backup_dir)
                    metrics['storage_usage_percent'] = (used / total) * 100
                    break
        
        except Exception as e:
            self.logger.error(f"基本メトリクス収集エラー: {e}")
        
        return metrics
    
    def _collect_performance_metrics(self) -> Dict[str, Any]:
        """パフォーマンスメトリクス収集"""
        metrics = {
            'average_backup_duration': 0.0,
            'backup_speed_mbps': 0.0,
            'compression_ratio': 0.0,
            'performance_score': 1.0
        }
        
        try:
            # パフォーマンスログファイルから最近のメトリクスを収集
            performance_log_path = self.project_root / "logs" / "backup_performance.log"
            if performance_log_path.exists():
                # シンプルなログパーシング (実装例)
                with open(performance_log_path, 'r') as f:
                    lines = f.readlines()[-10:]  # 直近10行
                
                durations = []
                for line in lines:
                    if 'duration:' in line:
                        try:
                            duration = float(line.split('duration:')[1].split()[0])
                            durations.append(duration)
                        except:
                            pass
                
                if durations:
                    metrics['average_backup_duration'] = sum(durations) / len(durations)
                    
                    # パフォーマンススコア: 短い時間ほど高スコア
                    avg_duration = metrics['average_backup_duration']
                    if avg_duration < 30:  # 30秒以下
                        metrics['performance_score'] = 1.0
                    elif avg_duration < 60:  # 1分以下
                        metrics['performance_score'] = 0.8
                    elif avg_duration < 300:  # 5分以下
                        metrics['performance_score'] = 0.6
                    else:
                        metrics['performance_score'] = 0.3
        
        except Exception as e:
            self.logger.debug(f"パフォーマンスメトリクス収集エラー: {e}")
        
        return metrics
    
    def _collect_alert_metrics(self) -> Dict[str, Any]:
        """アラートメトリクス収集"""
        metrics = {
            'alert_count_24h': 0,
            'critical_alerts_24h': 0,
            'warning_alerts_24h': 0,
            'recent_alert_types': []
        }
        
        try:
            # アラートログファイルから最近24時間のアラートを収集
            alert_log_path = self.project_root / "logs" / "backup_alerts.log"
            if alert_log_path.exists():
                now = datetime.datetime.now()
                cutoff_time = now - datetime.timedelta(hours=24)
                
                with open(alert_log_path, 'r') as f:
                    lines = f.readlines()
                
                for line in lines:
                    try:
                        # シンプルなタイムスタンプパーシング (実装例)
                        if ' - ' in line:
                            timestamp_str = line.split(' - ')[0]
                            try:
                                log_time = datetime.datetime.strptime(timestamp_str.split(',')[0], '%Y-%m-%d %H:%M:%S')
                                if log_time > cutoff_time:
                                    metrics['alert_count_24h'] += 1
                                    
                                    # 重要度判定
                                    if 'CRITICAL' in line or 'ERROR' in line:
                                        metrics['critical_alerts_24h'] += 1
                                    elif 'WARNING' in line:
                                        metrics['warning_alerts_24h'] += 1
                            except ValueError:
                                pass
                    except Exception:
                        continue
        
        except Exception as e:
            self.logger.debug(f"アラートメトリクス収集エラー: {e}")
        
        return metrics
    
    def _evaluate_backup_conditions(self) -> Dict[str, Any]:
        """バックアップ条件評価"""
        conditions = {
            'status': 'unknown',
            'can_run': False,
            'blocking_conditions': [],
            'recommended_action': 'wait'
        }
        
        try:
            if self.backup_manager:
                action, condition_results = self.backup_manager.evaluate_backup_conditions("incremental")
                
                conditions['recommended_action'] = action.value
                conditions['can_run'] = (action == BackupAction.RUN)
                
                blocking_conditions = []
                for result in condition_results:
                    if result.action in [BackupAction.SKIP, BackupAction.POSTPONE]:
                        blocking_conditions.append({
                            'condition': result.condition_name,
                            'reason': result.reason,
                            'action': result.action.value
                        })
                
                conditions['blocking_conditions'] = blocking_conditions
                
                if conditions['can_run']:
                    conditions['status'] = 'ready'
                elif blocking_conditions:
                    conditions['status'] = 'blocked'
                else:
                    conditions['status'] = 'evaluating'
        
        except Exception as e:
            self.logger.debug(f"バックアップ条件評価エラー: {e}")
        
        return conditions
    
    def _calculate_comprehensive_health_score(self, basic_metrics: Dict[str, Any],
                                            performance_metrics: Dict[str, Any],
                                            alert_metrics: Dict[str, Any],
                                            conditions_status: Dict[str, Any]) -> float:
        """総合ヘルススコア計算"""
        try:
            # 各要素の重み付け
            weights = {
                'backup_success_rate': 0.3,
                'frequency_compliance': 0.25,
                'performance': 0.2,
                'alerts': 0.15,
                'conditions': 0.1
            }
            
            scores = {}
            
            # バックアップ成功率スコア
            total_backups = basic_metrics.get('total_backups', 0)
            if total_backups > 0:
                success_rate = basic_metrics.get('successful_backups', 0) / total_backups
                
                # 連続失敗によるペナルティ
                consecutive_failures = basic_metrics.get('consecutive_failures', 0)
                failure_penalty = min(0.3, consecutive_failures * 0.1)
                
                scores['backup_success_rate'] = max(0.0, success_rate - failure_penalty)
            else:
                scores['backup_success_rate'] = 0.5  # ニュートラルスコア
            
            # 頻度コンプライアンススコア
            scores['frequency_compliance'] = basic_metrics.get('frequency_compliance', 1.0)
            
            # パフォーマンススコア
            scores['performance'] = performance_metrics.get('performance_score', 1.0)
            
            # アラートスコア (アラートが少ないほど高スコア)
            alert_count = alert_metrics.get('alert_count_24h', 0)
            critical_count = alert_metrics.get('critical_alerts_24h', 0)
            
            if critical_count > 0:
                scores['alerts'] = max(0.0, 0.5 - critical_count * 0.2)
            elif alert_count > 5:
                scores['alerts'] = max(0.3, 1.0 - (alert_count - 5) * 0.1)
            else:
                scores['alerts'] = 1.0
            
            # 条件スコア (実行可能なら高スコア)
            if conditions_status.get('can_run', False):
                scores['conditions'] = 1.0
            elif conditions_status.get('status') == 'blocked':
                scores['conditions'] = 0.3
            else:
                scores['conditions'] = 0.7
            
            # 重み付き平均計算
            total_score = sum(scores[key] * weights[key] for key in weights.keys())
            
            return round(min(1.0, max(0.0, total_score)), 3)
        
        except Exception as e:
            self.logger.error(f"ヘルススコア計算エラー: {e}")
            return 0.5
    
    def _determine_overall_status(self, health_score: float, 
                                basic_metrics: Dict[str, Any],
                                alert_metrics: Dict[str, Any]) -> BackupMonitoringStatus:
        """総合ステータス決定"""
        try:
            # クリティカル条件チェック
            critical_alerts = alert_metrics.get('critical_alerts_24h', 0)
            consecutive_failures = basic_metrics.get('consecutive_failures', 0)
            
            if critical_alerts > 0 or consecutive_failures >= 3:
                return BackupMonitoringStatus.CRITICAL
            
            # スコアベースのステータス決定
            if health_score >= 0.8:
                return BackupMonitoringStatus.HEALTHY
            elif health_score >= 0.5:
                return BackupMonitoringStatus.WARNING
            else:
                return BackupMonitoringStatus.CRITICAL
        
        except Exception as e:
            self.logger.error(f"ステータス決定エラー: {e}")
            return BackupMonitoringStatus.UNKNOWN
    
    def _estimate_next_backup_time(self) -> Optional[datetime.datetime]:
        """次回バックアップ時刻予測"""
        try:
            # シンプルな予測: 日次バックアップを仮定
            # 次の日の深夜2時を予測
            tomorrow = datetime.datetime.now().replace(hour=2, minute=0, second=0, microsecond=0)
            tomorrow += datetime.timedelta(days=1)
            return tomorrow
        
        except Exception as e:
            self.logger.debug(f"次回バックアップ時刻予測エラー: {e}")
            return None
    
    def save_monitoring_data(self, metrics: BackupHealthMetrics) -> bool:
        """監視データ保存 (Webダッシュボード用)"""
        try:
            # ディレクトリ作成
            self.monitoring_data_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 監視データ構造
            monitoring_data = {
                'timestamp': datetime.datetime.now().isoformat(),
                'backup_health': metrics.to_dict(),
                'version': '1.0',
                'monitoring_type': 'comprehensive_backup_status'
            }
            
            # JSONファイル保存
            with open(self.monitoring_data_file, 'w', encoding='utf-8') as f:
                json.dump(monitoring_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"監視データ保存完了: {self.monitoring_data_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"監視データ保存エラー: {e}")
            return False
    
    def generate_status_report(self, metrics: BackupHealthMetrics) -> str:
        """ステータスレポート生成"""
        try:
            status_icon = {
                BackupMonitoringStatus.HEALTHY: "✅",
                BackupMonitoringStatus.WARNING: "⚠️",
                BackupMonitoringStatus.CRITICAL: "❌",
                BackupMonitoringStatus.UNKNOWN: "❓"
            }.get(metrics.overall_status, "❓")
            
            report = f"""
{status_icon} バックアップシステム状態レポート

総合ステータス: {metrics.overall_status.value.upper()}
ヘルススコア: {metrics.health_score:.1%}

📊 基本指標:
- 最終成功バックアップ: {metrics.last_successful_backup.strftime('%Y-%m-%d %H:%M') if metrics.last_successful_backup else '未実行'}
- 連続失敗回数: {metrics.consecutive_failures}回
- 頻度コンプライアンス: {metrics.backup_frequency_compliance:.1%}
- ストレージ使用率: {metrics.storage_usage_percent:.1f}%

🚀 パフォーマンス:
- パフォーマンススコア: {metrics.performance_score:.1%}

🚨 アラート:
- 24時間以内のアラート: {metrics.alert_count_last_24h}件

🕰️ スケジュール:
- 次回予定バックアップ: {metrics.estimated_next_backup.strftime('%Y-%m-%d %H:%M') if metrics.estimated_next_backup else '不明'}
- バックアップ条件: {metrics.backup_conditions_status}
"""
            
            return report
            
        except Exception as e:
            self.logger.error(f"ステータスレポート生成エラー: {e}")
            return f"❌ ステータスレポート生成エラー: {e}"
    
    def run_comprehensive_monitoring(self) -> Tuple[BackupHealthMetrics, str]:
        """包括的監視実行メイン関数"""
        try:
            self.logger.info("包括的バックアップ監視実行開始")
            
            # 包括的バックアップ状態収集
            metrics = self.collect_comprehensive_backup_status()
            
            # 監視データ保存
            self.save_monitoring_data(metrics)
            
            # ステータスレポート生成
            report = self.generate_status_report(metrics)
            
            self.logger.info(
                f"包括的バックアップ監視完了: "
                f"{metrics.overall_status.value} (スコア: {metrics.health_score:.3f})"
            )
            
            return metrics, report
            
        except Exception as e:
            self.logger.error(f"包括的監視実行エラー: {e}")
            
            # エラー時のフォールバックメトリクス
            error_metrics = BackupHealthMetrics(
                overall_status=BackupMonitoringStatus.UNKNOWN,
                health_score=0.0,
                last_successful_backup=None,
                consecutive_failures=0,
                backup_frequency_compliance=0.0,
                storage_usage_percent=0.0,
                performance_score=0.0,
                alert_count_last_24h=0,
                estimated_next_backup=None,
                backup_conditions_status="error"
            )
            
            return error_metrics, f"❌ 監視エラー: {e}"


def main():
    """テスト実行関数"""
    print("=== Backup Monitoring Integration Test ===")
    
    try:
        # バックアップ監視統合システム初期化
        monitoring = BackupMonitoringIntegration()
        
        # 包括的監視実行
        metrics, report = monitoring.run_comprehensive_monitoring()
        
        print("\n✅ 監視システム統合テスト完了")
        print(report)
        
        # JSONデータ出力
        print("\n📊 JSONメトリクス:")
        print(json.dumps(metrics.to_dict(), ensure_ascii=False, indent=2))
        
    except Exception as e:
        print(f"❌ テスト実行エラー: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()