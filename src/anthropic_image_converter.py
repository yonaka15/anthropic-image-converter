#!/usr/bin/env python3
"""
anthropic_image_converter.py - Anthropic API用に画像を最適化するスクリプト

Anthropic APIの要件:
- 最大ファイルサイズ: 5MB
- 最適な解像度: 長辺が1568ピクセルを超えないこと
- サポートされる形式: JPEG, PNG, GIF, WebP

このスクリプトは指定されたディレクトリ内の画像を処理し、
Anthropic APIに最適化された画像を新しいディレクトリに保存します。
"""

import os
import sys
import argparse
from pathlib import Path
from PIL import Image
import logging

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

# サポートされるファイル拡張子
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

def parse_args():
    """コマンドライン引数を解析する"""
    parser = argparse.ArgumentParser(description='Anthropic API用に画像を最適化する')
    parser.add_argument('--input', '-i', required=True, help='入力画像ディレクトリのパス')
    parser.add_argument('--output', '-o', required=True, help='出力画像ディレクトリのパス')
    parser.add_argument('--format', '-f', choices=['jpg', 'png', 'webp'], default='jpg',
                        help='出力画像のフォーマット (default: jpg)')
    parser.add_argument('--quality', '-q', type=int, default=OPTIMAL_QUALITY,
                        help=f'JPEGまたはWebP品質 (0-100, default: {OPTIMAL_QUALITY})')
    parser.add_argument('--max-size', '-s', type=int, default=MAX_DIMENSION,
                        help=f'最大長辺サイズ (pixels, default: {MAX_DIMENSION})')
    parser.add_argument('--recursive', '-r', action='store_true',
                        help='入力ディレクトリを再帰的に処理する')
    return parser.parse_args()

def get_image_files(directory, recursive=False):
    """指定されたディレクトリから画像ファイルのリストを取得する"""
    directory_path = Path(directory)
    
    if not directory_path.exists() or not directory_path.is_dir():
        logger.error(f"ディレクトリが見つかりません: {directory}")
        return []
    
    if recursive:
        files = []
        for path in directory_path.rglob('*'):
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                files.append(path)
    else:
        files = [f for f in directory_path.iterdir() 
                if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS]
    
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

def optimize_image(input_path, output_path, output_format, quality, max_dimension):
    """画像を最適化して保存する"""
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
            
            # 出力ディレクトリがなければ作成
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 保存
            if output_format.lower() == 'jpg':
                resized_img = resized_img.convert('RGB')
                resized_img.save(output_path, format='JPEG', quality=quality, optimize=True)
            elif output_format.lower() == 'png':
                resized_img.save(output_path, format='PNG', optimize=True)
            elif output_format.lower() == 'webp':
                resized_img.save(output_path, format='WEBP', quality=quality)
            
            # ファイルサイズをチェック
            file_size = os.path.getsize(output_path)
            if file_size > MAX_FILE_SIZE_BYTES:
                logger.warning(f"警告: {output_path} のサイズが {file_size/1024/1024:.2f}MB で制限の5MBを超えています")
            
            # 元のサイズと最適化後のサイズを比較
            original_size = os.path.getsize(input_path)
            compression_ratio = (1 - file_size / original_size) * 100
            
            logger.info(f"処理完了: {input_path.name} -> {output_path}")
            logger.info(f"  元サイズ: {original_size/1024:.1f}KB, 新サイズ: {file_size/1024:.1f}KB " +
                       f"(圧縮率: {compression_ratio:.1f}%)")
            return True
            
    except Exception as e:
        logger.error(f"エラー: {input_path} の処理中にエラーが発生しました: {e}")
        return False

def process_directory(input_dir, output_dir, output_format, quality, max_dimension, recursive):
    """ディレクトリ内の画像を処理する"""
    input_files = get_image_files(input_dir, recursive)
    
    if not input_files:
        logger.warning(f"処理する画像ファイルがありません: {input_dir}")
        return 0
    
    logger.info(f"処理対象のファイル数: {len(input_files)}")
    
    success_count = 0
    for input_file in input_files:
        # 出力パスを計算
        rel_path = input_file.relative_to(input_dir) if input_file.is_relative_to(input_dir) else Path(input_file.name)
        output_file = Path(output_dir) / rel_path.with_suffix(f'.{output_format.lower()}')
        
        if optimize_image(input_file, output_file, output_format, quality, max_dimension):
            success_count += 1
    
    return success_count

def main():
    """メイン関数"""
    args = parse_args()
    
    logger.info(f"Anthropic Image Converter - 開始")
    logger.info(f"入力ディレクトリ: {args.input}")
    logger.info(f"出力ディレクトリ: {args.output}")
    logger.info(f"出力フォーマット: {args.format}")
    logger.info(f"画質設定: {args.quality}")
    logger.info(f"最大長辺: {args.max_size}px")
    logger.info(f"再帰処理: {'有効' if args.recursive else '無効'}")
    
    # ディレクトリの作成
    os.makedirs(args.output, exist_ok=True)
    
    # 処理の実行
    success_count = process_directory(
        args.input, args.output, args.format, args.quality, args.max_size, args.recursive
    )
    
    logger.info(f"処理完了: {success_count}ファイルが正常に変換されました")

if __name__ == "__main__":
    main()
