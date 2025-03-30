#!/usr/bin/env python3
"""
optimized_image_sender.py - Anthropic API用に画像を最適化してバックエンドに送信するスクリプト

このスクリプトは画像を最適化し、base64エンコードしてAPIに送信します。
APIはOpenAPI仕様に従って実装されており、エンベディングを生成して保存します。

使い方:
python optimized_image_sender.py --input <入力画像パス> --api-url <API URL> --api-key <API KEY>
"""

import os
import sys
import argparse
import json
import base64
import logging
import requests
from pathlib import Path
from typing import Dict, Any, Optional, Union, List, Tuple
from PIL import Image
import io
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Anthropic APIの制限値
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB
MAX_DIMENSION = 1568  # ピクセル単位の最大長辺
OPTIMAL_QUALITY = 90  # 出力JPEG品質

# デフォルトのAPIエンドポイント設定
API_HOST = os.environ.get("API_HOST", "http://localhost:1880")
REGISTER_IMAGE_ENDPOINT = os.environ.get("REGISTER_IMAGE_ENDPOINT", "/image-embed")
DEFAULT_API_KEY = os.environ.get("API_KEY", "")

# APIエンドポイントの完全URL
DEFAULT_API_ENDPOINT = f"{API_HOST}{REGISTER_IMAGE_ENDPOINT}"

# API設定をログに出力
logger.info(f"API設定: API_HOST={API_HOST}, ENDPOINT={REGISTER_IMAGE_ENDPOINT}, URL={DEFAULT_API_ENDPOINT}")

# MIMEタイプマッピング
MIME_TYPE_MAP = {
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'png': 'image/png',
    'webp': 'image/webp',
    'gif': 'image/gif'
}

def parse_args():
    """コマンドライン引数を解析する"""
    parser = argparse.ArgumentParser(description='画像を最適化してAPIに送信する')
    
    # 入力関連の引数
    input_group = parser.add_argument_group('入力オプション')
    input_group.add_argument('--input', '-i', required=True, help='入力画像ファイルまたはディレクトリのパス')
    input_group.add_argument('--recursive', '-r', action='store_true', help='入力ディレクトリを再帰的に処理する')
    
    # 最適化関連の引数
    optimize_group = parser.add_argument_group('最適化オプション')
    optimize_group.add_argument('--format', '-f', choices=['jpg', 'png', 'webp'], default='jpg',
                        help='出力画像のフォーマット (default: jpg)')
    optimize_group.add_argument('--quality', '-q', type=int, default=OPTIMAL_QUALITY,
                        help=f'JPEGまたはWebP品質 (0-100, default: {OPTIMAL_QUALITY})')
    optimize_group.add_argument('--max-size', '-s', type=int, default=MAX_DIMENSION,
                        help=f'最大長辺サイズ (pixels, default: {MAX_DIMENSION})')
    
    # API関連の引数
    api_group = parser.add_argument_group('API設定')
    api_group.add_argument('--api-url', '-u', help='APIエンドポイントURL')
    api_group.add_argument('--api-key', '-k', help='API認証キー')
    api_group.add_argument('--metadata', '-m', help='追加のメタデータを含むJSONファイル')
    api_group.add_argument('--include-base64', action='store_true',
                        help='メタデータにbase64データを含める')
    
    # 出力関連の引数
    output_group = parser.add_argument_group('出力オプション')
    output_group.add_argument('--save-optimized', '-o', help='最適化された画像を保存するディレクトリ')
    output_group.add_argument('--save-response', help='APIレスポンスを保存するJSONファイル')
    
    return parser.parse_args()

