"""清理存量 TV 示例库占用的素材用途为 material_library_video / cover。"""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "app.db")


def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1. 查找所有被 material_library_items 关联的视频
    cur.execute(
        "SELECT video_asset_id FROM material_library_items WHERE video_asset_id IS NOT NULL"
    )
    video_ids = [row[0] for row in cur.fetchall()]

    # 2. 查找所有被 material_library_items 关联的封面
    cur.execute(
        "SELECT cover_asset_id FROM material_library_items WHERE cover_asset_id IS NOT NULL"
    )
    cover_ids = [row[0] for row in cur.fetchall()]

    updated_videos = 0
    for aid in video_ids:
        cur.execute(
            "UPDATE assets SET purpose = 'material_library_video' WHERE id = ? AND purpose != 'material_library_video'",
            (aid,),
        )
        updated_videos += cur.rowcount

    updated_covers = 0
    for aid in cover_ids:
        cur.execute(
            "UPDATE assets SET purpose = 'material_library_cover' WHERE id = ? AND purpose != 'material_library_cover'",
            (aid,),
        )
        updated_covers += cur.rowcount

    conn.commit()
    conn.close()
    print(f"Migration completed. Updated {updated_videos} videos, {updated_covers} covers.")


if __name__ == "__main__":
    migrate()
