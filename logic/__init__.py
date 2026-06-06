"""
Logic層 - ビジネスロジック分離パッケージ

Phase 1-5 Logic分離統一により抽出された各種Logic classes:
- CalendarLogic: カレンダー・祝日処理
- SensorLogic: センサーデータ処理（ValidationLogicを統合）
- DataTransformationLogic: データ変換・フォーマット処理
- CalculationLogic: 計算・判定処理
- ValidationLogic: バリデーション・範囲チェック処理
- StyleLogic: UIスタイル・フォント・色管理処理
- FileProcessingLogic: ファイル処理・パス管理処理（Phase5）
"""