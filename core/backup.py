import os
import shutil
from typing import Any

def backup(src_dir: str, dst_dir: str) -> None:
    """
    Recursively copy all files from src_dir to dst_dir, preserving the directory
    structure. Uses shutil.copy2 to retain metadata and creates destination
    directories as needed.

    Args:
        src_dir: Path to the source directory to back up.
        dst_dir: Path to the destination directory where files will be copied.
    """
    if not os.path.isdir(src_dir):
        raise NotADirectoryError(f"Source directory does not exist: {src_dir}")

    # Ensure the destination root exists
    os.makedirs(dst_dir, exist_ok=True)

    for root, dirs, files in os.walk(src_dir):
        # Compute the relative path from src_dir to current root
        rel_path = os.path.relpath(root, src_dir)
        # Destination directory corresponding to the current root
        dest_dir = os.path.join(dst_dir, rel_path) if rel_path != "." else dst_dir
        os.makedirs(dest_dir, exist_ok=True)

        for file_name in files:
            src_file = os.path.join(root, file_name)
            dst_file = os.path.join(dest_dir, file_name)
            # copy2 preserves file metadata (timestamps, permissions)
            shutil.copy2(src_file, dst_file)