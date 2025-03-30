# Anthropic Image Converter

画像を Anthropic の API 要件に合わせて自動的に最適化し、API に送信するツールです。

## 重要事項

**注意**: このプロジェクトは個人用途として開発されており、画像変換機能は使用できますが、画像をベクトルデータとして保存するバックエンドの仕様は公開していません。

## 概要

Anthropic API で画像を使用する際には、特定の制約があります:

- 最大ファイルサイズ: 5MB
- 最適な解像度: 長辺が 1568 ピクセルを超えないこと
- サポートされる形式: JPEG, PNG, GIF, WebP

このツールは、これらの制約に合わせて画像を自動的に変換・最適化し、API に送信します。

## 特徴

### 画像変換機能

- 画像を指定された最大長辺に合わせてリサイズ
- アスペクト比を維持した変換
- 複数の出力フォーマット対応 (JPG, PNG, WebP)
- 透過画像のバックグラウンド処理
- 画質設定の調整
- 再帰的ディレクトリ処理
- 詳細なログ出力と圧縮率レポート

### API 送信機能

- 最適化した画像を base64 エンコード
- API キーによる認証対応
- メタデータの追加と管理
- バッチ処理サポート
- エラーハンドリング

## 要件

- Python 3.11 以上
- 依存パッケージ
  - Pillow: 画像処理
  - requests: API 通信
  - python-dotenv: 環境変数管理

## インストール

### リポジトリのクローン

```bash
git clone https://github.com/yourusername/anthropic-image-converter.git
cd anthropic-image-converter
```

### 依存関係のインストール

```bash
# 仮想環境を作成 (オプション)
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# または
.venv\Scripts\activate     # Windows

# パッケージをインストール
pip install -e .
# または
pip install -r requirements.txt
```

### 環境設定

```bash
# 環境変数の設定
cp .env.sample .env
# .envファイルを編集してAPI情報を設定
```

## 使い方

### 基本的な画像変換

```bash
python src/anthropic_image_converter.py --input ./images --output ./optimized
```

### 画像変換オプション

```
--input, -i      入力画像ディレクトリのパス（必須）
--output, -o     出力画像ディレクトリのパス（必須）
--format, -f     出力画像のフォーマット(jpg, png, webp) (デフォルト: jpg)
--quality, -q    JPEGまたはWebP品質 (0-100, デフォルト: 90)
--max-size, -s   最大長辺サイズ (ピクセル, デフォルト: 1568)
--recursive, -r  入力ディレクトリを再帰的に処理する
```

### 変換例

#### 基本変換 (デフォルト設定)

```bash
python src/anthropic_image_converter.py -i ./images -o ./optimized
```

#### 高品質 PNG 形式での出力

```bash
python src/anthropic_image_converter.py -i ./images -o ./optimized -f png
```

#### 最大サイズと品質の指定

```bash
python src/anthropic_image_converter.py -i ./images -o ./optimized -s 1200 -q 85
```

#### サブディレクトリを含む再帰的処理

```bash
python src/anthropic_image_converter.py -i ./images -o ./optimized -r
```

## 最適化画像の API 送信機能

画像を最適化し、base64 エンコードして API に送信する機能を利用できます。

### 使い方

#### 基本的な使用方法

```bash
python src/optimized_image_sender.py --input ./images/sample.jpg --api-key your_api_key
```

#### オプション

```
入力オプション:
  --input, -i         入力画像ファイルまたはディレクトリのパス（必須）
  --recursive, -r     入力ディレクトリを再帰的に処理する

最適化オプション:
  --format, -f        出力画像のフォーマット(jpg, png, webp) (デフォルト: jpg)
  --quality, -q       JPEGまたはWebP品質 (0-100, デフォルト: 90)
  --max-size, -s      最大長辺サイズ (ピクセル, デフォルト: 1568)

API設定:
  --api-url, -u       APIエンドポイントURL
  --api-key, -k       API認証キー
  --metadata, -m      追加のメタデータを含むJSONファイル

出力オプション:
  --save-optimized, -o  最適化された画像を保存するディレクトリ
  --save-response     APIレスポンスを保存するJSONファイル
```

#### 使用例

##### 単一画像の送信

```bash
python src/optimized_image_sender.py -i ./images/sample.jpg -k your_api_key
```

##### ディレクトリ内の画像を一括処理

```bash
python src/optimized_image_sender.py -i ./images -r -k your_api_key
```

##### メタデータを追加して送信

```bash
python src/optimized_image_sender.py -i ./images/sample.jpg -k your_api_key -m metadata_template.json
```

##### 最適化画像と API レスポンスを保存

```bash
python src/optimized_image_sender.py -i ./images/sample.jpg -k your_api_key -o ./optimized --save-response ./responses
```

### 環境変数の設定

`.env`ファイルに API 関連の設定を追加するのがおすすめです：

```
API_ENDPOINT=http://localhost:8000/image-embed
API_KEY=your_api_key_here
```

これにより、コマンドラインでの指定が不要になります。

## 注意点

- このプロジェクトは個人用途として開発しています。コードの参考にしていただくことは歓迎します。画像変換部分のロジックや実装方法を自身のプロジェクトに応用することも自由です。問題の報告やプルリクエストなども歓迎します。
- 画像の変換機能は使用できますが、バックエンド部分は非公開です
- バックエンドサーバーの実装や API 仕様の詳細を公開する予定はありません。
- 透過 PNG を JPG 形式に変換する場合、透明部分は白背景に置き換えられます
- 出力ディレクトリが存在しない場合は自動的に作成されます
- 5MB を超える画像については警告が表示されますが処理は続行されます
- 元のディレクトリ構造は出力先でも維持されます（再帰モード使用時）

## ライセンス

[MIT License](LICENSE)