def get_image_files(directory, recursive=False):
    """指定されたディレクトリから画像ファイルのリストを取得する"""
    directory_path = Path(directory)
    
    if not directory_path.exists():
        logger.error(f"ディレクトリが見つかりません: {directory}")
        return []
    
    # ディレクトリでない場合は単一ファイルとして扱う
    if not directory_path.is_dir():
        if directory_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
            return [directory_path]
        else:
            logger.error(f"サポートされていないファイル形式です: {directory}")
            return []
    
    # ディレクトリ内のファイルを検索
    if recursive:
        files = []
        for path in directory_path.rglob('*'):
            if path.is_file() and path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                files.append(path)
    else:
        files = [f for f in directory_path.iterdir() 
                if f.is_file() and f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']]
    
    return sorted(files)

def resize_image(image, max_dimension):
    """画像を指定された最大長辺に合わせてリサイズする"""
    width, height = image.size
    
    # 既に最大長辺以下ならリサイズ不要
    if width <= max_dimension and height <= max_dimension:
        return image
    
    # アスペクト比を維持しながらリサイズ
    if width > height:
        new_width = max_dimension
        new_height = int(height * (max_dimension / width))
    else:
        new_height = max_dimension
        new_width = int(width * (max_dimension / height))
    
    return image.resize((new_width, new_height), Image.LANCZOS)

def optimize_image_memory(
    input_path: Union[str, Path],
    output_format: str = 'jpg',
    quality: int = OPTIMAL_QUALITY,
    max_dimension: int = MAX_DIMENSION
) -> Tuple[Optional[bytes], Optional[Image.Image]]:
    """
    画像を最適化してメモリ上に保持する
    
    Args:
        input_path: 入力画像ファイルのパス
        output_format: 出力フォーマット（jpg, png, webp）
        quality: 画質設定（JPEGとWebPのみ）
        max_dimension: 最大長辺ピクセル数
    
    Returns:
        Tuple[Optional[bytes], Optional[Image.Image]]: 最適化された画像のバイトデータとPILイメージオブジェクト
    """
    try:
        # 画像を開く
        with Image.open(input_path) as img:
            # RGBAモードの画像をRGBに変換（必要な場合）
            if img.mode == 'RGBA' and output_format.lower() == 'jpg':
                # 透明部分を白背景で変換
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])  # 3はアルファチャンネル
                img = background
            
            # 画像をリサイズ
            resized_img = resize_image(img, max_dimension)
            
            # メモリ上にバッファを作成
            buffer = io.BytesIO()
            
            # 保存
            if output_format.lower() == 'jpg':
                resized_img = resized_img.convert('RGB')
                resized_img.save(buffer, format='JPEG', quality=quality, optimize=True)
            elif output_format.lower() == 'png':
                resized_img.save(buffer, format='PNG', optimize=True)
            elif output_format.lower() == 'webp':
                resized_img.save(buffer, format='WEBP', quality=quality)
            
            # バッファの内容を取得
            buffer.seek(0)
            image_data = buffer.getvalue()
            
            # ファイルサイズをチェック
            file_size = len(image_data)
            if file_size > MAX_FILE_SIZE_BYTES:
                logger.warning(f"警告: 画像サイズが {file_size/1024/1024:.2f}MB で制限の5MBを超えています")
            
            logger.info(f"処理完了: {Path(input_path).name}")
            logger.info(f"  サイズ: {file_size/1024:.1f}KB, 寸法: {resized_img.width}x{resized_img.height}px")
            
            # 最適化された画像のバイナリデータとPILオブジェクトを返す
            return image_data, resized_img
            
    except Exception as e:
        logger.error(f"エラー: {input_path} の処理中にエラーが発生しました: {e}")
        return None, None

def image_to_base64(image_data: bytes) -> str:
    """画像バイナリデータをbase64エンコードする"""
    return base64.b64encode(image_data).decode('utf-8')

def save_optimized_image(
    image_data: bytes,
    output_dir: Union[str, Path],
    original_path: Union[str, Path],
    output_format: str = 'jpg'
) -> Optional[Path]:
    """
    最適化された画像を指定ディレクトリに保存する
    
    Args:
        image_data: 画像バイナリデータ
        output_dir: 出力ディレクトリ
        original_path: 元の画像パス（相対パス計算用）
        output_format: 出力フォーマット
    
    Returns:
        Optional[Path]: 保存されたファイルのパス
    """
    try:
        # 出力ディレクトリを作成
        output_dir_path = Path(output_dir)
        output_dir_path.mkdir(parents=True, exist_ok=True)
        
        # 出力ファイル名を決定
        original_path = Path(original_path)
        output_file = output_dir_path / f"{original_path.stem}.{output_format.lower()}"
        
        # 画像を保存
        with open(output_file, 'wb') as f:
            f.write(image_data)
        
        logger.info(f"最適化画像を保存しました: {output_file}")
        return output_file
    
    except Exception as e:
        logger.error(f"画像保存中にエラーが発生しました: {e}")
        return None

def send_to_api(
    base64_data: str,
    content_type: str,
    api_url: str,
    api_key: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Base64エンコードした画像をAPIに送信する
    
    Args:
        base64_data: Base64エンコードされた画像データ
        content_type: 画像のMIMEタイプ
        api_url: APIエンドポイントURL
        api_key: APIキー
        metadata: 追加のメタデータ
    
    Returns:
        Optional[Dict[str, Any]]: APIレスポンス（エラー時はNone）
    """
    if metadata is None:
        metadata = {}
    
    # リクエストボディの準備
    payload = {
        "content_type": content_type,
        "image_base64": base64_data,
        "metadata": metadata
    }
    
    # ヘッダーの準備（認証含む）
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }
    
    try:
        # APIリクエスト送信
        logger.info(f"APIリクエスト送信: {api_url}")
        response = requests.post(api_url, json=payload, headers=headers)
        
        # レスポンスをチェック
        if response.status_code == 200:
            logger.info("API呼び出し成功!")
            return response.json()
            
        elif response.status_code == 401:
            logger.error("認証エラー: APIキーが必要です")
            return None
            
        elif response.status_code == 403:
            logger.error("認証エラー: 不正なAPIキー")
            return None
            
        else:
            logger.error(f"APIエラー: ステータスコード {response.status_code}")
            logger.error(f"レスポンス: {response.text[:1000]}")
            return None
            
    except Exception as e:
        logger.error(f"APIリクエスト送信中にエラーが発生しました: {e}")
        return None

def save_api_response(response: Dict[str, Any], output_file: Union[str, Path]) -> bool:
    """
    APIレスポンスをJSONファイルに保存する
    
    Args:
        response: APIレスポンスデータ
        output_file: 出力ファイルパス
    
    Returns:
        bool: 保存が成功したかどうか
    """
    try:
        # 出力ディレクトリがなければ作成
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # JSONとして保存
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(response, f, indent=2, ensure_ascii=False)
        
        logger.info(f"APIレスポンスを保存しました: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"APIレスポンスの保存中にエラーが発生しました: {e}")
        return False

def load_metadata(metadata_file: Optional[Union[str, Path]]) -> Dict[str, Any]:
    """
    メタデータJSONファイルを読み込む
    
    Args:
        metadata_file: メタデータファイルのパス
    
    Returns:
        Dict[str, Any]: メタデータ辞書（ファイルがない場合は空辞書）
    """
    if not metadata_file:
        return {}
    
    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"メタデータファイルの読み込み中にエラーが発生しました: {e}")
        return {}

def process_image(
    input_path: Union[str, Path],
    api_url: str,
    api_key: str,
    output_format: str = 'jpg',
    quality: int = OPTIMAL_QUALITY,
    max_dimension: int = MAX_DIMENSION,
    metadata: Optional[Dict[str, Any]] = None,
    save_optimized_dir: Optional[Union[str, Path]] = None,
    save_response_path: Optional[Union[str, Path]] = None,
    include_base64_in_metadata: bool = True
) -> bool:
    """
    画像を処理し、最適化してAPIに送信する
    
    Args:
        input_path: 入力画像ファイルのパス
        api_url: APIエンドポイントURL
        api_key: APIキー
        output_format: 出力フォーマット
        quality: 画質設定
        max_dimension: 最大長辺ピクセル数
        metadata: 追加のメタデータ
        save_optimized_dir: 最適化画像を保存するディレクトリ
        save_response_path: APIレスポンスを保存するパス
        include_base64_in_metadata: メタデータにbase64データを含めるかどうか
    
    Returns:
        bool: 処理が成功したかどうか
    """
    # メタデータがなければ空の辞書を使用
    if metadata is None:
        metadata = {}
    
    # ファイル情報をメタデータに追加
    file_path = Path(input_path)
    metadata.update({
        "filename": file_path.name,
        "original_format": file_path.suffix.lstrip('.').lower()
    })
    
    # 画像を最適化
    image_data, _ = optimize_image_memory(input_path, output_format, quality, max_dimension)
    if not image_data:
        return False
    
    # 最適化画像を保存（必要な場合）
    if save_optimized_dir:
        saved_path = save_optimized_image(image_data, save_optimized_dir, input_path, output_format)
        if saved_path:
            metadata.update({"optimized_path": str(saved_path)})
    
    # Base64エンコード
    base64_data = image_to_base64(image_data)
    
    # メタデータにbase64データを追加（オプション）
    if include_base64_in_metadata:
        metadata.update({"image_base64": base64_data})
    
    # MIMEタイプを決定
    content_type = MIME_TYPE_MAP.get(output_format.lower(), 'image/jpeg')
    
    # APIに送信
    response = send_to_api(base64_data, content_type, api_url, api_key, metadata)
    if not response:
        return False
    
    # APIレスポンスを保存（必要な場合）
    if save_response_path:
        # ディレクトリが指定された場合はファイル名を生成
        response_path = Path(save_response_path)
        if response_path.is_dir() or not response_path.suffix:
            response_path = response_path / f"{file_path.stem}_response.json"
        
        save_api_response(response, response_path)
    
    return True

def main():
    """メイン関数"""
    args = parse_args()
    
    # APIエンドポイントの設定
    api_url = args.api_url or DEFAULT_API_ENDPOINT
    api_key = args.api_key or DEFAULT_API_KEY
    
    if not api_key:
        logger.error("APIキーが設定されていません。--api-key オプションか環境変数で指定してください。")
        sys.exit(1)
    
    # メタデータを読み込む
    metadata = load_metadata(args.metadata)
    
    # 処理対象の画像ファイルを取得
    if Path(args.input).is_dir():
        image_files = get_image_files(args.input, args.recursive)
        if not image_files:
            logger.error(f"処理する画像ファイルがありません: {args.input}")
            sys.exit(1)
        logger.info(f"処理対象のファイル数: {len(image_files)}")
    else:
        image_files = [Path(args.input)]
    
    # 各画像を処理
    success_count = 0
    error_count = 0
    
    for image_file in image_files:
        logger.info(f"処理中: {image_file}")
        
        # 画像処理とAPI送信
        success = process_image(
            image_file,
            api_url,
            api_key,
            args.format,
            args.quality,
            args.max_size,
            metadata.copy(),  # コピーを渡して個別に更新可能にする
            args.save_optimized,
            args.save_response,
            args.include_base64
        )
        
        if success:
            success_count += 1
        else:
            error_count += 1
    
    # 処理結果のサマリーを表示
    logger.info(f"処理完了: 成功={success_count}, 失敗={error_count}, 合計={len(image_files)}")
    
    # エラーがあった場合は非ゼロの終了コードを返す
    if error_count > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
